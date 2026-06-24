"""Cloud Run Job entrypoint for the consultation-reminder scan.

ENG-498 / ENG-486 — production has no always-on arq worker (ENG-172), so
the ``scan_consultation_reminders`` cron has nowhere to run on prod. This
wraps it in a Cloud-Run-Job ``run()`` so Cloud Scheduler can drive it on
the same pattern as the ingestion jobs.

One invocation = one scan across every tenant for CONFIRMED consultations
starting within the next 15 minutes, emitting a T-15m reminder for each.
At-most-once is guaranteed by the durable dedupe ledger (key = consultation
id), so re-running the same minute (or two concurrent invocations) cannot
double-post.

The cron owns its own unit of work (it commits per tenant), so this entry
point only configures logging, invokes the cron with an empty ctx, and
logs the summary.
"""

from __future__ import annotations

import asyncio
from typing import Any

from packages.core.logging import configure_logging, get_logger

from .consultation_reminders import scan_consultation_reminders

log = get_logger("worker.consult_reminder_scan")


async def run() -> dict[str, int]:
    """Top-level entrypoint for the Cloud Run Job: one reminder scan."""
    configure_logging()
    summary = await scan_consultation_reminders({})
    log.info("consult_reminder_scan.complete", summary=summary)
    return summary


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()


# Typed alias kept for parity with the other ``*_for_all_tenants`` job
# entrypoints, in case a future scheduler wires this through arq.
async def scan_consultation_reminders_job(ctx: dict[str, Any]) -> dict[str, int]:
    _ = ctx
    return await run()
