"""Refresh ``analytics.fact_patient_journey`` (ENG-506).

Projects the per-person revenue-journey read-model from the canonical domains
via :class:`FactPatientJourneyBuilder`. Idempotent — a re-run produces identical
rows and merges provenance (manual > auto > unresolved) rather than clobbering.

**Gated OFF by default. NO cron entry** — these functions are registered in
``WorkerSettings.functions`` so the operator can enqueue them on demand, but
they are intentionally absent from ``WorkerSettings.cron_jobs``, so nothing runs
automatically in production (same posture as ``backfill_marketing_history``).
The analytics read-model is rebuilt deliberately, not on a silent schedule,
until the epic graduates it (ENG-528/529).

Wiring lives here at the app boundary (``packages/analytics`` composes domain
services but the worker owns session + service construction). One
``AsyncSession`` per invocation; the ``async_session()`` context manager commits
on success.
"""

from __future__ import annotations

from uuid import UUID

from packages.actor.service import ActorService
from packages.analytics.fact_builder import FactPatientJourneyBuilder
from packages.analytics.fact_repository import FactPatientJourneyRepository
from packages.attribution.service import AttributionService
from packages.catalog.service import CatalogService
from packages.core.logging import get_logger
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.identity.service import IdentityService
from packages.ingest.service import IngestService
from packages.interaction.service import InteractionService
from packages.marketing.service import MarketingService
from packages.ops.service import OpsService
from packages.tenant.service import TenantService

log = get_logger("worker.fact_patient_journey")


async def refresh_fact_patient_journey(
    ctx: dict,
    *,
    tenant_id: str,
    only_persons: list[str] | None = None,
) -> dict:
    """Backfill or incrementally refresh one tenant's fact rows.

    ``only_persons`` (a list of person_uid strings) restricts the WRITTEN rows
    to those persons (incremental refresh of changed persons); omit it for a
    full backfill. On-demand only — see module docstring.
    """
    tid = TenantId(UUID(tenant_id))
    persons = {UUID(p) for p in only_persons} if only_persons else None
    async with async_session() as session:
        builder = FactPatientJourneyBuilder(
            ops=OpsService(session),
            identity=IdentityService(session),
            interaction=InteractionService(session),
            attribution=AttributionService(session),
            actor=ActorService(session),
            ingest=IngestService(session),
            catalog=CatalogService(session),
            repo=FactPatientJourneyRepository(session),
            marketing=MarketingService(session),
        )
        result = await builder.build(tid, only_persons=persons)
    log.info(
        "fact_patient_journey.refresh.done",
        tenant_id=tenant_id,
        incremental=persons is not None,
        persons=result.persons,
        rows_written=result.rows_written,
        spend_without_leads=result.spend_without_leads,
    )
    return {
        "tenant_id": tenant_id,
        "persons": result.persons,
        "rows_written": result.rows_written,
        "incremental": persons is not None,
        "spend_without_leads": result.spend_without_leads,
    }


async def refresh_fact_patient_journey_for_all_tenants(ctx: dict) -> dict:
    """Full backfill across every registered tenant (on-demand only)."""
    async with async_session() as session:
        tenants = await TenantService(session).list_tenants()
    tenant_ids = [str(t.id) for t in tenants]

    total_persons = 0
    total_rows = 0
    for tenant_id in tenant_ids:
        result = await refresh_fact_patient_journey(ctx, tenant_id=tenant_id)
        total_persons += int(result["persons"])
        total_rows += int(result["rows_written"])
    log.info(
        "fact_patient_journey.refresh_all.done",
        tenants=len(tenant_ids),
        persons=total_persons,
        rows_written=total_rows,
    )
    return {
        "tenants": len(tenant_ids),
        "persons": total_persons,
        "rows_written": total_rows,
    }
