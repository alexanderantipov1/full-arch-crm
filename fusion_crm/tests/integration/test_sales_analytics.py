"""DB-backed tests for the ENG-473 Sales dashboard aggregations.

Exercises the new OpsService sales reads against a real Postgres test DB on a
fresh tenant (rolled back on teardown):

- ``OpsService.get_sales_pipeline_summary`` — pipeline value / active / closed
  / won counts + won revenue, all from the ``extra.is_closed`` / ``is_won``
  JSONB booleans (not the free-form ``stage`` string).
- ``OpsService.get_pipeline_by_stage`` — dynamic group-by on the raw ``stage``.
- ``OpsService.get_tc_leaderboard`` — group-by ``extra.owner_name`` with the
  person_uids the route needs to attribute Collected cash.
- ``OpsService.list_sales_consultations`` — consultation → covering-opportunity
  LEFT join.

Plus the route-level Collected attribution: a recorded payment flows through
``InteractionService.collected_by_person`` and is attributed to the TC behind
that person's opportunity, exactly as the ``/analytics/sales`` route does.
These are the parts a mocked-repo unit test cannot verify (the JSONB boolean
filters, the ``array_agg(distinct ...)`` person rollup, and the outer join).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.identity.models import Person
from packages.interaction.models import Event
from packages.interaction.service import InteractionService
from packages.ops.models import Consultation, ConsultationStatus, Opportunity
from packages.ops.service import OpsService
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


async def _seed_person(session: AsyncSession, tenant_id: TenantId) -> Person:
    person = Person(
        tenant_id=tenant_id,
        given_name="Sales",
        family_name="Patient",
        display_name="Sales Patient",
    )
    session.add(person)
    await session.flush()
    return person


async def _seed_opportunity(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    person_uid: uuid.UUID,
    stage: str,
    amount: float,
    owner_name: str,
    is_closed: bool,
    is_won: bool,
    close_date: datetime | None = None,
) -> Opportunity:
    opp = Opportunity(
        tenant_id=tenant_id,
        person_uid=person_uid,
        source_provider="salesforce",
        source_instance="sf-test",
        external_id=f"opp-{uuid.uuid4().hex[:12]}",
        stage=stage,
        amount=amount,
        close_date=close_date,
        extra={
            "owner_name": owner_name,
            "is_closed": is_closed,
            "is_won": is_won,
        },
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
async def test_sales_pipeline_summary_uses_extra_booleans(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="sales-summary")
    person = await _seed_person(db_session, tenant_id)

    # Two open opps (pipeline 1000 + 500), one won (3000), one closed-lost (700).
    await _seed_opportunity(
        db_session, tenant_id, person_uid=person.id, stage="Consultation Scheduled",
        amount=1000.0, owner_name="Alice", is_closed=False, is_won=False,
    )
    await _seed_opportunity(
        db_session, tenant_id, person_uid=person.id, stage="Consultation Completed",
        amount=500.0, owner_name="Alice", is_closed=False, is_won=False,
    )
    await _seed_opportunity(
        db_session, tenant_id, person_uid=person.id, stage="Surgery Completed",
        amount=3000.0, owner_name="Bob", is_closed=True, is_won=True,
        close_date=datetime(2026, 5, 1, tzinfo=UTC),
    )
    await _seed_opportunity(
        db_session, tenant_id, person_uid=person.id, stage="Closed Lost",
        amount=700.0, owner_name="Bob", is_closed=True, is_won=False,
        close_date=datetime(2026, 5, 2, tzinfo=UTC),
    )
    await db_session.flush()

    summary = await OpsService(db_session).get_sales_pipeline_summary(tenant_id)

    assert summary.active_opps == 2
    assert summary.closed_opps == 2
    assert summary.won_opps == 1
    assert summary.pipeline_value == pytest.approx(1500.0)  # 1000 + 500 (open)
    assert summary.won_revenue == pytest.approx(3000.0)


@pytest.mark.asyncio
async def test_pipeline_by_stage_groups_raw_stage_strings(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="sales-stage")
    person = await _seed_person(db_session, tenant_id)

    await _seed_opportunity(
        db_session, tenant_id, person_uid=person.id, stage="Consultation Completed",
        amount=1000.0, owner_name="Alice", is_closed=False, is_won=False,
    )
    await _seed_opportunity(
        db_session, tenant_id, person_uid=person.id, stage="Consultation Completed",
        amount=500.0, owner_name="Alice", is_closed=False, is_won=False,
    )
    await _seed_opportunity(
        db_session, tenant_id, person_uid=person.id, stage="Surgery Scheduled",
        amount=2000.0, owner_name="Bob", is_closed=False, is_won=False,
    )
    await db_session.flush()

    rows = await OpsService(db_session).get_pipeline_by_stage(tenant_id)
    by_stage = {r.stage: r for r in rows}

    assert by_stage["Consultation Completed"].count == 2
    assert by_stage["Consultation Completed"].value == pytest.approx(1500.0)
    assert by_stage["Surgery Scheduled"].count == 1
    assert by_stage["Surgery Scheduled"].value == pytest.approx(2000.0)
    # Ordered by value descending — Surgery Scheduled (2000) leads.
    assert rows[0].stage == "Surgery Scheduled"


@pytest.mark.asyncio
async def test_tc_leaderboard_groups_owner_and_attributes_collected(
    db_session: AsyncSession,
) -> None:
    """TC leaderboard group-by + the route's Collected attribution."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="sales-tc")

    alice_person = await _seed_person(db_session, tenant_id)
    bob_person = await _seed_person(db_session, tenant_id)

    # Alice: one won (3000), one open (1000). Bob: one closed-lost (700).
    await _seed_opportunity(
        db_session, tenant_id, person_uid=alice_person.id, stage="Surgery Completed",
        amount=3000.0, owner_name="Alice", is_closed=True, is_won=True,
        close_date=datetime(2026, 5, 1, tzinfo=UTC),
    )
    await _seed_opportunity(
        db_session, tenant_id, person_uid=alice_person.id, stage="Consultation Completed",
        amount=1000.0, owner_name="Alice", is_closed=False, is_won=False,
    )
    await _seed_opportunity(
        db_session, tenant_id, person_uid=bob_person.id, stage="Closed Lost",
        amount=700.0, owner_name="Bob", is_closed=True, is_won=False,
        close_date=datetime(2026, 5, 2, tzinfo=UTC),
    )

    # Alice's person paid 1500 (net Collected). Bob's person paid nothing.
    db_session.add(
        Event(
            tenant_id=tenant_id,
            person_uid=alice_person.id,
            kind="payment_recorded",
            source_provider="carestack",
            data_class="billing",
            source_kind="carestack_accounting_transaction",
            source_external_id=f"txn-{uuid.uuid4().hex[:12]}",
            review_status="auto",
            occurred_at=datetime(2026, 5, 3, tzinfo=UTC),
            summary="payment_recorded test",
            payload={"amount": "1500.00"},
        )
    )
    await db_session.flush()

    rows = await OpsService(db_session).get_tc_leaderboard(tenant_id)
    by_tc = {r.tc: r for r in rows}

    assert by_tc["Alice"].opps == 2
    assert by_tc["Alice"].won == 1
    assert by_tc["Alice"].lost == 0
    assert by_tc["Alice"].value == pytest.approx(4000.0)
    assert by_tc["Alice"].won_revenue == pytest.approx(3000.0)
    assert alice_person.id in by_tc["Alice"].person_uids

    assert by_tc["Bob"].opps == 1
    assert by_tc["Bob"].won == 0
    assert by_tc["Bob"].lost == 1

    # Route-level Collected attribution: sum collected_by_person over the TC's
    # person_uids (the exact arithmetic the /analytics/sales route performs).
    collected = await InteractionService(db_session).collected_by_person(tenant_id)
    alice_collected = sum(
        collected.get(uid, 0.0) for uid in by_tc["Alice"].person_uids
    )
    bob_collected = sum(collected.get(uid, 0.0) for uid in by_tc["Bob"].person_uids)
    assert alice_collected == pytest.approx(1500.0)
    assert bob_collected == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_list_sales_consultations_joins_covering_opportunity(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="sales-consults")
    person = await _seed_person(db_session, tenant_id)

    opp = await _seed_opportunity(
        db_session, tenant_id, person_uid=person.id, stage="Surgery Scheduled",
        amount=2141.0, owner_name="Marina Godin", is_closed=False, is_won=False,
        close_date=datetime(2026, 6, 1, tzinfo=UTC),
    )
    # One consult linked to the opportunity, one with no covering opportunity.
    await _seed_consultation(
        db_session, tenant_id, person_uid=person.id,
        scheduled_at=datetime(2026, 5, 20, tzinfo=UTC),
        covering_opportunity_id=opp.id,
    )
    await _seed_consultation(
        db_session, tenant_id, person_uid=person.id,
        scheduled_at=datetime(2026, 5, 10, tzinfo=UTC),
        status=ConsultationStatus.NO_SHOW,
    )
    await db_session.flush()

    rows = await OpsService(db_session).list_sales_consultations(tenant_id, limit=50)
    # Ordered by scheduled_at descending — the linked consult (May 20) first.
    assert len(rows) == 2
    linked, unlinked = rows[0], rows[1]

    assert linked.tc == "Marina Godin"
    assert linked.stage == "Surgery Scheduled"
    assert linked.opp_value == pytest.approx(2141.0)
    assert linked.close_date == datetime(2026, 6, 1, tzinfo=UTC)

    # No covering opportunity → opportunity-derived fields are None.
    assert unlinked.tc is None
    assert unlinked.stage is None
    assert unlinked.opp_value is None
    assert unlinked.close_date is None
    assert unlinked.status == ConsultationStatus.NO_SHOW
