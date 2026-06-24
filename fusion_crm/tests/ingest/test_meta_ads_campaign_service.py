"""Unit tests for ``MetaAdsCampaignIngestService`` (mocked I/O)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.ingest.meta_ads_campaign_service import MetaAdsCampaignIngestService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _insight(cid: str = "111", day: str = "2026-06-14") -> dict[str, Any]:
    return {
        "campaign_id": cid,
        "campaign_name": "Implants - Roseville",
        "spend": "123.45",
        "impressions": "1000",
        "clicks": "30",
        "actions": [
            {"action_type": "lead", "value": "3"},
            {"action_type": "link_click", "value": "30"},
        ],
        "date_start": day,
        "date_stop": day,
    }


def _make_service(
    rows: list[dict[str, Any]],
    *,
    campaigns: list[dict[str, Any]] | None = None,
    latest_payload: dict[str, Any] | None = None,
) -> tuple[MetaAdsCampaignIngestService, MagicMock, MagicMock]:
    session = MagicMock()
    nested = MagicMock()
    nested.__aenter__ = AsyncMock(return_value=None)
    nested.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested)

    client = MagicMock()
    client.ad_account_ids = ["938570599860690"]
    client.list_campaigns = AsyncMock(
        return_value=campaigns
        if campaigns is not None
        else [
            {"id": "111", "name": "Implants - Roseville", "status": "ACTIVE",
             "objective": "OUTCOME_LEADS"}
        ]
    )
    client.get_campaign_insights = AsyncMock(return_value=rows)

    service = MetaAdsCampaignIngestService(session=session, meta_ads_client=client)
    service._ingest = MagicMock(spec=["capture", "latest_payload", "sync_object_schema"])
    service._ingest.capture = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4(), received_at=datetime.now(UTC))
    )
    service._ingest.latest_payload = AsyncMock(return_value=latest_payload)
    service._ingest.sync_object_schema = AsyncMock(return_value=None)

    marketing = MagicMock(spec=["upsert_campaign", "upsert_metric_daily"])
    marketing.upsert_campaign = AsyncMock(return_value=None)
    marketing.upsert_metric_daily = AsyncMock(return_value=None)
    service._marketing = marketing

    return service, service._ingest, marketing


@pytest.mark.asyncio
async def test_happy_path_captures_and_projects() -> None:
    service, ingest, marketing = _make_service([_insight()])

    result = await service.import_recent_spend(_TENANT_ID, days=7)

    assert result.imported_count == 1
    assert result.campaigns_upserted == 1
    assert result.account_count == 1

    raw_in = ingest.capture.await_args.args[1]
    assert raw_in.source == "meta_ads"
    assert raw_in.event_type == "meta_ads.campaign_metric.upsert"
    assert raw_in.external_id == "111:2026-06-14"
    assert raw_in.payload == _insight()

    # campaign metadata from the campaigns endpoint wins
    camp_in = marketing.upsert_campaign.await_args.args[1]
    assert camp_in.provider == "meta_ads"
    assert camp_in.status == "ACTIVE"
    assert camp_in.objective == "OUTCOME_LEADS"
    assert camp_in.account_id == "938570599860690"

    # spend string parsed; conversions summed from lead actions only
    metric_in = marketing.upsert_metric_daily.await_args.args[1]
    assert metric_in.spend == pytest.approx(123.45)
    assert metric_in.impressions == 1000
    assert metric_in.clicks == 30
    assert metric_in.conversions == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_identical_payload_is_unchanged() -> None:
    service, ingest, marketing = _make_service([_insight()], latest_payload=_insight())
    result = await service.import_recent_spend(_TENANT_ID, days=7)
    assert result.unchanged_count == 1
    assert result.imported_count == 0
    ingest.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_campaigns_fetch_failure_degrades_gracefully() -> None:
    service, _, marketing = _make_service([_insight()])
    service._meta.list_campaigns = AsyncMock(side_effect=RuntimeError("boom"))

    result = await service.import_recent_spend(_TENANT_ID, days=7)

    # still imports the metric using the insight's own campaign_name
    assert result.imported_count == 1
    camp_in = marketing.upsert_campaign.await_args.args[1]
    assert camp_in.name == "Implants - Roseville"
    assert camp_in.status is None  # no metadata available


@pytest.mark.asyncio
async def test_one_inaccessible_account_does_not_abort_others() -> None:
    # Account 1 raises (e.g. Meta 403); account 2 returns a usable row. The
    # pull must still import account 2 rather than propagating the error
    # (which at the job boundary would roll back everything).
    service, ingest, _ = _make_service([_insight()])
    service._meta.ad_account_ids = ["111111", "222222"]
    service._meta.get_campaign_insights = AsyncMock(
        side_effect=[RuntimeError("403 forbidden"), [_insight("999")]]
    )

    result = await service.import_recent_spend(_TENANT_ID, days=7)

    assert result.account_count == 2
    assert result.imported_count == 1
    assert ingest.capture.await_count == 1


@pytest.mark.asyncio
async def test_unparseable_row_is_skipped() -> None:
    service, ingest, _ = _make_service([{"spend": "1.00"}])  # no campaign_id/date
    result = await service.import_recent_spend(_TENANT_ID, days=7)
    assert result.skipped_count == 1
    assert result.imported_count == 0
    ingest.capture.assert_not_awaited()
