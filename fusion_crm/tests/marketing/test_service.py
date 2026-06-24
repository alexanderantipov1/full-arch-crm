"""Unit tests for ``MarketingService`` (mocked repository)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId
from packages.marketing.schemas import (
    AdCampaignUpsertIn,
    AdMetricDailyUpsertIn,
    GaMetricDailyUpsertIn,
    GscQueryDailyUpsertIn,
)
from packages.marketing.service import MarketingService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _service() -> tuple[MarketingService, MagicMock]:
    session = MagicMock()
    session.flush = AsyncMock(return_value=None)
    service = MarketingService(session)
    repo = MagicMock(
        spec=[
            "get_campaign",
            "add_campaign",
            "get_metric",
            "add_metric",
            "aggregate_spend",
            "get_ga_metric",
            "add_ga_metric",
            "get_gsc_query",
            "add_gsc_query",
        ]
    )
    repo.get_campaign = AsyncMock(return_value=None)
    repo.add_campaign = AsyncMock(side_effect=lambda c: c)
    repo.get_metric = AsyncMock(return_value=None)
    repo.add_metric = AsyncMock(side_effect=lambda m: m)
    repo.aggregate_spend = AsyncMock(return_value=[])
    repo.get_ga_metric = AsyncMock(return_value=None)
    repo.add_ga_metric = AsyncMock(side_effect=lambda m: m)
    repo.get_gsc_query = AsyncMock(return_value=None)
    repo.add_gsc_query = AsyncMock(side_effect=lambda m: m)
    service._repo = repo
    return service, repo


@pytest.mark.asyncio
async def test_upsert_gsc_query_creates_and_hashes() -> None:
    from datetime import date as _date

    service, repo = _service()
    result = await service.upsert_gsc_query_daily(
        _TENANT_ID,
        GscQueryDailyUpsertIn(
            site_url="sc-domain:example.com", metric_date=_date(2026, 6, 14),
            query="dental implants", clicks=5, impressions=120, ctr=0.04, position=3.2,
        ),
    )
    assert result.was_created and result.was_changed
    row = repo.add_gsc_query.await_args.args[0]
    # query_hash is the sha256 of the raw query (keys the unique constraint)
    import hashlib as _h
    assert row.query_hash == _h.sha256(b"dental implants").hexdigest()
    assert row.query == "dental implants"


@pytest.mark.asyncio
async def test_upsert_ga_metric_creates_then_noops() -> None:
    from datetime import date as _date
    from decimal import Decimal

    service, repo = _service()
    payload = GaMetricDailyUpsertIn(
        property_id="510182665", metric_date=_date(2026, 6, 14),
        sessions=123, total_users=100, new_users=40, screen_page_views=300,
        conversions=4.0,
    )
    created = await service.upsert_ga_metric_daily(_TENANT_ID, payload)
    assert created.was_created and created.was_changed
    repo.add_ga_metric.assert_awaited_once()

    # Existing identical row → no change (Decimal conversions compared safely).
    repo.get_ga_metric = AsyncMock(
        return_value=SimpleNamespace(
            sessions=123, total_users=100, new_users=40, screen_page_views=300,
            conversions=Decimal("4.00"), raw_event_id=None,
        )
    )
    again = await service.upsert_ga_metric_daily(_TENANT_ID, payload)
    assert not again.was_created and not again.was_changed


@pytest.mark.asyncio
async def test_upsert_campaign_creates_when_absent() -> None:
    service, repo = _service()
    result = await service.upsert_campaign(
        _TENANT_ID,
        AdCampaignUpsertIn(
            provider="google_ads", external_id="111", name="X", status="ENABLED"
        ),
    )
    assert result.was_created and result.was_changed
    repo.add_campaign.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_campaign_detects_change() -> None:
    service, repo = _service()
    existing = SimpleNamespace(
        name="Old", status="PAUSED", objective=None, account_id=None,
        raw_event_id=None, extra={},
    )
    repo.get_campaign = AsyncMock(return_value=existing)
    result = await service.upsert_campaign(
        _TENANT_ID,
        AdCampaignUpsertIn(provider="google_ads", external_id="111", name="New", status="ENABLED"),
    )
    assert not result.was_created and result.was_changed
    assert existing.name == "New" and existing.status == "ENABLED"


@pytest.mark.asyncio
async def test_upsert_campaign_no_change_is_noop() -> None:
    service, repo = _service()
    existing = SimpleNamespace(
        name="Same", status="ENABLED", objective="SEARCH", account_id="acct",
        raw_event_id=None, extra={},
    )
    repo.get_campaign = AsyncMock(return_value=existing)
    result = await service.upsert_campaign(
        _TENANT_ID,
        AdCampaignUpsertIn(
            provider="google_ads", external_id="111", name="Same",
            status="ENABLED", objective="SEARCH", account_id="acct",
        ),
    )
    assert not result.was_created and not result.was_changed


@pytest.mark.asyncio
async def test_upsert_campaign_rejects_unknown_provider() -> None:
    service, _ = _service()
    with pytest.raises(ValidationError):
        await service.upsert_campaign(
            _TENANT_ID, AdCampaignUpsertIn(provider="bing_ads", external_id="1")
        )


@pytest.mark.asyncio
async def test_upsert_metric_change_detection_handles_decimal() -> None:
    service, repo = _service()
    # DB Numeric comes back as Decimal — equal value must NOT flag a change.
    existing = SimpleNamespace(
        spend=Decimal("12.34"), impressions=100, clicks=5,
        conversions=Decimal("2.00"), currency="USD", raw_event_id=None,
    )
    repo.get_metric = AsyncMock(return_value=existing)
    result = await service.upsert_metric_daily(
        _TENANT_ID,
        AdMetricDailyUpsertIn(
            provider="google_ads", campaign_external_id="111",
            metric_date=date(2026, 6, 14), spend=12.34, impressions=100,
            clicks=5, conversions=2.0, currency="USD",
        ),
    )
    assert not result.was_changed


@pytest.mark.asyncio
async def test_ad_spend_totals_sums_rows() -> None:
    service, repo = _service()
    repo.aggregate_spend = AsyncMock(
        return_value=[
            {
                "provider": "google_ads", "campaign_external_id": "1",
                "campaign_name": "A", "spend": 100.0, "impressions": 10,
                "clicks": 2, "conversions": 1.0,
            },
            {
                "provider": "google_ads", "campaign_external_id": "2",
                "campaign_name": "B", "spend": 50.0, "impressions": 5,
                "clicks": 1, "conversions": 0.0,
            },
        ]
    )
    totals = await service.ad_spend_totals(
        _TENANT_ID, start_date=date(2026, 6, 1), end_date=date(2026, 6, 30)
    )
    assert totals.spend == pytest.approx(150.0)
    assert totals.impressions == 15
    assert len(totals.rows) == 2


@pytest.mark.asyncio
async def test_ad_spend_totals_rejects_inverted_range() -> None:
    service, _ = _service()
    with pytest.raises(ValidationError):
        await service.ad_spend_totals(
            _TENANT_ID, start_date=date(2026, 6, 30), end_date=date(2026, 6, 1)
        )
