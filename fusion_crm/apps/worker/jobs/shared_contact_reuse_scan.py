"""Cloud Run Job entrypoint for the shared-contact-reuse alert scan (ENG-555).

Production has no always-on arq worker (ENG-172), so the
``scan_shared_contact_reuse`` cron has nowhere to run on prod. This wraps it in
a Cloud-Run-Job ``run()`` so Cloud Scheduler can drive it on the same pattern as
``consult_reminder_scan`` and the ingestion jobs.

One invocation = one scan across every tenant for OPEN shared-contact-reuse
match candidates created after ``NOTIFICATIONS_CUTOFF_AT``, emitting one alert
per new candidate. At-most-once is guaranteed by the durable dedupe ledger
(key = match-candidate id), so re-running (or two concurrent invocations) cannot
double-post.

INFRA FOLLOW-UP (NOT in this PR — operator handles, like ENG-550): register a
``fusion-job-shared-contact-reuse-scan`` Cloud Run Job in ``deploy_cloud_run.sh``
(reuses the API image) + a Cloud Scheduler trigger (~every 5-10 min).
"""

from __future__ import annotations

import asyncio
from typing import Any

from packages.core.logging import configure_logging, get_logger

from .shared_contact_reuse import scan_shared_contact_reuse

log = get_logger("worker.shared_contact_reuse_scan")


async def run() -> dict[str, int]:
    """Top-level entrypoint for the Cloud Run Job: one reuse-alert scan."""
    configure_logging()
    summary = await scan_shared_contact_reuse({})
    log.info("shared_contact_reuse_scan.complete", summary=summary)
    return summary


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()


# Typed alias kept for parity with the other ``*_for_all_tenants`` job
# entrypoints, in case a future scheduler wires this through arq.
async def scan_shared_contact_reuse_job(ctx: dict[str, Any]) -> dict[str, int]:
    _ = ctx
    return await run()
