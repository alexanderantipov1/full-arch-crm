"""DB-backed tests for the ENG-472 full-funnel report aggregations.

Exercises the two new monthly reads the full-funnel composer adds, against a
real Postgres test DB on a fresh tenant (rolled back on teardown):

- ``MarketingRepository.aggregate_monthly_by_provider`` (via
  ``MarketingService.monthly_spend_by_provider``) — monthly spend group-by.
- ``OpsRepository.count_opportunity_outcomes_by_month`` (via
  ``OpsService.get_opportunity_outcomes_by_month``) — per-close-month
  closed/won/carryover counts, the latter joining
  ``consultation.covering_opportunity_id``.

Plus a small end-to-end check that the per-month ``get_lead_source_tree``
folds google/facebook/other channels with revenue attributed via
``collected_by_person`` — the exact wiring the route performs. These are the
parts a mocked-repo unit test cannot verify (the JSONB boolean filters, the
``to_char`` month bucket, and the correlated carryover EXISTS).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.identity.models import Person
from packages.interaction.models import Event
from packages.interaction.service import InteractionService
from packages.marketing.models import AdMetricDaily
from packages.marketing.service import MarketingService
from packages.ops.models import Consultation, ConsultationStatus, Lead, Opportunity
from packages.ops.service import OpsService
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


async def _seed_person(session: AsyncSession, tenant_id: TenantId) -> Person:
    person = Person(
        tenant_id=tenant_id,
        given_name="Funnel",
        family_name="Person",
        display_name="Funnel Person",
    )
    session.add(person)
    await session.flush()
    return person


async def _seed_opportunity(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    person_uid: uuid.UUID,
    close_date: datetime,
    is_closed: bool,
    is_won: bool,
) -> Opportunity:
    opp = Opportunity(
        tenant_id=tenant_id,
        person_uid=person_uid,
        source_provider="salesforce",
        source_instance="sf-test",
        external_id=f"opp-{uuid.uuid4().hex[:12]}",
        stage="Surgery Completed" if is_won else "Consultation Completed",
        close_date=close_date,
        extra={"is_closed": is_closed, "is_won": is_won},
    )
    session.add(opp)
    await session.flush()
    return opp


async def _seed_consultation(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    person_uid: uuid.UUID,
    scheduled_at: datetime,
    status: ConsultationStatus = ConsultationStatus.COMPLETED,
    covering_opportunity_id: uuid.UUID | None = None,
) -> Consultation:
    consult = Consultation(
        tenant_id=tenant_id,
        person_uid=person_uid,
        source_provider="carestack",
        source_instance="carestack-test",
        external_id=f"appt-{uuid.uuid4().hex[:12]}",
        scheduled_at=scheduled_at,
        status=status,
        covering_opportunity_id=covering_opportunity_id,
    )
    session.add(consult)
    await session.flush()
    return consult


@pytest.mark.asyncio
async def test_monthly_spend_by_provider_buckets_by_month(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="funnel-spend")

    # google_ads spread across April + May; meta_ads in May only.
    for d, spend in ((date(2026, 4, 10), 100.0), (date(2026, 4, 20), 50.0)):
        db_session.add(
            AdMetricDaily(
                tenant_id=tenant_id, provider="google_ads",
                campaign_external_id="g1", metric_date=d, spend=spend,
                impressions=1000, clicks=10, conversions=1.0, currency="USD",
            )
        )
    db_session.add(
        AdMetricDaily(
            tenant_id=tenant_id, provider="google_ads",
            campaign_external_id="g1", metric_date=date(2026, 5, 5), spend=200.0,
            impressions=2000, clicks=20, conversions=2.0, currency="USD",
        )
    )
    db_session.add(
        AdMetricDaily(
            tenant_id=tenant_id, provider="meta_ads",
            campaign_external_id="m1", metric_date=date(2026, 5, 6), spend=40.0,
            impressions=500, clicks=5, conversions=0.0, currency="USD",
        )
    )
    await db_session.flush()

    rows = await MarketingService(db_session).monthly_spend_by_provider(
        tenant_id, start_date=date(2026, 4, 1), end_date=date(2026, 5, 31)
    )
    by_key = {(r.month, r.provider): r for r in rows}

    # April google = 100 + 50 (impressions 2000); May google = 200; May meta = 40.
    assert by_key[("2026-04", "google_ads")].spend == pytest.approx(150.0)
    assert by_key[("2026-04", "google_ads")].impressions == 2000
    assert by_key[("2026-05", "google_ads")].spend == pytest.approx(200.0)
    assert by_key[("2026-05", "meta_ads")].spend == pytest.approx(40.0)
    # No April meta row.
    assert ("2026-04", "meta_ads") not in by_key


@pytest.mark.asyncio
async def test_opportunity_outcomes_by_month_counts_and_carryover(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="funnel-opps")

    person = await _seed_person(db_session, tenant_id)

    # May: one won (closed), one open (not closed → excluded from closed count).
    won_may = await _seed_opportunity(
        db_session, tenant_id, person_uid=person.id,
        close_date=datetime(2026, 5, 20, tzinfo=UTC), is_closed=True, is_won=True,
    )
    await _seed_opportunity(
        db_session, tenant_id, person_uid=person.id,
        close_date=datetime(2026, 5, 25, tzinfo=UTC), is_closed=False, is_won=False,
    )
    # June: one closed-not-won.
    closed_june = await _seed_opportunity(
        db_session, tenant_id, person_uid=person.id,
        close_date=datetime(2026, 6, 10, tzinfo=UTC), is_closed=True, is_won=False,
    )

    # Carryover: the May-won opp is covered by a consult SCHEDULED in April
    # (a different month) → counts as carryover for May. The June opp's consult
    # is in June (same month) → NOT carryover.
    await _seed_consultation(
        db_session, tenant_id, person_uid=person.id,
        scheduled_at=datetime(2026, 4, 15, tzinfo=UTC),
        covering_opportunity_id=won_may.id,
    )
    await _seed_consultation(
        db_session, tenant_id, person_uid=person.id,
        scheduled_at=datetime(2026, 6, 3, tzinfo=UTC),
        covering_opportunity_id=closed_june.id,
    )

    outcomes = await OpsService(db_session).get_opportunity_outcomes_by_month(
        tenant_id,
        close_from=datetime(2026, 5, 1, tzinfo=UTC),
        close_to=datetime(2026, 7, 1, tzinfo=UTC),
    )
    by_month = {o.month: o for o in outcomes}

    assert by_month["2026-05"].closed == 1
    assert by_month["2026-05"].won == 1
    assert by_month["2026-05"].carryover == 1  # consult in April, closed in May
    assert by_month["2026-06"].closed == 1
    assert by_month["2026-06"].won == 0
    assert by_month["2026-06"].carryover == 0  # consult + close both in June


@pytest.mark.asyncio
async def test_lead_source_tree_folds_channels_with_revenue(
    db_session: AsyncSession,
) -> None:
    """End-to-end channel fold the route performs: google/facebook/other with
    revenue attributed via ``collected_by_person``."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="funnel-channels")

    created = datetime(2026, 6, 5, 12, tzinfo=UTC)

    # A google lead (classified), a facebook lead, and a billboard lead
    # (unclassified → folds into "other"). Each with one completed consult.
    specs = [
        ({"utm_source": "google", "utm_medium": "cpc"}, "google"),
        ({"utm_source": "facebook", "utm_medium": "paid_social"}, "facebook"),
        ({"utm_source": "billboard"}, "other"),
    ]
    paying_person_uid: uuid.UUID | None = None
    for extra, _expected in specs:
        person = await _seed_person(db_session, tenant_id)
        lead = Lead(tenant_id=tenant_id, person_uid=person.id, extra=extra)
        lead.created_at = created
        db_session.add(lead)
        await db_session.flush()
        await _seed_consultation(
            db_session, tenant_id, person_uid=person.id, scheduled_at=created,
            status=ConsultationStatus.COMPLETED,
        )
        if extra.get("utm_source") == "google":
            paying_person_uid = person.id
            # A recorded payment so collected_by_person attributes revenue.
            db_session.add(
                Event(
                    tenant_id=tenant_id,
                    person_uid=person.id,
                    kind="payment_recorded",
                    source_provider="carestack",
                    data_class="billing",
                    source_kind="carestack_accounting_transaction",
                    source_external_id=f"txn-{uuid.uuid4().hex[:12]}",
                    review_status="auto",
                    occurred_at=created,
                    summary="payment_recorded test",
                    payload={"amount": "1500.00"},
                )
            )
            await db_session.flush()

    collected = await InteractionService(db_session).collected_by_person(tenant_id)
    assert paying_person_uid is not None
    assert collected.get(paying_person_uid) == pytest.approx(1500.0)

    tree = await OpsService(db_session).get_lead_source_tree(
        tenant_id,
        created_from=datetime(2026, 6, 1, tzinfo=UTC),
        created_to=datetime(2026, 7, 1, tzinfo=UTC),
        collected_by_person=collected,
    )

    # Fold the tree's top-level channel nodes into google/facebook/other.
    folded: dict[str, dict[str, float]] = {}
    for node in tree.sources:
        channel = node.key if node.key in ("google", "facebook") else "other"
        agg = folded.setdefault(
            channel, {"leads": 0.0, "attended": 0.0, "revenue": 0.0}
        )
        agg["leads"] += node.leads
        agg["attended"] += node.consults_attended
        agg["revenue"] += node.collected_amount

    assert folded["google"]["leads"] == 1
    assert folded["google"]["attended"] == 1
    assert folded["google"]["revenue"] == pytest.approx(1500.0)
    assert folded["facebook"]["leads"] == 1
    assert folded["other"]["leads"] == 1
    assert folded["other"]["revenue"] == pytest.approx(0.0)
    # Total revenue rolls up only the paying person.
    assert tree.collected_amount == pytest.approx(1500.0)
