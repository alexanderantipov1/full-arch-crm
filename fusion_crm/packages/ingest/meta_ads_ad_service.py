"""Meta (Facebook) Ads ad-level spend ingest pipeline (ENG-512).

Same capture-then-project shape as :mod:`meta_ads_campaign_service`, but at
``level=ad``: capture each verbatim ad-insight row into ``ingest.raw_event``
(full fidelity, invariant #11) + the schema registry, then project into the
curated ad-tier ``marketing`` tables (``ad_set`` / ``ad`` / ``ad_metric_daily_ad``)
via ``MarketingService``. The campaign-level tables are untouched — this is an
additive, finer-grained tier feeding the cost-per-lead allocator.

Meta specifics (mirrors the campaign service):
* ``spend`` arrives as a string; ``conversions`` is derived best-effort from the
  ``actions`` array (lead-type actions). The verbatim row (incl. full
  ``actions``) is always preserved in ``raw_event`` for later re-mapping.
* One row per (ad, day) via ``time_increment=1``.

Account coverage is config-only: the pull iterates ``client.ad_account_ids``
(env / per-tenant credential). Adding the Phase-2 accounts is a credential
change, no code change here.

The Meta HTTP client is consumed via a local Protocol so this module does not
import ``packages.integrations``. Read-only end to end.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import ValidationError
from packages.core.logging import get_logger
from packages.core.types import TenantId
from packages.ingest.schemas import MarketingSpendImportOut, ObservedFieldIn, RawEventIn
from packages.ingest.service import IngestService
from packages.marketing.schemas import (
    AdMetricDailyAdUpsertIn,
    AdSetUpsertIn,
    AdUpsertIn,
)
from packages.marketing.service import MarketingService

log = get_logger("ingest.meta_ads_ad")

_PROVIDER = "meta_ads"
_EVENT_TYPE = "meta_ads.ad_metric.upsert"
_OBJECT_NAME = "ad_insight"

# action_type values that count as a conversion/lead for the curated
# ``conversions`` column. Best-effort; the full ``actions`` array stays in raw.
_LEAD_ACTION_TYPES = frozenset(
    {
        "lead",
        "onsite_conversion.lead_grouped",
        "offsite_conversion.fb_pixel_lead",
        "onsite_conversion.lead",
        "leadgen.other",
    }
)


class MetaAdsAdClientProtocol(Protocol):
    """Minimum Meta Ads client surface needed by this ad-level ingest service."""

    @property
    def ad_account_ids(self) -> list[str]: ...

    async def get_ad_insights(
        self,
        account_id: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]: ...


class MetaAdsAdIngestService:
    """Pull Meta Ads ad-level spend, capture raw, project into marketing."""

    def __init__(
        self,
        session: AsyncSession,
        meta_ads_client: MetaAdsAdClientProtocol,
    ) -> None:
        self._session = session
        self._meta = meta_ads_client
        self._ingest = IngestService(session)
        self._marketing = MarketingService(session)

    async def import_recent_spend(
        self,
        tenant_id: TenantId,
        *,
        days: int = 3,
    ) -> MarketingSpendImportOut:
        """Capture the last ``days`` of ad-level spend across all ad accounts.

        The window settles on **completed days only**: ``end_date`` is D-1
        (yesterday), never today — today's spend is still accruing and a partial
        figure would be captured then re-pulled, churning the dedupe. ``days`` is
        the rolling lookback that absorbs late-settling spend (default 3 →
        ``[D-3, D-1]``); the daily refresh re-pulls it and relies on
        content-identity dedupe so overlapping runs are idempotent.
        """
        if days < 1 or days > 365:
            raise ValidationError("days must be between 1 and 365", details={"days": days})

        end_date = datetime.now(UTC).date() - timedelta(days=1)
        start_date = end_date - timedelta(days=days - 1)
        return await self.import_window(
            tenant_id, start_date=start_date, end_date=end_date
        )

    async def import_window(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
    ) -> MarketingSpendImportOut:
        """Capture ad-level spend for an explicit ``[start_date, end_date]`` window.

        Idempotent: a re-pulled row whose stored raw payload is byte-identical
        counts as ``unchanged`` and is skipped before any write, so overlapping
        windows and re-runs are safe.
        """
        if start_date > end_date:
            raise ValidationError(
                "start_date must be on or before end_date",
                details={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
            )
        days = (end_date - start_date).days + 1

        imported = 0
        unchanged = 0
        skipped = 0
        ads_seen: set[str] = set()
        observed_fields: dict[str, str] = {}
        account_count = 0

        for account_id in self._meta.ad_account_ids:
            account_count += 1
            try:
                rows = await self._meta.get_ad_insights(
                    account_id, start_date=start_date, end_date=end_date
                )
            except Exception as exc:  # noqa: BLE001 - one inaccessible account must not abort the rest
                log.warning(
                    "meta_ads.ad_insights.fetch_failed",
                    account_id=account_id,
                    error=type(exc).__name__,
                )
                continue
            for row in rows:
                _merge_observed(observed_fields, row)
                parsed = _parse_row(row)
                if parsed is None:
                    skipped += 1
                    continue
                external_id = f"{parsed['ad_id']}:{parsed['metric_date'].isoformat()}"

                latest = await self._ingest.latest_payload(
                    tenant_id, event_type=_EVENT_TYPE, external_id=external_id
                )
                if latest == row:
                    unchanged += 1
                    continue

                if await self._capture_and_project_safe(
                    tenant_id, row, parsed, external_id, account_id
                ):
                    imported += 1
                    ads_seen.add(parsed["ad_id"])
                else:
                    skipped += 1

        if observed_fields:
            await self._ingest.sync_object_schema(
                tenant_id,
                provider=_PROVIDER,
                object_name=_OBJECT_NAME,
                fields=[
                    ObservedFieldIn(
                        name=name,
                        field_type=field_type,
                        readable=True,
                        meta={"source": "observed_keys"},
                    )
                    for name, field_type in observed_fields.items()
                ],
                observed_at=datetime.now(UTC),
            )

        return MarketingSpendImportOut(
            imported_count=imported,
            unchanged_count=unchanged,
            skipped_count=skipped,
            campaigns_upserted=len(ads_seen),
            account_count=account_count,
            days=days,
        )

    async def _capture_and_project_safe(
        self,
        tenant_id: TenantId,
        row: dict[str, Any],
        parsed: dict[str, Any],
        external_id: str,
        account_id: str,
    ) -> bool:
        """Capture + project one row in a SAVEPOINT so one bad row is isolated."""
        try:
            async with self._session.begin_nested():
                raw_event = await self._ingest.capture(
                    tenant_id,
                    RawEventIn(
                        source=_PROVIDER,
                        event_type=_EVENT_TYPE,
                        external_id=external_id,
                        received_at=datetime.now(UTC),
                        payload=row,
                    ),
                )
                if parsed["adset_id"] is not None:
                    await self._marketing.upsert_ad_set(
                        tenant_id,
                        AdSetUpsertIn(
                            provider=_PROVIDER,
                            external_id=parsed["adset_id"],
                            name=parsed["adset_name"],
                            campaign_external_id=parsed["campaign_id"],
                            account_id=account_id,
                            raw_event_id=raw_event.id,
                        ),
                    )
                await self._marketing.upsert_ad(
                    tenant_id,
                    AdUpsertIn(
                        provider=_PROVIDER,
                        external_id=parsed["ad_id"],
                        name=parsed["ad_name"],
                        adset_external_id=parsed["adset_id"],
                        campaign_external_id=parsed["campaign_id"],
                        account_id=account_id,
                        raw_event_id=raw_event.id,
                    ),
                )
                await self._marketing.upsert_ad_metric_daily(
                    tenant_id,
                    AdMetricDailyAdUpsertIn(
                        provider=_PROVIDER,
                        ad_external_id=parsed["ad_id"],
                        adset_external_id=parsed["adset_id"],
                        campaign_external_id=parsed["campaign_id"],
                        metric_date=parsed["metric_date"],
                        spend=parsed["spend"],
                        impressions=parsed["impressions"],
                        clicks=parsed["clicks"],
                        conversions=parsed["conversions"],
                        raw_event_id=raw_event.id,
                    ),
                )
            return True
        except Exception as exc:  # noqa: BLE001 - one bad row must not abort the pull
            log.warning(
                "meta_ads.ad_spend.capture_failed",
                account_id=account_id,
                external_id=external_id,
                error=type(exc).__name__,
            )
            return False


def _parse_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    """Extract typed fields from a Meta ad insight row, or None if unusable."""
    ad_id = row.get("ad_id")
    metric_date = _parse_date(row.get("date_start"))
    if ad_id is None or metric_date is None:
        return None
    campaign_id = row.get("campaign_id")
    adset_id = row.get("adset_id")
    return {
        "ad_id": str(ad_id),
        "ad_name": _str_or_none(row.get("ad_name")),
        "adset_id": str(adset_id) if adset_id is not None else None,
        "adset_name": _str_or_none(row.get("adset_name")),
        "campaign_id": str(campaign_id) if campaign_id is not None else None,
        "campaign_name": _str_or_none(row.get("campaign_name")),
        "metric_date": metric_date,
        "spend": _to_float(row.get("spend")),
        "impressions": _to_int(row.get("impressions")),
        "clicks": _to_int(row.get("clicks")),
        "conversions": _conversions_from_actions(row.get("actions")),
    }


def _conversions_from_actions(actions: object) -> float:
    if not isinstance(actions, list):
        return 0.0
    total = 0.0
    for action in actions:
        if not isinstance(action, Mapping):
            continue
        if action.get("action_type") in _LEAD_ACTION_TYPES:
            total += _to_float(action.get("value"))
    return total


def _merge_observed(acc: dict[str, str], row: Mapping[str, Any]) -> None:
    for key, value in row.items():
        acc.setdefault(str(key), _json_type(value))


def _json_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, list | tuple):
        return "array"
    return "unknown"


def _str_or_none(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _to_int(value: object) -> int:
    if value is None:
        return 0
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def _to_float(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None
