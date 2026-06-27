"""Google Search Console daily-query ingest pipeline.

Same shape as the GA4 connector: capture each (day, query) row verbatim into
``ingest.raw_event`` (full fidelity) + schema registry, then project into
``marketing.gsc_query_daily`` via ``MarketingService``.

The GSC client is consumed via a local Protocol so this module does not import
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
from packages.marketing.schemas import GscQueryDailyUpsertIn
from packages.marketing.service import MarketingService

log = get_logger("ingest.gsc_query")

_PROVIDER = "google_search_console"
_EVENT_TYPE = "google_search_console.query.upsert"
_OBJECT_NAME = "search_query"


class GoogleSearchConsoleClientProtocol(Protocol):
    """Minimum GSC client surface needed by this ingest service."""

    async def resolve_site_url(self) -> str: ...

    async def get_query_metrics(
        self, site_url: str, *, start_date: date, end_date: date
    ) -> list[dict[str, Any]]: ...


class GoogleSearchConsoleQueryIngestService:
    """Pull GSC daily query rows, capture raw, project into marketing."""

    def __init__(
        self,
        session: AsyncSession,
        gsc_client: GoogleSearchConsoleClientProtocol,
    ) -> None:
        self._session = session
        self._gsc = gsc_client
        self._ingest = IngestService(session)
        self._marketing = MarketingService(session)

    async def import_recent_queries(
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
        """Capture GSC daily query rows for an explicit ``[start_date, end_date]``.

        Date-range core that ``import_recent_queries`` delegates to; the
        marketing historical backfill (ENG-492) drives it directly with bounded
        chunks. GSC caps each query response at a fixed row limit, so the
        backfill keeps each chunk narrow (default 30 days) to stay under it.
        Idempotent on captured-payload identity, so overlapping chunks and
        re-runs are safe.
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

        site_url = await self._gsc.resolve_site_url()

        rows = await self._gsc.get_query_metrics(
            site_url, start_date=start_date, end_date=end_date
        )

        imported = 0
        unchanged = 0
        skipped = 0
        observed_fields: dict[str, str] = {}

        for row in rows:
            _merge_observed(observed_fields, row)
            metric_date = _parse_date(row.get("date"))
            query = row.get("query")
            if metric_date is None or not isinstance(query, str) or not query:
                skipped += 1
                continue
            query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
            external_id = f"{site_url}|{metric_date.isoformat()}|{query_hash}"

            latest = await self._ingest.latest_payload(
                tenant_id, event_type=_EVENT_TYPE, external_id=external_id
            )
            if latest == row:
                unchanged += 1
                continue

            if await self._capture_and_project_safe(
                tenant_id, row, metric_date, query, external_id, site_url
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
        query: str,
        external_id: str,
        site_url: str,
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
                await self._marketing.upsert_gsc_query_daily(
                    tenant_id,
                    GscQueryDailyUpsertIn(
                        site_url=site_url,
                        metric_date=metric_date,
                        query=query,
                        clicks=_to_int(row.get("clicks")),
                        impressions=_to_int(row.get("impressions")),
                        ctr=_to_float(row.get("ctr")),
                        position=_to_float(row.get("position")),
                        raw_event_id=raw_event.id,
                    ),
                )
            return True
        except Exception as exc:  # noqa: BLE001 - one bad row must not abort the pull
            log.warning(
                "google_search_console.query.capture_failed",
                site_url=site_url,
                error=type(exc).__name__,
            )
            return False


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


def _parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None
