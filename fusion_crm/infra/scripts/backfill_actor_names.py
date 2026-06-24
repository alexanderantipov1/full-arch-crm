"""Repair placeholder ``actor.actor`` display names from data we already hold.

``ActorService.resolve_actor_from_source`` creates an actor with a
fallback name (``"CareStack Provider <id>"`` / ``"SF User <id>"``) when
no ``name_hint`` is available at first observation, and it deliberately
never renames an existing actor on re-pull. The CareStack appointment
sync feed only carries ``providerIds`` (integers, no names), so every
clinical (doctor) actor was born as a ``"CareStack Provider <id>"``
placeholder; a handful of SF users were created before any payload
exposed their ``Owner.Name``.

The real names already live locally — the CareStack provider directory
(``ingest.carestack_provider``, populated by ``backfill_providers.py``)
and the verbatim Salesforce payloads (``ingest.raw_event`` ->
``Owner.Name`` / ``CreatedBy.Name`` / ``LastModifiedBy.Name``). This
script joins them and renames the placeholder actors so names render
everywhere (funnel chain, dashboards, payments) per the development-phase
"show all data clearly" posture.

CLI::

    python3 infra/scripts/backfill_actor_names.py            # dry-run
    python3 infra/scripts/backfill_actor_names.py --apply    # update

Dry-run is the DEFAULT and prints per-tenant candidate counts without
touching data. Re-running is idempotent (``name IS DISTINCT FROM`` guards
every UPDATE) and also refreshes names after a provider/SF-side rename.

Exit codes:
    0  success (dry-run or apply)
    1  uncaught exception (logged before propagation)

Guard-rails: read-only against external systems (works purely on local
tables); structured logs carry ids + counts only — never the names.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.logging import configure_logging, get_logger
from packages.core.types import TenantId

log = get_logger("infra.backfill_actor_names")

# CareStack provider actors → directory name (First Last, then short_name).
_PROVIDER_NAME_EXPR = (
    "COALESCE("
    "  NULLIF(btrim(concat_ws(' ', p.first_name, p.last_name)), ''),"
    "  NULLIF(btrim(p.short_name), '')"
    ")"
)

_PROVIDER_COUNT_SQL = text(
    "SELECT count(*)"
    "  FROM actor.actor a"
    "  JOIN actor.actor_identifier i"
    "    ON i.actor_id = a.id AND i.kind = 'carestack_provider_id'"
    "  JOIN ingest.carestack_provider p"
    "    ON p.provider_carestack_id::text = i.value"
    "   AND p.tenant_id = :tenant_id"
    " WHERE a.tenant_id = :tenant_id"
    "   AND a.name LIKE 'CareStack Provider %'"
    f"   AND {_PROVIDER_NAME_EXPR} IS NOT NULL"
    f"   AND a.name IS DISTINCT FROM {_PROVIDER_NAME_EXPR}"
)

_PROVIDER_UPDATE_SQL = text(
    "UPDATE actor.actor a"
    f"   SET name = {_PROVIDER_NAME_EXPR}, updated_at = now()"
    "  FROM actor.actor_identifier i"
    "  JOIN ingest.carestack_provider p"
    "    ON p.provider_carestack_id::text = i.value"
    "   AND p.tenant_id = :tenant_id"
    " WHERE i.actor_id = a.id AND i.kind = 'carestack_provider_id'"
    "   AND a.tenant_id = :tenant_id"
    "   AND a.name LIKE 'CareStack Provider %'"
    f"   AND {_PROVIDER_NAME_EXPR} IS NOT NULL"
    f"   AND a.name IS DISTINCT FROM {_PROVIDER_NAME_EXPR}"
)

# SF user actors → name from any verbatim payload where the user appears
# as Owner / CreatedBy / LastModifiedBy. One name per user id (most common).
_SF_NAMES_CTE = (
    "WITH sf_names AS ("
    "  SELECT user_id, mode() WITHIN GROUP (ORDER BY name) AS name"
    "    FROM ("
    "      SELECT payload->>'OwnerId' AS user_id, payload->'Owner'->>'Name' AS name"
    "        FROM ingest.raw_event"
    "       WHERE tenant_id = :tenant_id AND payload->'Owner'->>'Name' IS NOT NULL"
    "      UNION ALL"
    "      SELECT payload->>'CreatedById', payload->'CreatedBy'->>'Name'"
    "        FROM ingest.raw_event"
    "       WHERE tenant_id = :tenant_id AND payload->'CreatedBy'->>'Name' IS NOT NULL"
    "      UNION ALL"
    "      SELECT payload->>'LastModifiedById', payload->'LastModifiedBy'->>'Name'"
    "        FROM ingest.raw_event"
    "       WHERE tenant_id = :tenant_id"
    "         AND payload->'LastModifiedBy'->>'Name' IS NOT NULL"
    "    ) s"
    "   WHERE user_id IS NOT NULL AND btrim(coalesce(name, '')) <> ''"
    "   GROUP BY user_id"
    ")"
)

_SF_COUNT_SQL = text(
    _SF_NAMES_CTE
    + " SELECT count(*)"
    "  FROM actor.actor a"
    "  JOIN actor.actor_identifier i"
    "    ON i.actor_id = a.id AND i.kind = 'salesforce_user_id'"
    "  JOIN sf_names n ON n.user_id = i.value"
    " WHERE a.tenant_id = :tenant_id"
    "   AND a.name LIKE 'SF User %'"
    "   AND a.name IS DISTINCT FROM n.name"
)

_SF_UPDATE_SQL = text(
    _SF_NAMES_CTE
    + " UPDATE actor.actor a"
    "   SET name = n.name, updated_at = now()"
    "  FROM actor.actor_identifier i"
    "  JOIN sf_names n ON n.user_id = i.value"
    " WHERE i.actor_id = a.id AND i.kind = 'salesforce_user_id'"
    "   AND a.tenant_id = :tenant_id"
    "   AND a.name LIKE 'SF User %'"
    "   AND a.name IS DISTINCT FROM n.name"
)


def _default_session_factory() -> Any:
    from packages.db.session import async_session

    return async_session()


async def _tenant_ids(session: AsyncSession) -> list[TenantId]:
    rows = await session.execute(text("SELECT id FROM tenant.tenant"))
    return [TenantId(row[0]) for row in rows]


async def run(
    args: argparse.Namespace,
    *,
    session_factory: Any | None = None,
) -> int:
    session_cm = session_factory() if session_factory is not None else _default_session_factory()
    apply = bool(args.apply)
    total_providers = 0
    total_sf = 0

    async with session_cm as session:
        for tenant_id in await _tenant_ids(session):
            params = {"tenant_id": str(tenant_id)}
            provider_n = (
                await session.execute(_PROVIDER_COUNT_SQL, params)
            ).scalar_one()
            sf_n = (await session.execute(_SF_COUNT_SQL, params)).scalar_one()
            if provider_n == 0 and sf_n == 0:
                continue

            log.info(
                "backfill_actor_names.candidates",
                tenant_id=str(tenant_id),
                provider_actors=int(provider_n),
                sf_user_actors=int(sf_n),
                mode="apply" if apply else "dry-run",
            )

            if apply:
                pr = await session.execute(_PROVIDER_UPDATE_SQL, params)
                sr = await session.execute(_SF_UPDATE_SQL, params)
                await session.commit()
                log.info(
                    "backfill_actor_names.updated",
                    tenant_id=str(tenant_id),
                    provider_actors=pr.rowcount,
                    sf_user_actors=sr.rowcount,
                )
            total_providers += int(provider_n)
            total_sf += int(sf_n)

    log.info(
        "backfill_actor_names.done",
        provider_actors=total_providers,
        sf_user_actors=total_sf,
        mode="apply" if apply else "dry-run",
    )
    if not apply and (total_providers or total_sf):
        print(
            f"DRY-RUN: would rename {total_providers} CareStack-provider and "
            f"{total_sf} SF-user placeholder actors. Re-run with --apply."
        )
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rename placeholder actor.actor names from local directory + raw data."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the renames. Default is a dry-run that only counts candidates.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    try:
        return asyncio.run(run(args))
    except Exception:
        log.exception("backfill_actor_names.failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
