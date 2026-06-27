"""DB-backed tests for the ENG-470 marketing dashboard aggregations.

Exercises ``MarketingService.spend_breakdown`` (which fans out to
``MarketingRepository.aggregate_daily_by_provider`` /
``aggregate_provider_totals`` / ``aggregate_spend``) against a real Postgres
test DB on a fresh tenant (rolled back on teardown). These group-bys over the
``marketing.ad_metric_daily`` table are exactly the part a mocked-repo unit
test cannot verify. Also confirms the cross-domain lead count the marketing
endpoint composes (``OpsService.count_leads_for_dashboard``) lines up.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.identity.models import Person
from packages.marketing.models import AdCampaign, AdMetricDaily
from packages.marketing.service import MarketingService
from packages.ops.models import Lead
from packages.ops.service import OpsService
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session

_DAY_1 = date(2026, 6, 1)
_DAY_2 = date(2026, 6, 2)
_OUTSIDE = date(2026, 5, 1)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


async def _seed_metric(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    provider: str,
    campaign_external_id: str,
    metric_date: date,
    spend: float,
    impressions: int,
    clicks: int,
    conversions: float,
) -> None:
    session.add(
        AdMetricDaily(
            tenant_id=tenant_id,
            provider=provider,
            campaign_external_id=campaign_external_id,
            metric_date=metric_date,
            spend=spend,
            impressions=impressions,
            clicks=clicks,
            conversions=conversions,
            currency="USD",
        )
    )
    await session.flush()


async def _seed_campaign(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    provider: str,
    external_id: str,
    name: str,
) -> None:
    session.add(
        AdCampaign(
            tenant_id=tenant_id,
            provider=provider,
            external_id=external_id,
            name=name,
        )
    )
    await session.flush()


async def _seed_lead(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    created_at: datetime,
) -> None:
    person = Person(
        tenant_id=tenant_id,
        given_name="Spend",
        family_name="Lead",
        display_name="Spend Lead",
    )
    session.add(person)
    await session.flush()
    lead = Lead(tenant_id=tenant_id, person_uid=person.id, source="google")
    lead.created_at = created_at
    session.add(lead)
    await session.flush()


@pytest.mark.asyncio
async def test_spend_breakdown_aggregates_by_day_provider_and_campaign(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="marketing-breakdown")

    await _seed_campaign(
        db_session, tenant_id, provider="google_ads", external_id="g1", name="Search"
    )
    await _seed_campaign(
        db_session, tenant_id, provider="meta_ads", external_id="m1", name="Leadgen"
    )

    # Two providers across two days, plus one campaign with no campaign row
    # (name should come back None), plus a row outside the window.
    await _seed_metric(
        db_session, tenant_id, provider="google_ads", campaign_external_id="g1",
        metric_date=_DAY_1, spend=100.0, impressions=1000, clicks=50, conversions=5.0,
    )
    await _seed_metric(
        db_session, tenant_id, provider="google_ads", campaign_external_id="g1",
        metric_date=_DAY_2, spend=50.0, impressions=500, clicks=20, conversions=2.0,
    )
    await _seed_metric(
        db_session, tenant_id, provider="meta_ads", campaign_external_id="m1",
        metric_date=_DAY_1, spend=40.0, impressions=2000, clicks=10, conversions=1.0,
    )
    await _seed_metric(
        db_session, tenant_id, provider="google_ads", campaign_external_id="g-nameless",
        metric_date=_DAY_1, spend=10.0, impressions=100, clicks=1, conversions=0.0,
    )
    await _seed_metric(
        db_session, tenant_id, provider="google_ads", campaign_external_id="g1",
        metric_date=_OUTSIDE, spend=999.0, impressions=9, clicks=9, conversions=9.0,
    )

    breakdown = await MarketingService(db_session).spend_breakdown(
        tenant_id, start_date=_DAY_1, end_date=_DAY_2
    )

    # Window totals exclude the out-of-window row (100+50+40+10 = 200).
    assert breakdown.spend == pytest.approx(200.0)
    assert breakdown.impressions == 1000 + 500 + 2000 + 100
    assert breakdown.clicks == 50 + 20 + 10 + 1
    assert breakdown.conversions == pytest.approx(8.0)

    # Daily trend: day1 has google(g1)+google(nameless)+meta, day2 has google.
    # Rows are (day, provider) grouped, ordered oldest-first.
    day1_google = next(
        p for p in breakdown.daily
        if p.metric_date == _DAY_1 and p.provider == "google_ads"
    )
    assert day1_google.spend == pytest.approx(110.0)  # g1 100 + nameless 10
    assert day1_google.clicks == 51
    day2_providers = {p.provider for p in breakdown.daily if p.metric_date == _DAY_2}
    assert day2_providers == {"google_ads"}

    # Provider split: google 160, meta 40, ordered by spend desc.
    assert [p.provider for p in breakdown.providers] == ["google_ads", "meta_ads"]
    google_split = breakdown.providers[0]
    assert google_split.spend == pytest.approx(160.0)

    # Campaign table: nameless campaign returns campaign_name None.
    by_external = {r.campaign_external_id: r for r in breakdown.campaigns}
    assert by_external["g1"].campaign_name == "Search"
    assert by_external["g-nameless"].campaign_name is None


@pytest.mark.asyncio
async def test_spend_breakdown_provider_filter_scopes_all_cuts(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="marketing-filter")

    await _seed_metric(
        db_session, tenant_id, provider="google_ads", campaign_external_id="g1",
        metric_date=_DAY_1, spend=100.0, impressions=1000, clicks=50, conversions=5.0,
    )
    await _seed_metric(
        db_session, tenant_id, provider="meta_ads", campaign_external_id="m1",
        metric_date=_DAY_1, spend=40.0, impressions=2000, clicks=10, conversions=1.0,
    )

    breakdown = await MarketingService(db_session).spend_breakdown(
        tenant_id, start_date=_DAY_1, end_date=_DAY_2, provider="google_ads"
    )

    assert breakdown.spend == pytest.approx(100.0)
    assert {p.provider for p in breakdown.providers} == {"google_ads"}
    assert {p.provider for p in breakdown.daily} == {"google_ads"}
    assert {r.provider for r in breakdown.campaigns} == {"google_ads"}


@pytest.mark.asyncio
async def test_lead_count_window_for_marketing_cpl(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="marketing-leads")

    # Two leads inside the window, one before it.
    await _seed_lead(db_session, tenant_id, created_at=datetime(2026, 6, 1, 9, tzinfo=UTC))
    await _seed_lead(db_session, tenant_id, created_at=datetime(2026, 6, 2, 9, tzinfo=UTC))
    await _seed_lead(db_session, tenant_id, created_at=datetime(2026, 5, 1, 9, tzinfo=UTC))

    count = await OpsService(db_session).count_leads_for_dashboard(
        tenant_id,
        created_from=datetime(2026, 6, 1, tzinfo=UTC),
        created_to=datetime(2026, 6, 3, tzinfo=UTC),
    )
    assert count == 2
