"""Cloud Run Job entrypoint for the notification-outbox drain.

ENG-498 — production has no always-on arq worker (``fusion-worker`` was
decommissioned in ENG-172), so the messenger's ``drain_notification_outbox``
cron has nowhere to run on prod. This wraps the cron in a Cloud-Run-Job
``run()`` so Cloud Scheduler can drive it on the same pattern as the
ingestion jobs (``salesforce_pull`` / ``carestack_pull``).

One invocation = one drain pass over ``integrations.notification_outbox``:
locks a batch with ``FOR UPDATE SKIP LOCKED`` and posts each row to the
resolved chat provider. Idempotent and safe to run concurrently — the row
lock + ``status == "locked"`` guard make a double-fire a no-op.

The cron owns its own unit of work (it commits per row), so this entry
point only configures logging, invokes the cron with an empty ctx, and
logs the summary.
"""

from __future__ import annotations

import asyncio
from typing import Any

from packages.core.logging import configure_logging, get_logger

from .notification_dispatch import drain_notification_outbox

log = get_logger("worker.notification_drain")


async def run() -> dict[str, int]:
    """Top-level entrypoint for the Cloud Run Job: one drain pass."""
    configure_logging()
    summary = await drain_notification_outbox({})
    log.info("notification_drain.complete", summary=summary)
    return summary


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()


# Typed alias kept for parity with the other ``*_for_all_tenants`` job
# entrypoints, in case a future scheduler wires this through arq.
async def drain_notification_outbox_job(ctx: dict[str, Any]) -> dict[str, int]:
    _ = ctx
    return await run()
