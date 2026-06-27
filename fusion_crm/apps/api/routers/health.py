"""Liveness/readiness endpoints for Docker + future K8s probes.

``/healthz`` doubles as the version oracle for the staff frontend:
the ``commit_sha`` field carries the deployed build's git SHA so the
browser can detect a backend update and prompt the operator to
reload a stale page (ENG-150 cache-busting hint). The value comes
from the ``APP_COMMIT_SHA`` env var, which ``deploy-prod.yml`` sets
on every Cloud Run revision; locally the variable is absent and we
emit ``"dev"`` so the watcher never trips.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import (
    get_db,
    get_integration_service,
    get_interaction_service,
    get_tenant_id,
)
from packages.core.logging import get_logger
from packages.core.types import TenantId
from packages.integrations.service import IntegrationService
from packages.interaction.service import InteractionService

log = get_logger(__name__)

router = APIRouter(tags=["health"])

_STALE_THRESHOLD = timedelta(hours=2)

# Payment-freshness configuration (ENG-327). Defaults are module-level
# constants — no env var — because the alert calculus should not drift
# between environments silently.
#
# Why these defaults:
#   * Window: the clinic's actual workday is roughly 07:00-19:00 local —
#     stale payments outside that window are usually just "the clinic is
#     closed", not an ingest failure. We don't want to page the operator
#     every weekend.
#   * Threshold: CareStack accounting transactions land within ~30 min of
#     a real cash collection. 3 hours of zero collections during clinic
#     hours is the earliest signal that the ingest pipeline is dark
#     without false positives from a quiet morning.
_PAYMENT_FRESHNESS_THRESHOLD = timedelta(hours=3)
_CLINIC_TZ = ZoneInfo("America/Los_Angeles")
_CLINIC_HOURS_START = 7  # 07:00 inclusive (local)
_CLINIC_HOURS_END = 19  # 19:00 exclusive (local)


def _in_clinic_hours(now: datetime, tz: ZoneInfo = _CLINIC_TZ) -> bool:
    """Return ``True`` if ``now`` falls inside the clinic-hours window.

    The window is half-open ``[_CLINIC_HOURS_START, _CLINIC_HOURS_END)``
    in ``tz``. ``now`` must be tz-aware — the route always passes
    ``datetime.now(UTC)`` so this is enforced upstream.
    """
    local = now.astimezone(tz)
    return _CLINIC_HOURS_START <= local.hour < _CLINIC_HOURS_END


def _commit_sha() -> str:
    return os.environ.get("APP_COMMIT_SHA", "dev")


@router.get("/healthz")
async def liveness() -> dict:
    return {"status": "ok", "commit_sha": _commit_sha()}


@router.get("/readyz")
async def readiness(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(text("SELECT 1"))
    return {"status": "ready", "commit_sha": _commit_sha()}


@router.get("/health/ingest")
async def ingest_health(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[TenantId, Depends(get_tenant_id)],
    integration_service: Annotated[
        IntegrationService, Depends(get_integration_service)
    ],
    interaction_service: Annotated[
        InteractionService, Depends(get_interaction_service)
    ],
) -> dict:
    """Operational health of the ingest worker — latest sync_run per provider.

    No auth required: this is an ops probe, not a data query. Returns
    per-provider status based on recency and outcome of the latest run.
    The frontend sidebar badge polls this to show a green/yellow/red dot.

    Per-tenant ``payment_freshness`` (ENG-327) reports two facets for the
    current tenant: the latest CareStack accounting ``sync_run`` (pipeline
    liveness) and the latest ``payment_recorded`` ``Event`` (data
    freshness). The data-freshness status downgrades to ``stale`` only
    during clinic hours; outside the window it reports ``quiet-hours``
    so the staff sidebar / on-call alerts do not page on closed-clinic
    overnight gaps. NO PHI in the output: timestamps, status strings,
    counts only — never names, DOB, notes, clinical text.
    """
    from packages.integrations.models import IntegrationAccount, SyncRun

    stmt = (
        select(
            IntegrationAccount.provider,
            SyncRun.status,
            SyncRun.started_at,
            SyncRun.finished_at,
            SyncRun.records_succeeded,
            SyncRun.records_failed,
        )
        .join(IntegrationAccount, IntegrationAccount.id == SyncRun.account_id)
        .order_by(SyncRun.started_at.desc())
        .limit(20)
    )
    rows = (await db.execute(stmt)).all()

    now = datetime.now(UTC)
    providers: dict[str, dict] = {}

    for provider, status, started_at, finished_at, succeeded, failed in rows:
        if provider in providers:
            continue
        age = now - started_at.replace(tzinfo=UTC) if started_at else None
        if status in ("failed",):
            health = "failed"
        elif age is not None and age > _STALE_THRESHOLD:
            health = "stale"
        elif status in ("succeeded", "success", "partial"):
            health = "ok"
        elif status == "running":
            health = "ok"
        else:
            health = "unknown"
        providers[provider] = {
            "status": health,
            "last_status": status,
            "last_run_at": (finished_at or started_at).isoformat() if (finished_at or started_at) else None,
            "records_succeeded": succeeded or 0,
            "records_failed": failed or 0,
        }

    all_statuses = [p["status"] for p in providers.values()]
    if not all_statuses:
        overall = "unknown"
    elif any(s == "failed" for s in all_statuses):
        overall = "failed"
    elif any(s == "stale" for s in all_statuses):
        overall = "stale"
    elif all(s == "ok" for s in all_statuses):
        overall = "ok"
    else:
        overall = "unknown"

    payment_freshness = await _build_payment_freshness(
        now=now,
        tenant_id=tenant_id,
        integration_service=integration_service,
        interaction_service=interaction_service,
    )

    # Cloud Monitoring's `fusion_payment_freshness_stale` log-based metric
    # (infra/scripts/provision_monitoring.sh) filters on
    # `jsonPayload.payment_freshness_status="stale"`. Emit the structured
    # field on every probe — the filter selects the `="stale"` subset.
    # PHI rule (CLAUDE.md): only the small enum of facet statuses, the
    # tenant id, and integer ages — never names/DOB/notes/payload.
    log.info(
        "health_ingest_probe",
        tenant_id=str(tenant_id),
        payment_freshness_status=payment_freshness["last_payment"]["status"],
        accounting_sync_status=payment_freshness["last_accounting_sync"]["status"],
        payment_age_seconds=payment_freshness["last_payment"]["age_seconds"],
        accounting_age_seconds=payment_freshness["last_accounting_sync"]["age_seconds"],
    )

    return {
        "status": overall,
        "providers": providers,
        "payment_freshness": payment_freshness,
    }


async def _build_payment_freshness(
    *,
    now: datetime,
    tenant_id: TenantId,
    integration_service: IntegrationService,
    interaction_service: InteractionService,
) -> dict:
    """Assemble the payment-freshness block for ``/health/ingest`` (ENG-327).

    Two facets, both per-tenant:

    * ``last_accounting_sync`` — pipeline liveness. Reuses
      :meth:`IntegrationsRepository.list_latest_runs_for_tenant` with
      ``provider="carestack"``. Status follows the same rules as the
      top-level ``providers`` block (``failed``, ``stale`` >
      :data:`_STALE_THRESHOLD`, ``ok``, or ``unknown`` when no runs
      exist).

    * ``last_payment`` — data freshness. Uses
      :meth:`InteractionService.max_event_occurred_at` filtered to
      ``payment_recorded``. Status is ``unknown`` when no rows exist;
      otherwise ``stale`` only when the age exceeds
      :data:`_PAYMENT_FRESHNESS_THRESHOLD` AND the current local time
      sits inside the clinic window. Outside clinic hours we report
      ``quiet-hours`` instead of ``stale`` so a quiet overnight gap does
      not page the on-call operator.

    All timestamps render as ISO-8601 (or ``None``). Ages render as
    integer seconds. The route layer is the only place that classifies
    status — the repo/service return raw timestamps so the contract is
    easy to test deterministically.
    """
    runs = await integration_service.list_latest_runs_for_tenant(
        tenant_id, provider="carestack", limit=1
    )
    last_accounting_sync = _classify_accounting_sync(now=now, runs=runs)

    last_payment_at = await interaction_service.max_event_occurred_at(
        tenant_id, kind="payment_recorded"
    )
    last_payment = _classify_payment_freshness(
        now=now, last_payment_at=last_payment_at
    )

    return {
        "tenant_id": str(tenant_id),
        "last_accounting_sync": last_accounting_sync,
        "last_payment": last_payment,
    }


def _classify_accounting_sync(
    *,
    now: datetime,
    runs: list,
) -> dict:
    """Translate the latest ``carestack`` sync_run into a freshness dict."""
    if not runs:
        return {
            "status": "unknown",
            "last_status": None,
            "finished_at": None,
            "age_seconds": None,
        }
    run, _provider = runs[0]
    finished_or_started = run.finished_at or run.started_at
    age: timedelta | None = None
    if finished_or_started is not None:
        finished_aware = finished_or_started
        if finished_aware.tzinfo is None:
            finished_aware = finished_aware.replace(tzinfo=UTC)
        age = now - finished_aware

    if run.status == "failed":
        status = "failed"
    elif age is not None and age > _STALE_THRESHOLD:
        status = "stale"
    elif run.status in ("succeeded", "success", "partial", "running"):
        status = "ok"
    elif run.status == "skipped_credential":
        # Tenants without active CareStack creds aren't broken — they're
        # simply not connected. Surface as ``unknown`` so the staff UI
        # does not raise a red badge on a fresh local dev DB.
        status = "unknown"
    else:
        status = "unknown"

    return {
        "status": status,
        "last_status": run.status,
        "finished_at": (
            finished_or_started.isoformat() if finished_or_started else None
        ),
        "age_seconds": int(age.total_seconds()) if age is not None else None,
    }


def _classify_payment_freshness(
    *,
    now: datetime,
    last_payment_at: datetime | None,
) -> dict:
    """Translate ``last(payment_recorded.occurred_at)`` into a freshness dict.

    ``unknown`` when no rows exist. ``stale`` only when the age exceeds
    :data:`_PAYMENT_FRESHNESS_THRESHOLD` AND it is currently clinic hours.
    During off-hours we degrade to ``quiet-hours`` instead.
    """
    clinic_open = _in_clinic_hours(now)
    if last_payment_at is None:
        return {
            "last_payment_at": None,
            "age_seconds": None,
            "status": "unknown",
            "clinic_hours": clinic_open,
        }

    last_aware = last_payment_at
    if last_aware.tzinfo is None:
        last_aware = last_aware.replace(tzinfo=UTC)
    age = now - last_aware

    if age <= _PAYMENT_FRESHNESS_THRESHOLD:
        status = "ok"
    elif clinic_open:
        status = "stale"
    else:
        status = "quiet-hours"

    return {
        "last_payment_at": last_aware.isoformat(),
        "age_seconds": int(age.total_seconds()),
        "status": status,
        "clinic_hours": clinic_open,
    }


@router.get("/health/services")
async def services_health(db: AsyncSession = Depends(get_db)) -> dict:
    """Check all backend dependencies for the Inspector services panel."""
    from arq.connections import RedisSettings, create_pool

    from packages.core.config import get_settings
    from packages.integrations.models import IntegrationAccount, SyncRun

    checks: dict[str, dict] = {}

    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = {"status": "ok"}
    except Exception:
        checks["postgres"] = {"status": "down"}

    try:
        redis = await create_pool(
            RedisSettings.from_dsn(str(get_settings().redis_url))
        )
        try:
            await redis.ping()
            checks["redis"] = {"status": "ok"}
        finally:
            await redis.aclose()
    except Exception:
        checks["redis"] = {"status": "down"}

    checks["api"] = {"status": "ok"}

    now = datetime.now(UTC)
    stmt = (
        select(
            IntegrationAccount.provider,
            SyncRun.status,
            SyncRun.started_at,
            SyncRun.finished_at,
            SyncRun.records_succeeded,
        )
        .join(IntegrationAccount, IntegrationAccount.id == SyncRun.account_id)
        .order_by(SyncRun.started_at.desc())
        .limit(10)
    )
    rows = (await db.execute(stmt)).all()
    latest_run = rows[0] if rows else None
    if latest_run:
        age = now - latest_run[2].replace(tzinfo=UTC) if latest_run[2] else None
        if age and age < timedelta(hours=2):
            checks["worker"] = {"status": "ok", "last_run_ago": str(age).split(".")[0]}
        else:
            checks["worker"] = {"status": "stale", "last_run_ago": str(age).split(".")[0] if age else None}
    else:
        checks["worker"] = {"status": "unknown"}

    all_ok = all(c["status"] == "ok" for c in checks.values())
    return {"status": "ok" if all_ok else "degraded", "services": checks}
