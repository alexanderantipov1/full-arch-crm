"""B1 enablement backfills for ``analytics.fact_patient_journey`` (ENG-509/510).

Two on-demand backfills that materialise the dimension actors the fact builder
surfaces:

* ``link_carestack_providers_to_actors`` — links every CareStack directory
  provider to an ``actor.actor`` (kind ``carestack_provider_id``, clinical) with
  a proper "Dr First Last" name. The fact builder's ``doctor_id`` comes from the
  clinical responsibility actor, which shares the SAME actor row (the
  ``actor_identifier`` ``(kind, value)`` is workspace-unique), so this backfill
  gives the doctor dimension a clean display name and links providers not yet
  seen on a consult (ENG-510).

The SF caller/coordinator actors (ENG-509) are backfilled inline by the builder
itself (``FactPatientJourneyBuilder._resolve_owner_actors``) — they need no
separate job because the builder resolves the small set of distinct SF owner ids
on every run.

**Gated OFF by default. NO cron entry** — registered in
``WorkerSettings.functions`` for on-demand operator enqueue only, same posture
as ``refresh_fact_patient_journey``. ``ingest`` may not import ``actor`` (cross-
package matrix), so the actor write is wired here at the worker boundary.
Logs stay PHI-free: provider names are PII — only counts + ids are logged.
"""

from __future__ import annotations

from uuid import UUID

from packages.actor.service import ActorService
from packages.core.logging import get_logger
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.ingest.service import IngestService
from packages.tenant.service import TenantService

log = get_logger("worker.fact_patient_journey_enablement")

_SOURCE_PROVIDER = "carestack"
_SOURCE_INSTANCE = "carestack-main"


async def link_carestack_providers_to_actors(
    ctx: dict, *, tenant_id: str
) -> dict:
    """Link every CareStack directory provider → ``actor.actor`` (ENG-510).

    Idempotent: ``ActorService.resolve_actor_from_source`` finds the existing
    actor by ``(carestack_provider_id, value)`` or creates it, seeding the
    display name on first creation. Returns the count linked.
    """
    tid = TenantId(UUID(tenant_id))
    async with async_session() as session:
        ingest = IngestService(session)
        actor = ActorService(session)
        directory = await ingest.list_carestack_provider_directory(tid)
        linked = 0
        for provider_id, display_name in directory.items():
            await actor.resolve_actor_from_source(
                tid,
                source_provider=_SOURCE_PROVIDER,
                source_instance=_SOURCE_INSTANCE,
                external_id=str(provider_id),
                name_hint=display_name,
                role_hint="doctor",
            )
            linked += 1
    log.info(
        "fact_patient_journey.providers_linked",
        tenant_id=tenant_id,
        providers=len(directory),
        linked=linked,
    )
    return {"tenant_id": tenant_id, "providers": len(directory), "linked": linked}


async def link_carestack_providers_for_all_tenants(ctx: dict) -> dict:
    """Run the provider→actor backfill across every registered tenant."""
    async with async_session() as session:
        tenants = await TenantService(session).list_tenants()
    tenant_ids = [str(t.id) for t in tenants]

    total_linked = 0
    for tenant_id in tenant_ids:
        result = await link_carestack_providers_to_actors(ctx, tenant_id=tenant_id)
        total_linked += int(result["linked"])
    log.info(
        "fact_patient_journey.providers_linked_all",
        tenants=len(tenant_ids),
        linked=total_linked,
    )
    return {"tenants": len(tenant_ids), "linked": total_linked}
