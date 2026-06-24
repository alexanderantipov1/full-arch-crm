"""Meta (Facebook) Ads Graph API client (v21.0, read-only).

Authenticates with a long-lived / system-user access token (the token used by
the Replit ``DataBase_Fusion`` project). The token configured for this account
is a SYSTEM_USER token that does not expire, so no auto-refresh is required.
For a non-permanent token, Meta's keep-alive is the
``grant_type=fb_exchange_token`` exchange (app_id + app_secret + current
token); :meth:`exchange_long_lived_token` exposes it for that future case but
is not called on the read path.

Phase 1 credentials come from env via ``Settings`` (``from_env()``). Read-only:
only insights + campaign metadata GETs — no create/update endpoints (the
Replit project's campaign-creation path is intentionally NOT ported).
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

import httpx

from packages.core.config import get_settings
from packages.core.logging import get_logger

from .exceptions import MetaAdsApiError, MetaAdsNotConnectedError

log = get_logger("integrations.meta_ads.client")

_DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
_API_VERSION = "v21.0"
_BASE = f"https://graph.facebook.com/{_API_VERSION}"
_PAGE_SAFETY_CAP = 200

_NON_DIGITS = re.compile(r"\D+")


def _parse_account_ids(value: str | None) -> list[str]:
    """Parse ``META_ADS_AD_ACCOUNT_ID`` into bare numeric account ids.

    The env value is a comma-separated list shaped like
    ``act=938570599860690,act=1175596492910619`` (note ``act=``, also tolerant
    of ``act_``). Returns the digit-only ids; the API path prepends ``act_``.
    """
    if not value:
        return []
    out: list[str] = []
    for part in value.split(","):
        digits = _NON_DIGITS.sub("", part)
        if digits:
            out.append(digits)
    return out


class MetaAdsClient:
    """Async Meta Ads Graph client. One instance per request/job."""

    def __init__(
        self,
        *,
        access_token: str,
        ad_account_ids: list[str],
        app_id: str | None = None,
        app_secret: str | None = None,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._access_token = access_token
        self._ad_account_ids = ad_account_ids
        self._app_id = app_id
        self._app_secret = app_secret
        self._http = http if http is not None else httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
        self._owns_http = http is None

    # ------------------------------------------------------------------ factories

    @classmethod
    def from_credential(
        cls,
        payload: dict[str, Any],
        http: httpx.AsyncClient | None = None,
    ) -> MetaAdsClient:
        """Build from the decrypted DB-backed credential payload (ENG-490).

        Validates ``payload`` against
        :class:`packages.tenant.schemas.MetaAdsCredentialPayload`. The stored
        ``ad_account_ids`` are already bare numeric ids; we still digit-strip
        each one defensively so an ``act_<id>`` form round-trips like the env
        path. Raises ``MetaAdsNotConnectedError`` on a malformed payload or an
        empty account list so the per-tenant pull skips gracefully. Never logs
        any payload value.
        """
        from pydantic import ValidationError as PydanticValidationError

        from packages.tenant.schemas import MetaAdsCredentialPayload

        try:
            cred = MetaAdsCredentialPayload.model_validate(payload)
        except PydanticValidationError as exc:
            raise MetaAdsNotConnectedError(
                "meta ads credential payload is invalid",
                details={"errors": exc.error_count()},
            ) from exc

        ad_account_ids = [
            d
            for d in (_NON_DIGITS.sub("", acct) for acct in cred.ad_account_ids)
            if d
        ]
        if not ad_account_ids:
            raise MetaAdsNotConnectedError(
                "meta ads credential payload lists no ad account ids",
                details={"missing": ["ad_account_ids"]},
            )

        return cls(
            access_token=cred.access_token,
            ad_account_ids=ad_account_ids,
            app_id=cred.app_id,
            app_secret=cred.app_secret,
            http=http,
        )

    @classmethod
    def from_env(cls, http: httpx.AsyncClient | None = None) -> MetaAdsClient:
        """Build from ``Settings``. Raises if required vars are missing."""
        settings = get_settings()
        missing: list[str] = []

        def _need_secret(value: object, env_name: str) -> str:
            if value is None:
                missing.append(env_name)
                return ""
            secret = value.get_secret_value() if hasattr(value, "get_secret_value") else value
            if not secret:
                missing.append(env_name)
                return ""
            return str(secret)

        access_token = _need_secret(settings.meta_ads_access_token, "META_ADS_ACCESS_TOKEN")
        ad_account_ids = _parse_account_ids(settings.meta_ads_ad_account_id)
        if not ad_account_ids:
            missing.append("META_ADS_AD_ACCOUNT_ID")

        if missing:
            raise MetaAdsNotConnectedError(
                "meta ads credentials missing in environment",
                details={"missing_env": missing},
            )

        app_secret = (
            settings.meta_ads_app_secret.get_secret_value()
            if settings.meta_ads_app_secret is not None
            else None
        )
        return cls(
            access_token=access_token,
            ad_account_ids=ad_account_ids,
            app_id=settings.meta_ads_app_id,
            app_secret=app_secret,
            http=http,
        )

    # ------------------------------------------------------------------ public

    @property
    def ad_account_ids(self) -> list[str]:
        return list(self._ad_account_ids)

    async def list_campaigns(self, account_id: str) -> list[dict[str, Any]]:
        """Campaign metadata for ``act_{account_id}`` (id, name, status, objective)."""
        return await self._get_paginated(
            f"act_{account_id}/campaigns",
            {"fields": "id,name,status,objective", "limit": 500},
        )

    async def get_campaign_insights(
        self,
        account_id: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Daily campaign insights for ``act_{account_id}`` over a date range.

        ``time_increment=1`` yields one row per (campaign, day). Each row is the
        verbatim Graph object (spend/impressions/clicks/actions + date_start).
        """
        params = {
            "level": "campaign",
            "fields": "campaign_id,campaign_name,spend,impressions,clicks,actions",
            "time_increment": 1,
            "time_range": json.dumps(
                {"since": start_date.isoformat(), "until": end_date.isoformat()}
            ),
            "limit": 500,
        }
        return await self._get_paginated(f"act_{account_id}/insights", params)

    async def get_ad_insights(
        self,
        account_id: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Daily ad-level insights for ``act_{account_id}`` over a date range.

        ``level=ad`` + ``time_increment=1`` yields one row per (ad, day). Each
        row is the verbatim Graph object carrying the full hierarchy ids/names
        (``ad_id``/``ad_name``/``adset_id``/``adset_name``/``campaign_id``/
        ``campaign_name``) plus ``spend``/``impressions``/``clicks``/``actions``
        and ``date_start``. The verbatim row (incl. full ``actions``) is captured
        at 100% fidelity into ``ingest.raw_event`` by the ingest service; this
        client only fetches.
        """
        params = {
            "level": "ad",
            "fields": (
                "ad_id,ad_name,adset_id,adset_name,campaign_id,campaign_name,"
                "spend,impressions,clicks,actions"
            ),
            "time_increment": 1,
            "time_range": json.dumps(
                {"since": start_date.isoformat(), "until": end_date.isoformat()}
            ),
            "limit": 500,
        }
        return await self._get_paginated(f"act_{account_id}/insights", params)

    async def exchange_long_lived_token(self) -> str | None:
        """Extend the current token via ``fb_exchange_token`` (keep-alive).

        NOT used on the read path — the configured token is a non-expiring
        system-user token. Kept for the future case of a 60-day user token:
        exchanges app_id + app_secret + current token for a fresh long-lived
        one. Returns the new token, or ``None`` if app creds are absent.
        """
        if not self._app_id or not self._app_secret:
            return None
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self._app_id,
            "client_secret": self._app_secret,
            "fb_exchange_token": self._access_token,
        }
        url = f"{_BASE}/oauth/access_token"
        response = await self._http.get(url, params=params)
        if response.status_code >= 400:
            raise MetaAdsNotConnectedError(
                f"meta ads token exchange failed: {response.status_code}",
                details={"status": response.status_code, "body": response.text[:300]},
            )
        new_token = response.json().get("access_token")
        if isinstance(new_token, str) and new_token:
            self._access_token = new_token
            return new_token
        return None

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> MetaAdsClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ------------------------------------------------------------------ private

    async def _get_paginated(
        self, path: str, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """GET ``{BASE}/{path}`` following ``paging.next`` to completion."""
        url = f"{_BASE}/{path}"
        query: dict[str, Any] | None = {**params, "access_token": self._access_token}
        rows: list[dict[str, Any]] = []
        pages = 0
        while pages < _PAGE_SAFETY_CAP:
            payload = await self._get_json(url, query)
            data = payload.get("data")
            if isinstance(data, list):
                rows.extend(r for r in data if isinstance(r, dict))
            pages += 1
            paging = payload.get("paging")
            next_url = paging.get("next") if isinstance(paging, dict) else None
            if isinstance(next_url, str) and next_url:
                # ``next`` is a fully-formed URL with the cursor + token baked in.
                url, query = next_url, None
                continue
            break
        return rows

    async def _get_json(self, url: str, params: dict[str, Any] | None) -> dict[str, Any]:
        response = await self._http.get(url, params=params)
        if response.status_code == 401 or response.status_code == 403:
            raise MetaAdsNotConnectedError(
                f"meta ads auth failed: {response.status_code}",
                details={"status": response.status_code, "body": response.text[:300]},
            )
        if response.status_code >= 400:
            raise MetaAdsApiError(
                f"meta ads request failed: {response.status_code}",
                details={"status": response.status_code, "body": response.text[:500]},
            )
        try:
            payload = response.json()
        except ValueError as exc:  # pragma: no cover — malformed JSON is rare
            raise MetaAdsApiError(
                "meta ads returned non-JSON body",
                details={"status": response.status_code},
            ) from exc
        if not isinstance(payload, dict):
            raise MetaAdsApiError(
                "meta ads returned non-object body",
                details={"type": type(payload).__name__},
            )
        if "error" in payload:
            err = payload["error"]
            raise MetaAdsApiError(
                "meta ads error envelope",
                details={"error": err if isinstance(err, dict) else str(err)},
            )
        return payload
