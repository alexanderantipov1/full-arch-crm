"""Re-project stranded Salesforce Tasks into the funnel timeline (ENG-462).

A SF Task whose ``WhoId`` lead/contact was not yet linked when the task
was first imported gets skipped, and the ``_import_records``
``LastModifiedDate`` change-guard then blocks any retry once the link
appears — so the task is captured in ``ingest.raw_event`` but never
projected into ``interaction.event`` (the Funnel chain). ~9% of tasks
were stranded this way.

This sweep reads the latest captured raw payload per task since a window
(no Salesforce round-trip) and re-runs the emit path
(``SfTaskIngestService.reproject_tasks_from_raw``). Idempotent: tasks
already projected dedup to no-ops; only now-linkable orphans add events.

CLI::

    # dry-run (default) — count candidate tasks per tenant, no writes
    python3 infra/scripts/reproject_sf_tasks.py [--days 400]

    # apply — re-project and commit per tenant
    python3 infra/scripts/reproject_sf_tasks.py --apply [--days 400]

``--days`` bounds the window by ``raw_event.received_at`` (default 400 —
effectively "all captured"). For routine catch-up a small window (e.g.
``--days 2``) is enough; the scheduled pull already runs a short-window
reconciliation each tick.

Exit codes:
    0  success (dry-run or apply)
    1  uncaught exception (logged before propagation)

Guard-rails: read-only against Salesforce (works purely on stored raw);
logs carry ids + counts only — never names or clinical content.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.worker.jobs.ingest_scheduled import _build_responsibility_resolver
from packages.core.logging import configure_logging, get_logger
from packages.core.types import TenantId
from packages.ingest.sf_task_service import SfTaskIngestService

log = get_logger("infra.reproject_sf_tasks")


class _UnusedSfClient:
    """Placeholder — ``reproject_tasks_from_raw`` never calls Salesforce."""

    async def soql(self, query: str) -> dict[str, Any]:  # pragma: no cover
        raise RuntimeError("reproject_sf_tasks must not call Salesforce")


def _default_session_factory() -> Any:
    from packages.db.session import async_session

    return async_session()


async def _tenant_ids(session: AsyncSession) -> list[TenantId]:
    rows = await session.execute(text("SELECT id FROM tenant.tenant"))
    return [TenantId(row[0]) for row in rows]


async def run(
    args: argparse.Namespace,
    *,
    session_factory: Any | None = None,
) -> int:
    since = datetime.now(UTC) - timedelta(days=args.days)
    apply = bool(args.apply)
    session_cm = (
        session_factory() if session_factory is not None else _default_session_factory()
    )
    total_candidates = 0
    total_imported = 0

    async with session_cm as session:
        for tenant_id in await _tenant_ids(session):
            svc = SfTaskIngestService(
                session=session,
                sf_client=_UnusedSfClient(),  # type: ignore[arg-type]
                responsibility_resolver=_build_responsibility_resolver(session),
            )
            if not apply:
                candidates = await session.execute(
                    text(
                        "SELECT count(DISTINCT external_id) FROM ingest.raw_event"
                        " WHERE tenant_id = :t"
                        "   AND event_type = 'salesforce.task.upsert'"
                        "   AND received_at >= :since"
                    ),
                    {"t": str(tenant_id), "since": since},
                )
                n = int(candidates.scalar_one())
                if n:
                    log.info(
                        "reproject_sf_tasks.candidates",
                        tenant_id=str(tenant_id),
                        candidate_tasks=n,
                    )
                total_candidates += n
                continue

            result = await svc.reproject_tasks_from_raw(tenant_id, since=since)
            await session.commit()
            total_imported += result.imported_count
            if result.queried_count:
                log.info(
                    "reproject_sf_tasks.applied",
                    tenant_id=str(tenant_id),
                    queried=result.queried_count,
                    resolved=result.imported_count,
                    skipped=result.skipped_count,
                )

    log.info(
        "reproject_sf_tasks.done",
        mode="apply" if apply else "dry-run",
        candidate_tasks=total_candidates,
        resolved=total_imported,
        days=args.days,
    )
    if not apply and total_candidates:
        print(
            f"DRY-RUN: {total_candidates} candidate task(s) in the last "
            f"{args.days}d. Re-run with --apply to project orphans."
        )
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Re-project stranded Salesforce Tasks into the funnel timeline."
    )
    parser.add_argument("--apply", action="store_true", help="Write (default: dry-run).")
    parser.add_argument(
        "--days",
        type=int,
        default=400,
        help="Window by raw_event.received_at (default 400 ≈ all captured).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    try:
        return asyncio.run(run(args))
    except Exception:
        log.exception("reproject_sf_tasks.failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
