"""Worker dependency health check.

Intended for local supervisors and container health checks. It verifies the
worker's two required dependencies without reading application data.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from arq.connections import RedisSettings, create_pool
from sqlalchemy import text

from packages.core.config import get_settings
from packages.db.session import async_session


async def check_postgres() -> None:
    async with async_session() as session:
        await session.execute(text("SELECT 1"))


async def check_redis() -> None:
    redis = await create_pool(RedisSettings.from_dsn(str(get_settings().redis_url)))
    try:
        await redis.ping()
    finally:
        await redis.aclose()


async def run_checks() -> dict[str, Any]:
    checks: dict[str, str] = {}
    errors: dict[str, str] = {}

    for name, fn in (
        ("postgres", check_postgres),
        ("redis", check_redis),
    ):
        try:
            await fn()
        except Exception as exc:  # noqa: BLE001 - health output must be stable.
            checks[name] = "failed"
            errors[name] = type(exc).__name__
        else:
            checks[name] = "ok"

    status = "ok" if all(value == "ok" for value in checks.values()) else "failed"
    return {"status": status, "checks": checks, "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser(description="Check worker dependencies.")
    parser.add_argument("--check", action="store_true", help="Run dependency checks.")
    args = parser.parse_args()
    if not args.check:
        parser.error("--check is required")

    result = asyncio.run(run_checks())
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
