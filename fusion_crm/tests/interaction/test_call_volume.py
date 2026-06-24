"""Integration tests for the Calls-dashboard call-event reads — ENG-474.

Focus: :meth:`InteractionService.get_call_volume` /
:meth:`InteractionRepository.count_events_by_kind` /
:meth:`InteractionRepository.call_volume_aggregate`, the windowed call-event
aggregation behind ``GET /dashboard/analytics/calls``. Exercised against a real
local Postgres test DB (per root CLAUDE.md: integration tests use a real
Postgres, not a mock); the suite skips cleanly when the DB is unavailable.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.identity.models import Person
from packages.interaction.models import Event
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
        slug=f"eng474-{suffix}",
        name="ENG-474 calls test",
        primary_email=f"eng474-{suffix}@example.test",
    )
    session.add(tenant)
    await session.flush()
    return TenantId(tenant.id)


async def _seed_person(session: AsyncSession, tenant_id: TenantId) -> uuid.UUID:
    person = Person(
        tenant_id=tenant_id,
        given_name="Call",
        family_name="Test",
        display_name="Call Test",
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
    payload: dict[str, Any] | None = None,
) -> Event:
    event = Event(
        tenant_id=tenant_id,
        person_uid=person_uid,
        kind=kind,
        source_provider="salesforce",
        source_event_id=None,
        data_class="operational",
        source_kind=None,
        source_external_id=source_external_id,
        projection_ref_type=None,
        projection_ref_id=None,
        review_status="auto",
        occurred_at=occurred_at,
        summary=summary_for_event(
            kind=kind,
            source_provider="salesforce",
            source_id=source_external_id,
        ),
        payload=payload or {},
    )
    session.add(event)
    await session.flush()
    return event


@pytest.mark.asyncio
async def test_get_call_volume_empty_window_is_zero_not_fake() -> None:
    async with _db_session() as session:
        tenant_id = await _seed_tenant(session)
        service = InteractionService(session)
        volume = await service.get_call_volume(tenant_id)
        assert volume.call_logged == 0
        assert volume.call_reference_found == 0
        assert volume.inbound == 0
        assert volume.outbound == 0
        # No duration-bearing calls → average is None (UI renders "—"), not 0.
        assert volume.avg_duration_seconds is None


@pytest.mark.asyncio
async def test_get_call_volume_counts_kinds_direction_and_duration() -> None:
    async with _db_session() as session:
        tenant_id = await _seed_tenant(session)
        person_uid = await _seed_person(session, tenant_id)
        now = datetime(2026, 6, 10, 18, 0, tzinfo=UTC)

        # Two inbound calls (durations 30s + 90s), one outbound (0s, ignored in
        # the average), one with no direction key at all.
        await _seed_event(
            session, tenant_id, person_uid,
            kind="call_logged", occurred_at=now - timedelta(hours=1),
            source_external_id="c1",
            payload={"direction": "inbound", "call_duration_seconds": 30},
        )
        await _seed_event(
            session, tenant_id, person_uid,
            kind="call_logged", occurred_at=now - timedelta(hours=2),
            source_external_id="c2",
            payload={"direction": "inbound", "call_duration_seconds": 90},
        )
        await _seed_event(
            session, tenant_id, person_uid,
            kind="call_logged", occurred_at=now - timedelta(hours=3),
            source_external_id="c3",
            payload={"direction": "outbound", "call_duration_seconds": 0},
        )
        await _seed_event(
            session, tenant_id, person_uid,
            kind="call_logged", occurred_at=now - timedelta(hours=4),
            source_external_id="c4",
            payload={"call_duration_seconds": 10},
        )
        # A recording reference + an unrelated kind (must not count as a call).
        await _seed_event(
            session, tenant_id, person_uid,
            kind="call_reference_found", occurred_at=now - timedelta(hours=1),
            source_external_id="ref-1",
            payload={"data_class": "call_recording_ref"},
        )
        await _seed_event(
            session, tenant_id, person_uid,
            kind="consultation_scheduled", occurred_at=now - timedelta(hours=1),
            source_external_id="appt-1",
        )

        service = InteractionService(session)
        volume = await service.get_call_volume(tenant_id)

        assert volume.call_logged == 4
        assert volume.call_reference_found == 1
        assert volume.inbound == 2
        assert volume.outbound == 1
        assert volume.unknown_direction == 1  # the no-direction row
        # 30 + 90 + 10 carry duration; the 0s outbound does not.
        assert volume.calls_with_duration == 3
        assert volume.total_duration_seconds == 130
        assert volume.avg_duration_seconds == pytest.approx(130 / 3)


@pytest.mark.asyncio
async def test_count_events_by_kind_respects_window_and_tenant() -> None:
    async with _db_session() as session:
        tenant_a = await _seed_tenant(session)
        tenant_b = await _seed_tenant(session)
        person_a = await _seed_person(session, tenant_a)
        person_b = await _seed_person(session, tenant_b)
        now = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)

        # In-window call for tenant A.
        await _seed_event(
            session, tenant_a, person_a,
            kind="call_logged", occurred_at=now - timedelta(days=1),
            source_external_id="a-in",
            payload={"direction": "inbound", "call_duration_seconds": 5},
        )
        # Out-of-window call for tenant A (60 days ago).
        await _seed_event(
            session, tenant_a, person_a,
            kind="call_logged", occurred_at=now - timedelta(days=60),
            source_external_id="a-out",
            payload={"direction": "inbound", "call_duration_seconds": 5},
        )
        # Tenant B call — must not leak into tenant A's count.
        await _seed_event(
            session, tenant_b, person_b,
            kind="call_logged", occurred_at=now - timedelta(days=1),
            source_external_id="b-in",
            payload={"direction": "outbound", "call_duration_seconds": 5},
        )

        service = InteractionService(session)
        counts = await service.count_events_by_kind(
            tenant_a,
            ["call_logged"],
            occurred_from=now - timedelta(days=30),
            occurred_to=now,
        )
        assert counts.get("call_logged") == 1
