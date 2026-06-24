"""Backfill ``identity.person_identifier.value_match_key`` for legacy rows.

The ``value_match_key`` column (migration ``e2f4a6c8b0d1``) is the canonical
comparison key the resolver/sweep now match on. New rows get it on write (the
``IdentityRepository.add_identifier`` choke point); this script fills it for the
~150k pre-existing rows so the live matcher catches cross-format phones
(``2015550123`` vs ``+12015550123``) without waiting for a re-pull.

Kept OFF the deploy path on purpose (a 150k-row libphonenumber loop must not
gate a prod migration). Idempotent: only touches rows where ``value_match_key
IS NULL``; safe to re-run and to interrupt (commits per batch, resumes by id).

CLI::

    python3 infra/scripts/backfill_phone_match_key.py            # dry-run
    python3 infra/scripts/backfill_phone_match_key.py --apply    # write
    [--batch-size N]

Dry-run (DEFAULT) writes nothing — it prints the total rows needing a key and a
per-kind breakdown only. PHI-free: it never emits raw phone/email values or the
E.164 key (which is itself the phone number).

Exit codes: 0 success; 1 uncaught exception.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.logging import configure_logging, get_logger
from packages.identity.canonical import identifier_match_key

log = get_logger("infra.backfill_phone_match_key")

_DEFAULT_BATCH = 2000


def _default_session_factory() -> Any:
    from packages.db.session import async_session

    return async_session()


async def _count_remaining(session: AsyncSession) -> int:
    row = await session.execute(
        text(
            "SELECT count(*) FROM identity.person_identifier "
            "WHERE value_match_key IS NULL"
        )
    )
    return int(row.scalar_one())


async def _remaining_by_kind(session: AsyncSession) -> list[tuple[str, int]]:
    rows = (
        await session.execute(
            text(
                "SELECT kind, count(*) AS n FROM identity.person_identifier "
                "WHERE value_match_key IS NULL GROUP BY kind ORDER BY n DESC"
            )
        )
    ).all()
    return [(r.kind, int(r.n)) for r in rows]


async def backfill(
    session_factory: Any = _default_session_factory,
    *,
    apply: bool = False,
    batch_size: int = _DEFAULT_BATCH,
) -> dict[str, int]:
    """Backfill missing match keys. Returns a summary dict of counts."""
    updated = 0
    async with session_factory() as session:
        remaining = await _count_remaining(session)
        log.info("backfill.start", remaining=remaining, apply=apply)

        if not apply:
            # PHI-free output: counts only, never raw phone/email values or the
            # E.164 key (which IS the phone number). The operator sees scope,
            # not identifiers.
            print(f"[dry-run] rows needing value_match_key: {remaining}")
            print("[dry-run] breakdown by kind:")
            for kind, n in await _remaining_by_kind(session):
                print(f"  {kind:24} {n}")
            print("[dry-run] re-run with --apply to write.")
            return {"remaining": remaining, "updated": 0}

        while True:
            rows = (
                await session.execute(
                    text(
                        "SELECT id, kind, value FROM identity.person_identifier "
                        "WHERE value_match_key IS NULL ORDER BY id LIMIT :n"
                    ),
                    {"n": batch_size},
                )
            ).all()
            if not rows:
                break
            params = [
                {
                    "id": r.id,
                    "k": identifier_match_key(r.kind, r.value),
                }
                for r in rows
            ]
            await session.execute(
                text(
                    "UPDATE identity.person_identifier "
                    "SET value_match_key = :k WHERE id = :id"
                ),
                params,
            )
            await session.commit()
            updated += len(rows)
            log.info("backfill.batch", updated=updated)

    log.info("backfill.done", updated=updated)
    return {"remaining": remaining, "updated": updated}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    parser.add_argument("--batch-size", type=int, default=_DEFAULT_BATCH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parse_args(argv)
    try:
        summary = asyncio.run(
            backfill(apply=args.apply, batch_size=args.batch_size)
        )
    except Exception:  # noqa: BLE001 - top-level script guard
        log.exception("backfill.failed")
        return 1
    log.info("backfill.summary", **summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
