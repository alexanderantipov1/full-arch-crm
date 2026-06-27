"""Repository-level tests for the interaction domain — ENG-327.

Focus: :meth:`InteractionRepository.max_event_occurred_at`, the per-tenant
aggregate that powers the payment-freshness facet of ``/health/ingest``.
The test exercises the real ``func.max(...).filter(...)`` query against a
local Postgres test DB (per the root CLAUDE.md: integration tests must
use a real Postgres, not a mock). When the DB is unavailable the test
skips cleanly (mirrors ``workflow_ready_db_session``).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.identity.models import Person
from packages.interaction.models import Event
from packages.interaction.repository import InteractionRepository
from packages.interaction.service import InteractionService, summary_for_event
from packages.tenant.models import Tenant


@asynccontextmanager
async def _db_session() -> AsyncIterator[AsyncSession]:
    """Yield a real DB session, skip when unreachable."""
    try:
        from packages.db.session import SessionFactory, engine
    except Exception as exc:  # pragma: no cover — environment dependent
        pytest.skip(f"database settings unavailable: {exc}")

    session = SessionFactory()
    try:
        await session.execute(sa.text("SELECT 1"))
    except OperationalError as exc:  # pragma: no cover — environment dependent
        await session.close()
        pytest.skip(f"database unavailable: {exc}")

    try:
        yield session
    finally:
        await session.rollback()
        await session.close()
        await engine.dispose()


async def _seed_tenant(session: AsyncSession) -> TenantId:
    suffix = uuid.uuid4().hex[:12]
    tenant = Tenant(
        id=uuid.uuid4(),
        slug=f"eng327-{suffix}",
        name="ENG-327 repo test",
        primary_email=f"eng327-{suffix}@example.test",
    )
    session.add(tenant)
    await session.flush()
    return TenantId(tenant.id)


async def _seed_person(session: AsyncSession, tenant_id: TenantId) -> uuid.UUID:
    person = Person(
        tenant_id=tenant_id,
        given_name="Repo",
        family_name="Test",
        display_name="Repo Test",
    )
    session.add(person)
    await session.flush()
    return person.id


async def _seed_event(
    session: AsyncSession,
    tenant_id: TenantId,
    person_uid: uuid.UUID,
    *,
    kind: str,
    occurred_at: datetime,
    source_external_id: str | None,
) -> Event:
    event = Event(
        tenant_id=tenant_id,
        person_uid=person_uid,
        kind=kind,
        source_provider="carestack",
        source_event_id=None,
        data_class="billing" if kind.startswith("payment_") else "operational",
        source_kind="carestack_accounting_transaction" if kind.startswith("payment_") else None,
        source_external_id=source_external_id,
        projection_ref_type=None,
        projection_ref_id=None,
        review_status="auto",
        occurred_at=occurred_at,
        summary=summary_for_event(
            kind=kind,
            source_provider="carestack",
            source_id=source_external_id,
        ),
        payload={},
    )
    session.add(event)
    await session.flush()
    return event


@pytest.mark.asyncio
async def test_max_event_occurred_at_returns_none_when_no_events() -> None:
    async with _db_session() as session:
        tenant_id = await _seed_tenant(session)
        repo = InteractionRepository(session)
        result = await repo.max_event_occurred_at(tenant_id, "payment_recorded")
        assert result is None


@pytest.mark.asyncio
async def test_max_event_occurred_at_returns_latest_for_kind() -> None:
    async with _db_session() as session:
        tenant_id = await _seed_tenant(session)
        person_uid = await _seed_person(session, tenant_id)

        now = datetime(2026, 6, 3, 18, 0, tzinfo=UTC)
        older = now - timedelta(hours=4)
        newest = now - timedelta(minutes=15)
        middle = now - timedelta(hours=1)

        # Three payment_recorded events; newest wins.
        for ts, ext_id in (
            (older, "tx-1"),
            (newest, "tx-3"),
            (middle, "tx-2"),
        ):
            await _seed_event(
                session,
                tenant_id,
                person_uid,
                kind="payment_recorded",
                occurred_at=ts,
                source_external_id=ext_id,
            )

        # Confounder rows that must NOT influence the result: different
        # kinds, recent timestamps.
        await _seed_event(
            session,
            tenant_id,
            person_uid,
            kind="payment_refunded",
            occurred_at=now - timedelta(minutes=1),
            source_external_id="tx-refund",
        )
        await _seed_event(
            session,
            tenant_id,
            person_uid,
            kind="payment_applied",
            occurred_at=now,
            source_external_id="tx-applied",
        )

        repo = InteractionRepository(session)
        result = await repo.max_event_occurred_at(tenant_id, "payment_recorded")
        assert result is not None
        assert result == newest


@pytest.mark.asyncio
async def test_max_event_occurred_at_isolates_by_tenant() -> None:
    async with _db_session() as session:
        tenant_a = await _seed_tenant(session)
        tenant_b = await _seed_tenant(session)
        person_a = await _seed_person(session, tenant_a)
        person_b = await _seed_person(session, tenant_b)

        now = datetime(2026, 6, 3, 12, 0, tzinfo=UTC)
        a_latest = now - timedelta(hours=2)
        b_latest = now - timedelta(minutes=10)  # newer in absolute time

        await _seed_event(
            session,
            tenant_a,
            person_a,
            kind="payment_recorded",
            occurred_at=a_latest,
            source_external_id="A-tx-1",
        )
        await _seed_event(
            session,
            tenant_b,
            person_b,
            kind="payment_recorded",
            occurred_at=b_latest,
            source_external_id="B-tx-1",
        )

        repo = InteractionRepository(session)
        assert await repo.max_event_occurred_at(tenant_a, "payment_recorded") == a_latest
        assert await repo.max_event_occurred_at(tenant_b, "payment_recorded") == b_latest


@pytest.mark.asyncio
async def test_service_validates_unknown_kind() -> None:
    """Service-layer guard: unknown kinds raise rather than silently returning None."""
    from packages.core.exceptions import ValidationError

    async with _db_session() as session:
        tenant_id = await _seed_tenant(session)
        service = InteractionService(session)
        with pytest.raises(ValidationError):
            await service.max_event_occurred_at(tenant_id, kind="patient_admitted")


@pytest.mark.asyncio
async def test_analytics_surgery_stage_milestones_by_person() -> None:  # ENG-511
    """Earliest treatment_accepted / surgery_scheduled / surgery_completed per person.

    Real-PG aggregate: seeds the three new B1.3 kinds (plus confounders) and
    asserts the builder-facing milestone map returns the EARLIEST occurrence of
    each kind, ignores unrelated kinds, and is absent for persons with none.
    """
    async with _db_session() as session:
        tenant_id = await _seed_tenant(session)
        person_uid = await _seed_person(session, tenant_id)
        other_person = await _seed_person(session, tenant_id)

        base = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
        accepted_first = base
        accepted_later = base + timedelta(days=2)
        scheduled = base + timedelta(days=10)
        completed = base + timedelta(days=30)

        # Two acceptances on one plan-life — the earliest must win.
        await _seed_event(
            session, tenant_id, person_uid,
            kind="treatment_accepted", occurred_at=accepted_later,
            source_external_id="plan-1b",
        )
        await _seed_event(
            session, tenant_id, person_uid,
            kind="treatment_accepted", occurred_at=accepted_first,
            source_external_id="plan-1a",
        )
        await _seed_event(
            session, tenant_id, person_uid,
            kind="surgery_scheduled", occurred_at=scheduled,
            source_external_id="proc-1",
        )
        await _seed_event(
            session, tenant_id, person_uid,
            kind="surgery_completed", occurred_at=completed,
            source_external_id="proc-1c",
        )
        # Confounder: an unrelated kind must not appear in any column.
        await _seed_event(
            session, tenant_id, person_uid,
            kind="treatment_proposed", occurred_at=base - timedelta(days=1),
            source_external_id="proc-prop",
        )

        repo = InteractionRepository(session)
        result = await repo.analytics_surgery_stage_milestones_by_person(tenant_id)

        assert result[person_uid] == (accepted_first, scheduled, completed)
        # A person with none of the three milestones is absent.
        assert other_person not in result
