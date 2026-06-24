"""Cloud Run Job entrypoint for scheduled CareStack procedure-code sync.

ENG-420 / ENG-538 — populates ``catalog.procedure_code`` once per tick by
resolving each needed ``procedureCodeId`` through the CareStack **by-id**
endpoint (``GET /api/v1.0/procedure-codes/{id}``) and upserting it. The
catalog is small and static (CDT changes annually); this job runs on a
low-frequency cadence (weekly).

ENG-538: the flat ``GET /api/v1.0/procedure-codes`` LIST endpoint is broken
on the real account, so by-id is the primary source. The work-list is the
distinct set of ``procedureCodeId`` values observed in captured
``carestack.treatment_procedure.upsert`` raw_events — enumerated per tenant
through ``IngestService`` (``catalog`` may not read ``ingest``). New/changed
codes are surfaced as drift.

Read-only against CareStack. Idempotent: re-running on unchanged data
is a no-op (only NEW / CHANGED rows are written).

Boundary contract: this entry point owns the unit of work. The catalog
service flushes but never commits/rolls back — on success the job
commits, on any exception it rolls back so the partial upsert is not
persisted.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from packages.catalog.service import CatalogService
from packages.core.exceptions import PlatformError
from packages.core.logging import configure_logging, get_logger
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.ingest.service import IngestService
from packages.integrations.carestack import CareStackClient
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)

log = get_logger("worker.carestack_procedure_codes_pull")


async def _pull_for_tenant(tenant_id_str: str) -> str:
    """Run the catalog sync once for one tenant. Returns
    ``'ok' | 'skipped' | 'failed'`` so the loop can keep a clean summary
    across all tenants.

    Owns the unit of work — commits on success, rolls back on error.
    """
    tenant_id = TenantId(UUID(tenant_id_str))
    async with async_session() as session:
        cred_svc = IntegrationCredentialService(session)
        try:
            payload = await cred_svc.read_for(
                tenant_id, "carestack", "password_grant"
            )
        except (NoCredentialError, PlatformError):
            log.info(
                "carestack.procedure_codes.skipped_credential",
                tenant_id=str(tenant_id),
            )
            return "skipped"

        cs_client = CareStackClient.from_credential(payload)
        try:
            # Work-list: distinct procedureCodeId ids observed in captured
            # treatment-procedure raw_events (ENG-538). ``catalog`` may not
            # read ``ingest``, so the boundary enumerates here.
            code_ids = await IngestService(
                session
            ).distinct_treatment_procedure_code_ids(tenant_id)
            svc = CatalogService(session)
            try:
                outcome = await svc.sync_procedure_codes_by_id(
                    cs_client, code_ids
                )
            except Exception:
                # The service flushes but never commits/rolls back; the
                # boundary owns the unit of work, so roll the partial
                # upsert back here before re-raising up to the per-tenant
                # error isolator in ``run``.
                await session.rollback()
                raise
        finally:
            close = getattr(cs_client, "close", None)
            if callable(close):
                maybe_awaitable = close()
                if maybe_awaitable is not None and hasattr(
                    maybe_awaitable, "__await__"
                ):
                    await maybe_awaitable

        log.info(
            "carestack.procedure_codes.imported",
            tenant_id=str(tenant_id),
            requested=outcome.requested,
            resolved=outcome.resolved,
            unresolved=len(outcome.unresolved),
            imported=outcome.imported,
            new_codes=len(outcome.new_codes),
            changed=len(outcome.changed),
        )
        # Success: commit the catalog upserts before returning so the
        # Cloud Run Job exits cleanly.
        await session.commit()
        return "ok"


async def _list_tenant_ids() -> list[str]:
    from packages.tenant.service import TenantService

    async with async_session() as session:
        tenant_rows = await TenantService(session).list_tenants()
        return [str(t.id) for t in tenant_rows]


async def run() -> dict[str, int]:
    """Top-level entrypoint for the Cloud Run Job.

    Iterates every tenant, runs the catalog sync per-tenant, and emits a
    summary log line. The catalog is workspace-wide so multiple tenants
    write to the same rows — that is intentional and idempotent.
    """
    configure_logging()
    summary: dict[str, int] = {
        "tenants": 0,
        "procedure_codes_ok": 0,
        "procedure_codes_skipped": 0,
        "procedure_codes_failed": 0,
    }
    tenant_ids = await _list_tenant_ids()
    if not tenant_ids:
        log.info("carestack.procedure_codes.no_tenants")
        return summary

    for tenant_id_str in tenant_ids:
        summary["tenants"] += 1
        try:
            outcome = await _pull_for_tenant(tenant_id_str)
        except Exception as exc:  # noqa: BLE001 — Job must not crash
            log.error(
                "carestack.procedure_codes.error",
                tenant_id=tenant_id_str,
                error=str(exc),
            )
            summary["procedure_codes_failed"] += 1
            continue
        if outcome == "ok":
            summary["procedure_codes_ok"] += 1
        elif outcome == "skipped":
            summary["procedure_codes_skipped"] += 1
        else:
            summary["procedure_codes_failed"] += 1

    log.info("carestack.procedure_codes.complete", summary=summary)
    return summary


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()


# A typed alias kept for parity with the other ``*_for_all_tenants`` job
# entrypoints in this package, in case ENG-419's funnel analytics or a
# future scheduler wires this through arq.
async def pull_procedure_codes_for_all_tenants(ctx: dict[str, Any]) -> dict[str, int]:
    _ = ctx
    return await run()
