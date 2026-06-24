"""Replay historical CareStack treatment procedures into surgery events (ENG-540).

The ENG-511/538 surgery split (``surgery_scheduled`` / ``surgery_completed``)
and the ENG-539 ``case_type`` dimension only emit when the treatment-procedure
ingest projects a row through the CURRENT logic. The ~10k historical
``carestack.treatment_procedure.upsert`` raw_events were captured under the OLD
logic, and a normal re-pull is **dedup-skipped** — ``import_recent_treatments``
/ ``pull_all_since`` skip any row whose ``lastUpdatedOn`` matches the captured
stamp before they ever project it. So historical implant surgeries never emit
the new ``surgery_*`` events and stay out of the funnel.

This operator-triggered sweep re-projects the EXISTING raw_events through the
current projection (``CareStackTreatmentIngestService.reproject_treatments_from_raw``)
WITHOUT re-pulling from CareStack — it reads ``ingest.raw_event`` only, oldest
external-id first, in resumable batches, and relies on
``create_event_idempotent`` for safety. A fact rebuild afterward backfills
``surgery_scheduled_date`` / ``surgery_completed_date`` (+ ``case_type``).

This script is **NOT** wired to any HTTP endpoint — long-running ingest work
behind Next's 30s proxy has burned us before. Run it from a workstation or a
Cloud Run Job; let it finish.

CLI::

    # dry-run is the default — count candidate procedures per tenant, no writes,
    # no CareStack calls
    python3 infra/scripts/replay_treatment_procedures.py [--tenant-id <uuid>]

    # apply mode — re-project in resumable batches, commit per batch
    python3 infra/scripts/replay_treatment_procedures.py \\
        --apply \\
        [--tenant-id <uuid>] \\
        [--batch-size 500] \\
        [--max-batches 0] \\
        [--start-after <external_id>] \\
        [--since-days 0]

After a successful apply, rebuild the fact table so the analytics layer picks
up the new surgery dates + case_type by enqueuing the existing on-demand arq
job (``apps/worker/jobs/fact_patient_journey_refresh.py``)::

    # per tenant
    await pool.enqueue_job("refresh_fact_patient_journey", tenant_id="<uuid>")
    # or every tenant
    await pool.enqueue_job("refresh_fact_patient_journey_for_all_tenants")

The rebuild is idempotent and preserves manual provenance (ENG-513): it
recomputes ``surgery_scheduled_date`` / ``surgery_completed_date`` (earliest
``surgery_*`` event) and ``case_type`` (derived from raw CDT) as ``method=auto``
but never clobbers a field an operator marked ``method=manual``.

Flags:

* ``--tenant-id`` — restrict to one tenant UUID. Omit to sweep every tenant.
  ``--start-after`` only makes sense with a single tenant.
* ``--batch-size`` — procedures per batch / commit (default 500, max 2000).
* ``--max-batches`` — stop after N batches per tenant (default 0 = unbounded,
  bounded only by the internal safety cap). Resume the rest with ``--start-after``.
* ``--start-after`` — resume cursor: skip external ids <= this value (the last
  ``external_id`` printed by a previous run).
* ``--since-days`` — only re-project raw_events captured within the last N days
  (by ``received_at``). Default 0 = all captured history.

Exit codes:
    0  success (including dry-run)
    1  uncaught exception (logged before propagation)

Operational guard-rails:

* Default is dry-run; you must pass ``--apply`` to write.
* Reads ``ingest.raw_event`` ONLY — NEVER pulls the CareStack treatment feed.
  The CareStack client is built solely so ENG-538 self-fill can resolve a
  still-missing procedure code via the read-only by-id endpoint; the feed-pull
  method is never called. When no credential exists the replay still runs —
  codes already in the catalog (from the ENG-538 backfill) resolve, and a
  brand-new code simply falls back to the generic mapping (fail-closed).
* The script owns the unit of work: COMMIT per batch on success; on any
  exception the in-flight batch is rolled back before the error propagates.
* Idempotent: a second run emits zero new events (every event already exists →
  ``unchanged``).
* Structured logs carry tenant ids + counts only — never PHI.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import PlatformError
from packages.core.logging import configure_logging, get_logger
from packages.core.types import TenantId
from packages.ingest.carestack_treatment_service import (
    CareStackTreatmentIngestService,
)
from packages.ingest.service import IngestService
from packages.integrations.carestack import CareStackClient
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)

log = get_logger("infra.replay_treatment_procedures")

_TREATMENT_PROCEDURE_EVENT_TYPE = "carestack.treatment_procedure.upsert"
_DEFAULT_BATCH_SIZE = 500
_MAX_BATCH_SIZE = 2000
# Defensive ceiling on batches per tenant so a cursor bug can never loop
# forever. 10k batches * 500 rows = 5M procedures — far above the real ~10k.
_BATCH_SAFETY_CAP = 10_000


def _default_session_factory() -> Any:
    from packages.db.session import async_session

    return async_session()


class _NoPullTreatmentClient:
    """Stand-in client for replays without a CareStack credential.

    Satisfies ``CareStackTreatmentClientProtocol`` but refuses the feed pull —
    the replay must never hit it. Deliberately exposes NO ``get_procedure_code``
    so ENG-538 self-fill stays fail-closed (a still-missing code keeps the
    generic mapping instead of round-tripping to CareStack).
    """

    async def list_treatment_procedures_modified_since(
        self,
        modified_since: datetime,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]:  # pragma: no cover - defensive guard
        raise RuntimeError(
            "replay_treatment_procedures must not pull the CareStack feed"
        )


async def _tenant_ids(session: AsyncSession) -> list[TenantId]:
    rows = await session.execute(text("SELECT id FROM tenant.tenant ORDER BY id"))
    return [TenantId(row[0]) for row in rows]


async def _build_self_fill_client(
    session: AsyncSession, tenant_id: TenantId
) -> Any:
    """Build a by-id self-fill client for a tenant, or the no-pull stand-in.

    Returns a real :class:`CareStackClient` when the tenant has a CareStack
    credential (so ENG-538 self-fill can resolve a missing procedure code via
    the read-only by-id endpoint), else a :class:`_NoPullTreatmentClient`.
    Either way the replay never calls the feed-pull method.
    """
    cred_svc = IntegrationCredentialService(session)
    try:
        payload = await cred_svc.read_for(tenant_id, "carestack", "password_grant")
    except (NoCredentialError, PlatformError):
        log.info(
            "replay_treatment_procedures.no_credential",
            tenant_id=str(tenant_id),
        )
        return _NoPullTreatmentClient()
    return CareStackClient.from_credential(payload)


async def _close_client(client: Any) -> None:
    close = getattr(client, "close", None)
    if callable(close):
        maybe_awaitable = close()
        if maybe_awaitable is not None and hasattr(maybe_awaitable, "__await__"):
            await maybe_awaitable


async def _replay_tenant(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    batch_size: int,
    max_batches: int,
    start_after: str | None,
    since: datetime | None,
) -> tuple[int, int, int, str | None]:
    """Re-project one tenant's captured treatment procedures in batches.

    Commits per batch. Returns
    ``(imported_total, unchanged_total, skipped_total, last_cursor)`` where
    ``last_cursor`` is the external id to resume from (``None`` when the tenant
    is fully drained or stopped on ``max_batches``).
    """
    client = await _build_self_fill_client(session, tenant_id)
    svc = CareStackTreatmentIngestService(session=session, carestack_client=client)
    cursor = start_after
    imported_total = 0
    unchanged_total = 0
    skipped_total = 0
    batch_index = 0
    try:
        while batch_index < _BATCH_SAFETY_CAP:
            if max_batches and batch_index >= max_batches:
                log.info(
                    "replay_treatment_procedures.max_batches_reached",
                    tenant_id=str(tenant_id),
                    batches=batch_index,
                    resume_after=cursor,
                )
                return imported_total, unchanged_total, skipped_total, cursor
            page = await IngestService(session).list_latest_by_type_paginated(
                tenant_id,
                event_type=_TREATMENT_PROCEDURE_EVENT_TYPE,
                limit=batch_size,
                after_external_id=cursor,
                since=since,
            )
            if not page:
                break
            rows: list[tuple[UUID, dict[str, Any]]] = [
                (raw_event_id, payload) for raw_event_id, _external_id, payload in page
            ]
            try:
                result = await svc.reproject_treatments_from_raw(
                    tenant_id, rows=rows
                )
                await session.commit()
            except Exception:
                # The script owns the unit of work — roll the in-flight batch
                # back before the error propagates up to ``run``.
                await session.rollback()
                raise
            imported_total += result.imported_count
            unchanged_total += result.unchanged_count
            skipped_total += result.skipped_count
            cursor = page[-1][1]
            batch_index += 1
            log.info(
                "replay_treatment_procedures.batch_done",
                tenant_id=str(tenant_id),
                batch=batch_index,
                rows=len(rows),
                imported=result.imported_count,
                unchanged=result.unchanged_count,
                skipped=result.skipped_count,
                cursor=cursor,
            )
    finally:
        await _close_client(client)

    return imported_total, unchanged_total, skipped_total, None


async def run(
    args: argparse.Namespace,
    *,
    session_factory: Any | None = None,
) -> int:
    apply = bool(args.apply)
    since = (
        datetime.now(UTC) - timedelta(days=args.since_days)
        if args.since_days and args.since_days > 0
        else None
    )
    session_cm = (
        session_factory() if session_factory is not None else _default_session_factory()
    )

    total_candidates = 0
    total_imported = 0
    total_unchanged = 0
    total_skipped = 0

    async with session_cm as session:
        if args.tenant_id is not None:
            tenant_ids = [TenantId(UUID(args.tenant_id))]
        else:
            tenant_ids = await _tenant_ids(session)

        for tenant_id in tenant_ids:
            if not apply:
                n = await IngestService(session).count_distinct_external_ids_by_type(
                    tenant_id,
                    event_type=_TREATMENT_PROCEDURE_EVENT_TYPE,
                    since=since,
                )
                if n:
                    log.info(
                        "replay_treatment_procedures.candidates",
                        tenant_id=str(tenant_id),
                        candidate_procedures=n,
                    )
                total_candidates += n
                continue

            imported, unchanged, skipped, resume_after = await _replay_tenant(
                session,
                tenant_id,
                batch_size=args.batch_size,
                max_batches=args.max_batches,
                start_after=args.start_after,
                since=since,
            )
            total_imported += imported
            total_unchanged += unchanged
            total_skipped += skipped
            if imported or unchanged or skipped:
                log.info(
                    "replay_treatment_procedures.tenant_done",
                    tenant_id=str(tenant_id),
                    imported=imported,
                    unchanged=unchanged,
                    skipped=skipped,
                    resume_after=resume_after,
                )

    log.info(
        "replay_treatment_procedures.done",
        mode="apply" if apply else "dry-run",
        candidate_procedures=total_candidates,
        imported=total_imported,
        unchanged=total_unchanged,
        skipped=total_skipped,
        since_days=args.since_days,
    )
    if not apply and total_candidates:
        print(
            f"DRY-RUN: {total_candidates} captured treatment procedure(s) would be "
            f"re-projected. Re-run with --apply to emit historical surgery events."
        )
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replay captured CareStack treatment procedures through the current "
            "projection so historical surgeries emit surgery_* events (ENG-540)."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write (default: dry-run — count candidates only, no CareStack calls).",
    )
    parser.add_argument(
        "--tenant-id",
        default=None,
        help="Restrict to one tenant UUID (default: every tenant).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=_DEFAULT_BATCH_SIZE,
        help=f"Procedures per batch / commit (default {_DEFAULT_BATCH_SIZE}).",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=0,
        help="Stop after N batches per tenant (default 0 = unbounded). Resume "
        "with --start-after.",
    )
    parser.add_argument(
        "--start-after",
        default=None,
        help="Resume cursor: skip external ids <= this value.",
    )
    parser.add_argument(
        "--since-days",
        type=int,
        default=0,
        help="Only re-project raw_events captured within the last N days "
        "(default 0 = all captured history).",
    )
    args = parser.parse_args(argv)
    if args.batch_size < 1 or args.batch_size > _MAX_BATCH_SIZE:
        parser.error(f"--batch-size must be between 1 and {_MAX_BATCH_SIZE}")
    if args.max_batches < 0:
        parser.error("--max-batches must be >= 0")
    if args.since_days < 0:
        parser.error("--since-days must be >= 0")
    return args


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    try:
        return asyncio.run(run(args))
    except Exception:
        log.exception("replay_treatment_procedures.failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
