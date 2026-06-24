"""Re-backfill ``ops.consultation.status`` from the LATEST raw appointment (ENG-481).

Context: ENG-481 widened the CareStack appointment status remap (more raw
statuses now map to COMPLETED / NO_SHOW / DELETED — see
``packages/ingest/carestack_appointment_service.py::_STATUS_MAP``). Existing
``ops.consultation`` rows were written under the OLD mapping, so their stored
``status`` is stale. This script recomputes every consultation's status from
the LATEST captured raw appointment event using the SAME ``_map_status``
function the live ingest uses (imported, never duplicated) and writes only the
rows whose status actually changes (idempotent).

For each ``ops.consultation`` (matched to its raw appointment by
``consultation.external_id = payload->>'id'``), the latest raw event is the
``ingest.raw_event`` row with ``event_type = 'carestack.appointment.upsert'``
that has the greatest ``received_at`` for that appointment id. Its
``payload->>'status'`` is fed through ``_map_status`` and compared to the
stored status.

``status`` is a varchar / ``StrEnum`` column, so new values (e.g. ``deleted``)
are just strings — NO Alembic migration is required.

CLI::

    PYTHONPATH=. .venv/bin/python infra/scripts/backfill_consultation_status.py          # dry-run
    PYTHONPATH=. .venv/bin/python infra/scripts/backfill_consultation_status.py --apply   # write

Dry-run is the DEFAULT: it prints how many rows would change, broken down by
``from → to``. ``--apply`` writes one tenant at a time with a commit per tenant,
so an interrupted run is resume-safe and re-running converges (idempotent).

Exit codes:
    0  success (dry-run or apply)
    1  uncaught exception

PHI safety: appointment status is non-clinical; logs and stdout carry only
counts and status labels — never patient ids, names, or payload content.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.logging import configure_logging, get_logger
from packages.core.types import TenantId

# Import the SINGLE source-of-truth normalizer + map — never duplicate it.
from packages.ingest.carestack_appointment_service import _map_status

log = get_logger("infra.backfill_consultation_status")

_APPOINTMENT_EVENT_TYPE = "carestack.appointment.upsert"

# Per tenant: the stored status + the latest captured raw appointment status
# string for every CareStack consultation. The latest raw event per appointment
# id is picked by greatest received_at (DISTINCT ON), matched to the
# consultation on external_id = payload->>'id'. Only CareStack consultations
# carry a CareStack appointment id, so the source_provider filter keeps the
# join honest (SF Event consultations are out of scope for this remap).
_SELECT_SQL = """
WITH latest_raw AS (
    SELECT DISTINCT ON (re.payload->>'id')
        re.payload->>'id'     AS appointment_id,
        re.payload->>'status' AS raw_status
    FROM ingest.raw_event re
    WHERE re.tenant_id = :tenant_id
      AND re.event_type = :event_type
      AND re.payload->>'id' IS NOT NULL
    ORDER BY re.payload->>'id', re.received_at DESC
)
SELECT
    c.id            AS consultation_id,
    c.status        AS current_status,
    lr.raw_status   AS raw_status
FROM ops.consultation c
JOIN latest_raw lr ON lr.appointment_id = c.external_id
WHERE c.tenant_id = :tenant_id
  AND c.source_provider = 'carestack'
"""

_UPDATE_SQL = """
UPDATE ops.consultation
   SET status = :new_status,
       updated_at = now()
 WHERE id = :consultation_id
   AND tenant_id = :tenant_id
   AND status IS DISTINCT FROM :new_status
"""


async def _compute_changes(
    session: AsyncSession, tenant_id: TenantId
) -> tuple[list[tuple[Any, str]], Counter[tuple[str, str]]]:
    """Return ``[(consultation_id, new_status)]`` + a ``(from, to)`` counter.

    Only rows whose recomputed status differs from the stored status are
    included, so the result is the exact change set (and the apply UPDATE is a
    no-op for everything else — idempotent).
    """
    rows = (
        await session.execute(
            text(_SELECT_SQL),
            {"tenant_id": str(tenant_id), "event_type": _APPOINTMENT_EVENT_TYPE},
        )
    ).all()
    changes: list[tuple[Any, str]] = []
    transitions: Counter[tuple[str, str]] = Counter()
    for consultation_id, current_status, raw_status in rows:
        new_status = str(_map_status(raw_status))
        if new_status != str(current_status):
            changes.append((consultation_id, new_status))
            transitions[(str(current_status), new_status)] += 1
    return changes, transitions


async def _apply(
    session: AsyncSession, tenant_id: TenantId, changes: list[tuple[Any, str]]
) -> int:
    touched = 0
    for consultation_id, new_status in changes:
        result: Any = await session.execute(
            text(_UPDATE_SQL),
            {
                "consultation_id": consultation_id,
                "tenant_id": str(tenant_id),
                "new_status": new_status,
            },
        )
        touched += int(result.rowcount or 0)
    return touched


def _make_session() -> Any:
    # Resolved at call time so ``--help`` and unit tests do not need a
    # configured environment (same pattern as the other backfills).
    from packages.db.session import async_session

    return async_session()


def _print_transitions(transitions: Counter[tuple[str, str]]) -> None:
    if not transitions:
        print("  (no transitions)")
        return
    for (frm, to), count in sorted(
        transitions.items(), key=lambda kv: (-kv[1], kv[0])
    ):
        print(f"  {frm:>11} -> {to:<11} {count}")


async def run(args: argparse.Namespace) -> int:
    configure_logging()

    async with _make_session() as session:
        tenant_rows = await session.execute(text("SELECT id FROM tenant.tenant"))
        tenant_ids = [TenantId(r.id) for r in tenant_rows]

    total = 0
    grand_transitions: Counter[tuple[str, str]] = Counter()
    for tenant_id in tenant_ids:
        async with _make_session() as session:
            changes, transitions = await _compute_changes(session, tenant_id)
            grand_transitions.update(transitions)
            if args.apply and changes:
                touched = await _apply(session, tenant_id, changes)
                await session.commit()
            else:
                touched = len(changes)
            total += touched
            log.info(
                "backfill_consultation_status.tenant_done",
                tenant_id=str(tenant_id),
                rows=touched,
                applied=args.apply,
            )

    log.info(
        "backfill_consultation_status.complete", rows=total, applied=args.apply
    )
    if not args.apply:
        print(f"\nDry-run: {total} consultation rows would change status.")
        print("By transition (from -> to):")
        _print_transitions(grand_transitions)
        print("\nRe-run with --apply to write. Commit per tenant; idempotent.")
    else:
        print(f"\nUpdated {total} consultation rows.")
        print("By transition (from -> to):")
        _print_transitions(grand_transitions)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute ops.consultation.status from the latest raw CareStack "
            "appointment event (ENG-481 status remap)."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the recomputed statuses (default: dry-run count only).",
    )
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except Exception as exc:  # noqa: BLE001
        log.error("backfill_consultation_status.failed", error=str(exc)[:300])
        return 1


if __name__ == "__main__":
    sys.exit(main())
