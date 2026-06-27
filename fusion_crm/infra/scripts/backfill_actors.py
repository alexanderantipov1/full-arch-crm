"""Backfill ``actor.actor`` from existing distinct SF owners + CareStack
providers (ENG-415).

Seeds the actor catalogue from rows we already have on file so every
responsible party referenced by ``ops.lead``, ``ops.opportunity``, and
the CareStack provider directory resolves to an Actor.

Sources read (read-only):

1. ``ops.lead.extra->>'owner_id'`` (SF Users + Groups) and
   ``extra->>'owner_name'`` (back-named by ENG-408).
2. ``ops.opportunity.extra->>'owner_id'`` and
   ``extra->>'owner_name'`` (back-named by
   ``backfill_opportunity_owner_names.py``).
3. ``ingest.carestack_provider`` (CareStack providers; the local
   directory mirror populated by ``backfill_providers.py``).
4. SF Tasks whose subject begins with ``"sofia ai call"`` → Sofia AI
   actor (one row, ``actor_type="ai"``).

Targets written via ``ActorService.resolve_actor_from_source``:

- SF ``005…`` → ``human`` actor + ``salesforce_user_id`` identifier.
- SF ``00G…`` → ``system`` actor + ``salesforce_group_id`` identifier.
- CareStack provider → ``human`` actor + ``carestack_provider_id``.
- Sofia AI → single ``ai`` actor + ``sofia_ai`` identifier.

CLI::

    python3 infra/scripts/backfill_actors.py \\
        --tenant-id <uuid> \\
        [--apply] \\
        [--include-leads] \\
        [--include-opportunities] \\
        [--include-providers] \\
        [--include-sofia]

Default (no scope flags) runs ALL sources. Dry-run by default; ``--apply``
commits per source bucket. Idempotent — re-runs hit the existing
``actor_identifier`` rows and return them unchanged.

Exit codes:
    0  success (including dry-run)
    1  uncaught exception

Hard rules:

- No SF / CareStack writes. This script reads from the local
  Postgres only (plus, when Sofia is enabled, a single SF probe
  to confirm the subject exists — actually NOT, we just seed Sofia
  unconditionally because the actor type is system-defined).
- Names are not PHI, but the structured log lines only carry counts
  + the SF id, never the resolved display name.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import select

from packages.actor.service import ActorService
from packages.core.logging import configure_logging, get_logger
from packages.core.types import TenantId
from packages.db.tenant_scope import for_tenant
from packages.ingest.models import CareStackProvider
from packages.ops.models import Lead, Opportunity

log = get_logger("infra.backfill_actors")

_SF_INSTANCE = "salesforce-main"
_CS_INSTANCE = "carestack-main"
_SOFIA_INSTANCE = "salesforce-main"


def _default_session_factory() -> Any:
    from packages.db.session import async_session

    return async_session()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seed actor.actor from existing SF owners, CareStack providers, "
            "and the Sofia AI subject. Dry-run by default."
        ),
    )
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Commit each source bucket after resolving. Without this flag, "
            "the script counts what it would resolve and exits."
        ),
    )
    parser.add_argument(
        "--include-leads",
        action="store_true",
        help="Include SF owner_ids on ops.lead.",
    )
    parser.add_argument(
        "--include-opportunities",
        action="store_true",
        help="Include SF owner_ids on ops.opportunity.",
    )
    parser.add_argument(
        "--include-providers",
        action="store_true",
        help="Include CareStack providers from ingest.carestack_provider.",
    )
    parser.add_argument(
        "--include-sofia",
        action="store_true",
        help="Seed the Sofia AI actor.",
    )
    return parser.parse_args(argv)


def _resolved_scope(args: argparse.Namespace) -> argparse.Namespace:
    """If the operator passes no scope flags, run ALL sources."""
    any_set = (
        args.include_leads
        or args.include_opportunities
        or args.include_providers
        or args.include_sofia
    )
    if not any_set:
        args.include_leads = True
        args.include_opportunities = True
        args.include_providers = True
        args.include_sofia = True
    return args


async def _distinct_lead_owner_ids(
    session: Any, tenant_id: TenantId
) -> list[tuple[str, str | None]]:
    """Return distinct ``(owner_id, owner_name?)`` tuples from ops.lead."""
    owner_id_expr = Lead.extra["owner_id"].astext
    owner_name_expr = Lead.extra["owner_name"].astext
    stmt = (
        for_tenant(
            select(owner_id_expr, owner_name_expr).select_from(Lead),
            tenant_id,
            Lead,
        )
        .where(owner_id_expr.is_not(None))
        .distinct()
    )
    rows = (await session.execute(stmt)).all()
    return [(oid, oname) for oid, oname in rows if oid]


async def _distinct_opportunity_owner_ids(
    session: Any, tenant_id: TenantId
) -> list[tuple[str, str | None]]:
    """Return distinct ``(owner_id, owner_name?)`` tuples from ops.opportunity."""
    owner_id_expr = Opportunity.extra["owner_id"].astext
    owner_name_expr = Opportunity.extra["owner_name"].astext
    stmt = (
        for_tenant(
            select(owner_id_expr, owner_name_expr).select_from(Opportunity),
            tenant_id,
            Opportunity,
        )
        .where(owner_id_expr.is_not(None))
        .distinct()
    )
    rows = (await session.execute(stmt)).all()
    return [(oid, oname) for oid, oname in rows if oid]


async def _list_carestack_providers(
    session: Any, tenant_id: TenantId
) -> list[tuple[str, str | None]]:
    """Return ``(provider_id, display_name?)`` tuples from
    ``ingest.carestack_provider`` for this tenant."""
    stmt = for_tenant(
        select(CareStackProvider), tenant_id, CareStackProvider
    )
    rows = (await session.execute(stmt)).scalars().all()
    out: list[tuple[str, str | None]] = []
    for row in rows:
        pid_value = row.provider_carestack_id
        first = row.first_name or ""
        last = row.last_name or ""
        name = (first + " " + last).strip() or None
        out.append((str(pid_value), name))
    return out


async def _seed(
    actor_service: ActorService,
    tenant_id: TenantId,
    *,
    source_provider: str,
    source_instance: str,
    pairs: list[tuple[str, str | None]],
    selector: str,
) -> int:
    seeded = 0
    for external_id, name_hint in pairs:
        try:
            await actor_service.resolve_actor_from_source(
                tenant_id,
                source_provider=source_provider,
                source_instance=source_instance,
                external_id=external_id,
                name_hint=name_hint,
            )
            seeded += 1
        except Exception as exc:  # noqa: BLE001 — per-row isolation
            log.warning(
                "backfill.actors.seed_failed",
                tenant_id=str(tenant_id),
                selector=selector,
                external_id=external_id,
                error_type=type(exc).__name__,
            )
    return seeded


async def main(
    args: argparse.Namespace,
    *,
    session_factory: Callable[[], Any] | None = None,
) -> int:
    """Run the actor backfill once. Returns a CLI exit code."""
    args = _resolved_scope(args)
    tenant_id = TenantId(UUID(args.tenant_id))
    session_cm = (session_factory or _default_session_factory)()
    async with session_cm as session:
        actor_service = ActorService(session)

        lead_pairs: list[tuple[str, str | None]] = []
        opp_pairs: list[tuple[str, str | None]] = []
        provider_pairs: list[tuple[str, str | None]] = []

        if args.include_leads:
            lead_pairs = await _distinct_lead_owner_ids(session, tenant_id)
        if args.include_opportunities:
            opp_pairs = await _distinct_opportunity_owner_ids(session, tenant_id)
        if args.include_providers:
            provider_pairs = await _list_carestack_providers(session, tenant_id)

        log.info(
            "backfill.actors.discovered",
            tenant_id=str(tenant_id),
            leads=len(lead_pairs),
            opportunities=len(opp_pairs),
            providers=len(provider_pairs),
            sofia=1 if args.include_sofia else 0,
        )

        if not args.apply:
            # Dedupe across leads + opportunities for the dry-run report
            # so the operator sees the actual catalogue size.
            unique_sf = {oid for oid, _ in lead_pairs} | {oid for oid, _ in opp_pairs}
            unique_cs = {pid for pid, _ in provider_pairs}
            log.info(
                "backfill.actors.dry_run",
                tenant_id=str(tenant_id),
                unique_sf=len(unique_sf),
                unique_cs=len(unique_cs),
                sofia=1 if args.include_sofia else 0,
            )
            return 0

        sf_total = 0
        if lead_pairs:
            sf_total += await _seed(
                actor_service,
                tenant_id,
                source_provider="salesforce",
                source_instance=_SF_INSTANCE,
                pairs=lead_pairs,
                selector="leads",
            )
            await session.commit()
        if opp_pairs:
            sf_total += await _seed(
                actor_service,
                tenant_id,
                source_provider="salesforce",
                source_instance=_SF_INSTANCE,
                pairs=opp_pairs,
                selector="opportunities",
            )
            await session.commit()

        cs_total = 0
        if provider_pairs:
            cs_total = await _seed(
                actor_service,
                tenant_id,
                source_provider="carestack",
                source_instance=_CS_INSTANCE,
                pairs=provider_pairs,
                selector="providers",
            )
            await session.commit()

        sofia_total = 0
        if args.include_sofia:
            await actor_service.resolve_actor_from_source(
                tenant_id,
                source_provider="sofia",
                source_instance=_SOFIA_INSTANCE,
                external_id="sofia_ai",
            )
            await session.commit()
            sofia_total = 1

        log.info(
            "backfill.actors.done",
            tenant_id=str(tenant_id),
            sf_seeded=sf_total,
            cs_seeded=cs_total,
            sofia_seeded=sofia_total,
        )
        return 0


def run(argv: list[str] | None = None) -> int:
    configure_logging()
    args = parse_args(argv)
    try:
        return asyncio.run(main(args))
    except Exception:  # noqa: BLE001 - top-level CLI boundary
        log.exception("backfill.actors.crashed")
        return 1


if __name__ == "__main__":
    sys.exit(run())
