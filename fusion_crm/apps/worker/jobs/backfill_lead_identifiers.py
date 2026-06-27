"""ENG-542 — one-shot backfill of phone/email identifiers for lead persons.

Salesforce-lead persons whose shared phone/email was dropped by the matcher
(to avoid the global ``UNIQUE(kind, value)`` violation) still carry the value
in ``ingest.normalized_person_hint``. This job persists those values as
``identity.person_identifier`` rows wherever the value is still FREE — through
``IngestService.backfill_lead_person_identifiers`` → ``IdentityService.
attach_identifier``, which is idempotent and collision-safe.

Values already owned by ANOTHER person (the true shared-contact case) are
reported as ``collision`` and left untouched; the card still surfaces those
siblings via the hint-based household resolver. Full identifier persistence
for shared contacts depends on the ENG-341 constraint rework.

On-demand only — NO cron entry. Re-running is safe (idempotent).

Usage (local):
    python -m apps.worker.jobs.backfill_lead_identifiers [--dry-run] [--limit N]

Usage (enqueue):
    await pool.enqueue_job("backfill_lead_identifiers", dry_run=True)
"""

from __future__ import annotations

import asyncio
import uuid

from packages.core.logging import configure_logging, get_logger
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.ingest.service import IngestService

log = get_logger("worker.backfill_lead_identifiers")


def _system_principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
        context={"actor": "system:backfill_lead_identifiers"},
    )


async def _backfill_tenant(
    tenant_id: TenantId, *, limit: int | None, dry_run: bool
) -> dict[str, int]:
    async with async_session() as session:
        svc = IngestService(session)
        result = await svc.backfill_lead_person_identifiers(
            tenant_id,
            principal=None if dry_run else _system_principal(tenant_id),
            limit=limit,
            dry_run=dry_run,
        )
    log.info(
        "backfill_lead_identifiers.tenant_done",
        tenant_id=str(tenant_id),
        dry_run=dry_run,
        **result,
    )
    return result


async def backfill_lead_identifiers(
    ctx: dict[str, object],
    *,
    tenant_id: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> list[dict[str, object]]:
    """arq entrypoint. Backfills one tenant (``tenant_id``) or all tenants."""
    del ctx
    configure_logging()

    if tenant_id is not None:
        result = await _backfill_tenant(
            TenantId(uuid.UUID(tenant_id)), limit=limit, dry_run=dry_run
        )
        return [{"tenant_id": tenant_id, **result}]

    from packages.tenant.service import TenantService

    async with async_session() as session:
        tenant_ids = [t.id for t in await TenantService(session).list_tenants()]

    out: list[dict[str, object]] = []
    for tid in tenant_ids:
        result = await _backfill_tenant(TenantId(tid), limit=limit, dry_run=dry_run)
        out.append({"tenant_id": str(tid), **result})
    log.info("backfill_lead_identifiers.complete", tenants=len(out))
    return out


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill lead-person phone/email identifiers from hints."
    )
    parser.add_argument("--tenant-id", default=None, help="Single tenant UUID.")
    parser.add_argument("--limit", type=int, default=None, help="Cap candidate rows.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report candidate counts without writing identifiers.",
    )
    args = parser.parse_args()

    asyncio.run(
        backfill_lead_identifiers(
            {},
            tenant_id=args.tenant_id,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
