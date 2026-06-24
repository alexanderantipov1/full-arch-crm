"""One-off cleanup of tick-duplicate ``ingest.raw_event`` rows (ENG-381).

Before ENG-381 the scheduled pullers re-read fixed provider windows every
~90s tick and captured every row unconditionally, accumulating millions of
byte-identical raw rows (e.g. 406,592 rows for 539 opportunities). The
pullers are fixed (watermark + capture change-guard); this script repairs
the data already on disk.

Duplicate definition — rows sharing the SAME logical version:

    (tenant_id, event_type, external_id,
     COALESCE(payload->>'<stamp key>', md5(payload::text)))

i.e. the provider modified-stamp when the payload carries one
(``LastModifiedDate`` for Salesforce, ``lastUpdatedOn`` for CareStack),
falling back to a payload-content hash for stamp-less feeds (payment
summary snapshots, pre-ENG-381 lead payloads). Within each group the
NEWEST row (``received_at`` desc, ``id`` desc) is kept.

Keep-rules (never deleted, even when duplicate):

* rows referenced by ``interaction.event.source_event_id``;
* rows referenced by ``ingest.normalized_person_hint.raw_event_id``.

CLI:

    python3 infra/scripts/cleanup_raw_event_duplicates.py            # dry-run
    python3 infra/scripts/cleanup_raw_event_duplicates.py --apply    # delete
    python3 infra/scripts/cleanup_raw_event_duplicates.py \
        --event-type salesforce.opportunity.upsert --apply

Dry-run is the DEFAULT and prints per-event-type delete candidates
without touching data. ``--apply`` deletes in batches with a commit per
batch so a mid-run interruption loses nothing and resumes safely (the
script is idempotent — re-running finds only the remaining duplicates).

Exit codes:
    0  success (dry-run or apply)
    1  uncaught exception

PHI safety: logs carry only event types, counts, and row ids — never
payload content.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.logging import configure_logging, get_logger

log = get_logger("infra.cleanup_raw_event_duplicates")

_DEFAULT_BATCH_SIZE = 10_000

# Scheduled feeds repaired by ENG-381, with the payload key that carries
# the provider-side modified stamp. ``None`` → content-hash fallback only
# (the COALESCE in the SQL handles both shapes uniformly).
DEFAULT_EVENT_TYPE_STAMP_KEYS: dict[str, str | None] = {
    "lead.pull": "LastModifiedDate",
    "salesforce.event.upsert": "LastModifiedDate",
    "salesforce.task.upsert": "LastModifiedDate",
    "salesforce.opportunity.upsert": "LastModifiedDate",
    "salesforce.case.upsert": "LastModifiedDate",
    "carestack.patient.upsert": "lastUpdatedOn",
    "carestack.appointment.upsert": "lastUpdatedOn",
    "carestack.treatment_procedure.upsert": "lastUpdatedOn",
    "carestack.invoice.upsert": "lastUpdatedOn",
    "carestack.accounting_transaction.upsert": "lastUpdatedOn",
    "carestack.payment_summary.snapshot": None,
}

# One window-function pass per event type. ``md5(payload::text)`` is a
# stable content fingerprint because Postgres normalises jsonb key order.
# The two EXCEPT legs enforce the keep-rules.
_DUPLICATE_IDS_SQL = text(
    """
    WITH ranked AS (
        SELECT id,
               row_number() OVER (
                   PARTITION BY tenant_id, event_type, external_id,
                                COALESCE(payload ->> :stamp_key,
                                         md5(payload::text))
                   ORDER BY received_at DESC, id DESC
               ) AS rn
        FROM ingest.raw_event
        WHERE event_type = :event_type
    )
    SELECT id FROM ranked WHERE rn > 1
    EXCEPT
    SELECT source_event_id FROM interaction.event
    WHERE source_event_id IS NOT NULL
    EXCEPT
    SELECT raw_event_id FROM ingest.normalized_person_hint
    """
)

_DELETE_BATCH_SQL = text(
    "DELETE FROM ingest.raw_event WHERE id = ANY(:ids)"
)


async def find_duplicate_ids(
    session: AsyncSession,
    *,
    event_type: str,
    stamp_key: str | None,
) -> list[UUID]:
    """Return ids of deletable duplicate rows for one event type."""
    result = await session.execute(
        _DUPLICATE_IDS_SQL,
        {
            "event_type": event_type,
            # COALESCE needs a non-null key name; an impossible key makes
            # the stamp leg always NULL → pure content-hash grouping.
            "stamp_key": stamp_key or "__no_stamp_key__",
        },
    )
    return [row[0] for row in result.fetchall()]


async def cleanup_duplicates(
    session: AsyncSession,
    *,
    event_types: dict[str, str | None],
    apply: bool,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    commit: Callable[[], Awaitable[None]] | None = None,
) -> dict[str, int]:
    """Find (and with ``apply=True`` delete) duplicates per event type.

    Returns ``{event_type: candidate_count}``. With ``apply=True`` the
    deletes run in ``batch_size`` chunks; ``commit`` (the caller's
    unit-of-work flush — the CLI passes ``session.commit``) runs after
    each chunk. ``commit=None`` leaves the transaction to the caller,
    which is what tests use so the fixture rollback stays hermetic.
    """
    deleted_per_type: dict[str, int] = {}
    for event_type, stamp_key in event_types.items():
        ids = await find_duplicate_ids(
            session, event_type=event_type, stamp_key=stamp_key
        )
        deleted_per_type[event_type] = len(ids)
        log.info(
            "cleanup_raw_event_duplicates.candidates",
            event_type=event_type,
            count=len(ids),
            apply=apply,
        )
        if not apply or not ids:
            continue
        for start in range(0, len(ids), batch_size):
            chunk = ids[start : start + batch_size]
            await session.execute(_DELETE_BATCH_SQL, {"ids": chunk})
            if commit is not None:
                await commit()
            log.info(
                "cleanup_raw_event_duplicates.batch_deleted",
                event_type=event_type,
                deleted=start + len(chunk),
                total=len(ids),
            )
    return deleted_per_type


def _default_session_factory() -> Any:
    # Resolved at call time so ``--help`` and unit tests do not need a
    # configured environment (same pattern as backfill_payment_summary).
    from packages.db.session import async_session

    return async_session()


async def run(args: argparse.Namespace) -> int:
    if args.event_type:
        unknown = [
            et for et in args.event_type if et not in DEFAULT_EVENT_TYPE_STAMP_KEYS
        ]
        if unknown:
            log.error(
                "cleanup_raw_event_duplicates.unknown_event_type",
                unknown=unknown,
                known=sorted(DEFAULT_EVENT_TYPE_STAMP_KEYS),
            )
            return 1
        event_types = {
            et: DEFAULT_EVENT_TYPE_STAMP_KEYS[et] for et in args.event_type
        }
    else:
        event_types = dict(DEFAULT_EVENT_TYPE_STAMP_KEYS)

    async with _default_session_factory() as session:
        counts = await cleanup_duplicates(
            session,
            event_types=event_types,
            apply=args.apply,
            batch_size=args.batch_size,
            # Commit per batch: a one-off repair script owns its unit of
            # work (same exception as the streaming backfills).
            commit=session.commit,
        )

    total = sum(counts.values())
    mode = "deleted" if args.apply else "would delete (dry-run)"
    print(f"\n{mode}: {total} duplicate raw_event rows")
    for event_type, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {event_type}: {count}")
    if not args.apply and total:
        print("\nRe-run with --apply to delete. Batches commit as they go.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete tick-duplicate ingest.raw_event rows (ENG-381).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete. Default is a dry-run report.",
    )
    parser.add_argument(
        "--event-type",
        action="append",
        help=(
            "Limit to one event type (repeatable). Default: all feeds "
            "covered by ENG-381."
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=_DEFAULT_BATCH_SIZE,
        help=f"Rows per DELETE batch/commit (default {_DEFAULT_BATCH_SIZE}).",
    )
    args = parser.parse_args()
    configure_logging()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
