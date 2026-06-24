"""Batch lead-attribution resolution as a Cloud Run Job (ENG-580).

Attribution resolution is NOT wired into ingest — a freshly-ingested lead has
no resolved chain until something runs the resolver over it. Today the only
ways a lead gets resolved are (a) the operator-run script
``infra/scripts/resolve_attribution.py``, (b) creating a vendor *claim* (which
re-resolves the matching leads), or (c) the per-lead resolve endpoint. On a
fresh environment where none of those have run, the attribution tree is empty
("No resolved attribution yet") even though the raw leads exist.

This module is the importable, in-VPC twin of that operator script so the same
pass can run as ``fusion-job-resolve-attribution`` under the worker service
account — no laptop / agent direct DB access (root ``CLAUDE.md`` invariant #6).
It seeds the default chain vocabulary, then resolves every lead that has a
Salesforce lead link, applying the current mapping rules.

Idempotent — re-running is safe; manual overrides (``method=manual``) are never
clobbered, and per-batch commits mean a timed-out run simply resumes coverage
on the next execution. ``infra/scripts/resolve_attribution.py`` delegates here
so the two paths can never drift.

Usage (local / operator):
    python -m apps.worker.jobs.resolve_attribution                # first 200
    python -m apps.worker.jobs.resolve_attribution --all          # every lead
    python -m apps.worker.jobs.resolve_attribution --all --tenant-id <uuid>

Usage (enqueue):
    await pool.enqueue_job("resolve_attribution", resolve_all=True)

Requires the ``attribution`` schema to be migrated.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from uuid import UUID

from sqlalchemy import text

from packages.attribution.service import AttributionService
from packages.core.logging import configure_logging, get_logger
from packages.core.types import TenantId
from packages.db.session import async_session

log = get_logger("worker.resolve_attribution")

# Single-tenant phase: the canonical tenant shared by the API principal and the
# operator script. Override per-run with --tenant-id once multi-tenant lands.
_DEFAULT_TENANT_ID = TenantId(UUID("11111111-1111-4111-8111-111111111111"))


async def resolve_attribution(
    ctx: dict[str, object],
    *,
    tenant_id: str | None = None,
    resolve_all: bool = False,
    limit: int = 200,
    batch: int = 200,
) -> dict[str, int]:
    """Seed default nodes, then resolve every Salesforce-lead person.

    Returns a JSON-serialisable summary ``{seeded, leads, resolved, skipped}``.
    """
    tid = TenantId(UUID(tenant_id)) if tenant_id else _DEFAULT_TENANT_ID

    async with async_session() as session:
        service = AttributionService(session)
        seeded = await service.seed_default_nodes(tid)
        log.info("attribution_resolve_seeded", tenant_id=str(tid), nodes=seeded)

        # Every person who has a Salesforce lead.
        stmt = text(
            "select distinct person_uid from identity.source_link "
            "where tenant_id = :t and source_system = 'salesforce' "
            "and source_kind = 'lead'" + ("" if resolve_all else " limit :lim")
        )
        params: dict[str, object] = {"t": str(tid)}
        if not resolve_all:
            params["lim"] = limit
        rows = (await session.execute(stmt, params)).scalars().all()
        person_uids = [r if isinstance(r, UUID) else UUID(str(r)) for r in rows]
        log.info("attribution_resolve_start", tenant_id=str(tid), leads=len(person_uids))

        totals = {"resolved": 0, "skipped": 0}
        for start in range(0, len(person_uids), batch):
            chunk = person_uids[start : start + batch]
            counts = await service.resolve_many(tid, chunk)
            totals["resolved"] += counts["resolved"]
            totals["skipped"] += counts["skipped"]
            await session.commit()
            log.info(
                "attribution_resolve_progress",
                done=start + len(chunk),
                total=len(person_uids),
                resolved=totals["resolved"],
                skipped=totals["skipped"],
            )

    summary = {
        "seeded": seeded,
        "leads": len(person_uids),
        "resolved": totals["resolved"],
        "skipped": totals["skipped"],
    }
    log.info("attribution_resolve_done", **summary)
    return summary


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(
        description="Resolve lead attribution (batch / Cloud Run Job)."
    )
    parser.add_argument("--tenant-id", default=None, help="Single tenant UUID.")
    parser.add_argument("--limit", type=int, default=200, help="Cap leads (ignored with --all).")
    parser.add_argument("--all", action="store_true", help="Resolve every lead.")
    parser.add_argument("--batch", type=int, default=200, help="Commit every N leads.")
    args = parser.parse_args()

    result = asyncio.run(
        resolve_attribution(
            {},
            tenant_id=args.tenant_id,
            resolve_all=args.all,
            limit=args.limit,
            batch=args.batch,
        )
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
