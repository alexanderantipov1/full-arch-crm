"""Google Search Console (Webmasters API v3) client (read-only).

Pulls daily search-analytics rows (query × date with clicks / impressions /
ctr / position). OAuth mirrors the GA4 connector: the GSC refresh token is
exchanged using the Google Ads OAuth client (the account has no separate GSC
OAuth client creds).

``GSC_SITE_URL`` is optional — :meth:`resolve_site_url` auto-discovers the
verified property via ``sites.list`` when it is unset.

Phase 2 credentials come from env via ``Settings`` (``from_env()``). Read-only.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from packages.core.config import get_settings
from packages.core.logging import get_logger

from .exceptions import (
    GoogleSearchConsoleApiError,
    GoogleSearchConsoleNotConnectedError,
)

log = get_logger("integrations.google_search_console.client")

_DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
_TOKEN_REFRESH_SKEW_SECONDS = 60
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_API_BASE = "https://www.googleapis.com/webmasters/v3"
_ROW_LIMIT = 25000  # Search Console hard max per page
_PAGE_SAFETY_CAP = 200


@dataclass(frozen=True)
class GoogleToken:
    access_token: str
    expires_at: datetime


class GoogleSearchConsoleClient:
    """Async Search Console client. One instance per request/job."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        site_url: str | None = None,
        http: httpx.AsyncClient | None = None,
        token: GoogleToken | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._site_url = site_url
        self._resolved_site_url = site_url
        self._http = http if http is not None else httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
        self._owns_http = http is None
        self._token = token

    @classmethod
    def from_credential(
        cls,
        payload: dict[str, Any],
        http: httpx.AsyncClient | None = None,
    ) -> GoogleSearchConsoleClient:
        """Build from the decrypted DB-backed credential payload (ENG-490).

        Validates ``payload`` against
        :class:`packages.tenant.schemas.GoogleSearchConsoleCredentialPayload`.
        ``site_url`` is optional — when absent the client auto-discovers the
        verified property via ``sites.list`` (same as the env path). The OAuth
        client is carried in the payload per provider, so this factory does not
        read ``Settings``. Raises ``GoogleSearchConsoleNotConnectedError`` on a
        malformed payload so the per-tenant pull skips gracefully. Never logs
        any payload value.
        """
        from pydantic import ValidationError as PydanticValidationError

        from packages.tenant.schemas import GoogleSearchConsoleCredentialPayload

        try:
            cred = GoogleSearchConsoleCredentialPayload.model_validate(payload)
        except PydanticValidationError as exc:
            raise GoogleSearchConsoleNotConnectedError(
                "google search console credential payload is invalid",
                details={"errors": exc.error_count()},
            ) from exc

        return cls(
            client_id=cred.client_id,
            client_secret=cred.client_secret,
            refresh_token=cred.refresh_token,
            site_url=cred.site_url,
            http=http,
        )

    @classmethod
    def from_env(cls, http: httpx.AsyncClient | None = None) -> GoogleSearchConsoleClient:
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
        refresh_token = _need_secret(settings.gsc_refresh_token, "GSC_REFRESH_TOKEN")

        if missing:
            raise GoogleSearchConsoleNotConnectedError(
                "google search console credentials missing in environment",
                details={"missing_env": missing},
            )
        # site_url is optional — auto-discovered when unset.
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            site_url=settings.gsc_site_url,
            http=http,
        )

    # ------------------------------------------------------------------ public

    async def list_sites(self) -> list[dict[str, Any]]:
        """``GET /sites`` — verified properties for the authorised user."""
        payload = await self._get("sites", attempt=0)
        entries = payload.get("siteEntry")
        return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []

    async def resolve_site_url(self) -> str:
        """Return the configured site, or auto-discover the best verified one.

        Discovery prefers a ``sc-domain:`` property (covers all subdomains),
        then any non-unverified entry. Raises
        ``GoogleSearchConsoleNotConnectedError`` when none is available.
        """
        if self._resolved_site_url:
            return self._resolved_site_url
        sites = await self.list_sites()
        verified = [
            s
            for s in sites
            if s.get("permissionLevel") not in (None, "siteUnverifiedUser")
            and isinstance(s.get("siteUrl"), str)
        ]
        if not verified:
            raise GoogleSearchConsoleNotConnectedError(
                "no verified Search Console site available",
                details={"site_count": len(sites)},
            )
        domain = next((s for s in verified if str(s["siteUrl"]).startswith("sc-domain:")), None)
        chosen = domain or verified[0]
        self._resolved_site_url = str(chosen["siteUrl"])
        log.info("google_search_console.site.resolved", site_url=self._resolved_site_url)
        return self._resolved_site_url

    async def get_query_metrics(
        self,
        site_url: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Daily query rows for a site: ``{date, query, clicks, impressions, ctr, position}``.

        Uses ``searchAnalytics.query`` with dimensions ``[date, query]`` and
        paginates via ``startRow`` until a short page is returned.
        """
        encoded = urllib.parse.quote(site_url, safe="")
        path = f"sites/{encoded}/searchAnalytics/query"
        rows: list[dict[str, Any]] = []
        start_row = 0
        pages = 0
        while pages < _PAGE_SAFETY_CAP:
            body = {
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": ["date", "query"],
                "rowLimit": _ROW_LIMIT,
                "startRow": start_row,
            }
            payload = await self._post(path, body, attempt=0)
            page = payload.get("rows")
            page_rows = [r for r in page if isinstance(r, dict)] if isinstance(page, list) else []
            for r in page_rows:
                keys = r.get("keys")
                record = {
                    "date": keys[0] if isinstance(keys, list) and len(keys) > 0 else None,
                    "query": keys[1] if isinstance(keys, list) and len(keys) > 1 else None,
                    "clicks": r.get("clicks"),
                    "impressions": r.get("impressions"),
                    "ctr": r.get("ctr"),
                    "position": r.get("position"),
                }
                rows.append(record)
            pages += 1
            if len(page_rows) < _ROW_LIMIT:
                break
            start_row += _ROW_LIMIT
        return rows

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> GoogleSearchConsoleClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ------------------------------------------------------------------ private

    async def _get(self, path: str, *, attempt: int) -> dict[str, Any]:
        url = f"{_API_BASE}/{path}"
        token = await self._ensure_token()
        response = await self._http.get(
            url, headers={"Authorization": f"Bearer {token.access_token}"}
        )
        return await self._handle(response, "GET", path, body=None, attempt=attempt)

    async def _post(self, path: str, body: dict[str, Any], *, attempt: int) -> dict[str, Any]:
        url = f"{_API_BASE}/{path}"
        token = await self._ensure_token()
        response = await self._http.post(
            url,
            headers={
                "Authorization": f"Bearer {token.access_token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        return await self._handle(response, "POST", path, body=body, attempt=attempt)

    async def _handle(
        self,
        response: httpx.Response,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None,
        attempt: int,
    ) -> dict[str, Any]:
        if response.status_code == 401 and attempt == 0:
            log.info("google_search_console.401_refreshing", path=path)
            self._token = None
            if method == "GET":
                return await self._get(path, attempt=attempt + 1)
            return await self._post(path, body or {}, attempt=attempt + 1)
        if response.status_code == 401:
            raise GoogleSearchConsoleNotConnectedError(
                "google search console 401 after token refresh",
                details={"status": 401, "path": path},
            )
        if response.status_code >= 400:
            raise GoogleSearchConsoleApiError(
                f"google search console {method} {path} failed: {response.status_code}",
                details={"status": response.status_code, "body": response.text[:500]},
            )
        try:
            payload = response.json()
        except ValueError as exc:  # pragma: no cover
            raise GoogleSearchConsoleApiError(
                "google search console returned non-JSON body",
                details={"status": response.status_code, "path": path},
            ) from exc
        if not isinstance(payload, dict):
            raise GoogleSearchConsoleApiError(
                "google search console returned non-object body",
                details={"type": type(payload).__name__},
            )
        return payload

    async def _ensure_token(self) -> GoogleToken:
        cached = self._token
        if cached is not None:
            cutoff = datetime.now(UTC) + timedelta(seconds=_TOKEN_REFRESH_SKEW_SECONDS)
            if cached.expires_at > cutoff:
                return cached
        return await self._refresh_access_token()

    async def _refresh_access_token(self) -> GoogleToken:
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
            raise GoogleSearchConsoleNotConnectedError(
                f"google search console token refresh failed: {response.status_code}",
                details={"status": response.status_code, "body": response.text[:300]},
            )
        body = response.json()
        access = body.get("access_token")
        expires_in = body.get("expires_in")
        if not access or not isinstance(expires_in, int):
            raise GoogleSearchConsoleNotConnectedError(
                "google search console token response missing required fields",
                details={"keys": list(body.keys()) if isinstance(body, dict) else None},
            )
        token = GoogleToken(
            access_token=access,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
        )
        self._token = token
        log.info("google_search_console.token.refreshed", expires_in=expires_in)
        return token
