"""DB-backed idempotency test for ad-level Meta ingest (ENG-512).

Runs :class:`MetaAdsAdIngestService` against a real Postgres test DB (fresh
tenant, rolled back on teardown) with a fake Meta client. Proves the curated
ad-tier projection (``marketing.ad_set`` / ``ad`` / ``ad_metric_daily_ad``) is
idempotent on its natural keys: a second pull of byte-identical rows imports
nothing new and leaves exactly one row per natural key — the part a mocked
session cannot verify.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.ingest.meta_ads_ad_service import MetaAdsAdIngestService
from packages.marketing.models import Ad, AdMetricDailyAd, AdSet
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session

_START = date(2026, 6, 17)
_END = date(2026, 6, 18)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


class _FakeMetaClient:
    """Returns canned ad-level insight rows for one account."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    @property
    def ad_account_ids(self) -> list[str]:
        return ["938570599860690"]

    async def get_ad_insights(
        self, account_id: str, *, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        return list(self._rows)


def _insight(ad_id: str, day: str, spend: str) -> dict[str, Any]:
    return {
        "ad_id": ad_id,
        "ad_name": f"Ad {ad_id}",
        "adset_id": "5001",
        "adset_name": "Roseville 35-55",
        "campaign_id": "111",
        "campaign_name": "Implants - Roseville",
        "spend": spend,
        "impressions": "900",
        "clicks": "22",
        "actions": [{"action_type": "lead", "value": "2"}],
        "date_start": day,
        "date_stop": day,
    }


async def _count(session: AsyncSession, model: Any, tenant_id: TenantId) -> int:
    stmt = select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
    return int((await session.execute(stmt)).scalar_one())


async def test_ad_level_ingest_is_idempotent(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="meta-ad-ingest")

    rows = [
        _insight("23856", "2026-06-17", "40.00"),
        _insight("23856", "2026-06-18", "60.00"),
        _insight("99999", "2026-06-18", "10.00"),
    ]
    service = MetaAdsAdIngestService(
        session=db_session, meta_ads_client=_FakeMetaClient(rows)
    )

    first = await service.import_window(
        tenant_id, start_date=_START, end_date=_END
    )
    assert first.imported_count == 3
    assert first.unchanged_count == 0

    # 2 distinct ads, 1 ad set, 3 (ad, day) metric rows.
    assert await _count(db_session, Ad, tenant_id) == 2
    assert await _count(db_session, AdSet, tenant_id) == 1
    assert await _count(db_session, AdMetricDailyAd, tenant_id) == 3

    # Re-pull identical rows → all unchanged, no new rows.
    second = await service.import_window(
        tenant_id, start_date=_START, end_date=_END
    )
    assert second.imported_count == 0
    assert second.unchanged_count == 3
    assert await _count(db_session, Ad, tenant_id) == 2
    assert await _count(db_session, AdMetricDailyAd, tenant_id) == 3

    # A changed spend value re-imports that one (ad, day) row in place.
    changed = [
        _insight("23856", "2026-06-17", "40.00"),
        _insight("23856", "2026-06-18", "75.00"),  # 60 -> 75
        _insight("99999", "2026-06-18", "10.00"),
    ]
    service2 = MetaAdsAdIngestService(
        session=db_session, meta_ads_client=_FakeMetaClient(changed)
    )
    third = await service2.import_window(
        tenant_id, start_date=_START, end_date=_END
    )
    assert third.imported_count == 1
    assert third.unchanged_count == 2
    assert await _count(db_session, AdMetricDailyAd, tenant_id) == 3
    stmt = select(AdMetricDailyAd.spend).where(
        AdMetricDailyAd.tenant_id == tenant_id,
        AdMetricDailyAd.ad_external_id == "23856",
        AdMetricDailyAd.metric_date == date(2026, 6, 18),
    )
    assert float((await db_session.execute(stmt)).scalar_one()) == pytest.approx(75.0)
