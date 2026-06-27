"""Operator-triggered historical backfill for SF + CareStack ingest.

Phase 1 (ENG-246) added the per-entity `pull_all_since` paths and the
operator route. Phase 2 + Phase 3 (ENG-247) retrofit two pieces that
landed in mission ENG-235:

* Each leg now opens and closes a real `integrations.sync_run` row via
  `IntegrationService.open_provider_sync_run` /
  `close_provider_sync_run`, returning the run id in the response so the
  operator can correlate. Failure paths close with `status='failed'` and a
  credential-safe error summary; missing credentials close with
  `status='skipped_credential'` without re-raising.
* `sf_tasks` is a new entity option backed by
  `SfTaskIngestService.pull_all_since` (shipped in PR #97 / ENG-240).

Scheduled pull jobs (``apps/worker/jobs/ingest_scheduled.py``) are NOT
touched; they already journal their own runs with `trigger='scheduled'`.

Out of scope for this PR:

* Phase 4 — production deploy + arq background job. The route still runs
  inline; long requests are acceptable on `localhost`. Prod rollout needs
  a background-job wrapper and a separate ticket.
* UI surface for `sync_run` history — separate frontend ticket.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import (
    get_carestack_accounting_transaction_ingest_service,
    get_carestack_appointment_ingest_service,
    get_carestack_patient_ingest_service,
    get_carestack_payment_summary_ingest_service,
    get_db,
    get_integration_service,
    get_principal_with_tenant,
    get_sf_event_ingest_service,
    get_sf_lead_ingest_service,
    get_sf_task_ingest_service,
)
from packages.core.exceptions import PlatformError
from packages.core.security import Principal
from packages.ingest.carestack_accounting_transaction_service import (
    CareStackAccountingTransactionIngestService,
)
from packages.ingest.carestack_appointment_service import (
    CareStackAppointmentIngestService,
)
from packages.ingest.carestack_patient_service import (
    CareStackPatientIngestService,
)
from packages.ingest.carestack_payment_summary_service import (
    CareStackPaymentSummaryIngestService,
)
from packages.ingest.sf_event_service import SfEventIngestService
from packages.ingest.sf_lead_service import SfLeadIngestService
from packages.ingest.sf_task_service import SfTaskIngestService
from packages.integrations.service import IntegrationService, ProviderSyncStatus

router = APIRouter(prefix="/backfill", tags=["backfill"])

# Epoch ≈ "from the beginning of time" for providers. Both SF SOQL and
# CareStack accept timestamps from the unix epoch onwards without issue.
_DEFAULT_SINCE = datetime(1970, 1, 1, tzinfo=UTC)
# ENG-285: the throttled CareStack payments backfill anchors at the
# fiscal year boundary instead of epoch — the scheduled pull keeps a
# small rolling window, so a separate historical "from 2026-01-01"
# sweep is the safe default. Operator-supplied ``since`` overrides.
_PAYMENTS_BACKFILL_DEFAULT_SINCE = datetime(2026, 1, 1, tzinfo=UTC)
_BACKFILL_TRIGGER = "backfill"

EntityName = Literal[
    "sf_leads",
    "sf_events",
    "sf_tasks",
    "cs_patients",
    "cs_appointments",
    "carestack_accounting_transactions",
    "carestack_payment_summary",
]
_ALL_ENTITIES: tuple[EntityName, ...] = (
    "sf_leads",
    "sf_events",
    "sf_tasks",
    "cs_patients",
    "cs_appointments",
)

# Provider / object_scope tuple per entity — both sides feed into
# integrations.sync_run for auditability.
_ENTITY_META: dict[EntityName, tuple[str, str]] = {
    "sf_leads": ("salesforce", "lead"),
    "sf_events": ("salesforce", "event"),
    "sf_tasks": ("salesforce", "task"),
    "cs_patients": ("carestack", "patient"),
    "cs_appointments": ("carestack", "appointment"),
    "carestack_accounting_transactions": ("carestack", "accounting_transaction"),
    "carestack_payment_summary": ("carestack", "payment_summary"),
}

# Errors that mean "no active credential for this tenant/provider yet" —
# treat as `skipped_credential` rather than `failed`, mirroring the
# scheduled-job behaviour. The class names are matched by suffix so we
# don't have to import every provider's exception type here.
_CREDENTIAL_ERROR_SUFFIXES: tuple[str, ...] = (
    "NotConnectedError",
    "NoCredentialError",
)


class BackfillRunIn(BaseModel):
    """Operator-supplied scope of the backfill run.

    ``since`` is optional and defaults to the unix epoch (full history).
    ``entities`` is optional and defaults to all five currently supported
    entities (SF leads/events/tasks + CareStack patients/appointments).
    """

    since: datetime | None = None
    entities: list[EntityName] = Field(default_factory=lambda: list(_ALL_ENTITIES))


class EntityBackfillOut(BaseModel):
    """Result of a single entity's backfill leg.

    ``sync_run_id`` is the real `integrations.sync_run` UUID the operator
    can use to look up the row (see ``IntegrationService.list_recent_runs``
    or the future sync-run UI). ``error`` carries the provider error
    message when the leg failed; on success it is ``None``.
    """

    entity: EntityName
    imported: int = 0
    skipped: int = 0
    pages: int | None = None
    next_continue_token: str | None = None
    sync_run_id: UUID | None = None
    sync_run_status: ProviderSyncStatus | None = None
    error: str | None = None


class BackfillRunOut(BaseModel):
    started_at: datetime
    finished_at: datetime
    since: datetime
    legs: list[EntityBackfillOut]


@router.post("/run", response_model=BackfillRunOut)
async def run_backfill(
    payload: BackfillRunIn,
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    integration: Annotated[
        IntegrationService, Depends(get_integration_service)
    ],
    sf_leads: Annotated[
        SfLeadIngestService, Depends(get_sf_lead_ingest_service)
    ],
    sf_events: Annotated[
        SfEventIngestService, Depends(get_sf_event_ingest_service)
    ],
    sf_tasks: Annotated[
        SfTaskIngestService, Depends(get_sf_task_ingest_service)
    ],
    cs_patients: Annotated[
        CareStackPatientIngestService,
        Depends(get_carestack_patient_ingest_service),
    ],
    cs_appointments: Annotated[
        CareStackAppointmentIngestService,
        Depends(get_carestack_appointment_ingest_service),
    ],
    cs_accounting_transactions: Annotated[
        CareStackAccountingTransactionIngestService,
        Depends(get_carestack_accounting_transaction_ingest_service),
    ],
    cs_payment_summary: Annotated[
        CareStackPaymentSummaryIngestService,
        Depends(get_carestack_payment_summary_ingest_service),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BackfillRunOut:
    tenant_id = principal.require_tenant()
    # ENG-285: preserve "operator omitted since" for the payments legs
    # so they can anchor at 2026-01-01 instead of epoch. The legacy
    # legs (SF + CS patients/appointments) keep epoch as their default.
    operator_since = payload.since
    since = operator_since if operator_since is not None else _DEFAULT_SINCE
    if since.tzinfo is None:
        since = since.replace(tzinfo=UTC)

    started_at = datetime.now(UTC)
    legs: list[EntityBackfillOut] = []
    requested = list(dict.fromkeys(payload.entities))  # preserve order, dedup

    if "sf_leads" in requested:
        legs.append(
            await _run_sf_leads(
                integration, principal, sf_leads, tenant_id, since, commit=db.commit
            )
        )
    if "sf_events" in requested:
        legs.append(
            await _run_sf_events(integration, principal, sf_events, tenant_id, since)
        )
    if "sf_tasks" in requested:
        legs.append(
            await _run_sf_tasks(integration, principal, sf_tasks, tenant_id, since)
        )
    if "cs_patients" in requested:
        legs.append(
            await _run_cs_patients(
                integration, principal, cs_patients, tenant_id, since
            )
        )
    if "cs_appointments" in requested:
        legs.append(
            await _run_cs_appointments(
                integration, principal, cs_appointments, tenant_id, since
            )
        )
    if "carestack_accounting_transactions" in requested:
        legs.append(
            await _run_cs_accounting_transactions(
                integration,
                principal,
                cs_accounting_transactions,
                tenant_id,
                operator_since,
            )
        )
    if "carestack_payment_summary" in requested:
        legs.append(
            await _run_cs_payment_summary(
                integration, principal, cs_payment_summary, tenant_id
            )
        )

    return BackfillRunOut(
        started_at=started_at,
        finished_at=datetime.now(UTC),
        since=since,
        legs=legs,
    )


# --- Per-entity legs (sync_run open/close + safe error funnel) --------


async def _run_sf_leads(
    integration: IntegrationService,
    principal: Principal,
    svc: SfLeadIngestService,
    tenant_id: object,
    since: datetime,
    *,
    commit: Callable[[], Awaitable[None]] | None = None,
) -> EntityBackfillOut:
    entity: EntityName = "sf_leads"
    provider, object_scope = _ENTITY_META[entity]
    out = EntityBackfillOut(entity=entity)
    run = await integration.open_provider_sync_run(
        tenant_id,  # type: ignore[arg-type]
        provider=provider,
        object_scope=object_scope,
        trigger=_BACKFILL_TRIGGER,
    )
    out.sync_run_id = run.id
    try:
        # Page-commit streaming backfill (ENG-326 pattern): a
        # full-history run inside ONE transaction deadlocked against the
        # scheduled tick on 2026-06-10 and lost 9 minutes of work.
        imported = await svc.pull_all_since(
            tenant_id,  # type: ignore[arg-type]
            since,
            commit=commit,
        )
        out.imported = imported
        await _close_succeeded(
            integration,
            principal=principal,
            run_id=run.id,
            tenant_id=tenant_id,
            provider=provider,
            object_scope=object_scope,
            succeeded=imported,
            failed=0,
            out=out,
        )
    except Exception as exc:  # noqa: BLE001 — funnel per-leg failures
        await _close_failed(
            integration,
            principal=principal,
            run_id=run.id,
            tenant_id=tenant_id,
            provider=provider,
            object_scope=object_scope,
            exc=exc,
            out=out,
        )
    return out


async def _run_sf_events(
    integration: IntegrationService,
    principal: Principal,
    svc: SfEventIngestService,
    tenant_id: object,
    since: datetime,
) -> EntityBackfillOut:
    entity: EntityName = "sf_events"
    provider, object_scope = _ENTITY_META[entity]
    out = EntityBackfillOut(entity=entity)
    run = await integration.open_provider_sync_run(
        tenant_id,  # type: ignore[arg-type]
        provider=provider,
        object_scope=object_scope,
        trigger=_BACKFILL_TRIGGER,
    )
    out.sync_run_id = run.id
    try:
        result = await svc.import_all_since(tenant_id, since)  # type: ignore[arg-type]
        out.imported = result.imported_count
        out.skipped = result.skipped_count
        await _close_succeeded(
            integration,
            principal=principal,
            run_id=run.id,
            tenant_id=tenant_id,
            provider=provider,
            object_scope=object_scope,
            succeeded=result.imported_count,
            failed=result.skipped_count,
            out=out,
        )
    except Exception as exc:  # noqa: BLE001
        await _close_failed(
            integration,
            principal=principal,
            run_id=run.id,
            tenant_id=tenant_id,
            provider=provider,
            object_scope=object_scope,
            exc=exc,
            out=out,
        )
    return out


async def _run_sf_tasks(
    integration: IntegrationService,
    principal: Principal,
    svc: SfTaskIngestService,
    tenant_id: object,
    since: datetime,
) -> EntityBackfillOut:
    entity: EntityName = "sf_tasks"
    provider, object_scope = _ENTITY_META[entity]
    out = EntityBackfillOut(entity=entity)
    run = await integration.open_provider_sync_run(
        tenant_id,  # type: ignore[arg-type]
        provider=provider,
        object_scope=object_scope,
        trigger=_BACKFILL_TRIGGER,
    )
    out.sync_run_id = run.id
    try:
        result = await svc.import_all_since(tenant_id, since)  # type: ignore[arg-type]
        out.imported = result.imported_count
        out.skipped = result.skipped_count
        await _close_succeeded(
            integration,
            principal=principal,
            run_id=run.id,
            tenant_id=tenant_id,
            provider=provider,
            object_scope=object_scope,
            succeeded=result.imported_count,
            failed=result.skipped_count,
            out=out,
        )
    except Exception as exc:  # noqa: BLE001
        await _close_failed(
            integration,
            principal=principal,
            run_id=run.id,
            tenant_id=tenant_id,
            provider=provider,
            object_scope=object_scope,
            exc=exc,
            out=out,
        )
    return out


async def _run_cs_patients(
    integration: IntegrationService,
    principal: Principal,
    svc: CareStackPatientIngestService,
    tenant_id: object,
    since: datetime,
) -> EntityBackfillOut:
    entity: EntityName = "cs_patients"
    provider, object_scope = _ENTITY_META[entity]
    out = EntityBackfillOut(entity=entity)
    run = await integration.open_provider_sync_run(
        tenant_id,  # type: ignore[arg-type]
        provider=provider,
        object_scope=object_scope,
        trigger=_BACKFILL_TRIGGER,
    )
    out.sync_run_id = run.id
    try:
        result = await svc.pull_all_since(tenant_id, since)  # type: ignore[arg-type]
        out.imported = result.imported_count
        out.skipped = result.skipped_count
        out.pages = result.page_count
        out.next_continue_token = result.next_continue_token
        await _close_succeeded(
            integration,
            principal=principal,
            run_id=run.id,
            tenant_id=tenant_id,
            provider=provider,
            object_scope=object_scope,
            succeeded=result.imported_count,
            failed=result.skipped_count,
            out=out,
        )
    except Exception as exc:  # noqa: BLE001
        await _close_failed(
            integration,
            principal=principal,
            run_id=run.id,
            tenant_id=tenant_id,
            provider=provider,
            object_scope=object_scope,
            exc=exc,
            out=out,
        )
    return out


async def _run_cs_appointments(
    integration: IntegrationService,
    principal: Principal,
    svc: CareStackAppointmentIngestService,
    tenant_id: object,
    since: datetime,
) -> EntityBackfillOut:
    entity: EntityName = "cs_appointments"
    provider, object_scope = _ENTITY_META[entity]
    out = EntityBackfillOut(entity=entity)
    run = await integration.open_provider_sync_run(
        tenant_id,  # type: ignore[arg-type]
        provider=provider,
        object_scope=object_scope,
        trigger=_BACKFILL_TRIGGER,
    )
    out.sync_run_id = run.id
    try:
        result = await svc.pull_all_since(tenant_id, since)  # type: ignore[arg-type]
        out.imported = result.imported_count
        out.skipped = result.skipped_count
        out.pages = result.page_count
        out.next_continue_token = result.next_continue_token
        await _close_succeeded(
            integration,
            principal=principal,
            run_id=run.id,
            tenant_id=tenant_id,
            provider=provider,
            object_scope=object_scope,
            succeeded=result.imported_count,
            failed=result.skipped_count,
            out=out,
        )
    except Exception as exc:  # noqa: BLE001
        await _close_failed(
            integration,
            principal=principal,
            run_id=run.id,
            tenant_id=tenant_id,
            provider=provider,
            object_scope=object_scope,
            exc=exc,
            out=out,
        )
    return out


async def _run_cs_accounting_transactions(
    integration: IntegrationService,
    principal: Principal,
    svc: CareStackAccountingTransactionIngestService,
    tenant_id: object,
    operator_since: datetime | None,
) -> EntityBackfillOut:
    """ENG-285 — throttled historical backfill of CareStack accounting transactions.

    Anchors at ``2026-01-01T00:00:00Z`` when the operator omits
    ``since`` (the fiscal year being reconstructed). The underlying
    ``pull_all_since`` method handles unbounded pagination, throttle
    between pages, and exponential backoff on 429/5xx — if backoff is
    exhausted the response carries ``next_continue_token`` so the
    operator can resume.
    """
    entity: EntityName = "carestack_accounting_transactions"
    provider, object_scope = _ENTITY_META[entity]
    out = EntityBackfillOut(entity=entity)
    run = await integration.open_provider_sync_run(
        tenant_id,  # type: ignore[arg-type]
        provider=provider,
        object_scope=object_scope,
        trigger=_BACKFILL_TRIGGER,
    )
    out.sync_run_id = run.id
    try:
        effective_since = (
            operator_since
            if operator_since is not None
            else _PAYMENTS_BACKFILL_DEFAULT_SINCE
        )
        if effective_since.tzinfo is None:
            effective_since = effective_since.replace(tzinfo=UTC)
        result = await svc.pull_all_since(tenant_id, effective_since)  # type: ignore[arg-type]
        out.imported = result.imported_count
        out.skipped = result.skipped_count
        out.pages = result.page_count
        out.next_continue_token = result.next_continue_token
        await _close_succeeded(
            integration,
            principal=principal,
            run_id=run.id,
            tenant_id=tenant_id,
            provider=provider,
            object_scope=object_scope,
            succeeded=result.imported_count,
            failed=result.skipped_count,
            out=out,
        )
    except Exception as exc:  # noqa: BLE001 — funnel per-leg failures
        await _close_failed(
            integration,
            principal=principal,
            run_id=run.id,
            tenant_id=tenant_id,
            provider=provider,
            object_scope=object_scope,
            exc=exc,
            out=out,
        )
    return out


async def _run_cs_payment_summary(
    integration: IntegrationService,
    principal: Principal,
    svc: CareStackPaymentSummaryIngestService,
    tenant_id: object,
) -> EntityBackfillOut:
    """ENG-285 — throttled per-patient balance snapshot sweep.

    Iterates all linked CareStack patients with sleep + backoff. The
    ``since`` parameter is not meaningful — CareStack has no bulk feed
    for balances and the snapshot is point-in-time per patient.
    Per-patient errors are failure-isolated by the service: counted as
    ``error_count`` and folded into ``out.skipped`` so the sync_run
    reflects the partial outcome.
    """
    entity: EntityName = "carestack_payment_summary"
    provider, object_scope = _ENTITY_META[entity]
    out = EntityBackfillOut(entity=entity)
    run = await integration.open_provider_sync_run(
        tenant_id,  # type: ignore[arg-type]
        provider=provider,
        object_scope=object_scope,
        trigger=_BACKFILL_TRIGGER,
    )
    out.sync_run_id = run.id
    try:
        result = await svc.pull_all_payment_summaries(tenant_id)  # type: ignore[arg-type]
        out.imported = result.snapshot_count
        # Per-patient errors (rate-limit exhaustion, persistent 5xx)
        # surface alongside skipped (no usable source_id) so the leg's
        # records_failed count is the true non-snapshot total.
        out.skipped = result.skipped_count + result.error_count
        await _close_succeeded(
            integration,
            principal=principal,
            run_id=run.id,
            tenant_id=tenant_id,
            provider=provider,
            object_scope=object_scope,
            succeeded=result.snapshot_count,
            failed=result.skipped_count + result.error_count,
            out=out,
        )
    except Exception as exc:  # noqa: BLE001 — funnel per-leg failures
        await _close_failed(
            integration,
            principal=principal,
            run_id=run.id,
            tenant_id=tenant_id,
            provider=provider,
            object_scope=object_scope,
            exc=exc,
            out=out,
        )
    return out


# --- sync_run lifecycle helpers --------------------------------------


async def _close_succeeded(
    integration: IntegrationService,
    *,
    principal: Principal,
    run_id: UUID,
    tenant_id: object,
    provider: str,
    object_scope: str,
    succeeded: int,
    failed: int,
    out: EntityBackfillOut,
) -> None:
    status: ProviderSyncStatus
    if failed > 0:
        status = "partial" if succeeded > 0 else "failed"
    else:
        status = "succeeded"
    await integration.close_provider_sync_run(
        tenant_id,  # type: ignore[arg-type]
        sync_run_id=run_id,
        principal=principal,
        provider=provider,
        object_scope=object_scope,
        status=status,
        records_total=succeeded + failed,
        records_succeeded=succeeded,
        records_failed=failed,
    )
    out.sync_run_status = status


async def _close_failed(
    integration: IntegrationService,
    *,
    principal: Principal,
    run_id: UUID,
    tenant_id: object,
    provider: str,
    object_scope: str,
    exc: BaseException,
    out: EntityBackfillOut,
) -> None:
    status: ProviderSyncStatus = (
        "skipped_credential" if _is_credential_error(exc) else "failed"
    )
    error_summary = _safe_msg(exc)
    await integration.close_provider_sync_run(
        tenant_id,  # type: ignore[arg-type]
        sync_run_id=run_id,
        principal=principal,
        provider=provider,
        object_scope=object_scope,
        status=status,
        records_total=out.imported + out.skipped,
        records_succeeded=out.imported,
        records_failed=out.skipped,
        error=error_summary,
    )
    out.sync_run_status = status
    # Skipped credential is an expected condition (e.g. tenant disconnected
    # SF after onboarding) — surface a stable hint string instead of the
    # raw exception text so the UI/operator can branch on it.
    out.error = (
        "no active credential for this tenant/provider"
        if status == "skipped_credential"
        else error_summary
    )


def _is_credential_error(exc: BaseException) -> bool:
    name = exc.__class__.__name__
    if any(name.endswith(suffix) for suffix in _CREDENTIAL_ERROR_SUFFIXES):
        return True
    if isinstance(exc, PlatformError) and exc.code in {
        "INTEGRATION_NOT_CONNECTED",
        "NO_CREDENTIAL",
    }:
        return True
    return False


def _safe_msg(exc: BaseException) -> str:
    """Short, non-stack error string suitable for the response body."""
    message = str(exc).strip() or exc.__class__.__name__
    return message[:500]
