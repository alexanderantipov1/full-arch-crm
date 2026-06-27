"""Google Analytics 4 daily-metric ingest pipeline.

Same shape as the ad-spend connectors: capture each day's GA4 metrics verbatim
into ``ingest.raw_event`` (full fidelity) + schema registry, then project into
``marketing.ga_metric_daily`` via ``MarketingService``.

The GA4 client is consumed via a local Protocol so this module does not import
``packages.integrations``. Read-only end to end.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import ValidationError
from packages.core.logging import get_logger
from packages.core.types import TenantId
from packages.ingest.schemas import (
    MarketingMetricImportOut,
    ObservedFieldIn,
    RawEventIn,
)
from packages.ingest.service import IngestService
from packages.marketing.schemas import (
    GaChannelDailyUpsertIn,
    GaMetricDailyUpsertIn,
    GaPageDailyUpsertIn,
)
from packages.marketing.service import MarketingService

log = get_logger("ingest.ga4_metric")

_PROVIDER = "google_analytics"
_EVENT_TYPE = "google_analytics.daily_metric.upsert"
_OBJECT_NAME = "daily_metric"

# ENG-478 dimension reports. Each is captured under its own raw event_type /
# schema-registry object so the forensic copy stays self-describing per grain.
_CHANNEL_EVENT_TYPE = "google_analytics.channel_daily.upsert"
_CHANNEL_OBJECT_NAME = "channel_daily"
_PAGE_EVENT_TYPE = "google_analytics.page_daily.upsert"
_PAGE_OBJECT_NAME = "page_daily"

# GA4 dimension id whose value identifies the landing page in the page report.
_PAGE_DIMENSION = "landingPage"
# GA4 dimension id for the acquisition channel split.
_CHANNEL_DIMENSION = "sessionDefaultChannelGroup"


class GoogleAnalyticsClientProtocol(Protocol):
    """Minimum GA4 client surface needed by this ingest service."""

    @property
    def property_id(self) -> str: ...

    async def get_daily_metrics(
        self, *, start_date: date, end_date: date
    ) -> list[dict[str, Any]]: ...

    async def get_daily_channel_metrics(
        self, *, start_date: date, end_date: date
    ) -> list[dict[str, Any]]: ...

    async def get_daily_landing_page_metrics(
        self, *, start_date: date, end_date: date
    ) -> list[dict[str, Any]]: ...


class GoogleAnalyticsMetricIngestService:
    """Pull GA4 daily metrics, capture raw, project into marketing."""

    def __init__(
        self,
        session: AsyncSession,
        ga_client: GoogleAnalyticsClientProtocol,
    ) -> None:
        self._session = session
        self._ga = ga_client
        self._ingest = IngestService(session)
        self._marketing = MarketingService(session)

    async def import_recent_metrics(
        self, tenant_id: TenantId, *, days: int = 7
    ) -> MarketingMetricImportOut:
        if days < 1 or days > 365:
            raise ValidationError("days must be between 1 and 365", details={"days": days})

        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=days - 1)
        return await self.import_window(
            tenant_id, start_date=start_date, end_date=end_date
        )

    async def import_window(
        self, tenant_id: TenantId, *, start_date: date, end_date: date
    ) -> MarketingMetricImportOut:
        """Capture GA4 daily metrics for an explicit ``[start_date, end_date]``.

        Date-range core that ``import_recent_metrics`` delegates to; the
        marketing historical backfill (ENG-492) drives it directly with bounded
        chunks. Idempotent on captured-payload identity, so overlapping chunks
        and re-runs are safe.
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
        property_id = self._ga.property_id

        rows = await self._ga.get_daily_metrics(start_date=start_date, end_date=end_date)

        imported = 0
        unchanged = 0
        skipped = 0
        observed_fields: dict[str, str] = {}

        for row in rows:
            _merge_observed(observed_fields, row)
            metric_date = _parse_ga_date(row.get("date"))
            if metric_date is None:
                skipped += 1
                continue
            external_id = f"{property_id}:{metric_date.isoformat()}"

            latest = await self._ingest.latest_payload(
                tenant_id, event_type=_EVENT_TYPE, external_id=external_id
            )
            if latest == row:
                unchanged += 1
                continue

            if await self._capture_and_project_safe(
                tenant_id, row, metric_date, external_id, property_id
            ):
                imported += 1
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

        return MarketingMetricImportOut(
            imported_count=imported,
            unchanged_count=unchanged,
            skipped_count=skipped,
            days=days,
        )

    async def _capture_and_project_safe(
        self,
        tenant_id: TenantId,
        row: dict[str, Any],
        metric_date: date,
        external_id: str,
        property_id: str,
    ) -> bool:
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
                await self._marketing.upsert_ga_metric_daily(
                    tenant_id,
                    GaMetricDailyUpsertIn(
                        property_id=property_id,
                        metric_date=metric_date,
                        sessions=_to_int(row.get("sessions")),
                        total_users=_to_int(row.get("totalUsers")),
                        new_users=_to_int(row.get("newUsers")),
                        screen_page_views=_to_int(row.get("screenPageViews")),
                        conversions=_to_float(row.get("conversions")),
                        # Engagement (ENG-478) — optional; ``None`` when GA4 did
                        # not return the metric so the column stays NULL.
                        engaged_sessions=_to_opt_int(row.get("engagedSessions")),
                        engagement_rate=_to_opt_float(row.get("engagementRate")),
                        avg_session_duration=_to_opt_float(
                            row.get("averageSessionDuration")
                        ),
                        bounce_rate=_to_opt_float(row.get("bounceRate")),
                        event_count=_to_opt_int(row.get("eventCount")),
                        raw_event_id=raw_event.id,
                    ),
                )
            return True
        except Exception as exc:  # noqa: BLE001 - one bad row must not abort the pull
            log.warning(
                "google_analytics.metric.capture_failed",
                property_id=property_id,
                external_id=external_id,
                error=type(exc).__name__,
            )
            return False

    async def import_recent_channels(
        self, tenant_id: TenantId, *, days: int = 7
    ) -> MarketingMetricImportOut:
        """Pull recent GA4 channel-split rows (``date × channel``), ENG-478.

        Full-fidelity capture into ``ingest.raw_event`` (event_type
        ``google_analytics.channel_daily.upsert``) + projection into
        ``marketing.ga_channel_daily``. Same content-identity dedupe as the
        daily-metric pull. One bad row never aborts the pull.
        """
        if days < 1 or days > 365:
            raise ValidationError("days must be between 1 and 365", details={"days": days})
        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=days - 1)
        property_id = self._ga.property_id
        rows = await self._ga.get_daily_channel_metrics(
            start_date=start_date, end_date=end_date
        )

        imported = unchanged = skipped = 0
        observed_fields: dict[str, str] = {}
        for row in rows:
            _merge_observed(observed_fields, row)
            metric_date = _parse_ga_date(row.get("date"))
            channel = _clean_str(row.get(_CHANNEL_DIMENSION))
            if metric_date is None or not channel:
                skipped += 1
                continue
            external_id = f"{property_id}:{metric_date.isoformat()}:{channel}"
            latest = await self._ingest.latest_payload(
                tenant_id, event_type=_CHANNEL_EVENT_TYPE, external_id=external_id
            )
            if latest == row:
                unchanged += 1
                continue
            if await self._capture_and_project_channel(
                tenant_id, row, metric_date, channel, external_id, property_id
            ):
                imported += 1
            else:
                skipped += 1

        await self._sync_schema_if_any(
            tenant_id, _CHANNEL_OBJECT_NAME, observed_fields
        )
        return MarketingMetricImportOut(
            imported_count=imported,
            unchanged_count=unchanged,
            skipped_count=skipped,
            days=days,
        )

    async def import_recent_pages(
        self, tenant_id: TenantId, *, days: int = 7
    ) -> MarketingMetricImportOut:
        """Pull recent GA4 page rows (``date × landingPage``), ENG-478.

        Full-fidelity capture into ``ingest.raw_event`` (event_type
        ``google_analytics.page_daily.upsert``) + projection into
        ``marketing.ga_page_daily``. One bad row never aborts the pull.
        """
        if days < 1 or days > 365:
            raise ValidationError("days must be between 1 and 365", details={"days": days})
        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=days - 1)
        property_id = self._ga.property_id
        rows = await self._ga.get_daily_landing_page_metrics(
            start_date=start_date, end_date=end_date
        )

        imported = unchanged = skipped = 0
        observed_fields: dict[str, str] = {}
        for row in rows:
            _merge_observed(observed_fields, row)
            metric_date = _parse_ga_date(row.get("date"))
            page_path = _clean_str(row.get(_PAGE_DIMENSION))
            if metric_date is None or not page_path:
                skipped += 1
                continue
            # Hash the page into the external_id so it stays index-safe even for
            # very long URLs (mirrors the page_hash natural key).
            page_hash = hashlib.sha256(page_path.encode("utf-8")).hexdigest()
            external_id = f"{property_id}:{metric_date.isoformat()}:{page_hash}"
            latest = await self._ingest.latest_payload(
                tenant_id, event_type=_PAGE_EVENT_TYPE, external_id=external_id
            )
            if latest == row:
                unchanged += 1
                continue
            if await self._capture_and_project_page(
                tenant_id, row, metric_date, page_path, external_id, property_id
            ):
                imported += 1
            else:
                skipped += 1

        await self._sync_schema_if_any(tenant_id, _PAGE_OBJECT_NAME, observed_fields)
        return MarketingMetricImportOut(
            imported_count=imported,
            unchanged_count=unchanged,
            skipped_count=skipped,
            days=days,
        )

    async def _capture_and_project_channel(
        self,
        tenant_id: TenantId,
        row: dict[str, Any],
        metric_date: date,
        channel: str,
        external_id: str,
        property_id: str,
    ) -> bool:
        try:
            async with self._session.begin_nested():
                raw_event = await self._ingest.capture(
                    tenant_id,
                    RawEventIn(
                        source=_PROVIDER,
                        event_type=_CHANNEL_EVENT_TYPE,
                        external_id=external_id,
                        received_at=datetime.now(UTC),
                        payload=row,
                    ),
                )
                await self._marketing.upsert_ga_channel_daily(
                    tenant_id,
                    GaChannelDailyUpsertIn(
                        property_id=property_id,
                        metric_date=metric_date,
                        channel=channel,
                        sessions=_to_int(row.get("sessions")),
                        total_users=_to_int(row.get("totalUsers")),
                        new_users=_to_int(row.get("newUsers")),
                        screen_page_views=_to_int(row.get("screenPageViews")),
                        conversions=_to_float(row.get("conversions")),
                        raw_event_id=raw_event.id,
                    ),
                )
            return True
        except Exception as exc:  # noqa: BLE001 - one bad row must not abort the pull
            log.warning(
                "google_analytics.channel.capture_failed",
                property_id=property_id,
                external_id=external_id,
                error=type(exc).__name__,
            )
            return False

    async def _capture_and_project_page(
        self,
        tenant_id: TenantId,
        row: dict[str, Any],
        metric_date: date,
        page_path: str,
        external_id: str,
        property_id: str,
    ) -> bool:
        try:
            async with self._session.begin_nested():
                raw_event = await self._ingest.capture(
                    tenant_id,
                    RawEventIn(
                        source=_PROVIDER,
                        event_type=_PAGE_EVENT_TYPE,
                        external_id=external_id,
                        received_at=datetime.now(UTC),
                        payload=row,
                    ),
                )
                await self._marketing.upsert_ga_page_daily(
                    tenant_id,
                    GaPageDailyUpsertIn(
                        property_id=property_id,
                        metric_date=metric_date,
                        page_path=page_path,
                        sessions=_to_int(row.get("sessions")),
                        total_users=_to_int(row.get("totalUsers")),
                        new_users=_to_int(row.get("newUsers")),
                        screen_page_views=_to_int(row.get("screenPageViews")),
                        conversions=_to_float(row.get("conversions")),
                        raw_event_id=raw_event.id,
                    ),
                )
            return True
        except Exception as exc:  # noqa: BLE001 - one bad row must not abort the pull
            log.warning(
                "google_analytics.page.capture_failed",
                property_id=property_id,
                external_id=external_id,
                error=type(exc).__name__,
            )
            return False

    async def _sync_schema_if_any(
        self, tenant_id: TenantId, object_name: str, observed_fields: dict[str, str]
    ) -> None:
        """Register observed fields in the schema registry (no-op when empty)."""
        if not observed_fields:
            return
        await self._ingest.sync_object_schema(
            tenant_id,
            provider=_PROVIDER,
            object_name=object_name,
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


def _to_opt_int(value: object) -> int | None:
    """Coerce a GA4 string metric to int, or ``None`` when absent/blank.

    Distinct from :func:`_to_int`: a missing engagement metric stays ``None``
    so the projection leaves the NULLABLE column NULL rather than writing 0.
    """
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _to_opt_float(value: object) -> float | None:
    """Coerce a GA4 string metric to float, or ``None`` when absent/blank."""
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _clean_str(value: object) -> str | None:
    """Return a stripped non-empty string, else ``None``."""
    if not isinstance(value, str):
        return None
    s = value.strip()
    return s or None


def _parse_ga_date(value: object) -> date | None:
    """GA4 ``date`` dimension is ``YYYYMMDD`` (no separators)."""
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    s = value.strip()
    if len(s) != 8 or not s.isdigit():
        return None
    try:
        return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None
