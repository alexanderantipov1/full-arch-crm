"""Gmail API client — ``users.messages.send`` + ``users.getProfile``.

Phase 1 / ENG-131 surface — implementation lives here, ENG-132 (the
outreach send service) is the first caller. The shape mirrors the
Salesforce / CareStack clients in this package:

  - One instance per request / job (cheap; httpx.AsyncClient lifecycle).
  - Tokens come from ``tenant.integration_credential`` via the
    ``IntegrationCredentialService`` — never from env. There is
    deliberately no ``from_env`` factory.
  - On 401 the client refreshes once, persists the new access_token
    + ``last_refreshed_at`` back into the credential row, retries the
    original call. A second 401 raises ``GoogleAPIError`` with a
    "reconnect this mailbox" reason so the operator UI prompts.

We deliberately keep the Gmail surface narrow:

  - ``send_message`` wraps ``users.messages.send`` (RFC 822 bytes →
    base64url → JSON body).
  - ``get_profile`` wraps ``users.getProfile`` (sanity check on first
    connect — confirms the tokens actually work).

ENG-134 (2026-05-11) adds two read-only inbox helpers used by the
bounce poller worker:

  - ``get_messages_list`` — ``users.messages.list`` with a query
    string (``q=``) so the poller can filter on
    ``from:mailer-daemon@* newer_than:1d``.
  - ``get_message`` — ``users.messages.get`` with ``format=metadata``
    and a ``metadataHeaders`` list so we read only the bounce-routing
    headers (``X-Failed-Recipients``, ``In-Reply-To``, ``References``,
    ``Subject``, ``From``) and nothing more — body is never fetched.

These methods require the ``gmail.readonly`` (or the narrower
``gmail.metadata``) scope. ENG-131 only granted ``gmail.send``;
ENG-134 documents the additional scope in the connect flow and
operators re-consent on next connect.
"""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Self
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.logging import get_logger
from packages.core.security import Principal
from packages.tenant.credential_service import IntegrationCredentialService

from .exceptions import GoogleAPIError, GoogleOAuthError
from .oauth import GoogleOAuthClient, GoogleTokens

log = get_logger("integrations.google_workspace.client")

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
SEND_PATH = "/users/me/messages/send"
PROFILE_PATH = "/users/me/profile"
MESSAGES_LIST_PATH = "/users/me/messages"
MESSAGE_GET_PATH = "/users/me/messages/{message_id}"

_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
# Refresh proactively when the token has this little time left.
_REFRESH_SKEW_SECONDS = 60


# Type alias for the persistence callback ``from_credential`` builds.
# Implemented as a closure that captures the credential row + a
# reference to ``IntegrationCredentialService`` so the new tokens land
# back in the encrypted column.
RefreshPersistFn = Callable[[GoogleTokens], Awaitable[None]]


class GoogleWorkspaceClient:
    """Gmail v1 REST client. Routes every call through one credential row.

    The constructor is intentionally low-level (raw token + a
    refresh callback). Most callers should use ``from_credential``
    which wires the credential store, the refresh path, and the
    OAuth client together.
    """

    def __init__(
        self,
        *,
        access_token: str,
        expires_at: datetime | None,
        oauth_client: GoogleOAuthClient,
        on_refresh: RefreshPersistFn | None,
        refresh_token: str | None,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._access_token = access_token
        self._expires_at = expires_at
        self._refresh_token = refresh_token
        self._oauth = oauth_client
        self._on_refresh = on_refresh
        self._http = http if http is not None else httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
        self._owns_http = http is None

    # ----------------------------------------------------------------- factory

    @classmethod
    async def from_credential(
        cls,
        credential_id: UUID,
        *,
        session: AsyncSession,
        principal: Principal,
        oauth_client: GoogleOAuthClient | None = None,
        http: httpx.AsyncClient | None = None,
    ) -> Self:
        """Build a client from a ``tenant.integration_credential`` row.

        ``principal`` is required so that any auto-refresh can be
        audited under the caller's identity (the OAuth refresh writes
        an audit row via the credential service).
        """
        cred_svc = IntegrationCredentialService(session)
        payload = await cred_svc.read_by_id(credential_id, tenant_id=principal.tenant_id)
        access = payload.get("access_token")
        refresh = payload.get("refresh_token")
        expires_at_raw = payload.get("expires_at")
        if not isinstance(access, str) or not access:
            raise GoogleOAuthError("credential payload missing access_token")
        if refresh is not None and not isinstance(refresh, str):
            raise GoogleOAuthError("credential payload refresh_token has wrong type")

        expires_at: datetime | None = None
        if isinstance(expires_at_raw, (int, float)):
            expires_at = datetime.fromtimestamp(float(expires_at_raw), tz=UTC)
        elif isinstance(expires_at_raw, str):
            try:
                expires_at = datetime.fromisoformat(expires_at_raw)
            except ValueError:
                expires_at = None

        oauth = oauth_client if oauth_client is not None else GoogleOAuthClient.from_settings(
            http=http,
        )

        async def _persist(new_tokens: GoogleTokens) -> None:
            """Refresh callback — write the new access_token back."""
            updated = dict(payload)
            updated["access_token"] = new_tokens.access_token
            updated["expires_at"] = new_tokens.expires_at.timestamp()
            if new_tokens.refresh_token is not None:
                updated["refresh_token"] = new_tokens.refresh_token
            mailbox_raw = payload.get("mailbox_email")
            mailbox = mailbox_raw if isinstance(mailbox_raw, str) else None
            await cred_svc.upsert(
                tenant_id=principal.require_tenant(),
                provider_kind="google_workspace",
                credential_kind="oauth_token",
                payload=updated,
                principal=principal,
                mailbox_email=mailbox,
                last_refreshed_at=datetime.now(UTC),
                expires_at=new_tokens.expires_at,
            )

        return cls(
            access_token=access,
            expires_at=expires_at,
            oauth_client=oauth,
            on_refresh=_persist,
            refresh_token=refresh,
            http=http,
        )

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> GoogleWorkspaceClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ----------------------------------------------------------------- API

    async def get_profile(self) -> dict[str, Any]:
        """Verify the token works. Returns ``{emailAddress, messagesTotal, ...}``."""
        body = await self._request_json("GET", PROFILE_PATH, attempt=0)
        if not isinstance(body, dict):
            raise GoogleAPIError("gmail getProfile returned non-object body")
        return body

    async def send_message(self, rfc822_bytes: bytes) -> dict[str, Any]:
        """Send a single RFC 822 message via ``users.messages.send``.

        Gmail's API accepts ``raw`` as a URL-safe base64 string of the
        full RFC 822 message bytes. Callers are responsible for
        producing valid RFC 822 (multipart/alternative, the right
        ``From``, ``To``, ``Subject``, ``List-Unsubscribe`` headers).

        Returns the Gmail response which contains ``id`` and
        ``threadId`` — the outreach send pipeline persists these on
        the ``outreach.send`` row.
        """
        if not rfc822_bytes:
            raise GoogleAPIError("send_message called with empty rfc822 bytes")
        raw = base64.urlsafe_b64encode(rfc822_bytes).decode("ascii").rstrip("=")
        json_body = {"raw": raw}
        body = await self._request_json(
            "POST",
            SEND_PATH,
            json_body=json_body,
            attempt=0,
        )
        if not isinstance(body, dict):
            raise GoogleAPIError("gmail messages.send returned non-object body")
        return {
            "message_id": body.get("id"),
            "thread_id": body.get("threadId"),
        }

    async def get_messages_list(
        self,
        *,
        query: str,
        max_results: int = 100,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """``users.messages.list`` — light list of message ids matching ``q=``.

        Used by the ENG-134 bounce poller with a query like
        ``from:mailer-daemon@* newer_than:1d``. Returns the raw Gmail
        response (``{"messages": [...], "nextPageToken": "..."}``).
        Returns an empty messages list when the mailbox has none.
        """
        params: dict[str, str] = {
            "q": query,
            "maxResults": str(max(1, min(max_results, 500))),
        }
        if page_token:
            params["pageToken"] = page_token
        body = await self._request_json(
            "GET",
            MESSAGES_LIST_PATH,
            params=params,
            attempt=0,
        )
        if not isinstance(body, dict):
            raise GoogleAPIError("gmail messages.list returned non-object body")
        if "messages" not in body:
            # Gmail omits "messages" when there are no matches —
            # normalise so callers can always iterate.
            body["messages"] = []
        return body

    async def get_message(
        self,
        message_id: str,
        *,
        format_: str = "metadata",
        metadata_headers: list[str] | None = None,
    ) -> dict[str, Any]:
        """``users.messages.get`` — fetch a single message.

        Defaults to ``format=metadata`` so we read headers only. The
        bounce poller asks for ``In-Reply-To`` / ``References`` /
        ``X-Failed-Recipients`` / ``Subject`` / ``From`` — never the
        body. Metadata-only is a strict subset of
        ``gmail.readonly``.
        """
        if not message_id:
            raise GoogleAPIError("get_message called with empty message_id")
        if metadata_headers:
            params_list: list[tuple[str, str]] = [("format", format_)]
            for header in metadata_headers:
                params_list.append(("metadataHeaders", header))
            return await self._request_raw_list_params(
                "GET",
                MESSAGE_GET_PATH.format(message_id=message_id),
                params_list=params_list,
                attempt=0,
            )
        params: dict[str, str] = {"format": format_}
        body = await self._request_json(
            "GET",
            MESSAGE_GET_PATH.format(message_id=message_id),
            params=params,
            attempt=0,
        )
        if not isinstance(body, dict):
            raise GoogleAPIError("gmail messages.get returned non-object body")
        return body

    # ----------------------------------------------------------------- private

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        attempt: int,
    ) -> Any:
        """Single retry on 401 → refresh → retry, mirroring SF / CS clients."""
        url = f"{GMAIL_API_BASE}{path}"
        await self._refresh_if_close_to_expiry()

        response = await self._http.request(
            method,
            url,
            headers=self._auth_headers(),
            json=json_body,
            params=params,
        )

        if response.status_code == 401 and attempt == 0:
            log.info("gmail.401_refreshing", path=path)
            await self._refresh_access_token()
            return await self._request_json(
                method,
                path,
                json_body=json_body,
                params=params,
                attempt=attempt + 1,
            )

        if response.status_code == 401:
            raise GoogleOAuthError(
                "gmail 401 after refresh — refresh token expired or revoked",
                details={"status": 401},
            )

        if response.status_code >= 400:
            raise GoogleAPIError(
                f"gmail {method} {path} failed: {response.status_code}",
                details={
                    "status": response.status_code,
                    "body": response.text[:500],
                },
            )

        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise GoogleAPIError(
                "gmail returned non-JSON body",
                details={"status": response.status_code, "path": path},
            ) from exc

    async def _request_raw_list_params(
        self,
        method: str,
        path: str,
        *,
        params_list: list[tuple[str, str]],
        attempt: int,
    ) -> dict[str, Any]:
        """Variant of ``_request_json`` that accepts repeated query params.

        Gmail's ``metadataHeaders`` parameter is expected as a repeated
        ``metadataHeaders=Name`` query string. httpx accepts that
        shape through a ``list[tuple[str, str]]`` for ``params``.
        """
        url = f"{GMAIL_API_BASE}{path}"
        await self._refresh_if_close_to_expiry()

        response = await self._http.request(
            method, url, headers=self._auth_headers(), params=params_list
        )

        if response.status_code == 401 and attempt == 0:
            log.info("gmail.401_refreshing", path=path)
            await self._refresh_access_token()
            return await self._request_raw_list_params(
                method,
                path,
                params_list=params_list,
                attempt=attempt + 1,
            )

        if response.status_code == 401:
            raise GoogleOAuthError(
                "gmail 401 after refresh — refresh token expired or revoked",
                details={"status": 401},
            )

        if response.status_code >= 400:
            raise GoogleAPIError(
                f"gmail {method} {path} failed: {response.status_code}",
                details={
                    "status": response.status_code,
                    "body": response.text[:500],
                },
            )

        if response.status_code == 204 or not response.content:
            return {}
        try:
            body = response.json()
        except ValueError as exc:
            raise GoogleAPIError(
                "gmail returned non-JSON body",
                details={"status": response.status_code, "path": path},
            ) from exc
        if not isinstance(body, dict):
            raise GoogleAPIError("gmail metadata response not an object")
        return body

    async def _refresh_if_close_to_expiry(self) -> None:
        """Proactively refresh when the access_token is near expiry.

        Avoids the round-trip of a 401 → refresh → retry when we
        already know the token is stale. ``expires_at`` may be None
        for legacy rows; in that case we trust the request and let
        the 401 handler kick in.
        """
        if self._expires_at is None:
            return
        cutoff = datetime.now(UTC) + timedelta(seconds=_REFRESH_SKEW_SECONDS)
        if self._expires_at > cutoff:
            return
        await self._refresh_access_token()

    async def _refresh_access_token(self) -> None:
        """Run refresh + write new tokens back to the credential row."""
        if not self._refresh_token:
            raise GoogleOAuthError("no refresh_token available — cannot refresh")
        new_tokens = await self._oauth.refresh(refresh_token=self._refresh_token)
        self._access_token = new_tokens.access_token
        self._expires_at = new_tokens.expires_at
        if new_tokens.refresh_token:
            self._refresh_token = new_tokens.refresh_token
        if self._on_refresh is not None:
            await self._on_refresh(new_tokens)

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }


__all__ = [
    "GMAIL_API_BASE",
    "GoogleWorkspaceClient",
    "MESSAGE_GET_PATH",
    "MESSAGES_LIST_PATH",
    "PROFILE_PATH",
    "RefreshPersistFn",
    "SEND_PATH",
]
