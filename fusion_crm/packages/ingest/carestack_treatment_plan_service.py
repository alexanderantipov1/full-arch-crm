"""CareStack TreatmentPlan ingest pipeline (ENG-511, B1.3).

CareStack has no bulk/sync feed for treatment plans — the only endpoint is
``GET /api/v1.0/patients/{patientId}/treatment-plans`` (one patient per
request). This service runs a bounded per-patient sweep over already-linked
CareStack patients (rows surfaced by ``IdentityService.source_links_for_dashboard``
with ``source_system="carestack"`` / ``source_kind="patient"``) and, for each:

1. Captures every plan row verbatim to ``ingest.raw_event``
   (``source=carestack``, ``event_type=carestack.treatment_plan.upsert``)
   BEFORE any normalisation — full-fidelity capture (invariant #11): no field
   filter, 100% of the fields CareStack exposes. The TreatmentPlan carries
   clinical context (plan name, condition ids), so the raw row stays gated by
   the existing ``ingest`` access rules.
2. Emits an ``interaction.event`` of kind ``treatment_accepted`` ONLY when the
   plan's ``StatusId == 3`` (Accepted) — NOT 8/10 (Completed/ServiceCompleted),
   NOT 9 (Presented); phases carry no status. The acceptance date is the FIRST
   observed ``StatusId=3`` (the event is idempotent on the stable plan id, so a
   re-pull never moves or duplicates it). The event summary + payload are
   no-PII: action verb + provider + plan id only — NO plan name, condition ids,
   or any clinical detail (those live in raw only).

Identity is resolved via the ENG-185 cutover pattern (raw_event ->
normalized_person_hint -> ``MatchHintIn`` -> ``IdentityService
.resolve_or_create_from_hint`` -> ``IdentityService.get_person``). Because we
sweep already-linked patients, this is a Tier-0 source-link recapture that
returns the existing person without writing a match-candidate row. The hint is
written only on the FIRST acceptance observation (guarded by an event-existence
pre-check) so re-pulls do not accumulate redundant hint rows.

The CareStack HTTP client is consumed via a local Protocol so this package does
not import ``packages.integrations``. Failure isolation: one patient's plan
fetch may 4xx/5xx; we log a PHI-safe line (patient id + error class) and
continue so one bad patient never poisons the sweep.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import ValidationError
from packages.core.logging import get_logger
from packages.core.types import PersonUID, TenantId
from packages.identity.schemas import MatchHintIn
from packages.identity.service import IdentityService
from packages.ingest.models import RawEvent
from packages.ingest.schemas import (
    CareStackTreatmentPlanImportOut,
    NormalizedPersonHintIn,
    RawEventIn,
)
from packages.ingest.service import IngestService
from packages.interaction.schemas import EventIn
from packages.interaction.service import InteractionService, summary_for_event

log = get_logger("ingest.carestack_treatment_plan")

_TREATMENT_PLAN_EVENT_TYPE = "carestack.treatment_plan.upsert"
_SOURCE_INSTANCE = "carestack-main"

# CareStack TreatmentPlanStatus enum (docs/.../resources/treatment-plans.md):
#   0 NotSet, 1 Proposed, 2 Recommended, 3 Accepted, 4 Rejected, 5 Alternative,
#   6 Hold, 7 ReferredOut, 8 Completed, 9 Presented, 10 ServiceCompleted.
# Acceptance is StatusId=3 ONLY — NOT 8/10 (completed), NOT 9 (presented).
_ACCEPTED_STATUS_ID = 3


class CareStackTreatmentPlanClientProtocol(Protocol):
    """Minimum CareStack client surface needed by the TreatmentPlan ingest."""

    async def get_treatment_plans(
        self, patient_id: int | str
    ) -> list[dict[str, Any]]: ...


class CareStackTreatmentPlanIngestService:
    """Per-patient TreatmentPlan sweep: capture raw + emit treatment_accepted."""

    def __init__(
        self,
        session: AsyncSession,
        carestack_client: CareStackTreatmentPlanClientProtocol,
    ) -> None:
        self._session = session
        self._carestack = carestack_client
        self._ingest = IngestService(session)
        self._identity = IdentityService(session)
        self._interaction = InteractionService(session)

    async def import_treatment_plans(
        self,
        tenant_id: TenantId,
        *,
        max_patients: int = 50,
    ) -> CareStackTreatmentPlanImportOut:
        """Bounded sweep: pull treatment plans for the N most-recently-linked patients.

        ``max_patients`` is the hard cap. The sweep walks
        ``identity.source_link`` (via ``IdentityService.source_links_for_dashboard``,
        NOT the repo) ordered by ``first_seen_at`` desc — the same ordering the
        dashboard uses — so a single tick covers the most-recently-imported
        patients first.
        """
        if max_patients < 1 or max_patients > 500:
            raise ValidationError(
                "max_patients must be between 1 and 500",
                details={"max_patients": max_patients},
            )

        links = await self._identity.source_links_for_dashboard(
            tenant_id,
            source_system="carestack",
            source_kind="patient",
            limit=max_patients,
        )

        captured_count = 0
        accepted_count = 0
        unchanged_count = 0
        skipped_count = 0
        error_count = 0
        patient_count = len(links)

        for link in links:
            patient_id = link.source_id
            if patient_id is None or not str(patient_id).strip():
                skipped_count += 1
                continue
            try:
                plans = await self._carestack.get_treatment_plans(patient_id)
            except Exception as exc:  # noqa: BLE001 — failure isolation per patient
                log.warning(
                    "carestack.treatment_plan.fetch_failed",
                    patient_id=str(patient_id),
                    error_class=type(exc).__name__,
                )
                error_count += 1
                continue

            for plan in plans:
                plan_id = _plan_source_id(plan)
                if plan_id is None:
                    skipped_count += 1
                    continue
                raw_event = await self._capture_plan_if_changed(
                    tenant_id, plan_id, plan
                )
                if raw_event is not None:
                    captured_count += 1
                else:
                    unchanged_count += 1

                if _plan_status_id(plan) == _ACCEPTED_STATUS_ID:
                    emitted = await self._emit_accepted(
                        tenant_id, str(patient_id), plan, plan_id, raw_event
                    )
                    if emitted:
                        accepted_count += 1

        log.info(
            "carestack.treatment_plan.sweep_done",
            tenant_id=str(tenant_id),
            patients=patient_count,
            captured=captured_count,
            accepted=accepted_count,
            unchanged=unchanged_count,
            skipped=skipped_count,
            errors=error_count,
        )
        return CareStackTreatmentPlanImportOut(
            captured_count=captured_count,
            accepted_count=accepted_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            error_count=error_count,
            patient_count=patient_count,
        )

    async def _capture_plan_if_changed(
        self, tenant_id: TenantId, plan_id: str, plan: dict[str, Any]
    ) -> RawEvent | None:
        """Capture one plan row to raw, deduping on the verbatim payload.

        TreatmentPlan rows carry no provider modified-stamp, so the guard
        compares the whole payload against the newest captured row for the plan
        id (mirrors the payment-summary content-dedup). Returns the freshly
        captured ``RawEvent`` when it changed, or ``None`` when the payload was
        identical to the latest capture (skipped before any write).
        """
        latest = await self._ingest.latest_payload(
            tenant_id,
            event_type=_TREATMENT_PLAN_EVENT_TYPE,
            external_id=plan_id,
        )
        if latest is not None and latest == plan:
            return None
        return await self._ingest.capture(
            tenant_id,
            RawEventIn(
                source="carestack",
                event_type=_TREATMENT_PLAN_EVENT_TYPE,
                external_id=plan_id,
                received_at=datetime.now(UTC),
                payload=plan,
            ),
        )

    async def _emit_accepted(
        self,
        tenant_id: TenantId,
        patient_id: str,
        plan: dict[str, Any],
        plan_id: str,
        raw_event: RawEvent | None,
    ) -> bool:
        """Emit ``treatment_accepted`` for an Accepted plan; True when created.

        Pre-checks event existence so an idempotent re-pull skips the ENG-185
        hint round-trip (no redundant hint rows on every sweep). ``raw_event``
        is the row captured this iteration (``None`` when content-dedup skipped
        it — only possible when the event already exists, i.e. we will return
        early — but a prior-pull partial is covered by capturing an anchor).
        """
        existing = await self._interaction.find_provider_event_by_external_id(
            tenant_id,
            source_provider="carestack",
            source_kind="carestack_treatment_plan",
            source_external_id=plan_id,
            kind="treatment_accepted",
        )
        if existing is not None:
            return False

        # Anchor the ENG-185 hint on a raw_event. Normally captured this
        # iteration; capture one if dedup skipped it (prior-pull partial).
        anchor = raw_event
        if anchor is None:
            anchor = await self._ingest.capture(
                tenant_id,
                RawEventIn(
                    source="carestack",
                    event_type=_TREATMENT_PLAN_EVENT_TYPE,
                    external_id=plan_id,
                    received_at=datetime.now(UTC),
                    payload=plan,
                ),
            )

        person_uid = await self._resolve_person(tenant_id, patient_id, anchor)
        if person_uid is None:
            return False

        # Acceptance date = first observed StatusId=3 (lastUpdatedOn else now).
        occurred_at = (
            _parse_carestack_datetime(plan.get("lastUpdatedOn"))
            or datetime.now(UTC)
        )
        summary = summary_for_event(
            kind="treatment_accepted",
            source_provider="carestack",
            source_id=plan_id,
        )
        result = await self._interaction.create_event_idempotent(
            tenant_id,
            EventIn(
                person_uid=person_uid,
                kind="treatment_accepted",
                source_provider="carestack",
                source_event_id=anchor.id,
                data_class="phi_protected",
                source_kind="carestack_treatment_plan",
                source_external_id=plan_id,
                review_status="auto",
                occurred_at=occurred_at,
                summary=summary,
                # No-PII payload: NO plan name, condition ids, or clinical
                # detail — those stay in raw only.
                payload={},
            ),
        )
        return result.was_created

    async def _resolve_person(
        self,
        tenant_id: TenantId,
        patient_id: str,
        raw_event: RawEvent,
    ) -> PersonUID | None:
        """Resolve patient -> person via the ENG-185 cutover pattern.

        Captures a (non-PHI) ``normalized_person_hint`` keyed on the CareStack
        patient id, anchored on the plan ``raw_event``, then resolves through
        ``IdentityService.resolve_or_create_from_hint`` (Tier-0 source-link
        recapture for an already-linked patient) and re-fetches the person via
        ``get_person``. TreatmentPlan rows carry no patient demographics, so the
        hint supplies only the external-record key.
        """
        hint = await self._ingest.capture_normalized_person_hint(
            tenant_id,
            NormalizedPersonHintIn(
                raw_event_id=raw_event.id,
                source_system="carestack",
                source_instance=_SOURCE_INSTANCE,
                source_kind="patient",
                source_id=patient_id,
                observed_at=raw_event.received_at,
            ),
        )
        result = await self._identity.resolve_or_create_from_hint(
            tenant_id,
            MatchHintIn(
                hint_id=hint.id,
                source_system="carestack",
                source_instance=_SOURCE_INSTANCE,
                source_kind="patient",
                source_id=patient_id,
            ),
        )
        person = await self._identity.get_person(
            tenant_id, PersonUID(result.person_uid)
        )
        return PersonUID(person.id)


# ---------------------------------------------------------- payload helpers


def _plan_source_id(plan: dict[str, Any]) -> str | None:
    """Extract the TreatmentPlan id from the row."""
    for key in ("TreatmentPlanId", "treatmentPlanId", "id"):
        value = plan.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, str | int) and str(value).strip():
            return str(value)
    return None


def _plan_status_id(plan: dict[str, Any]) -> int | None:
    """Parse the TreatmentPlan ``StatusId`` (int), tolerating strings."""
    for key in ("StatusId", "statusId"):
        value = plan.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return int(value.strip())
            except ValueError:
                return None
    return None


def _parse_carestack_datetime(value: object) -> datetime | None:
    """Parse a CareStack datetime string or passthrough a datetime object."""
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
