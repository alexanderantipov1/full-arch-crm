"""Unit tests for ``GoogleAdsCampaignIngestService`` (mocked I/O)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.ingest.google_ads_campaign_service import GoogleAdsCampaignIngestService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _row(campaign_id: str = "111", day: str = "2026-06-14") -> dict[str, Any]:
    return {
        "campaign": {
            "id": campaign_id,
            "name": "Implants - Search",
            "status": "ENABLED",
            "advertisingChannelType": "SEARCH",
        },
        "metrics": {
            "costMicros": "12340000",
            "impressions": "100",
            "clicks": "5",
            "conversions": 2.0,
        },
        "segments": {"date": day},
    }


def _make_service(
    rows: list[dict[str, Any]],
    *,
    latest_payload: dict[str, Any] | None = None,
) -> tuple[GoogleAdsCampaignIngestService, MagicMock, MagicMock]:
    session = MagicMock()
    nested = MagicMock()
    nested.__aenter__ = AsyncMock(return_value=None)
    nested.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested)

    client = MagicMock()
    client.customer_ids = ["8185418623"]
    client.search_campaign_metrics = AsyncMock(return_value=rows)

    service = GoogleAdsCampaignIngestService(session=session, google_ads_client=client)

    service._ingest = MagicMock(
        spec=["capture", "latest_payload", "sync_object_schema"]
    )
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
    service, ingest, marketing = _make_service([_row()])

    result = await service.import_recent_spend(_TENANT_ID, days=7)

    assert result.imported_count == 1
    assert result.unchanged_count == 0
    assert result.skipped_count == 0
    assert result.campaigns_upserted == 1
    assert result.account_count == 1

    # raw captured verbatim under the marketing event type
    raw_in = ingest.capture.await_args.args[1]
    assert raw_in.source == "google_ads"
    assert raw_in.event_type == "google_ads.campaign_metric.upsert"
    assert raw_in.external_id == "111:2026-06-14"
    assert raw_in.payload == _row()

    # campaign projected
    camp_in = marketing.upsert_campaign.await_args.args[1]
    assert camp_in.provider == "google_ads"
    assert camp_in.external_id == "111"
    assert camp_in.name == "Implants - Search"
    assert camp_in.objective == "SEARCH"
    assert camp_in.account_id == "8185418623"

    # metric projected with micros→units conversion
    metric_in = marketing.upsert_metric_daily.await_args.args[1]
    assert metric_in.spend == pytest.approx(12.34)
    assert metric_in.impressions == 100
    assert metric_in.clicks == 5
    assert metric_in.conversions == pytest.approx(2.0)

    # schema registry reconciled once with flattened observed fields
    assert ingest.sync_object_schema.await_count == 1
    observed = {f.name for f in ingest.sync_object_schema.await_args.kwargs["fields"]}
    assert "campaign.id" in observed
    assert "metrics.costMicros" in observed
    assert "segments.date" in observed


@pytest.mark.asyncio
async def test_identical_payload_is_unchanged_and_not_recaptured() -> None:
    service, ingest, marketing = _make_service([_row()], latest_payload=_row())

    result = await service.import_recent_spend(_TENANT_ID, days=7)

    assert result.unchanged_count == 1
    assert result.imported_count == 0
    ingest.capture.assert_not_awaited()
    marketing.upsert_campaign.assert_not_awaited()


@pytest.mark.asyncio
async def test_unparseable_row_is_skipped() -> None:
    service, ingest, _ = _make_service([{"metrics": {"costMicros": "1"}}])

    result = await service.import_recent_spend(_TENANT_ID, days=7)

    assert result.skipped_count == 1
    assert result.imported_count == 0
    ingest.capture.assert_not_awaited()
