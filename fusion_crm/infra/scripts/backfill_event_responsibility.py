"""Backfill ``interaction.event_responsibility`` for historical events (ENG-416).

The W2 resolver wiring writes responsibility rows for every event
emitted GOING FORWARD. Historical events captured by W1 and earlier
W2 commits have no responsibility rows yet — this script seeds them
by replaying the same resolver against the existing event population.

Hard rules:
- Operator-runs-it. Dry-run by default; ``--apply`` commits each
  per-event seed.
- Idempotent + partial-seed safe. The scan returns every event
  missing AT LEAST ONE of the ``--expected-roles`` (default
  ``operational,clinical``), so a re-run picks up events where
  ``operational`` was written by an earlier pass but ``clinical``
  is still absent. ``set_responsibilities_idempotent`` skips any
  ``(actor_id, role)`` pair already present, so re-runs are safe.
- No SF / CareStack writes. Reads:
    - ``interaction.event`` (target),
    - ``ops.opportunity`` (covering Opportunity lookup),
    - ``ops.lead`` (owner_id fallback),
    - ``ops.consultation`` (for the consult↔opportunity link backfill
      half — see ``backfill_consultation_covering_opportunity`` below).
  Writes only to ``interaction.event_responsibility`` and
  ``actor.actor`` / ``actor.actor_identifier`` via
  ``ActorService.resolve_actor_from_source`` (the same idempotent
  resolver used at ingest).
- No PHI in structured logs — only event ids, kinds, counts.

CLI::

    python3 infra/scripts/backfill_event_responsibility.py \\
        --tenant-id <uuid> \\
        [--apply] \\
        [--batch-size 200] \\
        [--max-batches 100] \\
        [--kinds consultation_scheduled,consultation_completed,...]

Exit codes:
    0  success (including dry-run)
    1  uncaught exception
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any
from uuid import UUID

from packages.actor.service import ActorService
from packages.core.logging import configure_logging, get_logger
from packages.core.types import TenantId
from packages.ingest.responsibility_resolver import FunnelResponsibilityResolver
from packages.interaction.service import InteractionService
from packages.ops.service import OpsService

log = get_logger("infra.backfill_event_responsibility")


def _default_session_factory() -> Any:
    from packages.db.session import async_session

    return async_session()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seed interaction.event_responsibility for historical events "
            "by replaying the funnel-responsibility resolver. Dry-run by default."
        ),
    )
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit each batch. Without this flag, the script counts what "
        "it would seed and exits.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Events per batch (default 200, max 5000).",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=100,
        help="Safety cap on the number of batches per invocation (default 100).",
    )
    parser.add_argument(
        "--kinds",
        type=str,
        default=None,
        help=(
            "Comma-separated list of interaction.event.kind values to limit "
            "the seed to (default: all kinds). Useful when the operator wants "
            "to re-attribute only e.g. consultation_* events after a resolver "
            "logic change."
        ),
    )
    parser.add_argument(
        "--expected-roles",
        type=str,
        default="operational,clinical",
        help=(
            "Comma-separated responsibility roles the scan treats as expected. "
            "Events missing ANY of these roles are re-selected so the resolver "
            "can repair partially-seeded rows (default: 'operational,clinical'). "
            "Pass an empty string to fall back to the legacy 'zero rows only' "
            "scan."
        ),
    )
    parser.add_argument(
        "--link-consultations",
        action="store_true",
        help=(
            "Also backfill ops.consultation.covering_opportunity_id by "
            "computing the covering Opportunity for every consult that "
            "currently has NULL. Runs after the event-responsibility pass."
        ),
    )
    return parser.parse_args(argv)


async def _seed_event(
    *,
    tenant_id: TenantId,
    event: Any,
    interaction: InteractionService,
    resolver: FunnelResponsibilityResolver,
) -> int:
    """Resolve responsibilities for one event and write missing rows.

    Returns the count of NEW responsibility rows inserted (0 when the
    event already has all the rows the resolver would produce).
    """
    resolved = await resolver.resolve(
        tenant_id,
        event_kind=event.kind,
        person_uid=event.person_uid,
        occurred_at=event.occurred_at,
    )
    if not resolved.assignments:
        return 0
    return await interaction.set_responsibilities_idempotent(
        tenant_id, event.id, resolved.assignments
    )


async def _backfill_consultation_links(
    *,
    tenant_id: TenantId,
    ops: OpsService,
    apply: bool,
) -> int:
    """Seed ``ops.consultation.covering_opportunity_id`` for NULL rows.

    Touched as a follow-up pass only when ``--link-consultations`` is
    set: the responsibility seed already exercises
    ``find_covering_opportunity`` per event, so for typical operator
    runs the link backfill is a separate, narrow operation.
    """
    # Use the existing consultation listing surface; this is intentionally
    # tenant-scoped and bounded — operators run repeatedly if more rows
    # appear.
    rows = await ops._repo.list_consultations_for_tenant(  # noqa: SLF001 — operator script
        tenant_id, limit=5000
    )
    linked = 0
    for row in rows:
        if row.covering_opportunity_id is not None:
            continue
        covering = await ops.find_covering_opportunity(
            tenant_id, row.person_uid, row.scheduled_at
        )
        if covering is None:
            continue
        if apply:
            await ops.attach_consultation_to_opportunity(
                tenant_id, row.id, covering.id
            )
        linked += 1
    return linked


async def run(args: argparse.Namespace) -> None:
    configure_logging()
    tenant_id = TenantId(UUID(args.tenant_id))
    if args.batch_size < 1 or args.batch_size > 5000:
        raise SystemExit("--batch-size must be between 1 and 5000")
    if args.max_batches < 1:
        raise SystemExit("--max-batches must be >= 1")

    kinds: tuple[str, ...] | None = None
    if args.kinds:
        kinds = tuple(k.strip() for k in args.kinds.split(",") if k.strip())

    expected_roles: tuple[str, ...] | None = None
    if args.expected_roles:
        expected_roles = tuple(
            r.strip() for r in args.expected_roles.split(",") if r.strip()
        ) or None

    session_cm = _default_session_factory()
    async with session_cm as session:
        interaction = InteractionService(session)
        ops = OpsService(session)
        actor_service = ActorService(session)
        resolver = FunnelResponsibilityResolver(ops, actor_service)

        total_events_scanned = 0
        total_rows_seeded = 0
        after_occurred_at = None
        batches = 0
        while batches < args.max_batches:
            events = await interaction.list_events_missing_responsibility(
                tenant_id,
                limit=args.batch_size,
                after_occurred_at=after_occurred_at,
                kinds=kinds,
                expected_roles=expected_roles,
            )
            if not events:
                break
            batches += 1
            for event in events:
                total_events_scanned += 1
                seeded = await _seed_event(
                    tenant_id=tenant_id,
                    event=event,
                    interaction=interaction,
                    resolver=resolver,
                )
                total_rows_seeded += seeded
                after_occurred_at = event.occurred_at
            if args.apply:
                await session.commit()
            else:
                await session.rollback()
            log.info(
                "backfill.event_responsibility.batch",
                batch=batches,
                events_in_batch=len(events),
                rows_seeded_running=total_rows_seeded,
                apply=args.apply,
            )

        consult_linked = 0
        if args.link_consultations:
            consult_linked = await _backfill_consultation_links(
                tenant_id=tenant_id, ops=ops, apply=args.apply
            )
            if args.apply:
                await session.commit()
            else:
                await session.rollback()

        log.info(
            "backfill.event_responsibility.summary",
            tenant_id=str(tenant_id),
            events_scanned=total_events_scanned,
            rows_seeded=total_rows_seeded,
            consultations_linked=consult_linked,
            apply=args.apply,
            batches=batches,
        )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    asyncio.run(run(args))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
