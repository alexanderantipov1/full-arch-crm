"""DB-backed tests for the ENG-560 location-tab classifier.

Exercises ``OpsService.classify_location_tabs`` against a real Postgres test
DB on a fresh tenant (rolled back on teardown). The classifier is the
contract behind the ``location_tab`` filter on ``GET /pm/leads``:

Precedence (operator-fixed):
  1. latest consultation by ``scheduled_at`` → tab via
     ``tenant.location.short_name``;
  2. else SF ``assigned_center`` (NBSP-normalized): "El Dorado Hills" →
     el_dorado, everything else → galleria default.

``fusion`` / ``cosmo`` are reachable only via a consultation; ``galleria`` is
the default bucket; every person lands in exactly one tab. These cross-table
joins (consultation → location short_name, lead.extra JSONB) are exactly what
a mocked-repo unit test cannot verify.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.identity.models import Person
from packages.ops.models import Consultation, ConsultationStatus, Lead
from packages.ops.service import OpsService
from packages.tenant.models import Location
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session

_EARLIER = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
_LATER = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


async def _seed_person(session: AsyncSession, tenant_id: TenantId) -> Person:
    person = Person(
        tenant_id=tenant_id,
        given_name="Tab",
        family_name="Subject",
        display_name="Tab Subject",
    )
    session.add(person)
    await session.flush()
    return person


async def _seed_location(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    short_name: str,
    name: str,
) -> Location:
    location = Location(tenant_id=tenant_id, name=name, short_name=short_name)
    session.add(location)
    await session.flush()
    return location


async def _seed_lead(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    person_uid: uuid.UUID,
    assigned_center: str | None = None,
) -> Lead:
    extra: dict = {}
    if assigned_center is not None:
        extra["assigned_center"] = assigned_center
    lead = Lead(tenant_id=tenant_id, person_uid=person_uid, extra=extra)
    session.add(lead)
    await session.flush()
    return lead


async def _seed_consultation(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    person_uid: uuid.UUID,
    location_id: uuid.UUID | None,
    scheduled_at: datetime,
    status: ConsultationStatus = ConsultationStatus.SCHEDULED,
) -> Consultation:
    consultation = Consultation(
        tenant_id=tenant_id,
        person_uid=person_uid,
        source_provider="carestack",
        source_instance="carestack-test",
        external_id=f"appt-{uuid.uuid4().hex[:12]}",
        scheduled_at=scheduled_at,
        status=status,
        location_id=location_id,
    )
    session.add(consultation)
    await session.flush()
    return consultation


async def _seed_four_locations(
    session: AsyncSession, tenant_id: TenantId
) -> dict[str, Location]:
    return {
        "galleria": await _seed_location(
            session, tenant_id, short_name="GALLERIA", name="Galleria OMS"
        ),
        "fusion": await _seed_location(
            session, tenant_id, short_name="FUSION-ROS", name="Fusion Roseville"
        ),
        "el_dorado": await _seed_location(
            session, tenant_id, short_name="FUSION-EDH", name="Fusion El Dorado"
        ),
        "cosmo": await _seed_location(
            session, tenant_id, short_name="COSMO", name="Cosmo"
        ),
    }


@pytest.mark.asyncio
async def test_latest_consultation_wins_across_two_locations(
    db_session: AsyncSession,
) -> None:
    """Two consultations at different locations → the newest one decides."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="loc-tab-latest")
    locations = await _seed_four_locations(db_session, tenant_id)
    ops = OpsService(db_session)

    person = await _seed_person(db_session, tenant_id)
    # Older consult at El Dorado, newer at Fusion-Roseville → fusion wins.
    await _seed_consultation(
        db_session, tenant_id, person_uid=person.id,
        location_id=locations["el_dorado"].id, scheduled_at=_EARLIER,
    )
    await _seed_consultation(
        db_session, tenant_id, person_uid=person.id,
        location_id=locations["fusion"].id, scheduled_at=_LATER,
    )

    tabs = await ops.classify_location_tabs(tenant_id, [person.id])
    assert tabs == {person.id: "fusion"}


@pytest.mark.asyncio
async def test_consultation_overrides_assigned_center(
    db_session: AsyncSession,
) -> None:
    """Roseville-assigned lead + a Fusion-Roseville consult → fusion, not galleria."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="loc-tab-override")
    locations = await _seed_four_locations(db_session, tenant_id)
    ops = OpsService(db_session)

    person = await _seed_person(db_session, tenant_id)
    await _seed_lead(
        db_session, tenant_id, person_uid=person.id, assigned_center="Roseville"
    )
    await _seed_consultation(
        db_session, tenant_id, person_uid=person.id,
        location_id=locations["fusion"].id, scheduled_at=_LATER,
    )

    tabs = await ops.classify_location_tabs(tenant_id, [person.id])
    assert tabs == {person.id: "fusion"}


@pytest.mark.asyncio
async def test_el_dorado_raw_path_plain_and_nbsp(db_session: AsyncSession) -> None:
    """No consult + assigned_center 'El Dorado Hills' (plain & NBSP) → el_dorado."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="loc-tab-edh")
    await _seed_four_locations(db_session, tenant_id)
    ops = OpsService(db_session)

    plain = await _seed_person(db_session, tenant_id)
    nbsp = await _seed_person(db_session, tenant_id)
    await _seed_lead(
        db_session, tenant_id, person_uid=plain.id, assigned_center="El Dorado Hills"
    )
    # SF emits U+00A0 between the words — the classifier must still match.
    await _seed_lead(
        db_session, tenant_id, person_uid=nbsp.id,
        assigned_center="El Dorado Hills",
    )

    tabs = await ops.classify_location_tabs(tenant_id, [plain.id, nbsp.id])
    assert tabs == {plain.id: "el_dorado", nbsp.id: "el_dorado"}


@pytest.mark.asyncio
async def test_no_consult_defaults_to_galleria(db_session: AsyncSession) -> None:
    """null / empty / Roseville / Galleria OMS, no consult → galleria default."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="loc-tab-default")
    await _seed_four_locations(db_session, tenant_id)
    ops = OpsService(db_session)

    null_center = await _seed_person(db_session, tenant_id)
    empty = await _seed_person(db_session, tenant_id)
    roseville = await _seed_person(db_session, tenant_id)
    galleria_oms = await _seed_person(db_session, tenant_id)
    no_lead = await _seed_person(db_session, tenant_id)

    await _seed_lead(db_session, tenant_id, person_uid=null_center.id)  # no key
    await _seed_lead(db_session, tenant_id, person_uid=empty.id, assigned_center="")
    await _seed_lead(
        db_session, tenant_id, person_uid=roseville.id, assigned_center="Roseville"
    )
    await _seed_lead(
        db_session, tenant_id, person_uid=galleria_oms.id, assigned_center="Galleria OMS"
    )
    # no_lead has no Lead row at all.

    person_uids = [null_center.id, empty.id, roseville.id, galleria_oms.id, no_lead.id]
    tabs = await ops.classify_location_tabs(tenant_id, person_uids)
    assert tabs == {uid: "galleria" for uid in person_uids}


@pytest.mark.asyncio
async def test_fusion_and_cosmo_never_hold_no_consult_raw_leads(
    db_session: AsyncSession,
) -> None:
    """A raw lead with no consultation can never resolve to fusion or cosmo."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="loc-tab-exclusive")
    await _seed_four_locations(db_session, tenant_id)
    ops = OpsService(db_session)

    # Even an assigned_center that names Roseville / Cosmo stays in galleria
    # without consultation evidence — rule 2 only ever yields el_dorado or
    # galleria.
    centers = ["Roseville", "Galleria OMS", "Cosmo", "Fusion Roseville", None]
    persons = []
    for center in centers:
        person = await _seed_person(db_session, tenant_id)
        await _seed_lead(
            db_session, tenant_id, person_uid=person.id, assigned_center=center
        )
        persons.append(person)

    tabs = await ops.classify_location_tabs(tenant_id, [p.id for p in persons])
    assert set(tabs.values()) <= {"galleria", "el_dorado"}
    assert "fusion" not in tabs.values()
    assert "cosmo" not in tabs.values()


@pytest.mark.asyncio
async def test_cosmo_reachable_only_via_consultation(db_session: AsyncSession) -> None:
    """A Cosmo consultation is the only way into the cosmo tab."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="loc-tab-cosmo")
    locations = await _seed_four_locations(db_session, tenant_id)
    ops = OpsService(db_session)

    person = await _seed_person(db_session, tenant_id)
    await _seed_lead(
        db_session, tenant_id, person_uid=person.id, assigned_center="Roseville"
    )
    await _seed_consultation(
        db_session, tenant_id, person_uid=person.id,
        location_id=locations["cosmo"].id, scheduled_at=_LATER,
    )

    tabs = await ops.classify_location_tabs(tenant_id, [person.id])
    assert tabs == {person.id: "cosmo"}


@pytest.mark.asyncio
async def test_consultation_without_location_falls_through_to_assigned_center(
    db_session: AsyncSession,
) -> None:
    """A consult with a null location_id cannot decide a tab → rule 2 applies."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="loc-tab-nullloc")
    await _seed_four_locations(db_session, tenant_id)
    ops = OpsService(db_session)

    person = await _seed_person(db_session, tenant_id)
    await _seed_lead(
        db_session, tenant_id, person_uid=person.id, assigned_center="El Dorado Hills"
    )
    await _seed_consultation(
        db_session, tenant_id, person_uid=person.id,
        location_id=None, scheduled_at=_LATER,
    )

    tabs = await ops.classify_location_tabs(tenant_id, [person.id])
    assert tabs == {person.id: "el_dorado"}


@pytest.mark.asyncio
async def test_empty_person_list_returns_empty_map(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="loc-tab-empty")
    ops = OpsService(db_session)
    assert await ops.classify_location_tabs(tenant_id, []) == {}
