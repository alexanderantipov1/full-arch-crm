"""DB-backed test for the ENG-270 location_id backfill migration.

Replays the migration's UPDATE (via the module-level ``BACKFILL_SQL``
constant) against a seeded slice of ``interaction.event`` +
``ingest.raw_event`` + ``tenant.location`` and asserts:

1. An event whose raw_event carries a mappable CareStack ``locationId``
   gains ``payload.location_id`` set to the tenant-local
   ``tenant.location.id`` (as a string, matching the runtime emit
   shape).
2. An event whose raw_event has no ``locationId`` is left unchanged.
3. An event whose raw_event has an *unmappable* ``locationId`` (no
   matching ``tenant.location.external_ref->>'carestack_location_id'``
   in the same tenant) is left unchanged.
4. An event of a kind outside the backfill set (e.g. ``lead_created``)
   is left unchanged even if every other column would qualify.
5. An event that already carries ``payload.location_id`` is left
   unchanged (idempotent guard preserves the pre-existing value).
6. Re-running the SQL keeps every seeded row at the same final state
   (idempotent).
7. Tenant isolation — a CareStack location id that exists in both
   tenants resolves to each tenant's own location uuid.

The test imports ``BACKFILL_SQL`` directly from the migration module
instead of running the full ``alembic upgrade`` so the assertion stays
in the test session's transaction (rolled back on teardown) and does
not depend on the migration head pointer in the live test database.

Assertions are per-seeded-row (not against the global ``rowcount``)
because the local dev database may already contain CareStack
billing/treatment events without ``location_id`` from prior pulls;
the migration legitimately touches those too, so a global rowcount
check would be brittle. Per-row assertions stay correct regardless of
the surrounding DB state.
"""

from __future__ import annotations

import importlib.util
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.identity.models import Person
from packages.ingest.models import RawEvent
from packages.interaction.models import Event
from packages.tenant.models import Location
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session

# Alembic version files start with a date prefix (``20260530_0700_...``)
# which is not a valid Python module path. Load the module by its
# absolute path so the migration stays the single source of truth for
# the UPDATE SQL.
_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "packages"
    / "db"
    / "alembic"
    / "versions"
    / "20260530_0700_a5b6c7d8e9f0_backfill_event_location_id_from_raw.py"
)
_spec = importlib.util.spec_from_file_location(
    "eng_270_backfill_migration", _MIGRATION_PATH
)
assert _spec is not None and _spec.loader is not None, _MIGRATION_PATH
_migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_migration)
BACKFILL_SQL: str = _migration.BACKFILL_SQL


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


async def _seed_person(session: AsyncSession, tenant_id: TenantId) -> Person:
    person = Person(
        tenant_id=tenant_id,
        given_name="Backfill",
        family_name="Subject",
        display_name="Backfill Subject",
    )
    session.add(person)
    await session.flush()
    return person


async def _seed_location(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    carestack_location_id: int,
    name: str,
) -> Location:
    location = Location(
        tenant_id=tenant_id,
        name=name,
        external_ref={"carestack_location_id": carestack_location_id},
    )
    session.add(location)
    await session.flush()
    return location


async def _seed_raw_event(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    payload: dict[str, object],
    external_id: str,
) -> RawEvent:
    now = datetime.now(UTC)
    raw = RawEvent(
        tenant_id=tenant_id,
        source="carestack",
        event_type="carestack.invoice.upsert",
        external_id=external_id,
        received_at=now,
        payload=payload,
    )
    session.add(raw)
    await session.flush()
    return raw


async def _seed_event(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    person_uid: uuid.UUID,
    raw_event_id: uuid.UUID | None,
    kind: str,
    source_kind: str,
    source_external_id: str,
    payload: dict[str, object],
    source_provider: str = "carestack",
) -> Event:
    now = datetime.now(UTC)
    event = Event(
        tenant_id=tenant_id,
        person_uid=person_uid,
        kind=kind,
        source_provider=source_provider,
        source_event_id=raw_event_id,
        data_class="billing",
        source_kind=source_kind,
        source_external_id=source_external_id,
        review_status="auto",
        occurred_at=now,
        summary=f"{kind} from {source_provider}:{source_external_id}",
        payload=payload,
    )
    session.add(event)
    await session.flush()
    return event


async def _payload(session: AsyncSession, event_id: uuid.UUID) -> dict[str, object]:
    row = await session.execute(
        sa.text("SELECT payload FROM interaction.event WHERE id = :id"),
        {"id": event_id},
    )
    return dict(row.scalar_one())


async def _run_backfill(session: AsyncSession) -> None:
    """Execute ``BACKFILL_SQL`` against the session's open transaction.

    We deliberately do not assert against ``CursorResult.rowcount`` here
    because the dev database may already contain CareStack
    billing/treatment events that pre-date the location feature; the
    migration legitimately updates those too. Tests verify outcomes by
    inspecting per-seeded-row state instead.
    """
    await session.execute(sa.text(BACKFILL_SQL))


@pytest.mark.asyncio
async def test_backfill_sets_location_id_for_mappable_events(
    db_session: AsyncSession,
) -> None:
    """The six billing/treatment kinds gain payload.location_id when mappable."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="eng-270-mappable")
    person = await _seed_person(db_session, tenant_id)

    cs_location_id = 8001
    location = await _seed_location(
        db_session,
        tenant_id,
        carestack_location_id=cs_location_id,
        name="ENG-270 mappable location",
    )

    # One event per backfill-eligible kind, each linked to a raw_event
    # carrying the mappable CareStack locationId.
    kinds = [
        ("invoice_created", "carestack_invoice"),
        ("payment_recorded", "carestack_accounting_transaction"),
        ("payment_refunded", "carestack_accounting_transaction"),
        ("payment_reversed", "carestack_accounting_transaction"),
        ("treatment_proposed", "carestack_treatment_procedure"),
        ("treatment_completed", "carestack_treatment_procedure"),
    ]
    seeded: list[uuid.UUID] = []
    for index, (kind, source_kind) in enumerate(kinds):
        raw = await _seed_raw_event(
            db_session,
            tenant_id,
            payload={"locationId": cs_location_id, "id": f"raw-{index}"},
            external_id=f"raw-{index}-{uuid.uuid4().hex[:8]}",
        )
        event = await _seed_event(
            db_session,
            tenant_id,
            person_uid=person.id,
            raw_event_id=raw.id,
            kind=kind,
            source_kind=source_kind,
            source_external_id=f"cs-{kind}-{index}-{uuid.uuid4().hex[:8]}",
            payload={},
        )
        seeded.append(event.id)

    await db_session.flush()

    # Apply the migration UPDATE inside the same transaction.
    await _run_backfill(db_session)

    # Every seeded event now carries payload.location_id pointing at our
    # tenant.location row.
    for event_id in seeded:
        payload = await _payload(db_session, event_id)
        assert payload.get("location_id") == str(location.id), payload

    # Idempotent: a second pass leaves every seeded row at the same
    # final state (the NOT (payload ? 'location_id') guard skips them).
    await _run_backfill(db_session)
    for event_id in seeded:
        payload = await _payload(db_session, event_id)
        assert payload.get("location_id") == str(location.id), payload


@pytest.mark.asyncio
async def test_backfill_leaves_unmappable_events_unchanged(
    db_session: AsyncSession,
) -> None:
    """Events whose raw has no/Unmappable locationId stay untouched."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="eng-270-unmappable")
    person = await _seed_person(db_session, tenant_id)

    # Seed ONE valid location so the join could succeed in principle —
    # but the seeded events below all reference raws that fail the
    # mapping for distinct reasons.
    await _seed_location(
        db_session,
        tenant_id,
        carestack_location_id=8101,
        name="ENG-270 unrelated location",
    )

    # Case A: raw_event has no ``locationId`` key at all.
    raw_no_location = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"id": "raw-no-location"},
        external_id=f"raw-nokey-{uuid.uuid4().hex[:8]}",
    )
    event_no_location = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_no_location.id,
        kind="invoice_created",
        source_kind="carestack_invoice",
        source_external_id=f"cs-inv-nokey-{uuid.uuid4().hex[:8]}",
        payload={},
    )

    # Case B: raw_event has a ``locationId`` that maps to no
    # tenant.location row for this tenant.
    raw_unmapped = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"locationId": 999999, "id": "raw-unmapped"},
        external_id=f"raw-unmapped-{uuid.uuid4().hex[:8]}",
    )
    event_unmapped = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_unmapped.id,
        kind="payment_recorded",
        source_kind="carestack_accounting_transaction",
        source_external_id=f"cs-pay-unmapped-{uuid.uuid4().hex[:8]}",
        payload={},
    )

    # Case C: raw_event has ``locationId: null``.
    raw_null_location = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"locationId": None, "id": "raw-null"},
        external_id=f"raw-null-{uuid.uuid4().hex[:8]}",
    )
    event_null_location = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_null_location.id,
        kind="treatment_proposed",
        source_kind="carestack_treatment_procedure",
        source_external_id=f"cs-tx-null-{uuid.uuid4().hex[:8]}",
        payload={},
    )

    await _run_backfill(db_session)

    for event_id in (event_no_location.id, event_unmapped.id, event_null_location.id):
        payload = await _payload(db_session, event_id)
        assert "location_id" not in payload, payload


@pytest.mark.asyncio
async def test_backfill_skips_ineligible_kind_and_already_set(
    db_session: AsyncSession,
) -> None:
    """Non-billing kinds and rows that already carry location_id stay put."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="eng-270-skip")
    person = await _seed_person(db_session, tenant_id)

    cs_location_id = 8201
    location = await _seed_location(
        db_session,
        tenant_id,
        carestack_location_id=cs_location_id,
        name="ENG-270 skip-case location",
    )
    raw = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"locationId": cs_location_id, "id": "raw-skip"},
        external_id=f"raw-skip-{uuid.uuid4().hex[:8]}",
    )

    # Out-of-scope kind: ``lead_created`` is not in the backfill kind
    # set. Use a salesforce source_provider/source_kind pair so the
    # row also looks coherent — the kind filter is what should reject
    # it, but a coherent seed makes the assertion intent clear.
    lead_event = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw.id,
        kind="lead_created",
        source_kind="salesforce_lead",
        source_external_id=f"sf-lead-{uuid.uuid4().hex[:8]}",
        payload={},
        source_provider="salesforce",
    )

    # Eligible kind that already carries location_id should stay
    # untouched (idempotent guard preserves the pre-existing value
    # rather than clobbering it with the resolved one).
    preexisting_uid = uuid.uuid4()
    invoice_already_set = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw.id,
        kind="invoice_created",
        source_kind="carestack_invoice",
        source_external_id=f"cs-inv-preset-{uuid.uuid4().hex[:8]}",
        payload={"location_id": str(preexisting_uid)},
    )

    await _run_backfill(db_session)

    lead_payload = await _payload(db_session, lead_event.id)
    assert "location_id" not in lead_payload

    invoice_payload = await _payload(db_session, invoice_already_set.id)
    # Pre-existing value is preserved exactly (NOT clobbered by the
    # backfill location uuid).
    assert invoice_payload["location_id"] == str(preexisting_uid)
    assert invoice_payload["location_id"] != str(location.id)


@pytest.mark.asyncio
async def test_backfill_is_tenant_scoped(db_session: AsyncSession) -> None:
    """A raw_event in tenant A's scope does not leak to tenant B's events.

    The join requires ``l.tenant_id = r.tenant_id`` AND
    ``r.tenant_id = e.tenant_id``, so a CareStack locationId that maps
    to a location in tenant A must not enrich an event in tenant B
    even if tenant B happens to have a location with the same
    CareStack id.
    """
    tenant_a = TenantId(uuid.uuid4())
    tenant_b = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_a, label="eng-270-a")
    await seed_tenant(db_session, tenant_b, label="eng-270-b")
    person_a = await _seed_person(db_session, tenant_a)
    person_b = await _seed_person(db_session, tenant_b)

    shared_cs_id = 8301
    location_a = await _seed_location(
        db_session,
        tenant_a,
        carestack_location_id=shared_cs_id,
        name="ENG-270 tenant-a location",
    )
    location_b = await _seed_location(
        db_session,
        tenant_b,
        carestack_location_id=shared_cs_id,
        name="ENG-270 tenant-b location",
    )

    raw_a = await _seed_raw_event(
        db_session,
        tenant_a,
        payload={"locationId": shared_cs_id, "id": "raw-a"},
        external_id=f"raw-a-{uuid.uuid4().hex[:8]}",
    )
    raw_b = await _seed_raw_event(
        db_session,
        tenant_b,
        payload={"locationId": shared_cs_id, "id": "raw-b"},
        external_id=f"raw-b-{uuid.uuid4().hex[:8]}",
    )
    event_a = await _seed_event(
        db_session,
        tenant_a,
        person_uid=person_a.id,
        raw_event_id=raw_a.id,
        kind="invoice_created",
        source_kind="carestack_invoice",
        source_external_id=f"cs-inv-a-{uuid.uuid4().hex[:8]}",
        payload={},
    )
    event_b = await _seed_event(
        db_session,
        tenant_b,
        person_uid=person_b.id,
        raw_event_id=raw_b.id,
        kind="invoice_created",
        source_kind="carestack_invoice",
        source_external_id=f"cs-inv-b-{uuid.uuid4().hex[:8]}",
        payload={},
    )

    await _run_backfill(db_session)

    payload_a = await _payload(db_session, event_a.id)
    payload_b = await _payload(db_session, event_b.id)
    assert payload_a["location_id"] == str(location_a.id)
    assert payload_b["location_id"] == str(location_b.id)
    assert payload_a["location_id"] != payload_b["location_id"]
