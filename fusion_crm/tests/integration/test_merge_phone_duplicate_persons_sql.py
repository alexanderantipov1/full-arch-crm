"""DB-backed tests for the ENG-463 phase-2 merge script (--apply).

Locks the destructive path of ``merge_phone_duplicate_persons.py``:

* a true duplicate (same canonical phone + same name) is merged — the
  loser's ``ops.lead`` repoints to the survivor, the loser's
  ``phi.patient_profile`` is dropped on the UNIQUE(person_uid) collision
  (the survivor's is kept), and a ``merge_event`` is written;
* a household (same phone, DIFFERENT names) is left untouched;
* a DOB conflict (same phone + name, different non-null DOB) is
  quarantined, not merged;
* dry-run writes nothing.

Like the merge_split tests, these COMMIT into the test DB (the script
opens its own session) and clean up a throwaway tenant in ``finally``.
"""

from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys
import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text

from packages.core.types import TenantId
from packages.db.session import SessionFactory
from packages.identity.models import Person, PersonIdentifier, SourceLink
from packages.ops.models import Lead
from packages.phi.models import PatientProfile
from tests._fixtures.workflow_ready import seed_tenant

_SCRIPT = (
    pathlib.Path(__file__).resolve().parents[2]
    / "infra"
    / "scripts"
    / "merge_phone_duplicate_persons.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("merge_phone_dups_apply", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_CLEANUP_SQL = (
    "DELETE FROM phi.patient_profile WHERE tenant_id = :t",
    "DELETE FROM ops.lead WHERE tenant_id = :t",
    "DELETE FROM identity.merge_event WHERE tenant_id = :t",
    "DELETE FROM identity.person_identifier WHERE tenant_id = :t",
    "DELETE FROM identity.source_link WHERE tenant_id = :t",
    "DELETE FROM identity.person WHERE tenant_id = :t",
    "DELETE FROM tenant.tenant WHERE id = :t",
)


async def _cleanup(tenant_id: TenantId) -> None:
    async with SessionFactory() as session:
        for sql in _CLEANUP_SQL:
            await session.execute(text(sql), {"t": tenant_id})
        await session.commit()


def _person(tenant_id: TenantId, given: str, family: str, **kw) -> Person:
    return Person(
        tenant_id=tenant_id,
        given_name=given,
        family_name=family,
        display_name=f"{given} {family}",
        **kw,
    )


async def _lead_owner(tenant_id: TenantId, tag: str) -> uuid.UUID:
    async with SessionFactory() as session:
        return (
            await session.execute(
                text(
                    "SELECT person_uid FROM ops.lead "
                    "WHERE tenant_id = :t AND extra->>'tag' = :tag"
                ),
                {"t": tenant_id, "tag": tag},
            )
        ).scalar_one()


@pytest.mark.asyncio
async def test_merge_apply_dryrun_collision_household_and_dob() -> None:
    # One test function = one event loop: the module-global async engine
    # pools connections per loop, so splitting into multiple async tests
    # trips "Event loop is closed" on teardown (same reason the merge_split
    # integration test is a single function).
    module = _load_script()
    tenant_id = TenantId(uuid.uuid4())
    try:
        async with SessionFactory() as session:
            await seed_tenant(session, tenant_id, label="merge-dups")

            # --- Cluster A: TRUE duplicate (merge + patient_profile collision)
            survivor = _person(tenant_id, "Pat", "Test")  # CareStack-linked → richest
            loser = _person(tenant_id, "Test", "Pat")  # same name token set
            session.add_all([survivor, loser])
            await session.flush()
            session.add_all(
                [
                    # cross-form phone → same canonical +16502530000
                    PersonIdentifier(
                        tenant_id=tenant_id, person_id=survivor.id,
                        kind="phone", value="6502530000",
                    ),
                    PersonIdentifier(
                        tenant_id=tenant_id, person_id=loser.id,
                        kind="phone", value="16502530000",
                    ),
                    SourceLink(
                        tenant_id=tenant_id, person_uid=survivor.id,
                        source_system="carestack", source_instance="carestack-main",
                        source_kind="patient", source_id="CS-DUP-1",
                        first_seen_at=datetime(2026, 5, 1, tzinfo=UTC),
                    ),
                    PatientProfile(tenant_id=tenant_id, person_uid=survivor.id),
                    PatientProfile(tenant_id=tenant_id, person_uid=loser.id),
                    Lead(tenant_id=tenant_id, person_uid=loser.id, extra={"tag": "dup-loser"}),
                ]
            )

            # --- Cluster B: HOUSEHOLD (same phone, different names → keep)
            alice = _person(tenant_id, "Alice", "Adams")
            bob = _person(tenant_id, "Bob", "Adams")
            session.add_all([alice, bob])
            await session.flush()
            session.add_all(
                [
                    PersonIdentifier(tenant_id=tenant_id, person_id=alice.id, kind="phone", value="6502530001"),
                    PersonIdentifier(tenant_id=tenant_id, person_id=bob.id, kind="phone", value="16502530001"),
                    Lead(tenant_id=tenant_id, person_uid=alice.id, extra={"tag": "hh-alice"}),
                    Lead(tenant_id=tenant_id, person_uid=bob.id, extra={"tag": "hh-bob"}),
                ]
            )

            # --- Cluster C: same name + phone, DIFFERENT DOB → quarantine
            c1 = _person(tenant_id, "Carol", "Cole", dob=date(1990, 1, 1))
            c2 = _person(tenant_id, "Carol", "Cole", dob=date(1980, 1, 1))
            session.add_all([c1, c2])
            await session.flush()
            session.add_all(
                [
                    PersonIdentifier(tenant_id=tenant_id, person_id=c1.id, kind="phone", value="6502530002"),
                    PersonIdentifier(tenant_id=tenant_id, person_id=c2.id, kind="phone", value="16502530002"),
                    Lead(tenant_id=tenant_id, person_uid=c1.id, extra={"tag": "dob-c1"}),
                    Lead(tenant_id=tenant_id, person_uid=c2.id, extra={"tag": "dob-c2"}),
                ]
            )
            await session.commit()
            survivor_id, loser_id = survivor.id, loser.id
            alice_id, bob_id, c1_id, c2_id = alice.id, bob.id, c1.id, c2.id

        # Dry-run first: must write nothing.
        dry = argparse.Namespace(apply=False, tenant_id=uuid.UUID(str(tenant_id)), limit=None)
        assert await module.run(dry) == 0
        assert await _lead_owner(tenant_id, "dup-loser") == loser_id
        async with SessionFactory() as session:
            assert (await session.execute(
                text("SELECT count(*) FROM identity.merge_event WHERE tenant_id = :t"),
                {"t": tenant_id},
            )).scalar_one() == 0

        # Apply.
        args = argparse.Namespace(apply=True, tenant_id=uuid.UUID(str(tenant_id)), limit=None)
        rc = await module.run(args)
        assert rc == 0

        # A — merged: loser's lead now on survivor.
        assert await _lead_owner(tenant_id, "dup-loser") == survivor_id
        async with SessionFactory() as session:
            # patient_profile collision: survivor keeps exactly one, loser's gone.
            s_profiles = (await session.execute(
                text("SELECT count(*) FROM phi.patient_profile WHERE person_uid = :p"),
                {"p": survivor_id},
            )).scalar_one()
            l_profiles = (await session.execute(
                text("SELECT count(*) FROM phi.patient_profile WHERE person_uid = :p"),
                {"p": loser_id},
            )).scalar_one()
            assert s_profiles == 1
            assert l_profiles == 0
            merges = (await session.execute(
                text("SELECT count(*) FROM identity.merge_event WHERE tenant_id = :t"),
                {"t": tenant_id},
            )).scalar_one()
            assert merges == 1

        # B — household untouched (both leads stay on their persons).
        assert await _lead_owner(tenant_id, "hh-alice") == alice_id
        assert await _lead_owner(tenant_id, "hh-bob") == bob_id

        # C — DOB conflict quarantined (not merged).
        assert await _lead_owner(tenant_id, "dob-c1") == c1_id
        assert await _lead_owner(tenant_id, "dob-c2") == c2_id
    finally:
        await _cleanup(tenant_id)
