"""Salesforce REST + SOQL client.

Token-storage is decoupled via an ``on_refresh`` callback:

* :meth:`SfClient.from_dev_file` — Phase 1 local-dev: reads
  ``apps/web/.sf-tokens.json`` and persists rotated tokens back to the same
  file.
* :meth:`SfClient.from_credential` — production: receives the decrypted
  payload from ``IntegrationCredentialService.read_for`` and a callback
  that writes the rotated payload back to ``tenant.integration_credential``
  via ``IntegrationCredentialService.upsert``.

On a 401, the client refreshes the access token once and invokes the
callback with the new :class:`SfTokens`. If the refresh itself fails,
``SfNotConnectedError`` bubbles up; the FastAPI route translates it to
HTTP 409 so the operator UI prompts a reconnect.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from typing import Self

from packages.core.config import get_settings
from packages.core.logging import get_logger

from .exceptions import SfApiError, SfNotConnectedError
from .models import SoqlResult
from .tokens import SfTokens, persist_dev_tokens, read_dev_tokens

log = get_logger("integrations.salesforce.client")

API_VERSION = "v60.0"
_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

OnRefreshCallback = Callable[[SfTokens], Awaitable[None]]


async def _noop_refresh_persist(_tokens: SfTokens) -> None:
    """Default callback when none is supplied — drops rotated tokens.

    Used only by tests / call sites that explicitly do not want any
    persistence side effect. Real call sites supply a callback that
    writes to the dev file or to ``tenant.integration_credential``.
    """


class SfClient:
    """Async Salesforce REST client. One instance per request/job.

    Owns the underlying ``httpx.AsyncClient`` only when one wasn't injected;
    callers that pass their own client are responsible for closing it.
    """

    def __init__(
        self,
        tokens: SfTokens,
        http: httpx.AsyncClient | None = None,
        on_refresh: OnRefreshCallback | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self._tokens = tokens
        self._http = http if http is not None else httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
        self._owns_http = http is None
        self._on_refresh: OnRefreshCallback = on_refresh or _noop_refresh_persist
        # ``client_id`` / ``client_secret`` overrides for ``_refresh_access_token``.
        # When set, they win over ``Settings`` env values — the
        # ``from_credential`` factory plumbs in the DB-backed
        # ``(salesforce, api_key)`` payload so production refresh works
        # even when the env was wiped after the bootstrap seed.
        self._client_id_override = client_id
        self._client_secret_override = client_secret

    @classmethod
    def from_dev_file(cls) -> Self:
        """Phase 1 local-dev helper — reads ``apps/web/.sf-tokens.json``
        and persists rotated tokens back to the same file."""

        async def _persist_file(tokens: SfTokens) -> None:
            persist_dev_tokens(tokens)

        return cls(tokens=read_dev_tokens(), on_refresh=_persist_file)

    @classmethod
    def from_credential(
        cls,
        payload: dict[str, Any],
        *,
        on_refresh: OnRefreshCallback,
        http: httpx.AsyncClient | None = None,
        api_key_payload: dict[str, Any] | None = None,
    ) -> Self:
        """Build from a decrypted credential payload (DB-backed).

        ``payload`` is the dict returned by
        ``IntegrationCredentialService.read_for(tenant_id, "salesforce",
        "oauth_token")`` — it must carry ``access_token`` and
        ``instance_url`` at minimum. ``refresh_token`` is required for the
        401-refresh path to succeed; without it, a refresh attempt raises
        ``SfNotConnectedError`` and the operator must re-run the OAuth
        flow.

        ``api_key_payload`` is the optional companion
        ``(salesforce, api_key)`` row carrying ``client_id`` and
        ``client_secret``. When provided, the SF client uses these to
        refresh the access token instead of reading from
        ``Settings.salesforce_client_*``. This makes refresh work on
        production where the bootstrap-only env vars have been wiped
        after seeding the credential rows (ENG-153).

        ``on_refresh`` is invoked after a successful token refresh and is
        responsible for persisting the rotated payload back to the
        credential store (typically a closure around
        ``IntegrationCredentialService.upsert``).
        """
        access_token = payload.get("access_token")
        instance_url = payload.get("instance_url")
        if not access_token or not instance_url:
            raise SfNotConnectedError(
                "salesforce credential payload missing required fields",
                details={"missing": [
                    k for k in ("access_token", "instance_url")
                    if not payload.get(k)
                ]},
            )
        refresh_token = payload.get("refresh_token")
        issued_at = payload.get("issued_at")
        tokens = SfTokens(
            access_token=str(access_token),
            instance_url=str(instance_url),
            refresh_token=str(refresh_token) if refresh_token else None,
            issued_at=str(issued_at) if issued_at else None,
        )
        client_id: str | None = None
        client_secret: str | None = None
        if api_key_payload:
            ci = api_key_payload.get("client_id")
            cs = api_key_payload.get("client_secret")
            client_id = str(ci) if ci else None
            client_secret = str(cs) if cs else None
        return cls(
            tokens=tokens,
            http=http,
            on_refresh=on_refresh,
            client_id=client_id,
            client_secret=client_secret,
        )

    async def soql(self, query: str) -> SoqlResult:
        """Execute a SOQL query. Refreshes the access token once on 401."""
        url = self._soql_url()
        params = {"q": query}

        response = await self._http.get(url, params=params, headers=self._auth_header())
        if response.status_code == 401:
            log.info("sf.soql.401_refreshing")
            await self._refresh_access_token()
            response = await self._http.get(url, params=params, headers=self._auth_header())
            if response.status_code == 401:
                raise SfNotConnectedError(
                    "salesforce 401 after refresh — refresh token expired or revoked",
                    details={"action": "reconnect"},
                )

        if response.status_code >= 400:
            raise SfApiError(
                f"salesforce returned {response.status_code}",
                details={"status": response.status_code, "body": response.text[:500]},
            )

        return response.json()  # type: ignore[no-any-return]

    async def describe(self, resource: str) -> dict[str, Any]:
        """sObject describe — metadata for every field the integration user
        can read (ENG-427).

        ``GET /services/data/{API}/sobjects/{resource}/describe`` returns the
        object's field list with per-field ``name`` / ``type`` / ``custom``
        flags. This is the FLS-aware "readable" view; a field the integration
        user has no Field-Level-Security read on is not returned here. Pair it
        with :meth:`describe_tooling_fields` (the full, non-FLS-filtered list)
        to detect the FLS gap.
        """
        url = (
            f"{self._tokens.instance_url.rstrip('/')}/services/data/"
            f"{API_VERSION}/sobjects/{resource}/describe"
        )
        return await self._get_json(url)

    async def describe_tooling_fields(self, resource: str) -> list[dict[str, Any]]:
        """Full field list for an object via the Tooling API (ENG-427).

        Queries ``FieldDefinition`` through the Tooling API, which is NOT
        filtered by the integration user's Field-Level Security — so it returns
        fields the regular :meth:`describe` hides. The difference between this
        list and ``describe`` is the FLS-gap the Salesforce admin must open.

        Returns a list of ``{"QualifiedApiName": ..., "DataType": ...}`` rows
        (Tooling query envelope unwrapped, pagination followed).
        """
        safe_resource = resource.replace("'", "")
        query = (
            "SELECT QualifiedApiName, DataType FROM FieldDefinition "
            f"WHERE EntityDefinition.QualifiedApiName = '{safe_resource}'"
        )
        url = (
            f"{self._tokens.instance_url.rstrip('/')}/services/data/"
            f"{API_VERSION}/tooling/query"
        )
        records: list[dict[str, Any]] = []
        body = await self._get_json(url, params={"q": query})
        records.extend(body.get("records", []))
        # Tooling query paginates via ``nextRecordsUrl`` (an absolute path).
        next_url = body.get("nextRecordsUrl")
        while next_url:
            page = await self._get_json(
                f"{self._tokens.instance_url.rstrip('/')}{next_url}"
            )
            records.extend(page.get("records", []))
            next_url = page.get("nextRecordsUrl")
        return records

    async def get_object(self, resource: str, external_id: str) -> dict[str, object]:
        """Fetch a single SF object by Id with ALL readable fields.

        Uses the standard sObject Rows endpoint
        ``GET /services/data/{API}/sobjects/{resource}/{id}`` which returns
        every field the connected user has read access to — including custom
        fields. Used by the operator UI "view full payload" modal: not
        persisted, fresh round-trip on every open.
        """
        url = (
            f"{self._tokens.instance_url.rstrip('/')}/services/data/"
            f"{API_VERSION}/sobjects/{resource}/{external_id}"
        )
        response = await self._http.get(url, headers=self._auth_header())
        if response.status_code == 401:
            log.info("sf.get_object.401_refreshing")
            await self._refresh_access_token()
            response = await self._http.get(url, headers=self._auth_header())
            if response.status_code == 401:
                raise SfNotConnectedError(
                    "salesforce 401 after refresh — refresh token expired or revoked",
                    details={"action": "reconnect"},
                )
        if response.status_code == 404:
            raise SfApiError(
                f"salesforce {resource} not found",
                details={"status": 404, "external_id": external_id},
            )
        if response.status_code >= 400:
            raise SfApiError(
                f"salesforce returned {response.status_code}",
                details={"status": response.status_code, "body": response.text[:500]},
            )
        return response.json()  # type: ignore[no-any-return]

    async def refresh_access_token(self) -> None:
        """Refresh and persist the Salesforce access token proactively.

        Normal API calls refresh reactively after a 401. Worker keepalive
        jobs use this method to exercise the refresh-token grant before an
        operator hits the UI, keeping the stored access token fresh while
        preserving the same error handling and persistence callback.
        """
        await self._refresh_access_token()

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    # --- private ---

    async def _get_json(
        self, url: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """GET ``url`` as JSON with the standard refresh-once-on-401 retry.

        Shared by :meth:`describe` and :meth:`describe_tooling_fields`
        (ENG-427). Mirrors the error handling of :meth:`soql` /
        :meth:`get_object`: one token refresh on 401, ``SfNotConnectedError``
        if still 401, ``SfApiError`` on any other 4xx/5xx.
        """
        response = await self._http.get(
            url, params=params, headers=self._auth_header()
        )
        if response.status_code == 401:
            log.info("sf.get_json.401_refreshing")
            await self._refresh_access_token()
            response = await self._http.get(
                url, params=params, headers=self._auth_header()
            )
            if response.status_code == 401:
                raise SfNotConnectedError(
                    "salesforce 401 after refresh — refresh token expired or revoked",
                    details={"action": "reconnect"},
                )
        if response.status_code >= 400:
            raise SfApiError(
                f"salesforce returned {response.status_code}",
                details={"status": response.status_code, "body": response.text[:500]},
            )
        return response.json()  # type: ignore[no-any-return]

    def _soql_url(self) -> str:
        return f"{self._tokens.instance_url.rstrip('/')}/services/data/{API_VERSION}/query"

    def _auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._tokens.access_token}"}

    async def _refresh_access_token(self) -> None:
        """POST refresh_token grant; persist the new access token. Raise on failure."""
        if not self._tokens.refresh_token:
            raise SfNotConnectedError(
                "Salesforce connection has no refresh token. "
                "Please reconnect Salesforce in Settings → Integrations.",
                details={"action": "reconnect"},
            )

        # Constructor overrides (from the DB-backed
        # ``(salesforce, api_key)`` row) win over Settings env values.
        # On prod the env vars are wiped after bootstrap seeding, so
        # the overrides are the only viable source — see ENG-153.
        client_id = self._client_id_override
        client_secret = self._client_secret_override
        if not client_id or not client_secret:
            settings = get_settings()
            client_id = client_id or settings.salesforce_client_id
            if not client_secret and settings.salesforce_client_secret is not None:
                client_secret = settings.salesforce_client_secret.get_secret_value()
        if not client_id or not client_secret:
            raise SfNotConnectedError(
                "Salesforce client_id/client_secret are not configured "
                "(missing api_key credential row and no environment fallback). "
                "Reconnect Salesforce in Settings → Integrations.",
            )

        token_url = f"{self._tokens.instance_url.rstrip('/')}/services/oauth2/token"
        # `data` carries `refresh_token` + `client_secret` — NEVER log it.
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._tokens.refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        response = await self._http.post(token_url, data=data)
        if response.status_code >= 400:
            # Salesforce error envelope shape:
            #   {"error": "invalid_grant",
            #    "error_description": "expired access/refresh token"}
            # `invalid_grant` means the refresh token is dead and only a
            # fresh OAuth connect can recover. Surface a user-actionable
            # message for the UI, sanitized details for ops in `details`,
            # and a sanitized log line (no tokens, no client_secret).
            sf_error = ""
            sf_error_description = ""
            try:
                body = response.json()
                if isinstance(body, dict):
                    sf_error = str(body.get("error", "") or "")
                    sf_error_description = str(body.get("error_description", "") or "")
            except ValueError:
                pass
            log.warning(
                "sf.token.refresh_failed",
                status=response.status_code,
                sf_error=sf_error or "<unparsed>",
                sf_error_description=sf_error_description or "<empty>",
            )
            details: dict[str, object] = {
                "status": response.status_code,
                "sf_error": sf_error,
                "sf_error_description": sf_error_description,
            }
            if sf_error == "invalid_grant":
                details["action"] = "reconnect"
                raise SfNotConnectedError(
                    "Salesforce connection expired. "
                    "Please reconnect Salesforce in Settings → Integrations.",
                    details=details,
                )
            raise SfNotConnectedError(
                "Salesforce token refresh failed "
                f"({sf_error or f'HTTP {response.status_code}'}). "
                "Reconnect Salesforce in Settings → Integrations; "
                "if the problem persists, check the Salesforce Connected App config.",
                details=details,
            )

        body = response.json()
        new_access = body.get("access_token")
        if not new_access:
            raise SfNotConnectedError("refresh response missing access_token")

        self._tokens = SfTokens(
            access_token=new_access,
            instance_url=body.get("instance_url", self._tokens.instance_url),
            refresh_token=self._tokens.refresh_token,
            issued_at=body.get("issued_at"),
        )
        await self._on_refresh(self._tokens)
        log.info("sf.token.refreshed")
