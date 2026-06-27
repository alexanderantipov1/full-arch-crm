"""DB-backed tests for PM Payments pagination + applied-exclusion (ENG-301).

The PM Payments list was capped at 100 newest-first rows with no offset and
a fake ``total`` (the page length), so historical rows inside the window were
unreachable; worse, the ``payment_applied`` allocation leg (≈9:1 vs recorded)
crowded out real payments. These tests exercise the repository directly
against a real Postgres test DB on a fresh tenant (rolled back on teardown):

1. ``include_applied=False`` (default) excludes ``payment_applied``; the flag
   opts it back in.
2. ``count_payment_events_for_dashboard`` returns the true window-wide total,
   consistent with the list under the same filters.
3. ``limit``/``offset`` page the newest-first result with no overlap.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.identity.models import Person
from packages.interaction.models import Event
from packages.interaction.repository import InteractionRepository
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session

_BASE = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


async def _seed_person(session: AsyncSession, tenant_id: TenantId) -> Person:
    person = Person(
        tenant_id=tenant_id,
        given_name="Pagination",
        family_name="Payer",
        display_name="Pagination Payer",
    )
    session.add(person)
    await session.flush()
    return person


async def _seed_event(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    person_uid: uuid.UUID,
    kind: str,
    occurred_at: datetime,
    external_id: str,
    amount: float = 100.0,
) -> Event:
    event = Event(
        tenant_id=tenant_id,
        person_uid=person_uid,
        kind=kind,
        source_provider="carestack",
        source_event_id=None,
        data_class="billing",
        source_kind="carestack_accounting_transaction",
        source_external_id=external_id,
        review_status="auto",
        occurred_at=occurred_at,
        summary=f"{kind} {external_id}",
        payload={"amount": amount},
    )
    session.add(event)
    await session.flush()
    return event


async def _seed_payment_slice(
    session: AsyncSession,
    tenant_id: TenantId,
    person_uid: uuid.UUID,
) -> None:
    # 3 recorded (newest-first: r2 > r1 > r0) + 2 applied interleaved in time.
    await _seed_event(
        session, tenant_id, person_uid=person_uid, kind="payment_recorded",
        occurred_at=_BASE, external_id="REC-0",
    )
    await _seed_event(
        session, tenant_id, person_uid=person_uid, kind="payment_applied",
        occurred_at=_BASE + timedelta(hours=1), external_id="APP-0",
    )
    await _seed_event(
        session, tenant_id, person_uid=person_uid, kind="payment_recorded",
        occurred_at=_BASE + timedelta(hours=2), external_id="REC-1",
    )
    await _seed_event(
        session, tenant_id, person_uid=person_uid, kind="payment_applied",
        occurred_at=_BASE + timedelta(hours=3), external_id="APP-1",
    )
    await _seed_event(
        session, tenant_id, person_uid=person_uid, kind="payment_recorded",
        occurred_at=_BASE + timedelta(hours=4), external_id="REC-2",
    )


async def test_applied_excluded_by_default_included_on_flag(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="pm-pay-applied")
    person = await _seed_person(db_session, tenant_id)
    await _seed_payment_slice(db_session, tenant_id, person.id)
    repo = InteractionRepository(db_session)

    default_rows = await repo.list_payment_events_for_dashboard(tenant_id)
    assert [e.kind for e in default_rows] == [
        "payment_recorded",
        "payment_recorded",
        "payment_recorded",
    ]
    assert all(e.kind != "payment_applied" for e in default_rows)

    with_applied = await repo.list_payment_events_for_dashboard(
        tenant_id, include_applied=True
    )
    assert len(with_applied) == 5
    assert sum(e.kind == "payment_applied" for e in with_applied) == 2


async def test_count_matches_list_under_same_filters(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="pm-pay-count")
    person = await _seed_person(db_session, tenant_id)
    await _seed_payment_slice(db_session, tenant_id, person.id)
    repo = InteractionRepository(db_session)

    assert await repo.count_payment_events_for_dashboard(tenant_id) == 3
    assert (
        await repo.count_payment_events_for_dashboard(
            tenant_id, include_applied=True
        )
        == 5
    )


async def test_summarize_collected_payments_patients(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="pm-pay-summary")
    patient_a = await _seed_person(db_session, tenant_id)
    patient_b = await _seed_person(db_session, tenant_id)
    repo = InteractionRepository(db_session)

    # Patient A: 100 + 50 recorded, 20 refunded. Patient B: 200 recorded,
    # 30 reversed. Collected = (100+50+200) − (20+30) = 300.
    await _seed_event(
        db_session, tenant_id, person_uid=patient_a.id, kind="payment_recorded",
        occurred_at=_BASE, external_id="REC-A1", amount=100.0,
    )
    await _seed_event(
        db_session, tenant_id, person_uid=patient_a.id, kind="payment_recorded",
        occurred_at=_BASE + timedelta(hours=1), external_id="REC-A2", amount=50.0,
    )
    await _seed_event(
        db_session, tenant_id, person_uid=patient_a.id, kind="payment_refunded",
        occurred_at=_BASE + timedelta(hours=2), external_id="REF-A1", amount=20.0,
    )
    await _seed_event(
        db_session, tenant_id, person_uid=patient_b.id, kind="payment_recorded",
        occurred_at=_BASE + timedelta(hours=3), external_id="REC-B1", amount=200.0,
    )
    await _seed_event(
        db_session, tenant_id, person_uid=patient_b.id, kind="payment_reversed",
        occurred_at=_BASE + timedelta(hours=4), external_id="REV-B1", amount=30.0,
    )

    summary = await repo.summarize_payment_events_for_dashboard(tenant_id)
    assert float(str(summary["collected_total"])) == 300.0
    # 3 recorded events across 2 distinct patients.
    assert int(str(summary["payment_count"])) == 3
    assert int(str(summary["patient_count"])) == 2


async def test_offset_pages_newest_first_without_overlap(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="pm-pay-offset")
    person = await _seed_person(db_session, tenant_id)
    await _seed_payment_slice(db_session, tenant_id, person.id)
    repo = InteractionRepository(db_session)

    page1 = await repo.list_payment_events_for_dashboard(
        tenant_id, limit=2, offset=0
    )
    page2 = await repo.list_payment_events_for_dashboard(
        tenant_id, limit=2, offset=2
    )
    # Newest-first across recorded rows: REC-2, REC-1 | REC-0.
    assert [e.source_external_id for e in page1] == ["REC-2", "REC-1"]
    assert [e.source_external_id for e in page2] == ["REC-0"]
    assert {e.id for e in page1}.isdisjoint({e.id for e in page2})


@pytest.mark.asyncio
async def test_same_day_groups_collapse_legs_by_clinic_day(
    db_session: AsyncSession,
) -> None:
    """ENG-410: payment legs group by (person, kind, clinic-local day).

    CareStack splits one payment into per-invoice legs; the grouped read
    model must merge them on the AMERICA/LOS_ANGELES calendar day — an
    evening leg that crosses UTC midnight stays in the same group — while
    refunds and other persons stay separate rows.
    """
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="pm-pay-groups")
    repo = InteractionRepository(db_session)
    payer = await _seed_person(db_session, tenant_id)
    other = await _seed_person(db_session, tenant_id)

    # Morning + evening legs, same LA day (the evening one is past UTC
    # midnight: 2026-06-11 18:30 PDT == 2026-06-12 01:30 UTC).
    day_utc_morning = datetime(2026, 6, 11, 17, 27, tzinfo=UTC)
    day_utc_evening = datetime(2026, 6, 12, 1, 30, tzinfo=UTC)
    await _seed_event(
        db_session, tenant_id, person_uid=payer.id, kind="payment_recorded",
        occurred_at=day_utc_morning, external_id="g-leg-1", amount=450.0,
    )
    await _seed_event(
        db_session, tenant_id, person_uid=payer.id, kind="payment_recorded",
        occurred_at=day_utc_morning.replace(minute=28), external_id="g-leg-2",
        amount=344.0,
    )
    await _seed_event(
        db_session, tenant_id, person_uid=payer.id, kind="payment_recorded",
        occurred_at=day_utc_evening, external_id="g-leg-3", amount=125.0,
    )
    # Same person, same day, different KIND → its own group.
    await _seed_event(
        db_session, tenant_id, person_uid=payer.id, kind="payment_refunded",
        occurred_at=day_utc_morning, external_id="g-refund", amount=50.0,
    )
    # Different person, same day → its own group.
    await _seed_event(
        db_session, tenant_id, person_uid=other.id, kind="payment_recorded",
        occurred_at=day_utc_morning, external_id="g-other", amount=519.0,
    )
    # Same person, NEXT LA day → separate group.
    await _seed_event(
        db_session, tenant_id, person_uid=payer.id, kind="payment_recorded",
        occurred_at=datetime(2026, 6, 12, 17, 0, tzinfo=UTC),
        external_id="g-next-day", amount=10.0,
    )

    groups = await repo.list_payment_event_groups_for_dashboard(tenant_id)
    total = await repo.count_payment_event_groups_for_dashboard(tenant_id)
    assert total == 4
    assert len(groups) == 4

    by_key = {
        (g["person_uid"], g["kind"], g["local_day"].isoformat()): g
        for g in groups
    }
    merged = by_key[(payer.id, "payment_recorded", "2026-06-11")]
    assert merged["leg_count"] == 3
    assert float(str(merged["total_amount"])) == 919.0
    assert [e.source_external_id for e in merged["legs"]] == [
        "g-leg-3",
        "g-leg-2",
        "g-leg-1",
    ]

    refund = by_key[(payer.id, "payment_refunded", "2026-06-11")]
    assert refund["leg_count"] == 1
    next_day = by_key[(payer.id, "payment_recorded", "2026-06-12")]
    assert float(str(next_day["total_amount"])) == 10.0
    assert by_key[(other.id, "payment_recorded", "2026-06-11")]["leg_count"] == 1

    # Groups order newest-first by their latest leg: the next-day group
    # leads, then the merged group (its evening leg is newest of Jun 11).
    assert groups[0]["local_day"].isoformat() == "2026-06-12"
    assert groups[1]["leg_count"] == 3

    # The shared filter applies to groups too: scoping to the payer's
    # person id hides the other person's group.
    scoped = await repo.count_payment_event_groups_for_dashboard(
        tenant_id, person_uids=[payer.id]
    )
    assert scoped == 3
