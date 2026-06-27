"""Unit tests for ``GoogleSearchConsoleQueryIngestService`` (mocked I/O)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.ingest.gsc_query_service import GoogleSearchConsoleQueryIngestService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_SITE = "sc-domain:fusiondentalimplants.com"


def _row(day: str = "2026-06-14", query: str = "dental implants") -> dict[str, Any]:
    return {
        "date": day,
        "query": query,
        "clicks": 5,
        "impressions": 120,
        "ctr": 0.0416,
        "position": 3.2,
    }


def _make_service(
    rows: list[dict[str, Any]], *, latest_payload: dict[str, Any] | None = None
) -> tuple[GoogleSearchConsoleQueryIngestService, MagicMock, MagicMock]:
    session = MagicMock()
    nested = MagicMock()
    nested.__aenter__ = AsyncMock(return_value=None)
    nested.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested)

    client = MagicMock()
    client.resolve_site_url = AsyncMock(return_value=_SITE)
    client.get_query_metrics = AsyncMock(return_value=rows)

    service = GoogleSearchConsoleQueryIngestService(session=session, gsc_client=client)
    service._ingest = MagicMock(spec=["capture", "latest_payload", "sync_object_schema"])
    service._ingest.capture = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4(), received_at=datetime.now(UTC))
    )
    service._ingest.latest_payload = AsyncMock(return_value=latest_payload)
    service._ingest.sync_object_schema = AsyncMock(return_value=None)

    marketing = MagicMock(spec=["upsert_gsc_query_daily"])
    marketing.upsert_gsc_query_daily = AsyncMock(return_value=None)
    service._marketing = marketing
    return service, service._ingest, marketing


@pytest.mark.asyncio
async def test_happy_path_captures_and_projects() -> None:
    service, ingest, marketing = _make_service([_row()])

    result = await service.import_recent_queries(_TENANT_ID, days=7)

    assert result.imported_count == 1
    raw_in = ingest.capture.await_args.args[1]
    assert raw_in.source == "google_search_console"
    assert raw_in.event_type == "google_search_console.query.upsert"
    assert raw_in.payload == _row()
    assert _SITE in raw_in.external_id

    q_in = marketing.upsert_gsc_query_daily.await_args.args[1]
    assert q_in.site_url == _SITE
    assert q_in.query == "dental implants"
    assert q_in.clicks == 5
    assert q_in.impressions == 120
    assert q_in.ctr == pytest.approx(0.0416)
    assert q_in.position == pytest.approx(3.2)


@pytest.mark.asyncio
async def test_identical_payload_is_unchanged() -> None:
    service, ingest, _ = _make_service([_row()], latest_payload=_row())
    result = await service.import_recent_queries(_TENANT_ID, days=7)
    assert result.unchanged_count == 1
    assert result.imported_count == 0
    ingest.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_row_without_query_or_date_is_skipped() -> None:
    service, ingest, _ = _make_service([{"clicks": 1}, {"date": "2026-06-14"}])
    result = await service.import_recent_queries(_TENANT_ID, days=7)
    assert result.skipped_count == 2
    assert result.imported_count == 0
    ingest.capture.assert_not_awaited()


# --- ENG-492: explicit date-range window (drives the historical backfill) ---


@pytest.mark.asyncio
async def test_import_window_passes_explicit_dates() -> None:
    from datetime import date

    service, _, _ = _make_service([_row()])
    start, end = date(2025, 6, 1), date(2025, 6, 30)

    await service.import_window(_TENANT_ID, start_date=start, end_date=end)

    service._gsc.get_query_metrics.assert_awaited_once_with(
        _SITE, start_date=start, end_date=end
    )


@pytest.mark.asyncio
async def test_import_window_is_idempotent_on_identical_payload() -> None:
    from datetime import date

    # A re-run over the same window whose stored payload is byte-identical
    # captures nothing — the dedupe makes overlapping chunks/re-runs safe.
    service, ingest, _ = _make_service([_row()], latest_payload=_row())
    result = await service.import_window(
        _TENANT_ID, start_date=date(2025, 6, 1), end_date=date(2025, 6, 30)
    )
    assert result.unchanged_count == 1
    assert result.imported_count == 0
    ingest.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_window_rejects_inverted_range() -> None:
    from datetime import date

    from packages.core.exceptions import ValidationError

    service, _, _ = _make_service([_row()])
    with pytest.raises(ValidationError):
        await service.import_window(
            _TENANT_ID, start_date=date(2025, 6, 30), end_date=date(2025, 6, 1)
        )
