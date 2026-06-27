"""Google Analytics 4 Data API client (v1beta, read-only).

Pulls daily property metrics (sessions / users / pageviews / conversions) via
``properties/{id}:runReport``. OAuth mirrors the Replit fallback: the GA4
refresh token is exchanged using the Google Ads OAuth client (client_id /
secret), since the account does not provision separate GA OAuth client creds.

Phase 2 credentials come from env via ``Settings`` (``from_env()``). Read-only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from packages.core.config import get_settings
from packages.core.logging import get_logger

from .exceptions import GoogleAnalyticsApiError, GoogleAnalyticsNotConnectedError

log = get_logger("integrations.google_analytics.client")

_DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
_TOKEN_REFRESH_SKEW_SECONDS = 60
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_API_BASE = "https://analyticsdata.googleapis.com/v1beta"

# Metric names requested per day (GA4 Data API metric ids). Date is the single
# dimension so each returned row is one calendar day.
_METRICS = ("sessions", "totalUsers", "newUsers", "screenPageViews", "conversions")

# Engagement metrics GA4 exposes on the same per-day grain. Captured additively
# (ENG-478) alongside the core ``_METRICS`` rollup; the mapper coerces strings.
_ENGAGEMENT_METRICS = (
    "engagedSessions",
    "engagementRate",
    "averageSessionDuration",
    "bounceRate",
    "eventCount",
)

# GA4 caps a single runReport at 100k rows; we never expect to approach that
# for the property-day grains pulled here.
_REPORT_ROW_LIMIT = 100000


@dataclass(frozen=True)
class GoogleToken:
    access_token: str
    expires_at: datetime


class GoogleAnalyticsClient:
    """Async GA4 Data API client. One instance per request/job."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        property_id: str,
        http: httpx.AsyncClient | None = None,
        token: GoogleToken | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._property_id = property_id
        self._http = http if http is not None else httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
        self._owns_http = http is None
        self._token = token

    @classmethod
    def from_credential(
        cls,
        payload: dict[str, Any],
        http: httpx.AsyncClient | None = None,
    ) -> GoogleAnalyticsClient:
        """Build from the decrypted DB-backed credential payload (ENG-490).

        Validates ``payload`` against
        :class:`packages.tenant.schemas.GoogleAnalyticsCredentialPayload`. The
        OAuth client (``client_id`` / ``client_secret``) is carried inside the
        payload per provider (see the schema docstring), so this factory is
        self-contained and does not read ``Settings``. Raises
        ``GoogleAnalyticsNotConnectedError`` on a malformed payload so the
        per-tenant pull skips gracefully. Never logs any payload value.
        """
        from pydantic import ValidationError as PydanticValidationError

        from packages.tenant.schemas import GoogleAnalyticsCredentialPayload

        try:
            cred = GoogleAnalyticsCredentialPayload.model_validate(payload)
        except PydanticValidationError as exc:
            raise GoogleAnalyticsNotConnectedError(
                "google analytics credential payload is invalid",
                details={"errors": exc.error_count()},
            ) from exc

        return cls(
            client_id=cred.client_id,
            client_secret=cred.client_secret,
            refresh_token=cred.refresh_token,
            property_id=cred.property_id,
            http=http,
        )

    @classmethod
    def from_env(cls, http: httpx.AsyncClient | None = None) -> GoogleAnalyticsClient:
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

        # OAuth client is shared with Google Ads (Replit fallback behaviour).
        client_id = _need(settings.google_ads_client_id, "GOOGLE_ADS_CLIENT_ID")
        client_secret = _need_secret(
            settings.google_ads_client_secret, "GOOGLE_ADS_CLIENT_SECRET"
        )
        refresh_token = _need_secret(settings.ga_refresh_token, "GA_REFRESH_TOKEN")
        property_id = _need(settings.ga_property_id, "GA_PROPERTY_ID")

        if missing:
            raise GoogleAnalyticsNotConnectedError(
                "google analytics credentials missing in environment",
                details={"missing_env": missing},
            )
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            property_id=property_id,
            http=http,
        )

    @property
    def property_id(self) -> str:
        return self._property_id

    async def run_report(
        self,
        *,
        start_date: date,
        end_date: date,
        dimensions: Sequence[str],
        metrics: Sequence[str],
        limit: int = _REPORT_ROW_LIMIT,
    ) -> list[dict[str, Any]]:
        """Run an arbitrary read-only ``:runReport`` and return zipped rows.

        Generic core all the typed report helpers delegate to. Each returned
        dict zips *every* requested dimension and metric by its GA4 id (e.g.
        ``{"date": "YYYYMMDD", "sessionDefaultChannelGroup": "Paid Search",
        "sessions": "123", ...}``) so the captured ``raw_event`` payload is
        self-describing and full-fidelity. Read-only: ``:runReport`` only.
        """
        body = {
            "dateRanges": [
                {"startDate": start_date.isoformat(), "endDate": end_date.isoformat()}
            ],
            "dimensions": [{"name": d} for d in dimensions],
            "metrics": [{"name": m} for m in metrics],
            "limit": limit,
        }
        payload = await self._run_report(body, attempt=0)
        return _flatten_report(payload)

    async def get_daily_metrics(
        self, *, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Return one self-describing dict per day over the range.

        Each dict is ``{"date": "YYYYMMDD", "<metric>": "<value>", ...}`` — the
        GA4 header/value arrays zipped into named keys so the captured
        ``raw_event`` payload is self-describing (not positional). Carries the
        core five metrics plus the additive engagement metrics (ENG-478).
        """
        return await self.run_report(
            start_date=start_date,
            end_date=end_date,
            dimensions=["date"],
            metrics=[*_METRICS, *_ENGAGEMENT_METRICS],
        )

    async def get_daily_channel_metrics(
        self, *, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """One row per (day, ``sessionDefaultChannelGroup``) — the organic vs
        paid vs direct split (ENG-478). Carries the core five metrics."""
        return await self.run_report(
            start_date=start_date,
            end_date=end_date,
            dimensions=["date", "sessionDefaultChannelGroup"],
            metrics=list(_METRICS),
        )

    async def get_daily_host_metrics(
        self, *, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """One row per (day, ``hostName``) — the per-site split (ENG-478).

        Captured as a page row keyed by host (``page_path`` carries the host).
        """
        return await self.run_report(
            start_date=start_date,
            end_date=end_date,
            dimensions=["date", "hostName"],
            metrics=list(_METRICS),
        )

    async def get_daily_landing_page_metrics(
        self, *, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """One row per (day, ``landingPage``) — top landing pages (ENG-478)."""
        return await self.run_report(
            start_date=start_date,
            end_date=end_date,
            dimensions=["date", "landingPage"],
            metrics=list(_METRICS),
        )

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> GoogleAnalyticsClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ------------------------------------------------------------------ private

    async def _run_report(self, body: dict[str, Any], *, attempt: int) -> dict[str, Any]:
        url = f"{_API_BASE}/properties/{self._property_id}:runReport"
        token = await self._ensure_token()
        headers = {
            "Authorization": f"Bearer {token.access_token}",
            "Content-Type": "application/json",
        }
        response = await self._http.post(url, headers=headers, json=body)

        if response.status_code == 401 and attempt == 0:
            log.info("google_analytics.401_refreshing", property_id=self._property_id)
            self._token = None
            return await self._run_report(body, attempt=attempt + 1)
        if response.status_code == 401:
            raise GoogleAnalyticsNotConnectedError(
                "google analytics 401 after token refresh",
                details={"status": 401, "property_id": self._property_id},
            )
        if response.status_code >= 400:
            raise GoogleAnalyticsApiError(
                f"google analytics runReport failed: {response.status_code}",
                details={"status": response.status_code, "body": response.text[:500]},
            )
        try:
            payload = response.json()
        except ValueError as exc:  # pragma: no cover
            raise GoogleAnalyticsApiError(
                "google analytics returned non-JSON body",
                details={"status": response.status_code},
            ) from exc
        if not isinstance(payload, dict):
            raise GoogleAnalyticsApiError(
                "google analytics returned non-object body",
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
            raise GoogleAnalyticsNotConnectedError(
                f"google analytics token refresh failed: {response.status_code}",
                details={"status": response.status_code, "body": response.text[:300]},
            )
        body = response.json()
        access = body.get("access_token")
        expires_in = body.get("expires_in")
        if not access or not isinstance(expires_in, int):
            raise GoogleAnalyticsNotConnectedError(
                "google analytics token response missing required fields",
                details={"keys": list(body.keys()) if isinstance(body, dict) else None},
            )
        token = GoogleToken(
            access_token=access,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
        )
        self._token = token
        log.info("google_analytics.token.refreshed", expires_in=expires_in)
        return token


def _header_names(headers: object) -> list[str | None]:
    """Pull the ``name`` of each header dict, preserving order."""
    if not isinstance(headers, list):
        return []
    return [h.get("name") if isinstance(h, dict) else None for h in headers]


def _flatten_report(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Zip GA4 header/value arrays into one named dict per row.

    Zips *all* dimension values by their header name (not just the first as
    ``date``) so multi-dimension reports — e.g. ``date ×
    sessionDefaultChannelGroup`` — come back fully self-describing. Metrics are
    zipped the same way.
    """
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return []
    dimension_names = _header_names(payload.get("dimensionHeaders"))
    metric_names = _header_names(payload.get("metricHeaders"))
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        dim_values = row.get("dimensionValues")
        metric_values = row.get("metricValues")
        record: dict[str, Any] = {}
        if isinstance(dim_values, list):
            for name, dv in zip(dimension_names, dim_values, strict=False):
                if isinstance(name, str) and isinstance(dv, dict):
                    record[name] = dv.get("value")
        if isinstance(metric_values, list):
            for name, mv in zip(metric_names, metric_values, strict=False):
                if isinstance(name, str) and isinstance(mv, dict):
                    record[name] = mv.get("value")
        out.append(record)
    return out
