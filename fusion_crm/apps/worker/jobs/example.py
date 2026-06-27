"""Example async job: process buffered ``RawEvent`` rows.

This is a placeholder for real per-source ingest handlers (CareStack,
Salesforce). It demonstrates the canonical pattern:

  1. Open a session via ``async_session()`` (commits/rolls back automatically).
  2. Resolve the tenant for this job invocation (Phase 1: bootstrap slug).
  3. Call a service. Never touch a repository directly.

Per ENG-128 every per-tenant service method takes ``tenant_id`` as the first
argument. The Phase 1 worker resolves the bootstrap tenant from
``Settings.tenant_default_slug``; Phase 2 (real multi-tenant) extends the
arq job kwargs to carry ``tenant_id`` per enqueue.
"""

from __future__ import annotations

from packages.core.config import get_settings
from packages.core.logging import get_logger
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.ingest.service import IngestService
from packages.tenant.service import TenantService

log = get_logger("worker.ingest")


async def process_unprocessed_events(_ctx: dict, *, batch_size: int = 100) -> dict:
    processed = 0
    settings = get_settings()
    async with async_session() as session:
        # Phase 1: single-tenant. Resolve the bootstrap slug once per job.
        # Phase 2: pass ``tenant_id`` into the arq job kwargs and skip the lookup.
        tenant = await TenantService(session).resolve_default(
            settings.tenant_default_slug
        )
        tenant_id = TenantId(tenant.id)

        svc = IngestService(session)
        events = await svc.list_unprocessed(tenant_id, limit=batch_size)
        for event in events:
            # TODO: dispatch on event.source / event.event_type to a real handler.
            await svc.mark_processed(tenant_id, event.id)
            processed += 1

    log.info("ingest.processed", count=processed, tenant_id=str(tenant_id))
    return {"processed": processed}
