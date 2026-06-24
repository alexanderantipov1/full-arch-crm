"""ENG-507 — journey-metrics service integration (real Postgres).

Seeds fact_patient_journey via the builder, then drives
``AnalyticsMetricsService.journey_metrics`` over a real DB: aggregate counts +
derived metrics (divide-by-zero → None with no spend) and the per-location
filter (aggregate vs scoped). Skips when no test DB is available.
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
from packages.analytics.filters import AnalyticsFilters
from packages.analytics.metrics_service import AnalyticsMetricsService
from packages.attribution.service import AttributionService
from packages.catalog.service import CatalogService
from packages.core.types import TenantId
from packages.identity.models import Person
from packages.identity.service import IdentityService
from packages.ingest.service import IngestService
from packages.interaction.service import InteractionService
from packages.marketing.service import MarketingService
from packages.ops.models import Consultation, ConsultationStatus, Lead
from packages.ops.service import OpsService
from packages.tenant.service import LocationService, TenantService
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session

_LEAD_DATE = datetime(2026, 1, 10, 9, 0, tzinfo=UTC)
_CONSULT_AT = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
_NOW = datetime(2026, 6, 18, 18, 0, tzinfo=UTC)
_WIN_START = datetime(2026, 1, 1, tzinfo=UTC)
_WIN_END = datetime(2026, 2, 1, tzinfo=UTC)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


async def _person(session: AsyncSession, tenant_id: TenantId, name: str) -> Person:
    p = Person(tenant_id=tenant_id, given_name=name, family_name="M", display_name=name)
    session.add(p)
    await session.flush()
    return p


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


def _metrics(session: AsyncSession) -> AnalyticsMetricsService:
    return AnalyticsMetricsService(
        fact_repo=FactPatientJourneyRepository(session),
        marketing=MarketingService(session),
        tenant=TenantService(session),
        location=LocationService(session),
    )


async def test_journey_metrics_aggregate_and_per_location(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="journey-metrics")
    location_id = uuid.uuid4()

    # Person A: lead + completed consult at a location (lead, consult, show).
    a = await _person(db_session, tenant_id, "A")
    la = Lead(tenant_id=tenant_id, person_uid=a.id, source="google_ads", extra={})
    la.created_at = _LEAD_DATE
    db_session.add(la)
    db_session.add(
        Consultation(
            tenant_id=tenant_id,
            person_uid=a.id,
            source_provider="carestack",
            source_instance="cs",
            external_id=f"a-{uuid.uuid4().hex[:8]}",
            scheduled_at=_CONSULT_AT,
            status=ConsultationStatus.COMPLETED,
            location_id=location_id,
        )
    )
    # Person B: lead only, no consult, no location.
    b = await _person(db_session, tenant_id, "B")
    lb = Lead(tenant_id=tenant_id, person_uid=b.id, source="facebook", extra={})
    lb.created_at = _LEAD_DATE
    db_session.add(lb)
    await db_session.flush()

    await _builder(db_session).build(tenant_id, now=_NOW)
    await db_session.flush()

    filters = AnalyticsFilters(
        time_range="custom", custom_start=_WIN_START, custom_end=_WIN_END
    )
    out = await _metrics(db_session).journey_metrics(
        tenant_id, filters, now=_NOW, tz="UTC"
    )

    # Aggregate over both persons.
    assert out.aggregate.leads == 2
    assert out.aggregate.consults == 1
    assert out.aggregate.shows == 1
    assert out.aggregate.patients == 2
    assert out.aggregate.spend is None  # no marketing connected
    # No spend → cost/ROI None; conversions computed.
    assert out.derived.cost_per_lead is None
    assert out.derived.roi is None
    assert out.derived.consult_to_show == 1.0
    assert out.window.preset == "custom"

    # Per-location filter scopes to person A only (the one with this location).
    scoped = AnalyticsFilters(
        time_range="custom",
        custom_start=_WIN_START,
        custom_end=_WIN_END,
        location_id=location_id,
    )
    out_loc = await _metrics(db_session).journey_metrics(
        tenant_id, scoped, now=_NOW, tz="UTC"
    )
    assert out_loc.aggregate.leads == 1
    assert out_loc.aggregate.consults == 1
    assert out_loc.filters.location_id == location_id


async def test_journey_metrics_empty_window_is_all_none(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="journey-empty")
    # No fact rows seeded → zero aggregate, every derived metric None.
    filters = AnalyticsFilters(
        time_range="custom", custom_start=_WIN_START, custom_end=_WIN_END
    )
    out = await _metrics(db_session).journey_metrics(
        tenant_id, filters, now=_NOW, tz="UTC"
    )
    assert out.aggregate.leads == 0
    assert out.aggregate.revenue == 0.0
    assert out.derived.cost_per_lead is None
    assert out.derived.consult_to_show is None
