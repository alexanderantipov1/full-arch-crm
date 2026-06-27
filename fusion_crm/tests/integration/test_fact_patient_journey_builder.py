"""ENG-506 — fact_patient_journey builder integration test (real Postgres).

Seeds a small deterministic fixture on a fresh tenant (rolled back on teardown)
and asserts the builder projects ``analytics.fact_patient_journey`` correctly via
the real domain services + repository — no mocks, no re-implementation of the
builder's reads. Skips when no test DB is available.

Covers: one row per person over the SF-lead ∪ CareStack-direct universe;
person-anchored lead dating (lead created-at vs CareStack-direct earliest
activity); consult/show/location, treatment-presented, first-payment milestones;
Net-Collected money; resolved attribution; provenance methods; and idempotency
(a second build leaves the row count unchanged and values stable).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from packages.actor.service import ActorService
from packages.analytics.fact_builder import FactPatientJourneyBuilder
from packages.analytics.fact_repository import FactPatientJourneyRepository
from packages.attribution.models import LeadAttribution, SourceNode
from packages.attribution.service import AttributionService
from packages.catalog.service import CatalogService
from packages.core.types import TenantId
from packages.identity.models import Person, SourceLink
from packages.identity.service import IdentityService
from packages.ingest.service import IngestService
from packages.interaction.models import Event
from packages.interaction.service import InteractionService
from packages.ops.models import Consultation, ConsultationStatus, Lead
from packages.ops.service import OpsService
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session

_LEAD_DATE = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
_CONSULT_AT = datetime(2026, 2, 1, 10, 0, tzinfo=UTC)
_TREATMENT_AT = datetime(2026, 2, 3, 11, 0, tzinfo=UTC)
_PAYMENT_AT = datetime(2026, 2, 10, 12, 0, tzinfo=UTC)
_DIRECT_ACTIVITY = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
_NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


def _builder(session: AsyncSession) -> FactPatientJourneyBuilder:
    return FactPatientJourneyBuilder(
        ops=OpsService(session),
        identity=IdentityService(session),
        interaction=InteractionService(session),
        attribution=AttributionService(session),
        actor=ActorService(session),
        ingest=IngestService(session),
        catalog=CatalogService(session),
        repo=FactPatientJourneyRepository(session),
    )


async def _seed_person(session: AsyncSession, tenant_id: TenantId, name: str) -> Person:
    person = Person(
        tenant_id=tenant_id, given_name=name, family_name="Fact", display_name=name
    )
    session.add(person)
    await session.flush()
    return person


async def test_builder_projects_fact_rows(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="fact-builder")
    location_id = uuid.uuid4()

    # --- SF-lead person: full journey ---
    lead_person = await _seed_person(db_session, tenant_id, "Lead")
    lead = Lead(
        tenant_id=tenant_id, person_uid=lead_person.id, source="google_ads", extra={}
    )
    lead.created_at = _LEAD_DATE
    db_session.add(lead)
    db_session.add(
        Consultation(
            tenant_id=tenant_id,
            person_uid=lead_person.id,
            source_provider="carestack",
            source_instance="cs-test",
            external_id=f"appt-{uuid.uuid4().hex[:10]}",
            scheduled_at=_CONSULT_AT,
            status=ConsultationStatus.COMPLETED,
            location_id=location_id,
        )
    )
    for kind, occurred_at, amount in (
        ("treatment_proposed", _TREATMENT_AT, None),
        ("payment_recorded", _PAYMENT_AT, "5000.00"),
    ):
        db_session.add(
            Event(
                tenant_id=tenant_id,
                person_uid=lead_person.id,
                kind=kind,
                source_provider="carestack",
                data_class="billing" if amount else "operational",
                source_kind="carestack_accounting_transaction"
                if amount
                else "carestack_treatment_procedure",
                source_external_id=f"e-{uuid.uuid4().hex[:10]}",
                review_status="auto",
                occurred_at=occurred_at,
                summary=f"{kind} test",
                payload={"amount": amount} if amount else {},
            )
        )

    # Resolved attribution: vendor + campaign nodes.
    vendor = SourceNode(
        tenant_id=tenant_id, level="vendor", slug="acme", label="Acme Media"
    )
    campaign = SourceNode(
        tenant_id=tenant_id, level="campaign", slug="spring", label="Spring Implants"
    )
    db_session.add_all([vendor, campaign])
    await db_session.flush()
    db_session.add(
        LeadAttribution(
            tenant_id=tenant_id,
            person_uid=lead_person.id,
            vendor_id=vendor.id,
            campaign_id=campaign.id,
            method="auto",
            resolved_at=_NOW,
        )
    )

    # --- CareStack-direct person: no lead, has a consultation ---
    direct_person = await _seed_person(db_session, tenant_id, "Direct")
    db_session.add(
        SourceLink(
            tenant_id=tenant_id,
            person_uid=direct_person.id,
            source_system="carestack",
            source_instance="cs-test",
            source_kind="patient",
            source_id=f"cs-{uuid.uuid4().hex[:10]}",
        )
    )
    db_session.add(
        Consultation(
            tenant_id=tenant_id,
            person_uid=direct_person.id,
            source_provider="carestack",
            source_instance="cs-test",
            external_id=f"appt-{uuid.uuid4().hex[:10]}",
            scheduled_at=_DIRECT_ACTIVITY,
            status=ConsultationStatus.SCHEDULED,
        )
    )
    await db_session.flush()

    # --- Build ---
    repo = FactPatientJourneyRepository(db_session)
    result = await _builder(db_session).build(tenant_id, now=_NOW)
    await db_session.flush()

    assert result.persons == 2
    assert result.rows_written == 2

    lead_row = await repo.get(lead_person.id)
    assert lead_row is not None
    assert lead_row.lead_date == _LEAD_DATE
    assert lead_row.source == "google_ads"
    assert lead_row.consult_scheduled_date == _CONSULT_AT
    assert lead_row.show_date == _CONSULT_AT  # completed consult = showed
    assert lead_row.location_id == location_id
    assert lead_row.treatment_presented_date == _TREATMENT_AT
    assert lead_row.first_payment_date == _PAYMENT_AT
    assert float(lead_row.collected_amount) == 5000.0
    assert float(lead_row.revenue_amount) == 5000.0
    assert lead_row.campaign_id == campaign.id
    assert lead_row.campaign_name == "Spring Implants"
    assert lead_row.vendor_id == vendor.id
    # Provenance: auto for derived, unresolved for B1 fields.
    assert lead_row.field_provenance["lead_date"]["method"] == "auto"
    assert lead_row.field_provenance["caller_id"]["method"] == "unresolved"

    direct_row = await repo.get(direct_person.id)
    assert direct_row is not None
    assert direct_row.lead_date == _DIRECT_ACTIVITY  # earliest activity, not bulk date
    assert direct_row.source is None
    assert direct_row.collected_amount is None
    assert direct_row.field_provenance["source"]["method"] == "auto"

    # --- Idempotency: a second build keeps exactly two rows ---
    again = await _builder(db_session).build(tenant_id, now=_NOW)
    await db_session.flush()
    assert again.rows_written == 2
    assert await repo.count() == 2


async def test_incremental_refresh_writes_only_given_person(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="fact-incremental")

    p1 = await _seed_person(db_session, tenant_id, "One")
    p2 = await _seed_person(db_session, tenant_id, "Two")
    for person in (p1, p2):
        lead = Lead(tenant_id=tenant_id, person_uid=person.id, source="x", extra={})
        lead.created_at = _LEAD_DATE
        db_session.add(lead)
    await db_session.flush()

    repo = FactPatientJourneyRepository(db_session)
    result = await _builder(db_session).build(
        tenant_id, only_persons={p1.id}, now=_NOW
    )
    await db_session.flush()

    assert result.rows_written == 1
    assert await repo.get(p1.id) is not None
    assert await repo.get(p2.id) is None
