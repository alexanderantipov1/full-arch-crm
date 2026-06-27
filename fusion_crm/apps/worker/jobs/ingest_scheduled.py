"""ENG-222: scheduled ingestion fan-out.

Cron entry point (``ingest_scheduled_fanout``) iterates every active
tenant and runs both the CareStack and Salesforce pull pipelines.
Default cadence: every 24 hours, configurable via the env
``INGEST_INTERVAL_HOURS``.

Per-tenant pulls re-use the same services the HTTP endpoints expose:

- CareStack: ``CareStackPatientIngestService`` +
  ``CareStackAppointmentIngestService`` +
  ``CareStackTreatmentIngestService`` +
  ``CareStackInvoiceIngestService``.
- Salesforce: ``SfLeadIngestService.pull_recent`` +
  ``SfEventIngestService.import_recent_events`` +
  ``SfTaskIngestService.import_recent_tasks`` +
  ``SfOpportunityIngestService.import_recent_opportunities`` +
  ``SfCaseIngestService.import_recent_cases``.

Why this lives in the worker, not the API:

- Cron-driven background ingestion is exactly the workload arq exists
  for. Putting it behind an API endpoint would require an external
  scheduler (Cloud Scheduler in prod) to call back into the API,
  doubling network hops and auth surface.

What this PR does NOT do (deferred to ENG-223 or follow-ups):

- Postgres advisory lock per ``(tenant_id, provider)`` to avoid races
  with a concurrent manual ``/pull``. Today the fan-out runs once per
  24h so the race window is tiny; revisit if cadence drops.
- Per-tenant cadence override via ``tenant.setting`` (deferred to
  ENG-225 / UI work).
- ``sync_disabled`` tenant setting (treat all tenants as enabled in
  v1; the column does not exist yet).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.actor.service import ActorService
from packages.core.exceptions import NotFoundError, PlatformError
from packages.core.logging import get_logger
from packages.core.security import Principal, Role
from packages.core.types import PersonUID, TenantId
from packages.db.session import async_session
from packages.identity.service import IdentityService
from packages.ingest.carestack_accounting_transaction_service import (
    CareStackAccountingTransactionIngestService,
)
from packages.ingest.carestack_appointment_service import (
    CareStackAppointmentIngestService,
)
from packages.ingest.carestack_invoice_service import (
    CareStackInvoiceIngestService,
)
from packages.ingest.carestack_patient_service import CareStackPatientIngestService
from packages.ingest.carestack_payment_summary_service import (
    CareStackPaymentSummaryIngestService,
)
from packages.ingest.carestack_treatment_plan_service import (
    CareStackTreatmentPlanIngestService,
)
from packages.ingest.carestack_treatment_service import (
    CareStackTreatmentIngestService,
)
from packages.ingest.consultation_notify import ConsultationNotifier
from packages.ingest.responsibility_resolver import (
    ActorResolverProtocol,
    FunnelResponsibilityResolver,
)
from packages.ingest.service import IngestService
from packages.ingest.sf_account_service import (
    SfAccountClientProtocol,
    SfAccountIngestService,
)
from packages.ingest.sf_case_service import (
    SfCaseClientProtocol,
    SfCaseIngestService,
)
from packages.ingest.sf_contact_service import (
    SfContactClientProtocol,
    SfContactIngestService,
)
from packages.ingest.sf_event_service import (
    SfEventClientProtocol,
    SfEventIngestService,
)
from packages.ingest.sf_lead_service import (
    SfClientProtocol,
    SfLeadIngestService,
    SfLeadNotifySignal,
)
from packages.ingest.sf_opportunity_history_service import (
    SfOpportunityHistoryClientProtocol,
    SfOpportunityHistoryIngestService,
)
from packages.ingest.sf_opportunity_service import (
    SfOpportunityClientProtocol,
    SfOpportunityIngestService,
)
from packages.ingest.sf_schema_sync import (
    SF_FULL_FIDELITY_OBJECTS,
    SfSchemaSync,
)
from packages.ingest.sf_task_service import (
    SfTaskClientProtocol,
    SfTaskIngestService,
)
from packages.integrations.carestack import CareStackClient
from packages.integrations.carestack.exceptions import (
    CareStackApiError,
    CareStackNotConnectedError,
)
from packages.integrations.chat.event_service import NotificationEventService
from packages.integrations.chat.events import EVENT_LEAD_CREATED
from packages.integrations.salesforce import SfClient
from packages.integrations.salesforce.exceptions import (
    SfApiError,
    SfNotConnectedError,
)
from packages.integrations.salesforce.tokens import SfTokens
from packages.integrations.service import IntegrationService, ProviderSyncStatus
from packages.ops.service import OpsService
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)
from packages.tenant.service import LocationService


def _build_responsibility_resolver(session: AsyncSession) -> FunnelResponsibilityResolver:
    """Construct the funnel-responsibility resolver at the worker boundary.

    ``packages/ingest`` cannot import ``packages/actor`` (matrix rule in
    ``packages/CLAUDE.md``); the concrete ``ActorService`` is therefore
    wired here and handed to the resolver via :class:`ActorResolverProtocol`.
    """
    return FunnelResponsibilityResolver(
        OpsService(session),
        cast(ActorResolverProtocol, ActorService(session)),
    )


class _ActorNameResolverAdapter:
    """Worker-boundary adapter: external party id → ``actor.actor`` name.

    ENG-465: the CareStack appointment ingest needs the DOCTOR name (from the
    appointment's ``providerIds``) and, when the SF projection has no cached
    owner name, the TC OWNER name (from the SF user id). ``packages/ingest``
    may not import ``packages/actor``, so this thin adapter — constructed here
    where the worker already depends on both — satisfies the
    :class:`ActorNameResolver` Protocol by delegating to
    ``ActorService.find_by_identifier`` and returning the matched actor's
    display name (``None`` when no actor is mapped to the id yet).
    """

    def __init__(self, actors: ActorService) -> None:
        self._actors = actors

    async def resolve_actor_name(
        self, tenant_id: TenantId, kind: str, value: str
    ) -> str | None:
        actor = await self._actors.find_by_identifier(tenant_id, kind, value)
        return actor.name if actor is not None else None


def _build_actor_name_resolver(session: AsyncSession) -> _ActorNameResolverAdapter:
    """Construct the ENG-465 actor-name resolver at the worker boundary."""
    return _ActorNameResolverAdapter(ActorService(session))

log = get_logger("worker.ingest_scheduled")

_CS_OBJECT_SCOPE = (
    "location,patient,appointment,treatment_procedure,treatment_plan,invoice,"
    "accounting_transaction,payment_summary"
)
_SF_OBJECT_SCOPE = (
    "lead,event,task,opportunity,case,contact,account,opportunity_history"
)


def _scheduler_principal(tenant_id: TenantId) -> Principal:
    """Construct the audit principal for the cron tick.

    The scheduler is a system actor — `Role.SYSTEM` per `packages/core/
    security.py`. Audit rows produced by token rotation / consultation
    upserts will attribute to this principal so the trail is clear.
    """
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
        context={"actor": "system:ingest_scheduler"},
    )


async def _emit_lead_created_notifications(
    session: AsyncSession,
    tenant_id: TenantId,
    signals: tuple[SfLeadNotifySignal, ...],
    *,
    principal: Principal,
) -> None:
    """Fan genuinely-new ingested leads out to chat (ENG-456).

    Called at the SF scheduled-pull worker boundary with the NON-PII
    ``notify_signals`` collected by ``pull_recent_for_sync``. For each signal
    it calls :meth:`NotificationEventService.emit` with:

    * ``dedupe_key = sf_lead_id`` — the stable SF entity id, so a re-pull of the
      same lead is a guaranteed no-op via the durable
      ``integrations.notification_emitted`` ledger;
    * ``source_created_at = SF CreatedDate`` (tz-aware UTC) — feeds the
      historical cutoff guard so pre-cutoff leads do not page anyone;
    * a context carrying the ``source`` label, the optional ``has_phone``
      boolean (drives the missing-phone field-control rule), and — ENG-460 —
      the patient's REAL ``name`` + ``phone`` resolved via
      :class:`IdentityService`. The messenger is an authorized PHI surface,
      so the rich card shows the real person; the identity lookup happens
      HERE at the worker boundary (the worker owns the session and may read
      ``identity``), keeping the NON-PII ``SfLeadNotifySignal`` unchanged.
      One lookup per genuinely-new lead is cheap (new leads are rare).

    ``emit`` is itself a safe no-op when notifications are globally disabled
    (the default), so this wiring lands dark until an operator flips the flag.
    The outbox rows + ledger claims share ``session`` and commit atomically
    with the lead upsert at the ``async_session`` block exit.
    """
    if not signals:
        return
    events = NotificationEventService(session)
    identity = IdentityService(session)
    for signal in signals:
        # ENG-460: resolve the real name + phone at the boundary so the card
        # is useful to staff. Failure to resolve is non-fatal — the card
        # still posts with whatever fields are present (``{{name}}`` /
        # ``{{phone}}`` render blank when absent), and a missing person must
        # never crash an ingest tick.
        name: str | None = None
        phone: str | None = None
        person_uid = PersonUID(signal.person_uid)
        try:
            person = await identity.get_person(tenant_id, person_uid)
            name = person.display_name or person.given_name or person.family_name
            phone = await identity.get_primary_phone(tenant_id, person_uid)
        except NotFoundError:
            log.info(
                "ingest_scheduled.lead_notify.person_unresolved",
                person_uid=str(signal.person_uid),
            )

        context: dict[str, object] = {
            "lead": {"source": signal.source},
            "source": signal.source,
            "name": name,
            "phone": phone,
        }
        # Only assert phone-presence when the SF record actually carried a
        # ``Phone`` key (``has_phone is not None``); UNKNOWN stays omitted so
        # the missing-phone field-control rule never fires on uncertainty.
        if signal.has_phone is not None:
            context["has_phone"] = signal.has_phone
        await events.emit(
            tenant_id,
            EVENT_LEAD_CREATED,
            context,
            principal=principal,
            person_uid=signal.person_uid,
            dedupe_key=signal.sf_lead_id,
            source_created_at=signal.source_created_at,
        )


async def pull_carestack_for_tenant(
    _ctx: dict[str, Any], tenant_id_str: str, *, max_pages: int = 20
) -> dict[str, Any]:
    """Run a bounded CareStack locations + patients + appointments +
    treatment procedures + invoices pull.

    ``max_pages`` caps ONLY the three financial feeds that resume from a
    ``lastUpdatedOn`` watermark (treatments / invoices / accounting
    transactions). Its default (20) keeps the scheduled cron tick
    byte-identical with the pre-ENG-330 behaviour; the local-dev drain
    (``run_local_sync``) passes a larger value so a fresh checkout can
    clear a multi-day backlog without waiting for many hourly ticks.
    The bounded patients / appointments / payment_summaries feeds are
    intentionally left at their existing literals — re-pulling them every
    drain pass is wasted work, so only the watermark-resuming feeds scale.

    Returns a result envelope the cron summary uses. Missing credentials
    are NOT an error — they log at INFO and short-circuit to ``skipped``.
    """
    tenant_id = TenantId(UUID(tenant_id_str))
    async with async_session() as session:
        cred_svc = IntegrationCredentialService(session)
        integration_svc = IntegrationService(session)
        principal = _scheduler_principal(tenant_id)
        try:
            payload = await cred_svc.read_for(
                tenant_id, "carestack", "password_grant"
            )
        except NoCredentialError:
            run = await integration_svc.open_provider_sync_run(
                tenant_id,
                provider="carestack",
                object_scope=_CS_OBJECT_SCOPE,
                trigger="scheduled",
                account_status="disconnected",
            )
            await integration_svc.close_provider_sync_run(
                tenant_id,
                sync_run_id=run.id,
                principal=principal,
                provider="carestack",
                object_scope=_CS_OBJECT_SCOPE,
                status="skipped_credential",
                records_total=0,
                records_succeeded=0,
                records_failed=0,
                error="no active carestack credential",
            )
            log.info(
                "ingest_scheduled.carestack.no_credential",
                tenant_id=tenant_id_str,
            )
            return {"skipped": "no_credential"}

        run = await integration_svc.open_provider_sync_run(
            tenant_id,
            provider="carestack",
            object_scope=_CS_OBJECT_SCOPE,
            trigger="scheduled",
        )
        client = CareStackClient.from_credential(payload)
        # Each CareStack leg is isolated against provider-side failure. The
        # motivating case: a 403 "Request blocked due to CareStack Security
        # Policy" when our egress IP is not on CareStack's Sync-API allowlist
        # blocks the ENTIRE ``/sync/*`` family at once. Before this isolation a
        # single such 403 propagated, rolled back the whole ``async_session``,
        # and the tick reported "0 records · failed" even though
        # locations/patients/etc. had already imported. Now provider errors are
        # caught per-leg, recorded in ``failed_legs``, and the legs that DID
        # succeed still commit; the run closes ``partial`` instead of throwing
        # everything away. Non-provider errors (bugs, DB faults) still
        # propagate to the outer handler and fail the whole run. An HTTP error
        # does not poison the SQLAlchemy transaction, so continuing on the same
        # session is safe. See docs/integrations/carestack/sync-403-ip-allowlist.md.
        failed_legs: list[str] = []

        async def _leg(name: str, awaitable: Any) -> Any:
            try:
                return await awaitable
            except (CareStackApiError, CareStackNotConnectedError) as exc:
                failed_legs.append(name)
                log.warning(
                    "ingest_scheduled.carestack.leg_failed",
                    tenant_id=tenant_id_str,
                    leg=name,
                    error=str(exc)[:300],
                )
                return None

        try:
            location_svc = LocationService(session)
            locations = await _leg(
                "locations",
                location_svc.import_locations_from_carestack(
                    tenant_id, client, principal=principal
                ),
            )
            patient_svc = CareStackPatientIngestService(
                session=session, carestack_client=client
            )
            patients = await _leg(
                "patients",
                patient_svc.import_recent_patients(
                    tenant_id, days=1, page_size=100, max_pages=5
                ),
            )
            appt_svc = CareStackAppointmentIngestService(
                session=session,
                carestack_client=client,
                responsibility_resolver=_build_responsibility_resolver(session),
                actor_name_resolver=_build_actor_name_resolver(session),
            )
            # ENG-457: announce genuinely-new consultations to #scheduls. The
            # scheduled (recent) pull opts in by passing a notifier+principal;
            # the messenger emit is itself dark until ``notifications_enabled``.
            appointments = await _leg(
                "appointments",
                appt_svc.import_recent_appointments(
                    tenant_id,
                    days=1,
                    page_size=100,
                    max_pages=5,
                    notifier=cast(
                        ConsultationNotifier, NotificationEventService(session)
                    ),
                    principal=principal,
                ),
            )
            treatment_svc = CareStackTreatmentIngestService(
                session=session, carestack_client=client
            )
            # ENG: these three feeds resume from a persisted ``lastUpdatedOn``
            # watermark (see packages/ingest/sync_window.py), so a run drains
            # FORWARD from where the last one stopped. The larger page_size /
            # max_pages (max allowed: 500 / 20 → 10k rows/run) lets the
            # initial catch-up clear a multi-day backlog in a few ticks;
            # steady-state runs only fetch the small delta and stop early.
            treatments = await _leg(
                "treatments",
                treatment_svc.import_recent_treatments(
                    tenant_id, days=7, page_size=500, max_pages=max_pages
                ),
            )
            invoice_svc = CareStackInvoiceIngestService(
                session=session, carestack_client=client
            )
            invoices = await _leg(
                "invoices",
                invoice_svc.import_recent_invoices(
                    tenant_id, days=7, page_size=500, max_pages=max_pages
                ),
            )
            accounting_tx_svc = CareStackAccountingTransactionIngestService(
                session=session, carestack_client=client
            )
            accounting_transactions = await _leg(
                "accounting_transactions",
                accounting_tx_svc.import_recent_accounting_transactions(
                    tenant_id, days=7, page_size=500, max_pages=max_pages
                ),
            )
            payment_summary_svc = CareStackPaymentSummaryIngestService(
                session=session, carestack_client=client
            )
            # ENG-305: live signal. Refresh the authoritative balance for
            # every patient who just moved money on this tick. The
            # accounting-transactions pull above accumulates the distinct
            # patient_ids whose rows actually imported (payment events);
            # we snapshot ``payment-summary`` for each so the dashboard
            # Outstanding / AR-risk numbers track those patients without
            # waiting for the rolling 50-patient sweep below to walk to
            # them. Commits inside the sweep so a 1000-patient surge
            # doesn't wrap the whole tick in one transaction. Guarded on
            # ``accounting_transactions is not None`` because that leg may have
            # been skipped by a provider 403 above.
            if (
                accounting_transactions is not None
                and accounting_transactions.patient_ids
            ):
                await _leg(
                    "payment_summary_targeted",
                    payment_summary_svc.import_payment_summary_for_patients(
                        tenant_id,
                        accounting_transactions.patient_ids,
                        commit=session.commit,
                    ),
                )
            # KEEP the rolling sweep: it covers patients whose balance
            # drifted (refund processed externally, insurance settled
            # late) without producing a fresh accounting transaction in
            # this window. The targeted refresh above and the rolling
            # sweep are complementary — drop the rolling sweep only when
            # tests cover that removal explicitly (ENG-305 does not).
            payment_summaries = await _leg(
                "payment_summaries",
                payment_summary_svc.import_payment_summary_snapshots(
                    tenant_id, max_patients=50
                ),
            )
            # ENG-511: per-patient TreatmentPlan sweep — captures plan rows and
            # emits treatment_accepted (StatusId=3). Bounded like the
            # payment-summary sweep; no bulk feed exists for treatment plans.
            treatment_plan_svc = CareStackTreatmentPlanIngestService(
                session=session, carestack_client=client
            )
            treatment_plans = await _leg(
                "treatment_plans",
                treatment_plan_svc.import_treatment_plans(
                    tenant_id, max_patients=50
                ),
            )
            counters = _carestack_counters(
                locations,
                patients,
                appointments,
                treatments,
                invoices,
                accounting_transactions,
                payment_summaries,
                treatment_plans=treatment_plans,
            )
            # Leg-level failures (a whole feed skipped by a provider 403) are
            # surfaced separately from row-level skips: they bump
            # ``records_failed`` and list the feed names in ``meta.failed_legs``.
            # A run is ``partial`` when SOME legs produced data and others were
            # blocked; only ``failed`` when nothing got through at all.
            records_failed = counters["failed"] + len(failed_legs)
            status: ProviderSyncStatus
            if failed_legs:
                status = (
                    "partial"
                    if counters["succeeded"] + counters["unchanged"] > 0
                    else "failed"
                )
            else:
                status = _counter_status(
                    counters["succeeded"],
                    counters["failed"],
                    counters["unchanged"],
                )
            meta: dict[str, Any] = {"unchanged": counters["unchanged"]}
            if failed_legs:
                meta["failed_legs"] = failed_legs
            await integration_svc.close_provider_sync_run(
                tenant_id,
                sync_run_id=run.id,
                principal=principal,
                provider="carestack",
                object_scope=_CS_OBJECT_SCOPE,
                status=status,
                records_total=counters["total"],
                records_succeeded=counters["succeeded"],
                records_failed=records_failed,
                meta=meta,
            )
        except Exception as exc:
            await integration_svc.close_provider_sync_run(
                tenant_id,
                sync_run_id=run.id,
                principal=principal,
                provider="carestack",
                object_scope=_CS_OBJECT_SCOPE,
                status="failed",
                records_total=0,
                records_succeeded=0,
                records_failed=1,
                error=exc,
            )
            raise
        finally:
            await client.close()

    log.info(
        "ingest_scheduled.carestack.ok",
        tenant_id=tenant_id_str,
        failed_legs=failed_legs,
        locations=_safe_dump(locations),
        patients=_safe_dump(patients),
        appointments=_safe_dump(appointments),
        treatments=_safe_dump(treatments),
        invoices=_safe_dump(invoices),
        accounting_transactions=_safe_dump(accounting_transactions),
        payment_summaries=_safe_dump(payment_summaries),
        treatment_plans=_safe_dump(treatment_plans),
    )
    return {
        "locations": _safe_dump(locations),
        "patients": _safe_dump(patients),
        "appointments": _safe_dump(appointments),
        "treatments": _safe_dump(treatments),
        "invoices": _safe_dump(invoices),
        "accounting_transactions": _safe_dump(accounting_transactions),
        "payment_summaries": _safe_dump(payment_summaries),
        "treatment_plans": _safe_dump(treatment_plans),
        "failed_legs": failed_legs,
    }


async def backfill_carestack_for_tenant(
    _ctx: dict[str, Any], tenant_id_str: str, since: datetime
) -> dict[str, Any]:
    """ENG-351: DEEP CareStack backfill for one tenant.

    Mirrors :func:`pull_carestack_for_tenant` (same credential read, client
    setup, ``open/close_provider_sync_run`` lifecycle, ``NoCredential ->
    skipped`` short-circuit, and ``_carestack_counters`` aggregation) but
    swaps the watermark-resuming ``import_recent_*`` legs for
    ``pull_all_since(since)`` on patient / appointment / treatment / invoice
    / accounting_transaction.

    The watermark pulls are forward-only — they keep the newest data fresh
    but cannot refill historical HOLES (e.g. a day the local worker was
    asleep). ``pull_all_since`` scans the feed from ``since`` to exhaustion
    (ignoring the watermark) so those holes are filled; dedup of rows already
    present counts as ``unchanged``.

    Locations keep the one-shot import (no watermark, full re-import each
    run) and payment_summaries keep the normal rolling + targeted refresh —
    neither is a paginated historical feed, so deep mode does not change
    them. Returns the same result envelope ``pull_carestack_for_tenant``
    returns. Missing credentials short-circuit to ``skipped``.
    """
    tenant_id = TenantId(UUID(tenant_id_str))
    async with async_session() as session:
        cred_svc = IntegrationCredentialService(session)
        integration_svc = IntegrationService(session)
        principal = _scheduler_principal(tenant_id)
        try:
            payload = await cred_svc.read_for(
                tenant_id, "carestack", "password_grant"
            )
        except NoCredentialError:
            run = await integration_svc.open_provider_sync_run(
                tenant_id,
                provider="carestack",
                object_scope=_CS_OBJECT_SCOPE,
                trigger="manual",
                account_status="disconnected",
            )
            await integration_svc.close_provider_sync_run(
                tenant_id,
                sync_run_id=run.id,
                principal=principal,
                provider="carestack",
                object_scope=_CS_OBJECT_SCOPE,
                status="skipped_credential",
                records_total=0,
                records_succeeded=0,
                records_failed=0,
                error="no active carestack credential",
            )
            log.info(
                "ingest_scheduled.carestack.backfill.no_credential",
                tenant_id=tenant_id_str,
            )
            return {"skipped": "no_credential"}

        run = await integration_svc.open_provider_sync_run(
            tenant_id,
            provider="carestack",
            object_scope=_CS_OBJECT_SCOPE,
            trigger="manual",
        )
        client = CareStackClient.from_credential(payload)
        try:
            location_svc = LocationService(session)
            locations = await location_svc.import_locations_from_carestack(
                tenant_id, client, principal=principal
            )
            patient_svc = CareStackPatientIngestService(
                session=session, carestack_client=client
            )
            patients = await patient_svc.pull_all_since(tenant_id, since)
            appt_svc = CareStackAppointmentIngestService(
                session=session,
                carestack_client=client,
                responsibility_resolver=_build_responsibility_resolver(session),
                actor_name_resolver=_build_actor_name_resolver(session),
            )
            appointments = await appt_svc.pull_all_since(tenant_id, since)
            treatment_svc = CareStackTreatmentIngestService(
                session=session, carestack_client=client
            )
            treatments = await treatment_svc.pull_all_since(tenant_id, since)
            invoice_svc = CareStackInvoiceIngestService(
                session=session, carestack_client=client
            )
            invoices = await invoice_svc.pull_all_since(tenant_id, since)
            accounting_tx_svc = CareStackAccountingTransactionIngestService(
                session=session, carestack_client=client
            )
            accounting_transactions = await accounting_tx_svc.pull_all_since(
                tenant_id, since
            )
            payment_summary_svc = CareStackPaymentSummaryIngestService(
                session=session, carestack_client=client
            )
            # Keep the rolling balance sweep as the normal pull does — the
            # payment-summary endpoint is not a paginated historical feed,
            # so a deep backfill does not change it.
            payment_summaries = (
                await payment_summary_svc.import_payment_summary_snapshots(
                    tenant_id, max_patients=50
                )
            )
            # ENG-511: treatment-plan sweep (no historical feed — same bounded
            # per-patient sweep as the scheduled pull).
            treatment_plan_svc = CareStackTreatmentPlanIngestService(
                session=session, carestack_client=client
            )
            treatment_plans = await treatment_plan_svc.import_treatment_plans(
                tenant_id, max_patients=50
            )
            counters = _carestack_counters(
                locations,
                patients,
                appointments,
                treatments,
                invoices,
                accounting_transactions,
                payment_summaries,
                treatment_plans=treatment_plans,
            )
            await integration_svc.close_provider_sync_run(
                tenant_id,
                sync_run_id=run.id,
                principal=principal,
                provider="carestack",
                object_scope=_CS_OBJECT_SCOPE,
                status=_counter_status(
                    counters["succeeded"],
                    counters["failed"],
                    counters["unchanged"],
                ),
                records_total=counters["total"],
                records_succeeded=counters["succeeded"],
                records_failed=counters["failed"],
                meta={"unchanged": counters["unchanged"], "deep": True},
            )
        except Exception as exc:
            await integration_svc.close_provider_sync_run(
                tenant_id,
                sync_run_id=run.id,
                principal=principal,
                provider="carestack",
                object_scope=_CS_OBJECT_SCOPE,
                status="failed",
                records_total=0,
                records_succeeded=0,
                records_failed=1,
                error=exc,
            )
            raise
        finally:
            await client.close()

    log.info(
        "ingest_scheduled.carestack.backfill.ok",
        tenant_id=tenant_id_str,
        since=since.isoformat(),
        locations=locations.model_dump(),
        patients=patients.model_dump(),
        appointments=appointments.model_dump(),
        treatments=treatments.model_dump(),
        invoices=invoices.model_dump(),
        accounting_transactions=accounting_transactions.model_dump(),
        payment_summaries=payment_summaries.model_dump(),
        treatment_plans=treatment_plans.model_dump(),
    )
    return {
        "locations": locations.model_dump(),
        "patients": patients.model_dump(),
        "appointments": appointments.model_dump(),
        "treatments": treatments.model_dump(),
        "invoices": invoices.model_dump(),
        "accounting_transactions": accounting_transactions.model_dump(),
        "payment_summaries": payment_summaries.model_dump(),
        "treatment_plans": treatment_plans.model_dump(),
    }


async def pull_salesforce_for_tenant(
    _ctx: dict[str, Any], tenant_id_str: str
) -> dict[str, Any]:
    """Run a bounded Salesforce leads + events + tasks + opportunities + cases pull.

    Missing OAuth credentials log at INFO and short-circuit to
    ``skipped`` — operator must re-connect via the OAuth flow.
    """
    tenant_id = TenantId(UUID(tenant_id_str))
    async with async_session() as session:
        cred_svc = IntegrationCredentialService(session)
        integration_svc = IntegrationService(session)
        principal = _scheduler_principal(tenant_id)
        try:
            oauth_payload = await cred_svc.read_for(
                tenant_id, "salesforce", "oauth_token"
            )
        except NoCredentialError:
            run = await integration_svc.open_provider_sync_run(
                tenant_id,
                provider="salesforce",
                object_scope=_SF_OBJECT_SCOPE,
                trigger="scheduled",
                account_status="disconnected",
            )
            await integration_svc.close_provider_sync_run(
                tenant_id,
                sync_run_id=run.id,
                principal=principal,
                provider="salesforce",
                object_scope=_SF_OBJECT_SCOPE,
                status="skipped_credential",
                records_total=0,
                records_succeeded=0,
                records_failed=0,
                error="no active salesforce credential",
            )
            log.info(
                "ingest_scheduled.salesforce.no_credential",
                tenant_id=tenant_id_str,
            )
            return {"skipped": "no_credential"}

        try:
            api_key_payload: dict[str, object] | None = await cred_svc.read_for(
                tenant_id, "salesforce", "api_key"
            )
        except NoCredentialError:
            api_key_payload = None
        except PlatformError:
            api_key_payload = None

        async def _persist(tokens: SfTokens) -> None:
            new_payload: dict[str, object] = {
                "access_token": tokens.access_token,
                "instance_url": tokens.instance_url,
            }
            if tokens.refresh_token:
                new_payload["refresh_token"] = tokens.refresh_token
            if tokens.issued_at:
                new_payload["issued_at"] = tokens.issued_at
            await cred_svc.upsert(
                tenant_id,
                "salesforce",
                "oauth_token",
                new_payload,
                principal=principal,
                display_name="Salesforce OAuth tokens (rotated by scheduler)",
            )

        run = await integration_svc.open_provider_sync_run(
            tenant_id,
            provider="salesforce",
            object_scope=_SF_OBJECT_SCOPE,
            trigger="scheduled",
        )
        sf_client = SfClient.from_credential(
            oauth_payload,
            on_refresh=_persist,
            api_key_payload=api_key_payload,
        )
        try:
            # Cast: SfClient.soql returns SoqlResult (TypedDict, dict at
            # runtime); the ingest-side Protocols intentionally type it
            # as dict[str, Any] to avoid the ingest -> integrations import
            # forbidden by packages/CLAUDE.md.
            resolver = _build_responsibility_resolver(session)
            lead_svc = SfLeadIngestService(
                session=session,
                sf_client=cast(SfClientProtocol, sf_client),
                responsibility_resolver=resolver,
            )
            event_svc = SfEventIngestService(
                session=session,
                sf_client=cast(SfEventClientProtocol, sf_client),
            )
            task_svc = SfTaskIngestService(
                session=session,
                sf_client=cast(SfTaskClientProtocol, sf_client),
                responsibility_resolver=resolver,
            )
            opportunity_svc = SfOpportunityIngestService(
                session=session,
                sf_client=cast(SfOpportunityClientProtocol, sf_client),
                responsibility_resolver=resolver,
            )
            case_svc = SfCaseIngestService(
                session=session,
                sf_client=cast(SfCaseClientProtocol, sf_client),
            )
            contact_svc = SfContactIngestService(
                session=session,
                sf_client=cast(SfContactClientProtocol, sf_client),
            )
            account_svc = SfAccountIngestService(
                session=session,
                sf_client=cast(SfAccountClientProtocol, sf_client),
            )
            opportunity_history_svc = SfOpportunityHistoryIngestService(
                session=session,
                sf_client=cast(SfOpportunityHistoryClientProtocol, sf_client),
            )
            try:
                leads = await lead_svc.pull_recent_for_sync(tenant_id, limit=50)
            except SfNotConnectedError:
                await integration_svc.close_provider_sync_run(
                    tenant_id,
                    sync_run_id=run.id,
                    principal=principal,
                    provider="salesforce",
                    object_scope=_SF_OBJECT_SCOPE,
                    status="skipped_credential",
                    records_total=0,
                    records_succeeded=0,
                    records_failed=0,
                    error="salesforce credential expired",
                )
                log.info(
                    "ingest_scheduled.salesforce.expired",
                    tenant_id=tenant_id_str,
                )
                return {"skipped": "credentials_expired"}
            # ENG-456: fan genuinely-NEW leads out to #leads exactly once. The
            # emit lives HERE at the worker boundary — NOT inside the ingest /
            # ops services — because the packages import matrix forbids
            # ``ops``/``ingest`` → ``integrations``. This boundary already
            # depends on both ``ingest`` and ``integrations`` and owns the
            # session, so the outbox row + dedupe-ledger claim commit
            # atomically with the lead upsert at the ``async_session`` exit.
            await _emit_lead_created_notifications(
                session, tenant_id, leads.notify_signals, principal=principal
            )
            # ENG-457: announce genuinely-new consultations to #scheduls. The
            # scheduled (recent) pull opts in by passing a notifier+principal;
            # the messenger emit is itself dark until ``notifications_enabled``.
            events = await event_svc.import_recent_events(
                tenant_id,
                days=1,
                limit=200,
                notifier=cast(
                    ConsultationNotifier, NotificationEventService(session)
                ),
                principal=principal,
            )
            tasks = await task_svc.import_recent_tasks(
                tenant_id, days=7, limit=200
            )
            opportunities = await opportunity_svc.import_recent_opportunities(
                tenant_id, days=7, limit=200
            )
            cases = await case_svc.import_recent_cases(
                tenant_id, days=7, limit=200
            )
            # ENG-382 funnel segments. Ordering is deliberate: contacts +
            # accounts land their person links BEFORE opportunity history
            # so stage events resolve through the freshest links. All
            # three are watermark-first (ENG-381).
            contacts = await contact_svc.import_recent_contacts(
                tenant_id, days=7, limit=200
            )
            accounts = await account_svc.import_recent_accounts(
                tenant_id, days=7, limit=200
            )
            opportunity_history = await opportunity_history_svc.import_recent_history(
                tenant_id, days=7, limit=200
            )
            # ENG-462: re-project SF Tasks first seen before their lead /
            # contact was linked. The watermark task import skips unlinked
            # tasks and never retries them; this short-window pass re-runs
            # the emit from already-captured raw now that the links (pulled
            # just above this tick) exist. Idempotent. The deep one-off
            # catch-up lives in infra/scripts/reproject_sf_tasks.py.
            await task_svc.reproject_tasks_from_raw(
                tenant_id, since=datetime.now(UTC) - timedelta(hours=6)
            )
            counters = _salesforce_counters(
                leads,
                events,
                tasks,
                opportunities,
                cases,
                contacts,
                accounts,
                opportunity_history,
            )
            await integration_svc.close_provider_sync_run(
                tenant_id,
                sync_run_id=run.id,
                principal=principal,
                provider="salesforce",
                object_scope=_SF_OBJECT_SCOPE,
                status=_counter_status(
                    counters["succeeded"],
                    counters["failed"],
                    counters["unchanged"],
                ),
                records_total=counters["total"],
                records_succeeded=counters["succeeded"],
                records_failed=counters["failed"],
                meta={"unchanged": counters["unchanged"]},
            )
        except Exception as exc:
            await integration_svc.close_provider_sync_run(
                tenant_id,
                sync_run_id=run.id,
                principal=principal,
                provider="salesforce",
                object_scope=_SF_OBJECT_SCOPE,
                status="failed",
                records_total=0,
                records_succeeded=0,
                records_failed=1,
                error=exc,
            )
            raise
        finally:
            await sf_client.close()

    log.info(
        "ingest_scheduled.salesforce.ok",
        tenant_id=tenant_id_str,
        leads=leads.model_dump(),
        events=events.model_dump(),
        tasks=tasks.model_dump(),
        opportunities=opportunities.model_dump(),
        cases=cases.model_dump(),
        contacts=contacts.model_dump(),
        accounts=accounts.model_dump(),
        opportunity_history=opportunity_history.model_dump(),
    )
    return {
        "leads": leads.model_dump(),
        "leads_imported": leads.imported_count,
        "leads_skipped": leads.skipped_count,
        "events": events.model_dump(),
        "tasks": tasks.model_dump(),
        "opportunities": opportunities.model_dump(),
        "cases": cases.model_dump(),
        "contacts": contacts.model_dump(),
        "accounts": accounts.model_dump(),
        "opportunity_history": opportunity_history.model_dump(),
    }


async def ingest_scheduled_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    """Cron entry: iterate every tenant, pull CS + SF in sequence.

    Per ADR-0004 / bounce_poll pattern: the cron tick runs once,
    iterates tenants in-process, and reports a summary for arq's
    keep_result. We DO NOT enqueue per-tenant child jobs in v1 —
    the workload is small (one HTTP round-trip per provider per
    tenant) and serial execution keeps the audit + log story simple.
    """
    _ = ctx
    summary = _empty_summary()
    tenant_ids = await _list_tenant_ids()

    if not tenant_ids:
        log.info("ingest_scheduled.no_tenants")
        return summary

    for tenant_id_str in tenant_ids:
        summary["tenants"] += 1

        cs_outcome = await _run_safe(
            pull_carestack_for_tenant,
            tenant_id_str,
            tag="carestack",
        )
        if cs_outcome == "ok":
            summary["carestack_ok"] += 1
        elif cs_outcome == "skipped":
            summary["carestack_skipped"] += 1
        else:
            summary["carestack_failed"] += 1

        sf_outcome = await _run_safe(
            pull_salesforce_for_tenant,
            tenant_id_str,
            tag="salesforce",
        )
        if sf_outcome == "ok":
            summary["salesforce_ok"] += 1
        elif sf_outcome == "skipped":
            summary["salesforce_skipped"] += 1
        else:
            summary["salesforce_failed"] += 1

    log.info("ingest_scheduled.tick", summary=summary)
    return summary


async def refresh_salesforce_schemas_for_tenant(
    _ctx: dict[str, Any], tenant_id_str: str
) -> dict[str, Any]:
    """Refresh the Salesforce schema registry for one tenant (ENG-428).

    Reads describe + Tooling for every full-fidelity SF object, reconciles the
    ``ingest.source_object_field`` registry, and records drift (new / removed /
    type-changed fields + FLS gap) into the ``sync_run`` meta and the structured
    log. New fields are absorbed into the next pull automatically because the
    SOQL projection is derived from this registry. Cheap by design: one describe
    + one Tooling query per object, run on a low cadence. Missing credentials
    short-circuit to ``skipped``.
    """
    tenant_id = TenantId(UUID(tenant_id_str))
    async with async_session() as session:
        cred_svc = IntegrationCredentialService(session)
        integration_svc = IntegrationService(session)
        principal = _scheduler_principal(tenant_id)
        try:
            oauth_payload = await cred_svc.read_for(
                tenant_id, "salesforce", "oauth_token"
            )
        except NoCredentialError:
            log.info(
                "ingest_scheduled.sf_schema.no_credential", tenant_id=tenant_id_str
            )
            return {"skipped": "no_credential"}
        try:
            api_key_payload: dict[str, object] | None = await cred_svc.read_for(
                tenant_id, "salesforce", "api_key"
            )
        except (NoCredentialError, PlatformError):
            api_key_payload = None

        async def _persist(tokens: SfTokens) -> None:
            new_payload: dict[str, object] = {
                "access_token": tokens.access_token,
                "instance_url": tokens.instance_url,
            }
            if tokens.refresh_token:
                new_payload["refresh_token"] = tokens.refresh_token
            if tokens.issued_at:
                new_payload["issued_at"] = tokens.issued_at
            await cred_svc.upsert(
                tenant_id,
                "salesforce",
                "oauth_token",
                new_payload,
                principal=principal,
                display_name="Salesforce OAuth tokens (rotated by scheduler)",
            )

        run = await integration_svc.open_provider_sync_run(
            tenant_id,
            provider="salesforce",
            object_scope=_SF_OBJECT_SCOPE,
            trigger="scheduled",
        )
        sf_client = SfClient.from_credential(
            oauth_payload, on_refresh=_persist, api_key_payload=api_key_payload
        )
        ingest = IngestService(session)
        # ``drift`` holds objects whose FIELD SET actually changed since the
        # last run (added / removed / type-changed) — the real "something
        # changed" signal. ``fls_gaps`` holds the per-object FLS-blocked field
        # list, which is a persistent state (recorded every run so operators
        # always see the current remediation list), NOT a per-run change.
        drift: dict[str, object] = {}
        fls_gaps: dict[str, list[str]] = {}
        failed = 0
        try:
            for obj in SF_FULL_FIDELITY_OBJECTS:
                schema = SfSchemaSync(ingest, cast(Any, sf_client), object_name=obj)
                try:
                    diff, gap = await schema.sync(tenant_id)
                except (SfNotConnectedError, SfApiError) as exc:
                    failed += 1
                    log.warning(
                        "ingest_scheduled.sf_schema.object_failed",
                        tenant_id=tenant_id_str,
                        object_name=obj,
                        error=str(exc)[:200],
                    )
                    continue
                if diff.has_changes:
                    drift[obj] = {
                        "added": diff.added,
                        "removed": diff.removed,
                        "type_changed": [c.field for c in diff.type_changed],
                        "became_readable": diff.became_readable,
                        "became_unreadable": diff.became_unreadable,
                    }
                if gap:
                    fls_gaps[obj] = gap
            status: ProviderSyncStatus = "succeeded" if failed == 0 else "partial"
            await integration_svc.close_provider_sync_run(
                tenant_id,
                sync_run_id=run.id,
                principal=principal,
                provider="salesforce",
                object_scope=_SF_OBJECT_SCOPE,
                status=status,
                records_total=len(SF_FULL_FIDELITY_OBJECTS),
                records_succeeded=len(SF_FULL_FIDELITY_OBJECTS) - failed,
                records_failed=failed,
                meta={"schema_drift": drift, "fls_gaps": fls_gaps},
            )
        finally:
            await sf_client.close()
        log.info(
            "ingest_scheduled.sf_schema.tick",
            tenant_id=tenant_id_str,
            objects=len(SF_FULL_FIDELITY_OBJECTS),
            drifted=len(drift),
            fls_gap_objects=len(fls_gaps),
            failed=failed,
        )
        return {
            "objects": len(SF_FULL_FIDELITY_OBJECTS),
            "drifted": len(drift),
            "fls_gap_objects": len(fls_gaps),
            "failed": failed,
        }


async def refresh_salesforce_schemas_for_all_tenants(
    ctx: dict[str, Any],
) -> dict[str, int]:
    """Cloud Run Job / cron entrypoint: refresh SF schemas for every tenant."""
    _ = ctx
    summary: dict[str, int] = {
        "tenants": 0,
        "schema_ok": 0,
        "schema_skipped": 0,
        "schema_failed": 0,
    }
    tenant_ids = await _list_tenant_ids()
    if not tenant_ids:
        log.info("ingest_scheduled.sf_schema.no_tenants")
        return summary
    for tenant_id_str in tenant_ids:
        summary["tenants"] += 1
        outcome = await _run_safe(
            refresh_salesforce_schemas_for_tenant,
            tenant_id_str,
            tag="sf_schema",
        )
        if outcome == "ok":
            summary["schema_ok"] += 1
        elif outcome == "skipped":
            summary["schema_skipped"] += 1
        else:
            summary["schema_failed"] += 1
    log.info("ingest_scheduled.sf_schema.fanout_tick", summary=summary)
    return summary


# CareStack objects with no provider ``describe`` — their full-fidelity schema
# is derived from the union of observed payload keys (ENG-429). Keep in sync
# with the CareStack ingest services' event types.
_CARESTACK_SCHEMA_OBJECTS: tuple[tuple[str, str], ...] = (
    ("patient", "carestack.patient.upsert"),
    ("appointment", "carestack.appointment.upsert"),
    ("treatment_procedure", "carestack.treatment_procedure.upsert"),
    ("treatment_plan", "carestack.treatment_plan.upsert"),
    ("invoice", "carestack.invoice.upsert"),
    ("accounting_transaction", "carestack.accounting_transaction.upsert"),
    ("payment_summary", "carestack.payment_summary.snapshot"),
)


async def refresh_carestack_schemas_for_tenant(
    _ctx: dict[str, Any], tenant_id_str: str
) -> dict[str, Any]:
    """Snapshot the CareStack schema registry from observed payload keys (ENG-429).

    CareStack has no ``describe``: we already capture full objects verbatim
    (the REST client applies no field filter), so this job derives each
    object's schema from the union of keys across recently-captured raw events
    and reconciles ``ingest.source_object_field``. Field drift (new / removed
    keys) is recorded into ``sync_run.meta``. Reads only our own raw events —
    no CareStack credential or HTTP call needed.
    """
    tenant_id = TenantId(UUID(tenant_id_str))
    async with async_session() as session:
        integration_svc = IntegrationService(session)
        principal = _scheduler_principal(tenant_id)
        ingest = IngestService(session)
        run = await integration_svc.open_provider_sync_run(
            tenant_id,
            provider="carestack",
            object_scope=_CS_OBJECT_SCOPE,
            trigger="scheduled",
        )
        drift: dict[str, object] = {}
        for object_name, event_type in _CARESTACK_SCHEMA_OBJECTS:
            diff = await ingest.snapshot_observed_schema(
                tenant_id,
                provider="carestack",
                object_name=object_name,
                event_type=event_type,
            )
            if diff.has_changes:
                drift[object_name] = {
                    "added": diff.added,
                    "removed": diff.removed,
                    "type_changed": [c.field for c in diff.type_changed],
                }
        await integration_svc.close_provider_sync_run(
            tenant_id,
            sync_run_id=run.id,
            principal=principal,
            provider="carestack",
            object_scope=_CS_OBJECT_SCOPE,
            status="succeeded",
            records_total=len(_CARESTACK_SCHEMA_OBJECTS),
            records_succeeded=len(_CARESTACK_SCHEMA_OBJECTS),
            records_failed=0,
            meta={"schema_drift": drift},
        )
        log.info(
            "ingest_scheduled.cs_schema.tick",
            tenant_id=tenant_id_str,
            objects=len(_CARESTACK_SCHEMA_OBJECTS),
            drifted=len(drift),
        )
        return {"objects": len(_CARESTACK_SCHEMA_OBJECTS), "drifted": len(drift)}


async def refresh_carestack_schemas_for_all_tenants(
    ctx: dict[str, Any],
) -> dict[str, int]:
    """Cloud Run Job / cron entrypoint: snapshot CareStack schemas per tenant."""
    _ = ctx
    summary: dict[str, int] = {"tenants": 0, "schema_ok": 0, "schema_failed": 0}
    tenant_ids = await _list_tenant_ids()
    if not tenant_ids:
        log.info("ingest_scheduled.cs_schema.no_tenants")
        return summary
    for tenant_id_str in tenant_ids:
        summary["tenants"] += 1
        outcome = await _run_safe(
            refresh_carestack_schemas_for_tenant,
            tenant_id_str,
            tag="cs_schema",
        )
        if outcome == "ok":
            summary["schema_ok"] += 1
        else:
            summary["schema_failed"] += 1
    log.info("ingest_scheduled.cs_schema.fanout_tick", summary=summary)
    return summary


async def pull_salesforce_for_all_tenants(ctx: dict[str, Any]) -> dict[str, int]:
    """Cloud Run Job entrypoint: run only the Salesforce ingestion slice."""
    _ = ctx
    summary: dict[str, int] = {
        "tenants": 0,
        "salesforce_ok": 0,
        "salesforce_skipped": 0,
        "salesforce_failed": 0,
    }
    tenant_ids = await _list_tenant_ids()

    if not tenant_ids:
        log.info("ingest_scheduled.salesforce.no_tenants")
        return summary

    for tenant_id_str in tenant_ids:
        summary["tenants"] += 1
        outcome = await _run_safe(
            pull_salesforce_for_tenant,
            tenant_id_str,
            tag="salesforce",
        )
        if outcome == "ok":
            summary["salesforce_ok"] += 1
        elif outcome == "skipped":
            summary["salesforce_skipped"] += 1
        else:
            summary["salesforce_failed"] += 1

    log.info("ingest_scheduled.salesforce.tick", summary=summary)
    return summary


async def pull_carestack_for_all_tenants(ctx: dict[str, Any]) -> dict[str, int]:
    """Cloud Run Job entrypoint: run only the CareStack ingestion slice."""
    _ = ctx
    summary: dict[str, int] = {
        "tenants": 0,
        "carestack_ok": 0,
        "carestack_skipped": 0,
        "carestack_failed": 0,
    }
    tenant_ids = await _list_tenant_ids()

    if not tenant_ids:
        log.info("ingest_scheduled.carestack.no_tenants")
        return summary

    for tenant_id_str in tenant_ids:
        summary["tenants"] += 1
        outcome = await _run_safe(
            pull_carestack_for_tenant,
            tenant_id_str,
            tag="carestack",
        )
        if outcome == "ok":
            summary["carestack_ok"] += 1
        elif outcome == "skipped":
            summary["carestack_skipped"] += 1
        else:
            summary["carestack_failed"] += 1

    log.info("ingest_scheduled.carestack.tick", summary=summary)
    return summary


def _empty_summary() -> dict[str, int]:
    return {
        "tenants": 0,
        "carestack_ok": 0,
        "carestack_skipped": 0,
        "carestack_failed": 0,
        "salesforce_ok": 0,
        "salesforce_skipped": 0,
        "salesforce_failed": 0,
    }


def _safe_dump(summary: Any) -> dict[str, Any]:
    """``summary.model_dump()`` or ``{}`` when a CareStack leg was skipped.

    A leg blocked by a provider-side failure (e.g. a Sync-API 403) returns
    ``None`` from :func:`pull_carestack_for_tenant`'s ``_leg`` wrapper; the
    result envelope and the success log render it as an empty dict instead of
    raising ``AttributeError`` on ``None.model_dump()``.
    """
    return summary.model_dump() if summary is not None else {}


def _counter_status(
    records_succeeded: int,
    records_failed: int,
    records_unchanged: int = 0,
) -> ProviderSyncStatus:
    # ENG-389: after the ENG-381/384 change-guard a steady-state run
    # imports nothing (everything is `unchanged`), so a single benign
    # skip must not flip the whole run to `failed` — unchanged rows are
    # proof the pull worked. `failed` is reserved for runs that produced
    # nothing at all; hard exceptions keep their explicit status.
    if records_failed > 0:
        if records_succeeded + records_unchanged > 0:
            return "partial"
        return "failed"
    return "succeeded"


def _salesforce_counters(
    leads: Any,
    events: Any,
    tasks: Any | None = None,
    opportunities: Any | None = None,
    cases: Any | None = None,
    contacts: Any | None = None,
    accounts: Any | None = None,
    opportunity_history: Any | None = None,
) -> dict[str, int]:
    """Fold per-object SF import summaries into sync_run counters.

    ENG-381 adds the ``unchanged`` bucket (capture change-guard skips:
    the provider stamp did not move since the last capture). It mirrors
    the ENG-329 CareStack split: ``unchanged`` is HEALTHY, surfaced via
    sync_run ``meta`` and kept OUT of ``failed``. ENG-382 adds the
    contact / account / opportunity-history funnel segments.
    """
    lead_imported = int(
        getattr(leads, "imported_count", leads if isinstance(leads, int) else 0) or 0
    )
    lead_queried = int(getattr(leads, "queried_count", lead_imported) or 0)
    lead_skipped = int(
        getattr(leads, "skipped_count", max(lead_queried - lead_imported, 0)) or 0
    )
    lead_unchanged = int(getattr(leads, "unchanged_count", 0) or 0)

    total = lead_queried
    succeeded = lead_imported
    failed = lead_skipped
    unchanged = lead_unchanged
    for summary in (
        events,
        tasks,
        opportunities,
        cases,
        contacts,
        accounts,
        opportunity_history,
    ):
        imported = int(getattr(summary, "imported_count", 0) or 0)
        queried = int(getattr(summary, "queried_count", imported) or 0)
        skipped = int(
            getattr(summary, "skipped_count", max(queried - imported, 0)) or 0
        )
        total += queried
        succeeded += imported
        failed += skipped
        unchanged += int(getattr(summary, "unchanged_count", 0) or 0)

    return {
        "total": total,
        "succeeded": succeeded,
        "failed": failed,
        "unchanged": unchanged,
    }


def _carestack_counters(
    locations: Any,
    patients: Any,
    appointments: Any,
    treatments: Any | None = None,
    invoices: Any | None = None,
    accounting_transactions: Any | None = None,
    payment_summaries: Any | None = None,
    *,
    treatment_plans: Any | None = None,
) -> dict[str, int]:
    """Fold per-object import summaries into sync_run counters.

    ENG-329: a third ``unchanged`` bucket now carries idempotent dedup
    re-reads (``create_event_idempotent`` / consultation upsert returning
    ``was_created is False``). Before ENG-329 those rows were counted as
    ``*_skipped`` and folded into ``failed``, so a steady-state CareStack
    pull — which re-reads thousands of already-imported rows every run —
    reported ~1260 fake failures and a permanent ``partial`` status even
    when zero real errors occurred. ``unchanged`` is HEALTHY: it is
    surfaced in the sync_run ``meta`` but kept OUT of ``failed`` so
    ``_counter_status`` reports ``succeeded`` when there are no genuine
    errors. ``failed`` now counts ONLY genuine skips (no source id,
    missing patientId, unlinked patient, non-payment folio) plus
    payment-summary soft errors.
    """
    location_total = int(getattr(locations, "total_seen", 0) or 0)
    patient_imported = int(getattr(patients, "imported_count", 0) or 0)
    patient_unchanged = int(getattr(patients, "unchanged_count", 0) or 0)
    patient_skipped = int(getattr(patients, "skipped_count", 0) or 0)
    appointment_imported = int(getattr(appointments, "imported_count", 0) or 0)
    appointment_unchanged = int(getattr(appointments, "unchanged_count", 0) or 0)
    appointment_skipped = int(getattr(appointments, "skipped_count", 0) or 0)
    treatment_imported = int(getattr(treatments, "imported_count", 0) or 0)
    treatment_unchanged = int(getattr(treatments, "unchanged_count", 0) or 0)
    treatment_skipped = int(getattr(treatments, "skipped_count", 0) or 0)
    invoice_imported = int(getattr(invoices, "imported_count", 0) or 0)
    invoice_unchanged = int(getattr(invoices, "unchanged_count", 0) or 0)
    invoice_skipped = int(getattr(invoices, "skipped_count", 0) or 0)
    at_imported = int(
        getattr(accounting_transactions, "imported_count", 0) or 0
    )
    at_unchanged = int(
        getattr(accounting_transactions, "unchanged_count", 0) or 0
    )
    at_skipped = int(
        getattr(accounting_transactions, "skipped_count", 0) or 0
    )
    # Payment summary snapshots count toward records_total/succeeded so
    # the sync_run journal reflects sweep coverage. ``error_count`` is a
    # soft failure (one patient's API call); we surface it as failed.
    ps_snapshots = int(getattr(payment_summaries, "snapshot_count", 0) or 0)
    ps_skipped = int(getattr(payment_summaries, "skipped_count", 0) or 0)
    ps_errors = int(getattr(payment_summaries, "error_count", 0) or 0)
    # ENG-511: treatment-plan sweep. ``captured`` are fresh raw rows
    # (succeeded); ``unchanged`` are content-dedup re-reads; ``skipped`` (no
    # plan id) + ``error`` (per-patient fetch failure) are failures. The
    # ``accepted`` count is informational (a subset signal) and is logged via
    # the result envelope, not folded into succeeded to avoid double-counting.
    tp_captured = int(getattr(treatment_plans, "captured_count", 0) or 0)
    tp_unchanged = int(getattr(treatment_plans, "unchanged_count", 0) or 0)
    tp_skipped = int(getattr(treatment_plans, "skipped_count", 0) or 0)
    tp_errors = int(getattr(treatment_plans, "error_count", 0) or 0)
    succeeded = (
        location_total
        + patient_imported
        + appointment_imported
        + treatment_imported
        + invoice_imported
        + at_imported
        + ps_snapshots
        + tp_captured
    )
    unchanged = (
        patient_unchanged
        + appointment_unchanged
        + treatment_unchanged
        + invoice_unchanged
        + at_unchanged
        + tp_unchanged
    )
    failed = (
        patient_skipped
        + appointment_skipped
        + treatment_skipped
        + invoice_skipped
        + at_skipped
        + ps_skipped
        + ps_errors
        + tp_skipped
        + tp_errors
    )
    return {
        "total": succeeded + unchanged + failed,
        "succeeded": succeeded,
        "unchanged": unchanged,
        "failed": failed,
    }


async def _list_tenant_ids() -> list[str]:
    # Lazy import keeps worker cold start light when this job is not
    # registered (test harness, narrow workers).
    from packages.tenant.service import TenantService

    async with async_session() as session:
        tenant_rows = await TenantService(session).list_tenants()
        return [str(t.id) for t in tenant_rows]


async def _run_safe(
    fn: Any, tenant_id_str: str, *, tag: str
) -> str:
    """Run one per-tenant pull, catching errors so one bad tenant does
    not poison the whole tick. Returns 'ok' | 'skipped' | 'failed'.
    """
    try:
        result = await fn({}, tenant_id_str)
    except Exception as exc:  # noqa: BLE001 — cron tick must not crash
        log.error(
            f"ingest_scheduled.{tag}.error",
            tenant_id=tenant_id_str,
            error=str(exc),
        )
        return "failed"
    if isinstance(result, dict) and result.get("skipped"):
        return "skipped"
    return "ok"
