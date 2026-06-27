"""DB-backed tests for the ENG-404 merge_split_lead_persons.py script.

Simulates the prod split: a May-era patient-person (no identifiers) holding
a consultation + CareStack source_link + raw patient payload, and a fresh
lead-person holding the lead + email identifier. The script must stitch
them (lead repointed, identifiers moved, lead-person deleted) while leaving
ambiguous cases untouched.

Unlike most integration tests these COMMIT into the test database (the
script opens its own session and can only see committed rows), so every
test runs on a throwaway tenant and removes its rows in ``finally``.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from packages.core.types import TenantId
from packages.db.session import SessionFactory, engine
from packages.identity.models import Person, PersonIdentifier, SourceLink
from packages.identity.service import normalise_phone
from packages.ingest.models import RawEvent
from packages.ops.models import Consultation, ConsultationStatus, Lead
from tests._fixtures.workflow_ready import seed_tenant


def _norm_phone(phone):
    return normalise_phone(phone)

_SCRIPT = (
    pathlib.Path(__file__).resolve().parents[2]
    / "infra"
    / "scripts"
    / "merge_split_lead_persons.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("merge_split_lead_persons", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_CLEANUP_SQL = (
    "DELETE FROM interaction.event WHERE tenant_id = :t",
    "DELETE FROM ops.lead WHERE tenant_id = :t",
    "DELETE FROM ops.consultation WHERE tenant_id = :t",
    "DELETE FROM ops.person_location_profile WHERE tenant_id = :t",
    "DELETE FROM ingest.raw_event WHERE tenant_id = :t",
    "DELETE FROM identity.match_candidate WHERE tenant_id = :t",
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


async def _seed_split_pair(
    session,
    tenant_id: TenantId,
    *,
    patient_id: str,
    email: str | None = None,
    phone: str | None = None,
    lead_names: tuple[str, str] = ("Jane", "Implant"),
    payload_names: tuple[str, str] = ("Jane", "Implant"),
) -> tuple[Person, Person]:
    """One patient-person (no identifiers) + one lead-person (with email)."""
    patient = Person(
        tenant_id=tenant_id,
        given_name=payload_names[0],
        family_name=payload_names[1],
        display_name=f"{payload_names[0]} {payload_names[1]}",
    )
    lead_person = Person(
        tenant_id=tenant_id,
        given_name=lead_names[0],
        family_name=lead_names[1],
        display_name=f"{lead_names[0]} {lead_names[1]}",
    )
    session.add_all([patient, lead_person])
    await session.flush()

    session.add_all(
        [
            SourceLink(
                tenant_id=tenant_id,
                person_uid=patient.id,
                source_system="carestack",
                source_instance="carestack-main",
                source_kind="patient",
                source_id=patient_id,
                first_seen_at=datetime(2026, 5, 1, tzinfo=UTC),
            ),
            RawEvent(
                tenant_id=tenant_id,
                source="carestack",
                event_type="carestack.patient.upsert",
                external_id=patient_id,
                received_at=datetime(2026, 5, 1, tzinfo=UTC),
                payload={
                    "email": email,
                    "mobile": phone,
                    "firstName": payload_names[0],
                    "lastName": payload_names[1],
                },
            ),
            Consultation(
                tenant_id=tenant_id,
                person_uid=patient.id,
                source_provider="carestack",
                source_instance="carestack-main",
                external_id=f"appt-{patient_id}",
                scheduled_at=datetime(2026, 6, 1, tzinfo=UTC),
                status=ConsultationStatus.COMPLETED,
            ),
            PersonIdentifier(
                tenant_id=tenant_id,
                person_id=lead_person.id,
                kind="email" if email else "phone",
                value=(email.lower() if email else _norm_phone(phone)),
            ),
            SourceLink(
                tenant_id=tenant_id,
                person_uid=lead_person.id,
                source_system="salesforce",
                source_instance="salesforce-main",
                source_kind="lead",
                source_id=f"00Q-{patient_id}",
                first_seen_at=datetime(2026, 6, 11, tzinfo=UTC),
            ),
            Lead(
                tenant_id=tenant_id,
                person_uid=lead_person.id,
                source=None,
                extra={"lead_source": "Google Ads", "utm_medium": "cpc",
                       "utm_campaign": f"pair-{patient_id}"},
            ),
        ]
    )
    await session.flush()
    return patient, lead_person


@pytest.mark.asyncio
async def test_merge_stitches_split_pair_and_skips_ambiguous() -> None:
    module = _load_script()
    tenant_id = TenantId(uuid.uuid4())
    try:
        async with SessionFactory() as session:
            await seed_tenant(session, tenant_id, label="merge-split")
            patient, lead_person = await _seed_split_pair(
                session, tenant_id, patient_id="CS-1", email="jane@example.com"
            )
            # NOTE: a multi-candidate case is impossible by schema — the
            # (kind, value) unique constraint allows one owner per email —
            # so the script's multi_candidate bucket is a pure safety net.
            # Name conflict bucket.
            await _seed_split_pair(
                session, tenant_id, patient_id="CS-3", email="conflict@example.com",
                lead_names=("Maria", "Santos"), payload_names=("Olga", "Petrova"),
            )
            # Phone-only pair (no email anywhere) — owner policy 2026-06-11.
            phone_patient, phone_lead_person = await _seed_split_pair(
                session, tenant_id, patient_id="CS-4", phone="+1 (916) 555-0100",
            )
            # Household: shared phone, both sides fully named differently →
            # must stay split (name gate protects the spouse case).
            await _seed_split_pair(
                session, tenant_id, patient_id="CS-5", phone="+1 (916) 555-0200",
                lead_names=("Eduard", "Torosyan"), payload_names=("Gaiane", "Torosyan"),
            )
            await session.commit()

        buckets = await module.run(apply=True, limit=None, tenant=tenant_id)
        assert buckets.merged >= 2
        assert buckets.matched_by_phone >= 1
        assert buckets.name_conflict >= 1

        async with SessionFactory() as session:
            # Lead now lives on the patient-person; lead-person is gone.
            lead_owner = (
                await session.execute(
                    text("SELECT person_uid FROM ops.lead WHERE tenant_id = :t AND extra->>'utm_campaign' = 'pair-CS-1'"),
                    {"t": tenant_id},
                )
            ).scalar_one()
            assert lead_owner == patient.id
            gone = (
                await session.execute(
                    text("SELECT count(*) FROM identity.person WHERE id = :id"),
                    {"id": lead_person.id},
                )
            ).scalar_one()
            assert gone == 0
            # Email identifier followed onto the patient-person.
            email_owner = (
                await session.execute(
                    text("SELECT person_id FROM identity.person_identifier WHERE tenant_id = :t AND value = 'jane@example.com'"),
                    {"t": tenant_id},
                )
            ).scalar_one()
            assert email_owner == patient.id
            # The conflicted patient kept its split state (untouched).
            conflict_pair = (
                await session.execute(
                    text("""
                        SELECT count(*) FROM identity.source_link sl
                        WHERE sl.tenant_id = :t AND sl.source_id = 'CS-3'
                          AND NOT EXISTS (SELECT 1 FROM ops.lead l WHERE l.person_uid = sl.person_uid)
                    """),
                    {"t": tenant_id},
                )
            ).scalar_one()
            assert conflict_pair == 1

        async with SessionFactory() as session:
            phone_lead_owner = (
                await session.execute(
                    text("SELECT person_uid FROM ops.lead WHERE tenant_id = :t AND extra->>'utm_campaign' = 'pair-CS-4'"),
                    {"t": tenant_id},
                )
            ).scalar_one()
            assert phone_lead_owner == phone_patient.id
            phone_gone = (
                await session.execute(
                    text("SELECT count(*) FROM identity.person WHERE id = :id"),
                    {"id": phone_lead_person.id},
                )
            ).scalar_one()
            assert phone_gone == 0
            # The Torosyan household pair stays split.
            household = (
                await session.execute(
                    text("""
                        SELECT count(*) FROM identity.source_link sl
                        WHERE sl.tenant_id = :t AND sl.source_id = 'CS-5'
                          AND NOT EXISTS (SELECT 1 FROM ops.lead l WHERE l.person_uid = sl.person_uid)
                    """),
                    {"t": tenant_id},
                )
            ).scalar_one()
            assert household == 1

        # Idempotent: second run finds nothing mergeable for this tenant's
        # stitched pair (remaining candidates are the ambiguous ones).
        buckets2 = await module.run(apply=False, limit=None, tenant=tenant_id)
        assert buckets2.mergeable == 0 or all(
            pair[1] != patient.id for pair in buckets2.pairs
        )
    finally:
        await _cleanup(tenant_id)
        # The global engine pooled connections on THIS test's event loop;
        # dispose so the next DB test (fresh loop) doesn't trip on a dead
        # pooled connection during ping.
        await engine.dispose()
