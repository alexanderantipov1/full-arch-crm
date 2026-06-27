"""Unit tests for ``MetaAdsAdIngestService`` (mocked I/O) — ENG-512."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.ingest.meta_ads_ad_service import MetaAdsAdIngestService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _insight(
    ad_id: str = "23856", day: str = "2026-06-18"
) -> dict[str, Any]:
    return {
        "ad_id": ad_id,
        "ad_name": "Implant Promo - Video A",
        "adset_id": "5001",
        "adset_name": "Roseville 35-55",
        "campaign_id": "111",
        "campaign_name": "Implants - Roseville",
        "spend": "80.50",
        "impressions": "900",
        "clicks": "22",
        "actions": [
            {"action_type": "lead", "value": "2"},
            {"action_type": "link_click", "value": "22"},
        ],
        "date_start": day,
        "date_stop": day,
    }


def _make_service(
    rows: list[dict[str, Any]],
    *,
    latest_payload: dict[str, Any] | None = None,
) -> tuple[MetaAdsAdIngestService, MagicMock, MagicMock]:
    session = MagicMock()
    nested = MagicMock()
    nested.__aenter__ = AsyncMock(return_value=None)
    nested.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested)

    client = MagicMock()
    client.ad_account_ids = ["938570599860690"]
    client.get_ad_insights = AsyncMock(return_value=rows)

    service = MetaAdsAdIngestService(session=session, meta_ads_client=client)
    service._ingest = MagicMock(
        spec=["capture", "latest_payload", "sync_object_schema"]
    )
    service._ingest.capture = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4(), received_at=datetime.now(UTC))
    )
    service._ingest.latest_payload = AsyncMock(return_value=latest_payload)
    service._ingest.sync_object_schema = AsyncMock(return_value=None)

    marketing = MagicMock(
        spec=["upsert_ad_set", "upsert_ad", "upsert_ad_metric_daily"]
    )
    marketing.upsert_ad_set = AsyncMock(return_value=None)
    marketing.upsert_ad = AsyncMock(return_value=None)
    marketing.upsert_ad_metric_daily = AsyncMock(return_value=None)
    service._marketing = marketing

    return service, service._ingest, marketing


@pytest.mark.asyncio
async def test_happy_path_captures_and_projects_ad_level() -> None:
    service, ingest, marketing = _make_service([_insight()])

    result = await service.import_recent_spend(_TENANT_ID, days=3)

    assert result.imported_count == 1
    assert result.campaigns_upserted == 1  # ads_seen reuses this field
    assert result.account_count == 1

    raw_in = ingest.capture.await_args.args[1]
    assert raw_in.source == "meta_ads"
    assert raw_in.event_type == "meta_ads.ad_metric.upsert"
    assert raw_in.external_id == "23856:2026-06-18"
    assert raw_in.payload == _insight()

    ad_set_in = marketing.upsert_ad_set.await_args.args[1]
    assert ad_set_in.external_id == "5001"
    assert ad_set_in.campaign_external_id == "111"
    assert ad_set_in.account_id == "938570599860690"

    ad_in = marketing.upsert_ad.await_args.args[1]
    assert ad_in.external_id == "23856"
    assert ad_in.name == "Implant Promo - Video A"
    assert ad_in.adset_external_id == "5001"
    assert ad_in.campaign_external_id == "111"

    metric_in = marketing.upsert_ad_metric_daily.await_args.args[1]
    assert metric_in.ad_external_id == "23856"
    assert metric_in.spend == pytest.approx(80.50)
    assert metric_in.impressions == 900
    assert metric_in.clicks == 22
    assert metric_in.conversions == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_identical_payload_is_unchanged() -> None:
    service, ingest, _ = _make_service([_insight()], latest_payload=_insight())
    result = await service.import_recent_spend(_TENANT_ID, days=3)
    assert result.unchanged_count == 1
    assert result.imported_count == 0
    ingest.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_unparseable_row_is_skipped() -> None:
    service, ingest, _ = _make_service([{"spend": "1.00"}])  # no ad_id/date
    result = await service.import_recent_spend(_TENANT_ID, days=3)
    assert result.skipped_count == 1
    assert result.imported_count == 0
    ingest.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_adset_skips_ad_set_upsert_but_keeps_ad() -> None:
    row = _insight()
    del row["adset_id"]
    service, _, marketing = _make_service([row])
    result = await service.import_recent_spend(_TENANT_ID, days=3)
    assert result.imported_count == 1
    marketing.upsert_ad_set.assert_not_awaited()
    ad_in = marketing.upsert_ad.await_args.args[1]
    assert ad_in.adset_external_id is None


@pytest.mark.asyncio
async def test_recent_window_settles_on_completed_days_d_minus_1() -> None:
    # The rolling pull must END on D-1 (yesterday) — never today, whose spend is
    # still accruing — and look back ``days`` completed days from there.
    service, _, _ = _make_service([_insight()])
    await service.import_recent_spend(_TENANT_ID, days=3)

    today = datetime.now(UTC).date()
    kwargs = service._meta.get_ad_insights.await_args.kwargs
    assert kwargs["end_date"] == today - timedelta(days=1)
    # days=3 → [D-3, D-1], a 3-completed-day window.
    assert kwargs["start_date"] == today - timedelta(days=3)
    assert (kwargs["end_date"] - kwargs["start_date"]).days + 1 == 3


@pytest.mark.asyncio
async def test_one_inaccessible_account_does_not_abort_others() -> None:
    service, ingest, _ = _make_service([_insight()])
    service._meta.ad_account_ids = ["111111", "222222"]
    service._meta.get_ad_insights = AsyncMock(
        side_effect=[RuntimeError("403 forbidden"), [_insight("999")]]
    )
    result = await service.import_recent_spend(_TENANT_ID, days=3)
    assert result.account_count == 2
    assert result.imported_count == 1
    assert ingest.capture.await_count == 1
