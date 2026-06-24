"""Google Ads campaign + daily-spend ingest pipeline.

Captures Google Ads GAQL rows (campaign + daily metrics) into the canonical
ingest path, then projects them into the curated ``marketing`` tables:

1. ``IngestService.capture`` writes the verbatim GAQL row to
   ``ingest.raw_event`` (full fidelity).
2. ``IngestService.sync_object_schema`` reconciles the observed field set
   against the schema registry (drift detection).
3. ``MarketingService.upsert_campaign`` / ``upsert_metric_daily`` project the
   row into ``marketing.ad_campaign`` / ``marketing.ad_metric_daily``.

The Google Ads HTTP client is consumed via a local Protocol so this module
does not import ``packages.integrations``. Read-only end to end.
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
from packages.marketing.schemas import AdCampaignUpsertIn, AdMetricDailyUpsertIn
from packages.marketing.service import MarketingService

log = get_logger("ingest.google_ads_campaign")

_PROVIDER = "google_ads"
_EVENT_TYPE = "google_ads.campaign_metric.upsert"
_OBJECT_NAME = "campaign_metric"
_MICROS_PER_UNIT = 1_000_000


class GoogleAdsCampaignClientProtocol(Protocol):
    """Minimum Google Ads client surface needed by this ingest service."""

    @property
    def customer_ids(self) -> list[str]: ...

    async def search_campaign_metrics(
        self,
        customer_id: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]: ...


class GoogleAdsCampaignIngestService:
    """Pull Google Ads campaign spend, capture raw, project into marketing."""

    def __init__(
        self,
        session: AsyncSession,
        google_ads_client: GoogleAdsCampaignClientProtocol,
    ) -> None:
        self._session = session
        self._google_ads = google_ads_client
        self._ingest = IngestService(session)
        self._marketing = MarketingService(session)

    async def import_recent_spend(
        self,
        tenant_id: TenantId,
        *,
        days: int = 7,
    ) -> MarketingSpendImportOut:
        """Capture the last ``days`` of campaign spend across all ad accounts.

        Ad metrics have no provider modified-stamp and the recent window
        re-settles for ~1-3 days, so we dedupe on captured-payload identity:
        a re-pulled row whose stored raw payload is byte-identical is counted
        ``unchanged`` and skipped before any write. Changed/new rows are
        captured and upserted (the upsert is itself idempotent).
        """
        if days < 1 or days > 365:
            raise ValidationError("days must be between 1 and 365", details={"days": days})

        end_date = datetime.now(UTC).date()
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
        """Capture campaign spend for an explicit ``[start_date, end_date]`` window.

        This is the date-range core that ``import_recent_spend`` delegates to;
        the marketing historical backfill (ENG-492) drives it directly with
        bounded chunks so a ~12-month load never asks the provider for one
        enormous range. Idempotent: a re-pulled row whose stored raw payload is
        byte-identical is counted ``unchanged`` and skipped before any write, so
        overlapping chunks and re-runs are safe.
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
        campaigns_seen: set[str] = set()
        observed_fields: dict[str, str] = {}
        account_count = 0

        for customer_id in self._google_ads.customer_ids:
            account_count += 1
            try:
                rows = await self._google_ads.search_campaign_metrics(
                    customer_id, start_date=start_date, end_date=end_date
                )
            except Exception as exc:  # noqa: BLE001 - one inaccessible account must not abort the rest
                # e.g. the OAuth user lacks access to this child account. Log +
                # skip so the other accounts' spend is still captured (and not
                # rolled back at the job boundary).
                log.warning(
                    "google_ads.search.fetch_failed",
                    customer_id=customer_id,
                    error=type(exc).__name__,
                )
                continue
            for row in rows:
                _merge_observed(observed_fields, row)
                parsed = _parse_row(row)
                if parsed is None:
                    skipped += 1
                    continue
                external_id = f"{parsed['campaign_id']}:{parsed['metric_date'].isoformat()}"

                latest = await self._ingest.latest_payload(
                    tenant_id, event_type=_EVENT_TYPE, external_id=external_id
                )
                if latest == row:
                    unchanged += 1
                    continue

                if await self._capture_and_project_safe(
                    tenant_id, row, parsed, external_id, customer_id
                ):
                    imported += 1
                    campaigns_seen.add(parsed["campaign_id"])
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
            campaigns_upserted=len(campaigns_seen),
            account_count=account_count,
            days=days,
        )

    async def _capture_and_project_safe(
        self,
        tenant_id: TenantId,
        row: dict[str, Any],
        parsed: dict[str, Any],
        external_id: str,
        customer_id: str,
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
                await self._marketing.upsert_campaign(
                    tenant_id,
                    AdCampaignUpsertIn(
                        provider=_PROVIDER,
                        external_id=parsed["campaign_id"],
                        name=parsed["campaign_name"],
                        status=parsed["status"],
                        objective=parsed["objective"],
                        account_id=customer_id,
                        raw_event_id=raw_event.id,
                    ),
                )
                await self._marketing.upsert_metric_daily(
                    tenant_id,
                    AdMetricDailyUpsertIn(
                        provider=_PROVIDER,
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
                "google_ads.spend.capture_failed",
                customer_id=customer_id,
                external_id=external_id,
                error=type(exc).__name__,
            )
            return False


def _parse_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    """Extract typed fields from a GAQL result row, or None if unusable.

    REST returns int64 fields (id, costMicros, impressions, clicks) as
    strings; ``conversions`` as a float. ``segments.date`` is ``YYYY-MM-DD``.
    """
    campaign = row.get("campaign")
    segments = row.get("segments")
    if not isinstance(campaign, Mapping) or not isinstance(segments, Mapping):
        return None
    campaign_id = campaign.get("id")
    metric_date = _parse_date(segments.get("date"))
    if campaign_id is None or metric_date is None:
        return None

    metrics_raw = row.get("metrics")
    metrics: Mapping[str, Any] = metrics_raw if isinstance(metrics_raw, Mapping) else {}
    return {
        "campaign_id": str(campaign_id),
        "campaign_name": _str_or_none(campaign.get("name")),
        "status": _str_or_none(campaign.get("status")),
        "objective": _str_or_none(campaign.get("advertisingChannelType")),
        "metric_date": metric_date,
        "spend": _to_int(metrics.get("costMicros")) / _MICROS_PER_UNIT,
        "impressions": _to_int(metrics.get("impressions")),
        "clicks": _to_int(metrics.get("clicks")),
        "conversions": _to_float(metrics.get("conversions")),
    }


def _merge_observed(acc: dict[str, str], row: Mapping[str, Any]) -> None:
    """Flatten one level of the GAQL row into dotted field → JSON-type names."""
    for top_key, value in row.items():
        if isinstance(value, Mapping):
            for sub_key, sub_value in value.items():
                acc.setdefault(f"{top_key}.{sub_key}", _json_type(sub_value))
        else:
            acc.setdefault(str(top_key), _json_type(value))


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
        return int(str(value))
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
