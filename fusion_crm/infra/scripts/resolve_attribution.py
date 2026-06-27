"""Batch lead-attribution resolution (ENG-448 / ENG-449).

Operator-run: seed the default chain vocabulary, then resolve every lead that
has a Salesforce lead link, applying current mapping rules. Idempotent —
re-running is safe; manual overrides (method=manual) are never clobbered.

    set -a && . ./.env && set +a
    PYTHONPATH=. .venv/bin/python infra/scripts/resolve_attribution.py --limit 200
    PYTHONPATH=. .venv/bin/python infra/scripts/resolve_attribution.py --all

The resolution logic lives in ``apps.worker.jobs.resolve_attribution`` so the
operator script and the in-VPC ``fusion-job-resolve-attribution`` Cloud Run Job
(ENG-580) share one implementation and can never drift. Use the Cloud Run Job
for production — agents must never point this script at the prod DB
(root ``CLAUDE.md`` invariant #6).

Requires the ``attribution`` schema to be migrated.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from apps.worker.jobs.resolve_attribution import resolve_attribution


async def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve lead attribution")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--all", action="store_true", help="resolve every lead")
    parser.add_argument(
        "--batch", type=int, default=200, help="commit every N leads"
    )
    args = parser.parse_args()

    summary = await resolve_attribution(
        {}, resolve_all=args.all, limit=args.limit, batch=args.batch
    )
    print(
        f"seeded {summary['seeded']} default chain nodes\n"
        f"resolved {summary['leads']} leads "
        f"(resolved={summary['resolved']} skipped={summary['skipped']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
