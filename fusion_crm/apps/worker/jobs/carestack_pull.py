"""Cloud Run Job entrypoint for scheduled CareStack ingestion."""

from __future__ import annotations

import asyncio

from packages.core.logging import configure_logging, get_logger

from .ingest_scheduled import pull_carestack_for_all_tenants

log = get_logger("worker.carestack_pull")


async def run() -> dict[str, int]:
    configure_logging()
    result = await pull_carestack_for_all_tenants({})
    log.info("carestack_pull.complete", summary=result)
    return result


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
