"""Cloud Run Job entrypoint for scheduled Salesforce ingestion."""

from __future__ import annotations

import asyncio

from packages.core.logging import configure_logging, get_logger

from .ingest_scheduled import pull_salesforce_for_all_tenants

log = get_logger("worker.salesforce_pull")


async def run() -> dict[str, int]:
    configure_logging()
    result = await pull_salesforce_for_all_tenants({})
    log.info("salesforce_pull.complete", summary=result)
    return result


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
