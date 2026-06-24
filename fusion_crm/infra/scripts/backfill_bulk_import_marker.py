"""Mark the bulk-loaded CareStack patient base in ``source_link.meta`` (ENG-480).

Context (verified on real data 2026-06-16): the CareStack patient pull in
2026-05 brought in ~55k patient records at once. Of the CareStack-direct
persons (a ``carestack/patient`` source link but NO ``ops.lead``), ~27k have
**zero activity in any of our systems** — no consultation, no
``interaction.event``, no opportunity. The CareStack patient object exposes no
creation/registration date, so the only timestamp we hold for them is our pull
date (``source_link.first_seen_at`` = 2026-05), which is meaningless for funnel
timing. The operator's read: that activity-less cohort is a purchased / loaded
database from another clinic, not organic funnel leads.

This script stamps an **immutable provenance marker** onto those persons'
CareStack patient ``source_link.meta`` so they are identifiable as a bulk load
everywhere (not just inside the Full Funnel read model)::

    {"load_origin": "bulk_import", "batch": "carestack_2026_05", "no_activity": true}

The marker is provenance only. It does NOT set the funnel date — the Full Funnel
v2 read model dates a CareStack-direct person by their earliest real activity
(consultation / payment) and falls back to 2025-01-01 only when there is none,
so a person who later "wakes up" keeps the provenance marker but moves to a real
date automatically.

Scope: ``carestack/patient`` source links whose person has NO ``ops.lead`` AND
no consultation / interaction event / opportunity. Idempotent — only rows whose
``meta.load_origin`` is not already ``bulk_import`` are touched.

CLI::

    python3 infra/scripts/backfill_bulk_import_marker.py            # dry-run
    python3 infra/scripts/backfill_bulk_import_marker.py --apply    # write

Dry-run is the DEFAULT and only counts candidates. ``--apply`` writes one
tenant at a time with a commit per tenant, so an interrupted run is resume-safe.

Exit codes:
    0  success (dry-run or apply)
    1  uncaught exception

PHI safety: CareStack patient links are non-clinical; logs carry only counts
and the static batch label — never names or payload content.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.logging import configure_logging, get_logger
from packages.core.types import TenantId

log = get_logger("infra.backfill_bulk_import_marker")

# Immutable provenance marker merged into ``source_link.meta``.
_MARKER: dict[str, object] = {
    "load_origin": "bulk_import",
    "batch": "carestack_2026_05",
    "no_activity": True,
}

# The activity-less CareStack-direct cohort: a carestack/patient link whose
# person has NO lead and NO consultation / event / opportunity, and is not
# already marked. Shared by the dry-run count and the apply UPDATE.
_PREDICATE = """
        s.tenant_id = :tenant_id
    AND s.source_system = 'carestack'
    AND s.source_kind = 'patient'
    AND NOT EXISTS (SELECT 1 FROM ops.lead l WHERE l.person_uid = s.person_uid)
    AND NOT EXISTS (
        SELECT 1 FROM ops.consultation c WHERE c.person_uid = s.person_uid)
    AND NOT EXISTS (
        SELECT 1 FROM interaction.event e WHERE e.person_uid = s.person_uid)
    AND NOT EXISTS (
        SELECT 1 FROM ops.opportunity o WHERE o.person_uid = s.person_uid)
    AND (s.meta->>'load_origin') IS DISTINCT FROM 'bulk_import'
"""


async def _count_pending(session: AsyncSession, tenant_id: TenantId) -> int:
    row = await session.execute(
        text(f"SELECT count(*) FROM identity.source_link s WHERE {_PREDICATE}"),
        {"tenant_id": str(tenant_id)},
    )
    return int(row.scalar_one())


async def _apply(session: AsyncSession, tenant_id: TenantId, marker: str) -> int:
    result: Any = await session.execute(
        text(
            "UPDATE identity.source_link s"
            "   SET meta = COALESCE(s.meta, '{}'::jsonb) || CAST(:marker AS jsonb)"
            f" WHERE {_PREDICATE}"
        ),
        {"tenant_id": str(tenant_id), "marker": marker},
    )
    return int(result.rowcount or 0)


def _make_session() -> Any:
    # Resolved at call time so ``--help`` and unit tests do not need a
    # configured environment (same pattern as the other backfills).
    from packages.db.session import async_session

    return async_session()


async def run(args: argparse.Namespace) -> int:
    configure_logging()
    marker = json.dumps(_MARKER)

    async with _make_session() as session:
        tenant_rows = await session.execute(text("SELECT id FROM tenant.tenant"))
        tenant_ids = [TenantId(r.id) for r in tenant_rows]

    total = 0
    for tenant_id in tenant_ids:
        async with _make_session() as session:
            if args.apply:
                touched = await _apply(session, tenant_id, marker)
                await session.commit()
            else:
                touched = await _count_pending(session, tenant_id)
            total += touched
            log.info(
                "backfill_bulk_import_marker.tenant_done",
                tenant_id=str(tenant_id),
                rows=touched,
                applied=args.apply,
            )

    log.info(
        "backfill_bulk_import_marker.complete", rows=total, applied=args.apply
    )
    if not args.apply:
        print(f"\nDry-run: {total} source_link rows would be marked bulk_import.")
        print("Re-run with --apply to write. Commit per tenant; resume-safe.")
    else:
        print(f"\nMarked {total} source_link rows as bulk_import.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mark the bulk-loaded CareStack patient base in source_link.meta."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the marker (default: dry-run count only).",
    )
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except Exception as exc:  # noqa: BLE001
        log.error("backfill_bulk_import_marker.failed", error=str(exc)[:300])
        return 1


if __name__ == "__main__":
    sys.exit(main())
