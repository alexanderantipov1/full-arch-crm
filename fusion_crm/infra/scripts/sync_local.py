"""Drain CareStack + Salesforce provider pulls until the local DB is caught up.

Local-dev convenience: the scheduled worker pulls are page-bounded and the
arq cron only fires hourly (and not while the Mac is asleep), so a fresh
local checkout lags production by hours. This is the on-demand equivalent
of "wait for many cron ticks": it repeatedly runs the same per-tenant pull
the worker uses and stops once a full pass imports nothing new — i.e. the
``ingest.raw_event`` high-watermark (ENG-324) has caught up to "now".

This module is a THIN CLI wrapper. All drain orchestration lives in
``apps.worker.jobs.sync_local_job.run_local_sync`` so the CLI and the
local-gated ``POST /dev/sync-local`` API endpoint share one implementation.

Run:  ``make sync-local``  (or ``python -m infra.scripts.sync_local``)

Flags:
  --tenant <uuid>     only this tenant (default: all tenants)
  --provider {carestack,salesforce,all}   default: all
  --max-passes <int>  safety cap per provider/tenant (default: 12)
  --max-pages <int>   CareStack financial-feed page cap per pass (default: 20)
  --deep              DEEP backfill: scan from --since to exhaustion to
                      refill historical holes (ENG-351). Slower full re-scan;
                      ignores the watermark. CareStack only — Salesforce uses
                      its normal pull.
  --since YYYY-MM-DD  deep-mode lookback anchor (default: today - 30 days)

NOT for production. Reads tenant provider credentials from
``tenant.integration_credential`` exactly like the worker.
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from apps.worker.jobs.sync_local_job import run_local_sync


def _print_summary(summary: dict[str, Any]) -> None:
    for leg in summary["results"]:
        tenant_short = str(leg["tenant_id"])[:8]
        provider = leg["provider"]
        if leg.get("skipped"):
            print(f"  {tenant_short} {provider}: skipped ({leg['skipped']})")
            continue
        flag = "caught up" if leg["caught_up"] else "HIT MAX PASSES"
        print(
            f"  {tenant_short} {provider}: {flag} after {leg['passes']} passes,"
            f" {leg['imported']} rows imported"
        )
    mode = "deep" if summary.get("deep") else "fast"
    since_note = f" since={summary['since']}" if summary.get("since") else ""
    print(
        f"\n=== sync-local ({mode}{since_note}) done in"
        f" {summary['elapsed_seconds']:.1f}s — {summary['total_imported']} rows,"
        f" caught_up={summary['caught_up']} ==="
    )


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Catch the local DB up to provider state."
    )
    parser.add_argument("--tenant", help="Tenant UUID (default: all tenants).")
    parser.add_argument(
        "--provider",
        choices=["carestack", "salesforce", "all"],
        default="all",
    )
    parser.add_argument("--max-passes", type=int, default=12)
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Deep backfill: re-scan from --since to refill historical holes.",
    )
    parser.add_argument(
        "--since",
        help="Deep-mode ISO date (YYYY-MM-DD); default today - 30 days.",
    )
    args = parser.parse_args()

    tenant_ids = [args.tenant] if args.tenant else None
    providers = None if args.provider == "all" else [args.provider]

    summary = await run_local_sync(
        tenant_ids=tenant_ids,
        providers=providers,
        max_pages=args.max_pages,
        max_passes=args.max_passes,
        deep=args.deep,
        since=args.since,
    )
    _print_summary(summary)


if __name__ == "__main__":
    asyncio.run(main())
