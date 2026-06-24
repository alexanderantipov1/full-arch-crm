"""ENG-514…523 — B2 data-ready page services over a real Postgres.

Seeds ``analytics.fact_patient_journey`` rows directly (the projection is the
single source for these pages) and drives ``AnalyticsPagesService``: the
eight-stage funnel + conversions, realized-cash widgets, revenue-by-dimension
(resolved vs "Unattributed"), lead-month cohorts with revenue-after-N-days, and
the per-person journey timeline. Skips when no test DB is available.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from packages.analytics.filters import AnalyticsFilters
from packages.analytics.metrics_service import AnalyticsPagesService
from packages.analytics.models import FactPatientJourney
from packages.analytics.queries import FactAnalyticsQueries
from packages.core.types import TenantId
from packages.marketing.models import AdMetricDaily
from packages.marketing.service import MarketingService
from packages.tenant.service import LocationService, TenantService
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session

_NOW = datetime(2026, 6, 18, 18, 0, tzinfo=UTC)
_WIN_START = datetime(2026, 1, 1, tzinfo=UTC)
_WIN_END = datetime(2026, 2, 1, tzinfo=UTC)

_L1 = uuid.uuid4()
_L2 = uuid.uuid4()

# Person A — full journey through "treatment presented", paid inside the month.
_A = uuid.uuid4()
# Person B — lead + consult, paid early February (still within 30d of its lead).
_B = uuid.uuid4()
# Person C — bare lead, no money, no source/location (Unattributed bucket).
_C = uuid.uuid4()


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


def _pages(session: AsyncSession) -> AnalyticsPagesService:
    return AnalyticsPagesService(
        queries=FactAnalyticsQueries(session),
        marketing=MarketingService(session),
        tenant=TenantService(session),
        location=LocationService(session),
    )


async def _seed_facts(session: AsyncSession) -> None:
    session.add_all(
        [
            FactPatientJourney(
                person_uid=_A,
                source="google_ads",
                location_id=_L1,
                lead_date=datetime(2026, 1, 10, 9, 0, tzinfo=UTC),
                first_contact_date=datetime(2026, 1, 11, 9, 0, tzinfo=UTC),
                consult_scheduled_date=datetime(2026, 1, 15, 9, 0, tzinfo=UTC),
                show_date=datetime(2026, 1, 15, 10, 0, tzinfo=UTC),
                treatment_presented_date=datetime(2026, 1, 20, 9, 0, tzinfo=UTC),
                first_payment_date=datetime(2026, 1, 25, 9, 0, tzinfo=UTC),
                revenue_amount=10000.0,
                collected_amount=6000.0,
            ),
            FactPatientJourney(
                person_uid=_B,
                source="facebook",
                location_id=_L2,
                lead_date=datetime(2026, 1, 12, 9, 0, tzinfo=UTC),
                consult_scheduled_date=datetime(2026, 1, 16, 9, 0, tzinfo=UTC),
                first_payment_date=datetime(2026, 2, 5, 9, 0, tzinfo=UTC),
                revenue_amount=8000.0,
                collected_amount=8000.0,
            ),
            FactPatientJourney(
                person_uid=_C,
                lead_date=datetime(2026, 1, 20, 9, 0, tzinfo=UTC),
            ),
        ]
    )
    await session.flush()


def _jan_filters(**kwargs: object) -> AnalyticsFilters:
    return AnalyticsFilters(
        time_range="custom",
        custom_start=_WIN_START,
        custom_end=_WIN_END,
        **kwargs,  # type: ignore[arg-type]
    )


async def test_executive_overview_funnel_and_widgets(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="exec")
    await _seed_facts(db_session)

    out = await _pages(db_session).executive_overview(
        tenant_id, _jan_filters(), now=_NOW, tz="UTC"
    )

    stages = {s.key: s for s in out.funnel}
    assert stages["leads"].count == 3
    assert stages["reached"].count == 1
    assert stages["consults"].count == 2
    assert stages["shows"].count == 1
    assert stages["treatment_presented"].count == 1
    # B1-unresolved stages are honest zeros.
    assert stages["treatment_accepted"].count == 0
    assert stages["surgery_completed"].count == 0
    # Entry stage has no conversion; consults→shows = 1/2.
    assert stages["leads"].conversion is None
    assert stages["shows"].conversion == pytest.approx(0.5)

    assert out.revenue_total == pytest.approx(18000.0)
    assert out.collected_total == pytest.approx(14000.0)
    assert out.outstanding_total == pytest.approx(4000.0)
    assert out.patients == 3
    # No marketing connected → cost/ROI null, per-stage cost null.
    assert out.spend is None
    assert out.derived.roi is None
    assert stages["leads"].cost is None

    # Realized-cash widgets anchor on first_payment_date. Both payments land in
    # 2026, so the YTD card sees them; June (this_month) sees none.
    widgets = {w.preset: w for w in out.revenue_widgets}
    assert widgets["this_year"].collected == pytest.approx(14000.0)
    assert widgets["this_year"].payers == 2
    assert widgets["this_month"].collected == pytest.approx(0.0)


async def test_funnel_stages_full_ladder(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="funnel")
    await _seed_facts(db_session)

    out = await _pages(db_session).funnel_stages(
        tenant_id, _jan_filters(), now=_NOW, tz="UTC"
    )
    assert [s.key for s in out.stages] == [
        "leads",
        "reached",
        "consults",
        "shows",
        "treatment_presented",
        "treatment_accepted",
        "surgery_scheduled",
        "surgery_completed",
    ]
    assert out.stages[0].count == 3
    assert out.stages[-1].count == 0  # surgery_completed unresolved → 0
    assert out.revenue_total == pytest.approx(18000.0)


async def test_revenue_intelligence_dimensions(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="rev")
    await _seed_facts(db_session)

    out = await _pages(db_session).revenue_intelligence(
        tenant_id, _jan_filters(), now=_NOW, tz="UTC"
    )
    assert out.gross_total == pytest.approx(18000.0)
    assert out.collected_total == pytest.approx(14000.0)
    assert out.outstanding_total == pytest.approx(4000.0)
    assert out.case_count == 2  # A + B carry revenue; C does not
    assert out.avg_case_value == pytest.approx(9000.0)

    dims = {d.dimension: d for d in out.dimensions}
    # Source is resolved; vendor/caller/coordinator/doctor are not.
    assert dims["source"].resolved is True
    assert dims["vendor"].resolved is False
    source_groups = {g.group_label: g for g in dims["source"].groups}
    assert source_groups["google_ads"].gross == pytest.approx(10000.0)
    assert source_groups["facebook"].collected == pytest.approx(8000.0)
    # Every row has a null vendor → a single "Unattributed" (null-keyed) bucket.
    assert len(dims["vendor"].groups) == 1
    assert dims["vendor"].groups[0].group_id is None
    assert dims["vendor"].groups[0].gross == pytest.approx(18000.0)


async def test_cohort_revenue_after_n_days(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="cohort")
    await _seed_facts(db_session)

    # Year window so the single January cohort is captured.
    filters = AnalyticsFilters(
        time_range="custom",
        custom_start=datetime(2026, 1, 1, tzinfo=UTC),
        custom_end=datetime(2027, 1, 1, tzinfo=UTC),
    )
    out = await _pages(db_session).cohort_analytics(
        tenant_id, filters, now=_NOW, tz="UTC"
    )
    assert out.horizons == [30, 60, 90, 180, 365]
    assert len(out.cohorts) == 1
    cohort = out.cohorts[0]
    assert cohort.cohort_month == "2026-01"
    assert cohort.lead_count == 3
    # A paid 15 days after its lead, B 24 days after → both inside the 30d horizon.
    assert cohort.revenue.d30 == pytest.approx(14000.0)
    assert cohort.collected_total == pytest.approx(14000.0)


async def test_marketing_performance_breakdowns(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="mktg")

    camp = uuid.uuid4()
    p1, p2, p3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    db_session.add_all(
        [
            # Facebook / "Spring Implants": full journey through surgery, $400 cost.
            FactPatientJourney(
                person_uid=p1,
                source="facebook",
                campaign_id=camp,
                campaign_name="Spring Implants",
                lead_date=datetime(2026, 1, 10, 9, 0, tzinfo=UTC),
                consult_scheduled_date=datetime(2026, 1, 15, 9, 0, tzinfo=UTC),
                show_date=datetime(2026, 1, 16, 9, 0, tzinfo=UTC),
                surgery_completed_date=datetime(2026, 1, 25, 9, 0, tzinfo=UTC),
                revenue_amount=20000.0,
                collected_amount=12000.0,
                marketing_cost_allocated=400.0,
            ),
            # Google / no campaign (Unattributed campaign bucket), $100 cost.
            FactPatientJourney(
                person_uid=p2,
                source="google",
                lead_date=datetime(2026, 1, 12, 9, 0, tzinfo=UTC),
                consult_scheduled_date=datetime(2026, 1, 18, 9, 0, tzinfo=UTC),
                revenue_amount=0.0,
                collected_amount=0.0,
                marketing_cost_allocated=100.0,
            ),
            # Facebook / "Spring Implants": bare lead, uncovered ($0 allocated).
            FactPatientJourney(
                person_uid=p3,
                source="facebook",
                campaign_id=camp,
                campaign_name="Spring Implants",
                lead_date=datetime(2026, 1, 20, 9, 0, tzinfo=UTC),
                marketing_cost_allocated=0.0,
            ),
        ]
    )
    # Ground-truth window spend = $800 > allocated $500 → spend_without_leads 300.
    db_session.add(
        AdMetricDaily(
            tenant_id=tenant_id,
            provider="meta_ads",
            campaign_external_id="ext-1",
            metric_date=date(2026, 1, 15),
            spend=800.0,
        )
    )
    await db_session.flush()

    out = await _pages(db_session).marketing_performance(
        tenant_id, _jan_filters(), now=_NOW, tz="UTC"
    )

    # Window totals + spend reconciliation.
    assert out.total_spend == pytest.approx(800.0)
    assert out.allocated_spend == pytest.approx(500.0)
    assert out.spend_without_leads == pytest.approx(300.0)
    assert out.leads == 3
    assert out.consults == 2
    assert out.shows == 1
    assert out.surgeries == 1
    assert out.revenue_total == pytest.approx(20000.0)
    assert out.roi == pytest.approx(25.0)  # 20000 / 800

    bd = {b.dimension: b for b in out.breakdowns}
    assert bd["campaign"].resolved is True
    assert bd["source"].resolved is True
    # Ad set / ad carry no fact dimension → honest "no data".
    assert bd["ad_set"].resolved is False
    assert bd["ad_set"].groups == []
    assert bd["ad"].resolved is False
    assert bd["ad"].note is not None

    # Campaign breakdown: "Spring Implants" (p1 + p3) + Unattributed (p2).
    camp_groups = {g.group_label: g for g in bd["campaign"].groups}
    spring = camp_groups["Spring Implants"]
    assert spring.group_id == camp
    assert spring.spend == pytest.approx(400.0)
    assert spring.leads == 2
    assert spring.shows == 1
    assert spring.surgeries == 1
    assert spring.revenue == pytest.approx(20000.0)
    assert spring.roi == pytest.approx(50.0)  # 20000 / 400
    assert spring.cost_per_lead == pytest.approx(200.0)  # 400 / 2
    assert None in camp_groups  # null-campaign Unattributed bucket (p2)

    # Source breakdown.
    src_groups = {g.group_label: g for g in bd["source"].groups}
    assert src_groups["facebook"].leads == 2
    assert src_groups["facebook"].spend == pytest.approx(400.0)
    assert src_groups["google"].leads == 1
    assert src_groups["google"].spend == pytest.approx(100.0)
    # revenue 0 / spend 100 → 0.0 (a real zero return, not "no data").
    assert src_groups["google"].roi == pytest.approx(0.0)


async def test_marketing_performance_no_spend_connected(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="mktg-nospend")
    await _seed_facts(db_session)

    # No AdMetricDaily seeded → no spend source connected.
    out = await _pages(db_session).marketing_performance(
        tenant_id, _jan_filters(), now=_NOW, tz="UTC"
    )
    assert out.total_spend is None
    assert out.allocated_spend is None
    assert out.spend_without_leads is None
    assert out.roi is None
    # Outcome counts still surface from the fact.
    assert out.leads == 3
    bd = {b.dimension: b for b in out.breakdowns}
    for g in bd["source"].groups:
        assert g.spend is None
        assert g.roi is None
        assert g.cost_per_lead is None


async def test_patient_journey_steps_and_missing(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="journey")
    await _seed_facts(db_session)

    out = await _pages(db_session).patient_journey(tenant_id, _A)
    assert out.found is True
    assert out.source == "google_ads"
    steps = {s.key: s for s in out.steps}
    assert steps["lead_date"].occurred_at is not None
    assert steps["surgery_completed_date"].occurred_at is None
    # Revenue surfaces only on the payment step; responsibility is unresolved.
    assert steps["first_payment_date"].revenue == pytest.approx(6000.0)
    assert steps["lead_date"].responsible_employee is None

    missing = await _pages(db_session).patient_journey(tenant_id, uuid.uuid4())
    assert missing.found is False
    assert missing.steps == []
