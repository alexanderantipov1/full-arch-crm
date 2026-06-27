"""Unit tests for ``GoogleAnalyticsMetricIngestService`` (mocked I/O)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.ingest.ga4_metric_service import GoogleAnalyticsMetricIngestService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _row(day: str = "20260614") -> dict[str, Any]:
    return {
        "date": day,
        "sessions": "123",
        "totalUsers": "100",
        "newUsers": "40",
        "screenPageViews": "300",
        "conversions": "4",
    }


def _channel_row(day: str = "20260614", channel: str = "Paid Search") -> dict[str, Any]:
    return {
        "date": day,
        "sessionDefaultChannelGroup": channel,
        "sessions": "200",
        "totalUsers": "150",
        "newUsers": "90",
        "screenPageViews": "500",
        "conversions": "7",
    }


def _page_row(day: str = "20260614", page: str = "/implants") -> dict[str, Any]:
    return {
        "date": day,
        "landingPage": page,
        "sessions": "60",
        "totalUsers": "50",
        "newUsers": "20",
        "screenPageViews": "180",
        "conversions": "3",
    }


def _make_service(
    rows: list[dict[str, Any]],
    *,
    latest_payload: dict[str, Any] | None = None,
    channel_rows: list[dict[str, Any]] | None = None,
    page_rows: list[dict[str, Any]] | None = None,
) -> tuple[GoogleAnalyticsMetricIngestService, MagicMock, MagicMock]:
    session = MagicMock()
    nested = MagicMock()
    nested.__aenter__ = AsyncMock(return_value=None)
    nested.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested)

    client = MagicMock()
    client.property_id = "510182665"
    client.get_daily_metrics = AsyncMock(return_value=rows)
    client.get_daily_channel_metrics = AsyncMock(return_value=channel_rows or [])
    client.get_daily_landing_page_metrics = AsyncMock(return_value=page_rows or [])

    service = GoogleAnalyticsMetricIngestService(session=session, ga_client=client)
    service._ingest = MagicMock(spec=["capture", "latest_payload", "sync_object_schema"])
    service._ingest.capture = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4(), received_at=datetime.now(UTC))
    )
    service._ingest.latest_payload = AsyncMock(return_value=latest_payload)
    service._ingest.sync_object_schema = AsyncMock(return_value=None)

    marketing = MagicMock(
        spec=[
            "upsert_ga_metric_daily",
            "upsert_ga_channel_daily",
            "upsert_ga_page_daily",
        ]
    )
    marketing.upsert_ga_metric_daily = AsyncMock(return_value=None)
    marketing.upsert_ga_channel_daily = AsyncMock(return_value=None)
    marketing.upsert_ga_page_daily = AsyncMock(return_value=None)
    service._marketing = marketing
    return service, service._ingest, marketing


@pytest.mark.asyncio
async def test_happy_path_captures_and_projects() -> None:
    service, ingest, marketing = _make_service([_row()])

    result = await service.import_recent_metrics(_TENANT_ID, days=7)

    assert result.imported_count == 1
    assert result.unchanged_count == 0

    raw_in = ingest.capture.await_args.args[1]
    assert raw_in.source == "google_analytics"
    assert raw_in.event_type == "google_analytics.daily_metric.upsert"
    assert raw_in.external_id == "510182665:2026-06-14"
    assert raw_in.payload == _row()

    metric_in = marketing.upsert_ga_metric_daily.await_args.args[1]
    assert metric_in.property_id == "510182665"
    assert metric_in.sessions == 123
    assert metric_in.total_users == 100
    assert metric_in.new_users == 40
    assert metric_in.screen_page_views == 300
    assert metric_in.conversions == pytest.approx(4.0)

    assert ingest.sync_object_schema.await_count == 1


@pytest.mark.asyncio
async def test_identical_payload_is_unchanged() -> None:
    service, ingest, _ = _make_service([_row()], latest_payload=_row())
    result = await service.import_recent_metrics(_TENANT_ID, days=7)
    assert result.unchanged_count == 1
    assert result.imported_count == 0
    ingest.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_unparseable_date_is_skipped() -> None:
    service, ingest, _ = _make_service([{"sessions": "1"}])  # no date
    result = await service.import_recent_metrics(_TENANT_ID, days=7)
    assert result.skipped_count == 1
    assert result.imported_count == 0
    ingest.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_engagement_metrics_projected_when_present() -> None:
    row = {**_row(), "engagedSessions": "80", "engagementRate": "0.65",
           "averageSessionDuration": "72.5", "bounceRate": "0.35",
           "eventCount": "900"}
    service, _, marketing = _make_service([row])
    await service.import_recent_metrics(_TENANT_ID, days=7)
    metric_in = marketing.upsert_ga_metric_daily.await_args.args[1]
    assert metric_in.engaged_sessions == 80
    assert metric_in.engagement_rate == pytest.approx(0.65)
    assert metric_in.avg_session_duration == pytest.approx(72.5)
    assert metric_in.bounce_rate == pytest.approx(0.35)
    assert metric_in.event_count == 900


@pytest.mark.asyncio
async def test_engagement_metrics_none_when_absent() -> None:
    # The legacy _row() has no engagement keys → projection leaves them None.
    service, _, marketing = _make_service([_row()])
    await service.import_recent_metrics(_TENANT_ID, days=7)
    metric_in = marketing.upsert_ga_metric_daily.await_args.args[1]
    assert metric_in.engaged_sessions is None
    assert metric_in.engagement_rate is None
    assert metric_in.event_count is None


@pytest.mark.asyncio
async def test_channel_import_captures_and_projects() -> None:
    service, ingest, marketing = _make_service([], channel_rows=[_channel_row()])
    result = await service.import_recent_channels(_TENANT_ID, days=7)

    assert result.imported_count == 1
    raw_in = ingest.capture.await_args.args[1]
    assert raw_in.event_type == "google_analytics.channel_daily.upsert"
    assert raw_in.external_id == "510182665:2026-06-14:Paid Search"
    assert raw_in.payload == _channel_row()

    chan_in = marketing.upsert_ga_channel_daily.await_args.args[1]
    assert chan_in.channel == "Paid Search"
    assert chan_in.sessions == 200
    assert chan_in.conversions == pytest.approx(7.0)
    assert ingest.sync_object_schema.await_count == 1


@pytest.mark.asyncio
async def test_channel_row_without_channel_is_skipped() -> None:
    bad = {**_channel_row(), "sessionDefaultChannelGroup": ""}
    service, ingest, _ = _make_service([], channel_rows=[bad])
    result = await service.import_recent_channels(_TENANT_ID, days=7)
    assert result.skipped_count == 1
    assert result.imported_count == 0
    ingest.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_channel_identical_payload_unchanged() -> None:
    service, ingest, _ = _make_service(
        [], channel_rows=[_channel_row()], latest_payload=_channel_row()
    )
    result = await service.import_recent_channels(_TENANT_ID, days=7)
    assert result.unchanged_count == 1
    assert result.imported_count == 0
    ingest.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_page_import_captures_and_projects() -> None:
    service, ingest, marketing = _make_service([], page_rows=[_page_row()])
    result = await service.import_recent_pages(_TENANT_ID, days=7)

    assert result.imported_count == 1
    raw_in = ingest.capture.await_args.args[1]
    assert raw_in.event_type == "google_analytics.page_daily.upsert"
    # external_id is property:date:sha256(page_path) — index-safe for long URLs.
    import hashlib as _h
    expected_hash = _h.sha256(b"/implants").hexdigest()
    assert raw_in.external_id == f"510182665:2026-06-14:{expected_hash}"

    page_in = marketing.upsert_ga_page_daily.await_args.args[1]
    assert page_in.page_path == "/implants"
    assert page_in.sessions == 60


@pytest.mark.asyncio
async def test_page_row_without_path_is_skipped() -> None:
    bad = {**_page_row(), "landingPage": "   "}
    service, ingest, _ = _make_service([], page_rows=[bad])
    result = await service.import_recent_pages(_TENANT_ID, days=7)
    assert result.skipped_count == 1
    ingest.capture.assert_not_awaited()
