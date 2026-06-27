"""Google Ads REST client (API v23, read-only).

OAuth flow mirrors the Replit TypeScript connector:

1. Exchange the long-lived ``refresh_token`` for a short-lived access token
   at ``https://oauth2.googleapis.com/token`` (form-urlencoded
   ``grant_type=refresh_token``). Cache it in-memory until ~60 s before
   expiry.
2. Query the Google Ads API with the access token + ``developer-token`` and
   (for manager accounts) ``login-customer-id`` headers, via the
   ``customers/{id}/googleAds:search`` GAQL endpoint.

Phase 1 credentials come from env via ``Settings`` (``from_env()``), the same
bootstrap path CareStack used in ENG-124. Read-only: only ``:search`` (no
mutate endpoints). Tests inject ``http=`` / ``token=`` to avoid real traffic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from packages.core.config import get_settings
from packages.core.logging import get_logger

from .exceptions import GoogleAdsApiError, GoogleAdsNotConnectedError

log = get_logger("integrations.google_ads.client")

_DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
_TOKEN_REFRESH_SKEW_SECONDS = 60
_API_VERSION = "v23"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_API_BASE = "https://googleads.googleapis.com"
_PAGE_SAFETY_CAP = 200

_NON_DIGITS = re.compile(r"\D+")


def _digits(value: str) -> str:
    """Google customer ids are 10 digits; env may carry dashes (818-541-8623)."""
    return _NON_DIGITS.sub("", value)


def _split_ids(value: str | None) -> list[str]:
    """Parse a comma-separated customer-id env value into digit-only ids."""
    if not value:
        return []
    out: list[str] = []
    for part in value.split(","):
        cleaned = _digits(part)
        if cleaned:
            out.append(cleaned)
    return out


@dataclass(frozen=True)
class GoogleAdsToken:
    access_token: str
    expires_at: datetime


class GoogleAdsClient:
    """Async Google Ads REST client. One instance per request/job."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        developer_token: str,
        refresh_token: str,
        login_customer_id: str | None,
        customer_ids: list[str],
        http: httpx.AsyncClient | None = None,
        token: GoogleAdsToken | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._developer_token = developer_token
        self._refresh_token = refresh_token
        self._login_customer_id = _digits(login_customer_id) if login_customer_id else None
        self._customer_ids = customer_ids
        self._http = http if http is not None else httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
        self._owns_http = http is None
        self._token = token

    # ------------------------------------------------------------------ factories

    @classmethod
    def from_credential(
        cls,
        payload: dict[str, Any],
        http: httpx.AsyncClient | None = None,
    ) -> GoogleAdsClient:
        """Build from the decrypted DB-backed credential payload (ENG-490).

        Validates ``payload`` against
        :class:`packages.tenant.schemas.GoogleAdsCredentialPayload` so the
        envelope shape is enforced at the boundary (extra keys rejected,
        required fields present). Raises ``GoogleAdsNotConnectedError`` when
        the payload is malformed or lists no customer ids — the per-tenant
        pull translates that to a graceful skip, never a crash. Never logs
        any payload value.
        """
        from pydantic import ValidationError as PydanticValidationError

        from packages.tenant.schemas import GoogleAdsCredentialPayload

        try:
            cred = GoogleAdsCredentialPayload.model_validate(payload)
        except PydanticValidationError as exc:
            raise GoogleAdsNotConnectedError(
                "google ads credential payload is invalid",
                # Pydantic error locations name the offending fields only;
                # they never echo the secret values.
                details={"errors": exc.error_count()},
            ) from exc

        customer_ids = [c for c in (_digits(cid) for cid in cred.customer_ids) if c]
        if not customer_ids:
            raise GoogleAdsNotConnectedError(
                "google ads credential payload lists no customer ids",
                details={"missing": ["customer_ids"]},
            )

        return cls(
            client_id=cred.client_id,
            client_secret=cred.client_secret,
            developer_token=cred.developer_token,
            refresh_token=cred.refresh_token,
            login_customer_id=cred.login_customer_id,
            customer_ids=customer_ids,
            http=http,
        )

    @classmethod
    def from_env(cls, http: httpx.AsyncClient | None = None) -> GoogleAdsClient:
        """Build from ``Settings``. Raises if required vars are missing."""
        settings = get_settings()
        missing: list[str] = []

        def _need(value: str | None, env_name: str) -> str:
            if not value:
                missing.append(env_name)
                return ""
            return value

        def _need_secret(value: object, env_name: str) -> str:
            if value is None:
                missing.append(env_name)
                return ""
            secret = value.get_secret_value() if hasattr(value, "get_secret_value") else value
            if not secret:
                missing.append(env_name)
                return ""
            return str(secret)

        client_id = _need(settings.google_ads_client_id, "GOOGLE_ADS_CLIENT_ID")
        client_secret = _need_secret(
            settings.google_ads_client_secret, "GOOGLE_ADS_CLIENT_SECRET"
        )
        developer_token = _need_secret(
            settings.google_ads_developer_token, "GOOGLE_ADS_DEVELOPER_TOKEN"
        )
        refresh_token = _need_secret(
            settings.google_ads_refresh_token, "GOOGLE_ADS_REFRESH_TOKEN"
        )
        customer_ids = _split_ids(settings.google_ads_customer_id)
        if not customer_ids:
            missing.append("GOOGLE_ADS_CUSTOMER_ID")

        if missing:
            raise GoogleAdsNotConnectedError(
                "google ads credentials missing in environment",
                details={"missing_env": missing},
            )

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            developer_token=developer_token,
            refresh_token=refresh_token,
            login_customer_id=settings.google_ads_login_customer_id,
            customer_ids=customer_ids,
            http=http,
        )

    # ------------------------------------------------------------------ public

    @property
    def customer_ids(self) -> list[str]:
        return list(self._customer_ids)

    async def search_campaign_metrics(
        self,
        customer_id: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Return verbatim GAQL rows of campaign + daily metrics.

        One row per (campaign, day). Each row is the raw Google Ads result
        object (``campaign`` + ``metrics`` + ``segments`` sub-objects) so the
        ingest layer captures full fidelity and maps on demand.
        """
        query = (
            "SELECT campaign.id, campaign.name, campaign.status, "
            "campaign.advertising_channel_type, "
            "metrics.cost_micros, metrics.impressions, metrics.clicks, "
            "metrics.conversions, segments.date "
            "FROM campaign "
            f"WHERE segments.date BETWEEN '{start_date.isoformat()}' "
            f"AND '{end_date.isoformat()}'"
        )
        return await self.search(customer_id, query)

    async def search(self, customer_id: str, query: str) -> list[dict[str, Any]]:
        """Run a GAQL query against ``customers/{id}/googleAds:search``.

        Follows ``nextPageToken`` to completion and returns the flattened
        list of result rows. Refreshes the access token once on 401.
        """
        cid = _digits(customer_id)
        rows: list[dict[str, Any]] = []
        page_token: str | None = None
        pages = 0
        while pages < _PAGE_SAFETY_CAP:
            body: dict[str, Any] = {"query": query}
            if page_token:
                body["pageToken"] = page_token
            payload = await self._post_search(cid, body, attempt=0)
            results = payload.get("results")
            if isinstance(results, list):
                rows.extend(r for r in results if isinstance(r, dict))
            pages += 1
            next_token = payload.get("nextPageToken")
            if isinstance(next_token, str) and next_token:
                page_token = next_token
                continue
            break
        return rows

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> GoogleAdsClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ------------------------------------------------------------------ private

    async def _post_search(
        self, customer_id: str, body: dict[str, Any], *, attempt: int
    ) -> dict[str, Any]:
        url = f"{_API_BASE}/{_API_VERSION}/customers/{customer_id}/googleAds:search"
        token = await self._ensure_token()
        headers = {
            "Authorization": f"Bearer {token.access_token}",
            "developer-token": self._developer_token,
            "Content-Type": "application/json",
        }
        if self._login_customer_id:
            headers["login-customer-id"] = self._login_customer_id

        response = await self._http.post(url, headers=headers, json=body)

        if response.status_code == 401 and attempt == 0:
            log.info("google_ads.401_refreshing", customer_id=customer_id)
            self._token = None
            return await self._post_search(customer_id, body, attempt=attempt + 1)

        if response.status_code == 401:
            raise GoogleAdsNotConnectedError(
                "google ads 401 after token refresh",
                details={"status": 401, "customer_id": customer_id},
            )

        if response.status_code >= 400:
            raise GoogleAdsApiError(
                f"google ads search failed: {response.status_code}",
                details={
                    "status": response.status_code,
                    "customer_id": customer_id,
                    "body": response.text[:500],
                },
            )

        try:
            payload = response.json()
        except ValueError as exc:  # pragma: no cover — malformed JSON is rare
            raise GoogleAdsApiError(
                "google ads returned non-JSON body",
                details={"status": response.status_code, "customer_id": customer_id},
            ) from exc
        if not isinstance(payload, dict):
            raise GoogleAdsApiError(
                "google ads search returned non-object body",
                details={"type": type(payload).__name__, "customer_id": customer_id},
            )
        return payload

    async def _ensure_token(self) -> GoogleAdsToken:
        cached = self._token
        if cached is not None:
            cutoff = datetime.now(UTC) + timedelta(seconds=_TOKEN_REFRESH_SKEW_SECONDS)
            if cached.expires_at > cutoff:
                return cached
        return await self._refresh_access_token()

    async def _refresh_access_token(self) -> GoogleAdsToken:
        data = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
            "grant_type": "refresh_token",
        }
        response = await self._http.post(
            _TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code >= 400:
            raise GoogleAdsNotConnectedError(
                f"google ads token refresh failed: {response.status_code}",
                details={"status": response.status_code, "body": response.text[:300]},
            )
        body = response.json()
        access = body.get("access_token")
        expires_in = body.get("expires_in")
        if not access or not isinstance(expires_in, int):
            raise GoogleAdsNotConnectedError(
                "google ads token response missing required fields",
                details={"keys": list(body.keys()) if isinstance(body, dict) else None},
            )
        token = GoogleAdsToken(
            access_token=access,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
        )
        self._token = token
        log.info("google_ads.token.refreshed", expires_in=expires_in)
        return token
