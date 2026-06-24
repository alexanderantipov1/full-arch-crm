"""Cloud Run Job entrypoint for full-history provider backfill.

Pulls all entity types (sf_leads, sf_events, sf_tasks, cs_patients,
cs_appointments, cs_treatments, cs_accounting_transactions) from epoch
for every active tenant. Each entity runs in its own DB session so a
failure in one does not roll back the others.

``cs_accounting_transactions`` re-runs the ENG-285 ``pull_all_since``
path: it re-captures the ledger and (re)emits payment timeline events.
Because raw capture dedupes on ``(id, lastUpdatedOn)`` and events use
``create_event_idempotent``, it is safe to re-run — and it backfills
payment events for rows that were captured before their patient was
linked (ENG-324 follow-up).

Usage (local):
    python -m apps.worker.jobs.backfill_full

Usage (Cloud Run Job):
    gcloud run jobs execute fusion-job-backfill ...
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from packages.actor.service import ActorService
from packages.core.exceptions import PlatformError
from packages.core.logging import configure_logging, get_logger
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.ingest.carestack_accounting_transaction_service import (
    CareStackAccountingTransactionIngestService,
)
from packages.ingest.carestack_appointment_service import (
    CareStackAppointmentIngestService,
)
from packages.ingest.carestack_patient_service import CareStackPatientIngestService
from packages.ingest.carestack_treatment_service import (
    CareStackTreatmentIngestService,
)
from packages.ingest.responsibility_resolver import (
    ActorResolverProtocol,
    FunnelResponsibilityResolver,
)
from packages.ingest.sf_event_service import (
    SfEventClientProtocol,
    SfEventIngestService,
)
from packages.ingest.sf_lead_service import SfClientProtocol, SfLeadIngestService
from packages.ingest.sf_task_service import (
    SfTaskClientProtocol,
    SfTaskIngestService,
)
from packages.integrations.carestack import CareStackClient
from packages.integrations.salesforce import SfClient
from packages.integrations.salesforce.tokens import SfTokens
from packages.integrations.service import IntegrationService
from packages.ops.service import OpsService
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)

log = get_logger("worker.backfill_full")

_EPOCH = datetime(2015, 1, 1, tzinfo=UTC)
# Accounting/money backfill is scoped to the current fiscal year only
# (ENG-285): we reconstruct 2026 financials, not full provider history.
# This also keeps the CareStack ``modifiedSince`` scan tight.
_CS_ACCOUNTING_SINCE = datetime(2026, 1, 1, tzinfo=UTC)
_TRIGGER = "backfill-job"


def _system_principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
        context={"actor": "system:backfill_job"},
    )


def _build_responsibility_resolver(session: AsyncSession) -> FunnelResponsibilityResolver:
    """Construct the funnel-responsibility resolver at the worker boundary.

    Same pattern as ``apps/worker/jobs/ingest_scheduled.py``: ``packages/
    ingest`` cannot import ``packages/actor`` (matrix in
    ``packages/CLAUDE.md``), so ``ActorService`` is built here and handed
    to the resolver via :class:`ActorResolverProtocol`.
    """
    return FunnelResponsibilityResolver(
        OpsService(session),
        cast(ActorResolverProtocol, ActorService(session)),
    )


class _ActorNameResolverAdapter:
    """Worker-boundary adapter: external party id → ``actor.actor`` name (ENG-465).

    Mirrors the adapter in ``apps/worker/jobs/ingest_scheduled.py`` so the deep
    CareStack appointment backfill resolves the DOCTOR (and TC owner) name the
    same way the scheduled pull does. ``packages/ingest`` may not import
    ``packages/actor``; this app-boundary adapter satisfies the ingest-side
    ``ActorNameResolver`` Protocol by delegating to
    ``ActorService.find_by_identifier``.
    """

    def __init__(self, actors: ActorService) -> None:
        self._actors = actors

    async def resolve_actor_name(
        self, tenant_id: TenantId, kind: str, value: str
    ) -> str | None:
        actor = await self._actors.find_by_identifier(tenant_id, kind, value)
        return actor.name if actor is not None else None


def _build_actor_name_resolver(session: AsyncSession) -> _ActorNameResolverAdapter:
    """ENG-465: actor-name resolver for the deep CareStack appointment backfill."""
    return _ActorNameResolverAdapter(ActorService(session))


_ALL_ENTITIES = (
    "sf_leads",
    "sf_events",
    "sf_tasks",
    "cs_patients",
    "cs_appointments",
    "cs_treatments",
    "cs_accounting_transactions",
    "merge_split_persons",
)


async def _get_sf_client(
    cred_svc: IntegrationCredentialService, tenant_id: TenantId
) -> SfClient | None:
    try:
        oauth_payload = await cred_svc.read_for(
            tenant_id, "salesforce", "oauth_token"
        )
    except (NoCredentialError, PlatformError):
        return None
    try:
        api_key_payload: dict[str, object] | None = await cred_svc.read_for(
            tenant_id, "salesforce", "api_key"
        )
    except (NoCredentialError, PlatformError):
        api_key_payload = None
    async def _noop_refresh(_tokens: SfTokens) -> None:
        pass

    return SfClient.from_credential(
        oauth_payload,
        on_refresh=_noop_refresh,
        api_key_payload=api_key_payload,
    )


async def _get_cs_client(
    cred_svc: IntegrationCredentialService, tenant_id: TenantId
) -> CareStackClient | None:
    try:
        payload = await cred_svc.read_for(
            tenant_id, "carestack", "password_grant"
        )
    except (NoCredentialError, PlatformError):
        return None
    return CareStackClient.from_credential(payload)


async def _backfill_sf_leads(
    tenant_id: TenantId, principal: Principal
) -> dict[str, object]:
    async with async_session() as session:
        cred_svc = IntegrationCredentialService(session)
        sf = await _get_sf_client(cred_svc, tenant_id)
        if sf is None:
            log.info("backfill.sf_leads.skipped", tenant_id=str(tenant_id))
            return {"status": "skipped_credential"}
        integration = IntegrationService(session)
        svc = SfLeadIngestService(
            session=session,
            sf_client=cast(SfClientProtocol, sf),
            responsibility_resolver=_build_responsibility_resolver(session),
        )
        run = await integration.open_provider_sync_run(
            tenant_id, provider="salesforce", object_scope="lead",
            trigger=_TRIGGER,
        )
        try:
            imported = await svc.pull_all_since(tenant_id, _EPOCH)
            await integration.close_provider_sync_run(
                tenant_id, sync_run_id=run.id, principal=principal,
                provider="salesforce", object_scope="lead",
                status="succeeded", records_total=imported,
                records_succeeded=imported, records_failed=0,
            )
            log.info("backfill.sf_leads.done", imported=imported)
            return {"status": "succeeded", "imported": imported}
        except Exception as exc:  # noqa: BLE001
            await integration.close_provider_sync_run(
                tenant_id, sync_run_id=run.id, principal=principal,
                provider="salesforce", object_scope="lead",
                status="failed", records_total=0,
                records_succeeded=0, records_failed=0,
                error=str(exc)[:500],
            )
            log.error("backfill.sf_leads.failed", error=str(exc)[:200])
            return {"status": "failed", "error": str(exc)[:200]}


async def _backfill_sf_events(
    tenant_id: TenantId, principal: Principal
) -> dict[str, object]:
    async with async_session() as session:
        cred_svc = IntegrationCredentialService(session)
        sf = await _get_sf_client(cred_svc, tenant_id)
        if sf is None:
            return {"status": "skipped_credential"}
        integration = IntegrationService(session)
        svc = SfEventIngestService(
            session=session,
            sf_client=cast(SfEventClientProtocol, sf),
        )
        run = await integration.open_provider_sync_run(
            tenant_id, provider="salesforce", object_scope="event",
            trigger=_TRIGGER,
        )
        try:
            result = await svc.import_all_since(tenant_id, _EPOCH)
            await integration.close_provider_sync_run(
                tenant_id, sync_run_id=run.id, principal=principal,
                provider="salesforce", object_scope="event",
                status="succeeded",
                records_total=result.imported_count + result.skipped_count,
                records_succeeded=result.imported_count,
                records_failed=result.skipped_count,
            )
            log.info("backfill.sf_events.done", imported=result.imported_count)
            return {"status": "succeeded", "imported": result.imported_count}
        except Exception as exc:  # noqa: BLE001
            await integration.close_provider_sync_run(
                tenant_id, sync_run_id=run.id, principal=principal,
                provider="salesforce", object_scope="event",
                status="failed", records_total=0,
                records_succeeded=0, records_failed=0,
                error=str(exc)[:500],
            )
            log.error("backfill.sf_events.failed", error=str(exc)[:200])
            return {"status": "failed", "error": str(exc)[:200]}


async def _backfill_sf_tasks(
    tenant_id: TenantId, principal: Principal
) -> dict[str, object]:
    async with async_session() as session:
        cred_svc = IntegrationCredentialService(session)
        sf = await _get_sf_client(cred_svc, tenant_id)
        if sf is None:
            return {"status": "skipped_credential"}
        integration = IntegrationService(session)
        svc = SfTaskIngestService(
            session=session,
            sf_client=cast(SfTaskClientProtocol, sf),
            responsibility_resolver=_build_responsibility_resolver(session),
        )
        run = await integration.open_provider_sync_run(
            tenant_id, provider="salesforce", object_scope="task",
            trigger=_TRIGGER,
        )
        try:
            result = await svc.import_all_since(tenant_id, _EPOCH)
            await integration.close_provider_sync_run(
                tenant_id, sync_run_id=run.id, principal=principal,
                provider="salesforce", object_scope="task",
                status="succeeded",
                records_total=result.imported_count + result.skipped_count,
                records_succeeded=result.imported_count,
                records_failed=result.skipped_count,
            )
            log.info("backfill.sf_tasks.done", imported=result.imported_count)
            return {"status": "succeeded", "imported": result.imported_count}
        except Exception as exc:  # noqa: BLE001
            await integration.close_provider_sync_run(
                tenant_id, sync_run_id=run.id, principal=principal,
                provider="salesforce", object_scope="task",
                status="failed", records_total=0,
                records_succeeded=0, records_failed=0,
                error=str(exc)[:500],
            )
            log.error("backfill.sf_tasks.failed", error=str(exc)[:200])
            return {"status": "failed", "error": str(exc)[:200]}


async def _backfill_cs_patients(
    tenant_id: TenantId, principal: Principal
) -> dict[str, object]:
    async with async_session() as session:
        cred_svc = IntegrationCredentialService(session)
        cs = await _get_cs_client(cred_svc, tenant_id)
        if cs is None:
            log.info("backfill.cs_patients.skipped", tenant_id=str(tenant_id))
            return {"status": "skipped_credential"}
        integration = IntegrationService(session)
        svc = CareStackPatientIngestService(
            session=session, carestack_client=cs,
        )
        run = await integration.open_provider_sync_run(
            tenant_id, provider="carestack", object_scope="patient",
            trigger=_TRIGGER,
        )
        try:
            result = await svc.pull_all_since(tenant_id, _EPOCH)
            await integration.close_provider_sync_run(
                tenant_id, sync_run_id=run.id, principal=principal,
                provider="carestack", object_scope="patient",
                status="succeeded",
                records_total=result.imported_count + result.skipped_count,
                records_succeeded=result.imported_count,
                records_failed=result.skipped_count,
            )
            log.info(
                "backfill.cs_patients.done",
                imported=result.imported_count,
                pages=result.page_count,
            )
            return {
                "status": "succeeded",
                "imported": result.imported_count,
                "pages": result.page_count,
            }
        except Exception as exc:  # noqa: BLE001
            await integration.close_provider_sync_run(
                tenant_id, sync_run_id=run.id, principal=principal,
                provider="carestack", object_scope="patient",
                status="failed", records_total=0,
                records_succeeded=0, records_failed=0,
                error=str(exc)[:500],
            )
            log.error("backfill.cs_patients.failed", error=str(exc)[:200])
            return {"status": "failed", "error": str(exc)[:200]}


async def _backfill_cs_appointments(
    tenant_id: TenantId, principal: Principal
) -> dict[str, object]:
    async with async_session() as session:
        cred_svc = IntegrationCredentialService(session)
        cs = await _get_cs_client(cred_svc, tenant_id)
        if cs is None:
            return {"status": "skipped_credential"}
        integration = IntegrationService(session)
        svc = CareStackAppointmentIngestService(
            session=session,
            carestack_client=cs,
            responsibility_resolver=_build_responsibility_resolver(session),
            actor_name_resolver=_build_actor_name_resolver(session),
        )
        run = await integration.open_provider_sync_run(
            tenant_id, provider="carestack", object_scope="appointment",
            trigger=_TRIGGER,
        )
        try:
            result = await svc.pull_all_since(tenant_id, _EPOCH)
            await integration.close_provider_sync_run(
                tenant_id, sync_run_id=run.id, principal=principal,
                provider="carestack", object_scope="appointment",
                status="succeeded",
                records_total=result.imported_count + result.skipped_count,
                records_succeeded=result.imported_count,
                records_failed=result.skipped_count,
            )
            log.info(
                "backfill.cs_appointments.done",
                imported=result.imported_count,
                pages=result.page_count,
            )
            return {
                "status": "succeeded",
                "imported": result.imported_count,
                "pages": result.page_count,
            }
        except Exception as exc:  # noqa: BLE001
            await integration.close_provider_sync_run(
                tenant_id, sync_run_id=run.id, principal=principal,
                provider="carestack", object_scope="appointment",
                status="failed", records_total=0,
                records_succeeded=0, records_failed=0,
                error=str(exc)[:500],
            )
            log.error("backfill.cs_appointments.failed", error=str(exc)[:200])
            return {"status": "failed", "error": str(exc)[:200]}


async def _backfill_cs_treatments(
    tenant_id: TenantId, principal: Principal
) -> dict[str, object]:
    async with async_session() as session:
        cred_svc = IntegrationCredentialService(session)
        cs = await _get_cs_client(cred_svc, tenant_id)
        if cs is None:
            log.info("backfill.cs_treatments.skipped", tenant_id=str(tenant_id))
            return {"status": "skipped_credential"}
        integration = IntegrationService(session)
        svc = CareStackTreatmentIngestService(
            session=session, carestack_client=cs,
        )
        run = await integration.open_provider_sync_run(
            tenant_id, provider="carestack", object_scope="treatment_procedure",
            trigger=_TRIGGER,
        )
        try:
            result = await svc.pull_all_since(tenant_id, _EPOCH)
            await integration.close_provider_sync_run(
                tenant_id, sync_run_id=run.id, principal=principal,
                provider="carestack", object_scope="treatment_procedure",
                status="succeeded",
                records_total=result.imported_count + result.skipped_count,
                records_succeeded=result.imported_count,
                records_failed=result.skipped_count,
            )
            log.info(
                "backfill.cs_treatments.done",
                imported=result.imported_count,
                pages=result.page_count,
            )
            return {
                "status": "succeeded",
                "imported": result.imported_count,
                "pages": result.page_count,
            }
        except Exception as exc:  # noqa: BLE001
            await integration.close_provider_sync_run(
                tenant_id, sync_run_id=run.id, principal=principal,
                provider="carestack", object_scope="treatment_procedure",
                status="failed", records_total=0,
                records_succeeded=0, records_failed=0,
                error=str(exc)[:500],
            )
            log.error("backfill.cs_treatments.failed", error=str(exc)[:200])
            return {"status": "failed", "error": str(exc)[:200]}


async def _backfill_cs_accounting_transactions(
    tenant_id: TenantId, principal: Principal
) -> dict[str, object]:
    async with async_session() as session:
        cred_svc = IntegrationCredentialService(session)
        cs = await _get_cs_client(cred_svc, tenant_id)
        if cs is None:
            return {"status": "skipped_credential"}
        integration = IntegrationService(session)
        svc = CareStackAccountingTransactionIngestService(
            session=session, carestack_client=cs,
        )
        run = await integration.open_provider_sync_run(
            tenant_id, provider="carestack", object_scope="accounting_transaction",
            trigger=_TRIGGER,
        )
        try:
            result = await svc.pull_all_since(tenant_id, _CS_ACCOUNTING_SINCE)
            await integration.close_provider_sync_run(
                tenant_id, sync_run_id=run.id, principal=principal,
                provider="carestack", object_scope="accounting_transaction",
                status="succeeded",
                records_total=result.imported_count + result.skipped_count,
                records_succeeded=result.imported_count,
                records_failed=result.skipped_count,
            )
            log.info(
                "backfill.cs_accounting_transactions.done",
                imported=result.imported_count,
                skipped=result.skipped_count,
                pages=result.page_count,
            )
            return {
                "status": "succeeded",
                "imported": result.imported_count,
                "skipped": result.skipped_count,
                "pages": result.page_count,
            }
        except Exception as exc:  # noqa: BLE001
            await integration.close_provider_sync_run(
                tenant_id, sync_run_id=run.id, principal=principal,
                provider="carestack", object_scope="accounting_transaction",
                status="failed", records_total=0,
                records_succeeded=0, records_failed=0,
                error=str(exc)[:500],
            )
            log.error(
                "backfill.cs_accounting_transactions.failed", error=str(exc)[:200]
            )
            return {"status": "failed", "error": str(exc)[:200]}


async def _reconcile_merge_split_persons(
    tenant_id: TenantId, principal: Principal
) -> dict[str, object]:
    """Nightly identity reconciliation (ENG-406).

    The live resolver auto-merges named contacts on email/phone (Tier 1),
    but ambiguous arrivals create split persons that silently break the
    contact -> consultation -> payment joins (ENG-403). Re-running the
    idempotent ENG-404 stitcher every night keeps drift at zero instead of
    letting it accumulate until a human notices missing money. The script
    ships in the same image under /app/infra; importlib keeps the worker
    free of a package dependency on operator scripts.
    """
    del principal  # merge policy is data-driven; no actor-scoped reads
    try:
        module = _load_merge_script()
    except Exception as exc:  # noqa: BLE001
        log.error("reconcile.merge_split.load_failed", error=str(exc)[:200])
        return {"status": "failed", "error": str(exc)[:200]}
    try:
        buckets = await module.run(apply=True, limit=None, tenant=tenant_id)
    except Exception as exc:  # noqa: BLE001
        log.error("reconcile.merge_split.failed", error=str(exc)[:200])
        return {"status": "failed", "error": str(exc)[:200]}
    log.info(
        "reconcile.merge_split.done",
        merged=buckets.merged,
        matched_by_email=buckets.matched_by_email,
        matched_by_phone=buckets.matched_by_phone,
        name_conflict=buckets.name_conflict,
        no_candidate=buckets.no_candidate,
        no_identifiers=buckets.no_identifiers,
        dob_conflict=buckets.dob_conflict,
    )
    return {
        "status": "ok",
        "merged": buckets.merged,
        "name_conflict": buckets.name_conflict,
    }


def _load_merge_script():
    """Load the ENG-404 stitcher from infra/scripts via importlib.

    The module must be registered in ``sys.modules`` BEFORE exec_module —
    its ``@dataclass`` decorators resolve ``__module__`` through
    ``sys.modules`` and crash with ``AttributeError: 'NoneType'`` otherwise.
    parents[3] of apps/worker/jobs/backfill_full.py is the repo root
    (``/app`` in the image); parents[2] is ``apps/``, which has no infra/.
    """
    import importlib.util
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[3] / "infra" / "scripts" / (
        "merge_split_lead_persons.py"
    )
    spec = importlib.util.spec_from_file_location("merge_split_lead_persons", script)
    if spec is None or spec.loader is None:  # pragma: no cover - image layout
        raise FileNotFoundError(script)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_ENTITY_RUNNERS = {
    "sf_leads": _backfill_sf_leads,
    "sf_events": _backfill_sf_events,
    "sf_tasks": _backfill_sf_tasks,
    "cs_patients": _backfill_cs_patients,
    "cs_appointments": _backfill_cs_appointments,
    "cs_treatments": _backfill_cs_treatments,
    "cs_accounting_transactions": _backfill_cs_accounting_transactions,
    "merge_split_persons": _reconcile_merge_split_persons,
}


async def _backfill_tenant(
    tenant_id: TenantId, entities: tuple[str, ...] = _ALL_ENTITIES
) -> dict[str, object]:
    principal = _system_principal(tenant_id)
    results: dict[str, object] = {"tenant_id": str(tenant_id)}

    for name in entities:
        runner = _ENTITY_RUNNERS[name]
        results[name] = await runner(tenant_id, principal)

    return results


async def run(entities: tuple[str, ...] = _ALL_ENTITIES) -> list[dict[str, object]]:
    configure_logging()
    log.info("backfill_full.start", entities=list(entities))

    from packages.tenant.service import TenantService

    async with async_session() as session:
        tenant_svc = TenantService(session)
        tenants = await tenant_svc.list_tenants()
        tenant_ids = [t.id for t in tenants]

    log.info("backfill_full.tenants", count=len(tenant_ids))
    all_results = []
    for tid in tenant_ids:
        result = await _backfill_tenant(TenantId(tid), entities=entities)
        all_results.append(result)
        log.info("backfill_full.tenant_done", tenant_id=str(tid), result=result)

    log.info("backfill_full.complete", tenants=len(all_results))
    return all_results


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Full-history provider backfill.")
    parser.add_argument(
        "--entities",
        nargs="+",
        default=None,
        help="Entity names to backfill (e.g. cs_patients cs_appointments). Default: all.",
    )
    args = parser.parse_args()

    if args.entities:
        flat: list[str] = []
        for raw in args.entities:
            flat.extend(e.strip() for e in raw.split(",") if e.strip())
        for e in flat:
            if e not in _ALL_ENTITIES:
                parser.error(f"Unknown entity: {e}. Valid: {', '.join(_ALL_ENTITIES)}")
        chosen = tuple(flat)
    else:
        chosen = _ALL_ENTITIES

    asyncio.run(run(entities=chosen))


if __name__ == "__main__":
    main()
