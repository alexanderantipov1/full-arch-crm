"""DB-backed tests for the ENG-341 shared-contact uniqueness guards.

Locks the contract that Layer A of the household-identity epic establishes on
``identity.person_identifier`` against the real test PostgreSQL:

* a SHARED kind (``phone`` / ``email``) may be held by MULTIPLE persons — both
  identifier rows persist (household members share one contact);
* a UNIQUE kind (e.g. ``carestack_patient_id``) STILL rejects a cross-person
  duplicate at the DB level (partial unique index);
* the same ``(person_id, kind, value)`` cannot be inserted twice on ONE person
  (per-person idempotency guard), even for a shared kind;
* the migration pre-check raises (counts only, no values) when the table holds
  data that would violate the new guards, and stays silent on clean/shared data.

Single test function = single event loop (the module-global async engine pools
connections per loop). The committing phases clean up a throwaway tenant in
``finally``; the pre-check phases roll back fully and commit nothing.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from packages.core.types import PersonUID, TenantId
from packages.db.session import SessionFactory
from packages.identity.models import Person, PersonIdentifier
from packages.identity.service import IdentityService
from tests._fixtures.workflow_ready import seed_tenant

_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[2]
    / "packages"
    / "db"
    / "alembic"
    / "versions"
    / "20260621_1700_e9a1c7b4d2f3_eng341_person_identifier_shared_contacts.py"
)

_UNIQUE_INDEX = "identity.uq_person_identifier_unique_kind_value"
_PERSON_GUARD = "uq_person_identifier_person_kind_value"


def _load_migration():
    spec = importlib.util.spec_from_file_location("eng341_shared_contacts", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_CLEANUP_SQL = (
    "DELETE FROM identity.person_identifier WHERE tenant_id = :t",
    "DELETE FROM identity.person WHERE tenant_id = :t",
    "DELETE FROM tenant.tenant WHERE id = :t",
)


async def _cleanup(tenant_id: TenantId) -> None:
    async with SessionFactory() as session:
        for sql in _CLEANUP_SQL:
            await session.execute(text(sql), {"t": tenant_id})
        await session.commit()


def _person(tenant_id: TenantId, given: str, family: str) -> Person:
    return Person(
        tenant_id=tenant_id,
        given_name=given,
        family_name=family,
        display_name=f"{given} {family}",
    )


async def _count(session, tenant_id: TenantId, kind: str, value: str) -> int:
    return int(
        await session.scalar(
            text(
                "SELECT COUNT(*) FROM identity.person_identifier "
                "WHERE tenant_id = :t AND kind = :k AND value = :v"
            ),
            {"t": tenant_id, "k": kind, "v": value},
        )
    )


@pytest.mark.asyncio
async def test_shared_contact_guards_enforced_in_postgres() -> None:
    migration = _load_migration()
    tenant_id = TenantId(uuid.uuid4())
    shared_phone = "+19165550123"
    shared_email = "household@example.test"
    unique_cs_id = "CS-PATIENT-0001"

    try:
        # --- Phase 1: shared phone/email attach to two persons (committed) ---
        async with SessionFactory() as session:
            await seed_tenant(session, tenant_id, label="eng341")
            svc = IdentityService(session)

            person_a = _person(tenant_id, "Alice", "Household")
            person_b = _person(tenant_id, "Bob", "Household")
            session.add_all([person_a, person_b])
            await session.flush()

            # Alice owns phone, email, and a UNIQUE carestack id.
            session.add_all(
                [
                    PersonIdentifier(
                        tenant_id=tenant_id,
                        person_id=person_a.id,
                        kind="phone",
                        value=shared_phone,
                    ),
                    PersonIdentifier(
                        tenant_id=tenant_id,
                        person_id=person_a.id,
                        kind="email",
                        value=shared_email,
                    ),
                    PersonIdentifier(
                        tenant_id=tenant_id,
                        person_id=person_a.id,
                        kind="carestack_patient_id",
                        value=unique_cs_id,
                    ),
                ]
            )
            await session.flush()

            # Bob (a household member) attaches the SAME phone + email.
            assert (
                await svc.attach_identifier(
                    tenant_id, PersonUID(person_b.id), "phone", shared_phone
                )
                == "added"
            )
            assert (
                await svc.attach_identifier(
                    tenant_id, PersonUID(person_b.id), "email", shared_email
                )
                == "added"
            )

            # Bob attaching Alice's UNIQUE carestack id is refused (collision).
            assert (
                await svc.attach_identifier(
                    tenant_id,
                    PersonUID(person_b.id),
                    "carestack_patient_id",
                    unique_cs_id,
                )
                == "collision"
            )
            await session.commit()

        # Both shared rows persist; the unique kind stays 1:1.
        async with SessionFactory() as session:
            assert await _count(session, tenant_id, "phone", shared_phone) == 2
            assert await _count(session, tenant_id, "email", shared_email) == 2
            assert (
                await _count(session, tenant_id, "carestack_patient_id", unique_cs_id)
                == 1
            )

        # --- Phase 2: DB rejects a cross-person UNIQUE-kind duplicate ---
        async with SessionFactory() as session:
            other = _person(tenant_id, "Carol", "Household")
            session.add(other)
            await session.flush()
            session.add(
                PersonIdentifier(
                    tenant_id=tenant_id,
                    person_id=other.id,
                    kind="carestack_patient_id",
                    value=unique_cs_id,  # already owned by Alice
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()

        # --- Phase 3: DB rejects a duplicate (person_id, kind, value) row ---
        async with SessionFactory() as session:
            person_b_id = await session.scalar(
                text(
                    "SELECT person_id FROM identity.person_identifier "
                    "WHERE tenant_id = :t AND kind = 'phone' AND value = :v "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"t": tenant_id, "v": shared_phone},
            )
            session.add(
                PersonIdentifier(
                    tenant_id=tenant_id,
                    person_id=person_b_id,
                    kind="phone",
                    value=shared_phone,  # Bob already holds this exact row
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()

        # --- Phase 4: migration pre-check stays silent on clean/shared data ---
        async with SessionFactory() as session:
            conn = await session.connection()
            # Shared phone held by two persons does NOT violate the guards.
            await conn.run_sync(migration.precheck_for_shared_contact_guards)
            await session.rollback()

    finally:
        await _cleanup(tenant_id)

    # --- Phase 5: migration pre-check RAISES on violating data (rolled back) ---
    precheck_tenant = TenantId(uuid.uuid4())
    async with SessionFactory() as session:
        try:
            await seed_tenant(session, precheck_tenant, label="eng341-precheck")
            p1 = _person(precheck_tenant, "Dup", "One")
            p2 = _person(precheck_tenant, "Dup", "Two")
            session.add_all([p1, p2])
            await session.flush()

            # Drop the partial unique index inside this (uncommitted) tx so we
            # can seed a cross-person UNIQUE-kind duplicate the precheck counts.
            await session.execute(text(f"DROP INDEX {_UNIQUE_INDEX}"))
            session.add_all(
                [
                    PersonIdentifier(
                        tenant_id=precheck_tenant,
                        person_id=p1.id,
                        kind="carestack_patient_id",
                        value="CS-DUP-9",
                    ),
                    PersonIdentifier(
                        tenant_id=precheck_tenant,
                        person_id=p2.id,
                        kind="carestack_patient_id",
                        value="CS-DUP-9",
                    ),
                ]
            )
            await session.flush()

            conn = await session.connection()
            with pytest.raises(RuntimeError) as excinfo:
                await conn.run_sync(migration.precheck_for_shared_contact_guards)
            # Counts are surfaced; the offending value is NOT.
            assert "duplicate groups=1" in str(excinfo.value)
            assert "CS-DUP-9" not in str(excinfo.value)
        finally:
            # Roll back everything — including the DROP INDEX (DDL is
            # transactional in Postgres) — so the test commits nothing.
            await session.rollback()

    # --- Phase 6: pre-check RAISES on a (person_id, kind, value) duplicate ---
    person_dup_tenant = TenantId(uuid.uuid4())
    async with SessionFactory() as session:
        try:
            await seed_tenant(session, person_dup_tenant, label="eng341-persondup")
            p = _person(person_dup_tenant, "Same", "Person")
            session.add(p)
            await session.flush()

            # Drop the per-person guard inside this (uncommitted) tx so we can
            # seed two identical rows on ONE person. Use a SHARED kind (phone)
            # so the partial unique index is NOT involved — this isolates the
            # (person_id, kind, value) pre-check branch from the unique-kind one.
            await session.execute(
                text(
                    "ALTER TABLE identity.person_identifier "
                    f"DROP CONSTRAINT {_PERSON_GUARD}"
                )
            )
            session.add_all(
                [
                    PersonIdentifier(
                        tenant_id=person_dup_tenant,
                        person_id=p.id,
                        kind="phone",
                        value="+19165550999",
                    ),
                    PersonIdentifier(
                        tenant_id=person_dup_tenant,
                        person_id=p.id,
                        kind="phone",
                        value="+19165550999",
                    ),
                ]
            )
            await session.flush()

            conn = await session.connection()
            with pytest.raises(RuntimeError) as excinfo:
                await conn.run_sync(migration.precheck_for_shared_contact_guards)
            # The (person_id,kind,value) branch is surfaced; value NOT leaked.
            assert "(person_id,kind,value) duplicate groups=1" in str(excinfo.value)
            assert "+19165550999" not in str(excinfo.value)
        finally:
            # Roll back everything — including the DROP CONSTRAINT (DDL is
            # transactional in Postgres) — so the test commits nothing.
            await session.rollback()
