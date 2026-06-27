"""CareStack Appointment ingest pipeline.

For each CareStack appointment row pulled from the sync feed:

1. ``IngestService.capture`` writes the verbatim Appointment row to
   ``ingest.raw_event``. The CareStack feed may carry PHI (notes), so the
   raw row remains gated by the existing ``ingest`` access rules.
2. Look up the canonical ``identity.person`` for the appointment's
   ``patientId`` via the existing ``identity.source_link`` row. If the
   patient is not yet linked (patient ingest has not run), the appointment
   is skipped — operator can re-run after the patient pull.
3. ``OpsService.upsert_consultation_from_hint`` writes/updates the
   marketing-safe consultation row in ``ops.consultation``. Idempotent on
   ``(tenant_id, source_provider, source_instance, external_id)``.

PHI fields (``notes``, free text) NEVER enter ``ops.consultation``; the
allowlist is enforced by the ConsultationIn schema (no notes column).

The CareStack HTTP client is consumed via a local Protocol so this
package does not import ``packages.integrations``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.security import Principal
from packages.core.types import PersonUID, TenantId
from packages.identity.repository import IdentityRepository
from packages.identity.service import IdentityService
from packages.ingest.consultation_notify import (
    ConsultationNotifier,
    emit_consultation_scheduled_notification,
)
from packages.ingest.consultation_timeline import emit_consultation_timeline_event
from packages.ingest.responsibility_resolver import (
    FunnelResponsibilityResolver,
    ProviderOwnerHint,
)
from packages.ingest.schemas import (
    CareStackAppointmentImportOut,
    RawEventIn,
)
from packages.ingest.service import IngestService
from packages.ingest.sync_window import resume_modified_since
from packages.interaction.schemas import ResponsibilityAssignmentIn
from packages.interaction.service import InteractionService
from packages.ops.models import ConsultationKind, ConsultationStatus
from packages.ops.schemas import ConsultationIn
from packages.ops.service import OpsService
from packages.tenant.service import LocationService

logger = logging.getLogger(__name__)

_APPOINTMENT_EVENT_TYPE = "carestack.appointment.upsert"
_APPOINTMENT_LIST_KEYS = ("appointments", "items", "records", "results", "data")

# Actor-identifier kinds the ENG-465 card resolves through ``ActorNameResolver``.
# Kept as local literals (NOT imported from ``packages.actor``) so the ingest
# package honours the cross-package import matrix; they mirror
# ``packages.actor.service.ACTOR_KIND_CS_PROVIDER`` / ``ACTOR_KIND_SF_USER``.
_ACTOR_KIND_CS_PROVIDER = "carestack_provider_id"
_ACTOR_KIND_SF_USER = "salesforce_user_id"

# CareStack status string → canonical ConsultationStatus. The sync feed
# (per docs/integrations/carestack/sync/appointments.md) ships free-form
# status strings, while the resource feed uses an integer statusId. We
# only consume sync here, so we normalize on lowercase string keys.
#
# Unknown statuses fall back to SCHEDULED + a `Contract drift:` log so a
# CareStack vocabulary change does not silently mislabel rows.
_STATUS_MAP: dict[str, ConsultationStatus] = {
    # Keys must be lower-cased AND have spaces / underscores / hyphens / periods
    # stripped (the normaliser in _map_status strips all four). So "No-Show",
    # "Dr. Notes" and "Office Check-Out" normalise to "noshow" / "drnotes" /
    # "officecheckout".
    #
    # --- Pre-visit / not yet held → SCHEDULED (counts as "pending" until
    #     the appointment's scheduled_at passes, then read as no-show) ---
    "scheduled": ConsultationStatus.SCHEDULED,
    "confirmed": ConsultationStatus.SCHEDULED,
    "unconfirmed": ConsultationStatus.SCHEDULED,
    "confirmedelectronically": ConsultationStatus.SCHEDULED,
    "leftmessage": ConsultationStatus.SCHEDULED,
    "unabletoreach": ConsultationStatus.SCHEDULED,
    "unscheduled": ConsultationStatus.SCHEDULED,
    # --- Patient physically present in the office → COMPLETED ("showed") ---
    # CareStack uses "Checked Out" once the visit is finished and the patient
    # has left; "Checked In" / "In Chair" / "In Operatory" / "Ready To Seat" /
    # "Office Checkout" / "Arrived" all mean the patient was physically present
    # for the visit. That is operationally "showed" for the funnel.
    "completed": ConsultationStatus.COMPLETED,
    "checkedout": ConsultationStatus.COMPLETED,
    "checkedin": ConsultationStatus.COMPLETED,
    "inchair": ConsultationStatus.COMPLETED,
    "inoperatory": ConsultationStatus.COMPLETED,
    "readytoseat": ConsultationStatus.COMPLETED,
    "officecheckout": ConsultationStatus.COMPLETED,
    "arrived": ConsultationStatus.COMPLETED,
    # --- Did not attend → NO_SHOW. A "broken" appointment is a no-show. ---
    "cancelled": ConsultationStatus.CANCELLED,
    "canceled": ConsultationStatus.CANCELLED,
    "noshow": ConsultationStatus.NO_SHOW,
    "broken": ConsultationStatus.NO_SHOW,
    "rescheduled": ConsultationStatus.RESCHEDULED,
    # --- Deleted / note-only admin rows → DELETED (excluded from the funnel).
    #     These never represented a real appointment on the schedule. ---
    "deleted": ConsultationStatus.DELETED,
    "notecompleted": ConsultationStatus.DELETED,
    "drnotes": ConsultationStatus.DELETED,
    "asstnotes": ConsultationStatus.DELETED,
    "reviewrequired": ConsultationStatus.DELETED,
}


class CareStackAppointmentClientProtocol(Protocol):
    """Minimum CareStack client surface needed by the Appointment ingest."""

    async def list_appointments_modified_since(
        self,
        modified_since: datetime,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]: ...


class ActorNameResolver(Protocol):
    """Resolve an external party id to its ``actor.actor`` display name.

    ENG-465: two card fields need a name the appointment payload does not
    carry directly:

    * the DOCTOR — ``providerIds[0]`` maps to an ``actor.actor`` keyed by an
      ``actor_identifier`` of kind ``carestack_provider_id`` (populated by the
      responsibility resolver on every consult ingest), and
    * the TC OWNER — the SF Opportunity / Lead ``owner_id`` maps to an actor
      keyed by ``salesforce_user_id`` (used only when the owner_name is not
      cached on the SF projection row).

    ``packages/ingest`` may NOT import ``packages/actor`` (cross-package
    matrix), so the concrete resolver is built at the worker boundary and
    injected here as this Protocol — mirroring
    :class:`FunnelResponsibilityResolver` / :class:`ConsultationNotifier`.

    Returns the actor display name, or ``None`` when the id is unknown (no
    actor mapped yet). A miss never blocks the ingest — the consultation row
    keeps an empty ``provider_clinician_name`` and the card simply drops the
    field until a later pull resolves it.
    """

    async def resolve_actor_name(
        self, tenant_id: TenantId, kind: str, value: str
    ) -> str | None: ...


class CareStackAppointmentIngestService:
    """Pull CareStack Appointments, capture raw, upsert ops.consultation."""

    def __init__(
        self,
        session: AsyncSession,
        carestack_client: CareStackAppointmentClientProtocol,
        responsibility_resolver: FunnelResponsibilityResolver | None = None,
        actor_name_resolver: ActorNameResolver | None = None,
    ) -> None:
        self._session = session
        self._carestack = carestack_client
        self._ingest = IngestService(session)
        self._identity = IdentityService(session)
        self._identity_repo = IdentityRepository(session)
        self._ops = OpsService(session)
        self._interaction = InteractionService(session)
        self._locations = LocationService(session)
        # ENG-416 + ENG-417: optional resolver. CareStack consults get
        # BOTH a TC actor (covering Opportunity owner; SF is the sole
        # source — NEVER CareStack) AND a clinical actor (the doctor
        # from the appointment payload's provider id).
        self._responsibility = responsibility_resolver
        # ENG-465: optional actor-name resolver. Maps the appointment's
        # ``providerIds[0]`` → clinician name (kind ``carestack_provider_id``)
        # and the funnel owner's SF user id → TC name (kind
        # ``salesforce_user_id``) so the consultation row carries the real
        # doctor (not the source system label) and the #scheduls card shows the
        # owner. Injected at the worker boundary; ``None`` (backfill / tests)
        # leaves the column / card fields as the payload / projection supplied.
        self._actor_names = actor_name_resolver

    async def import_recent_appointments(
        self,
        tenant_id: TenantId,
        *,
        days: int = 7,
        page_size: int = 100,
        max_pages: int = 1,
        notifier: ConsultationNotifier | None = None,
        principal: Principal | None = None,
    ) -> CareStackAppointmentImportOut:
        """Capture recent CareStack Appointments into ingest and ops.

        Bounded by ``max_pages`` (default 1) to keep manual imports
        predictable. ``continue_token`` from the last page is returned so
        the caller can resume.

        ENG-457: when a ``notifier`` (and ``principal``) is supplied, a
        genuinely-new consultation also announces ``consultation.scheduled``
        to the messenger. The backfill path (``pull_all_since``) never
        supplies one, so backfill never notifies.
        """
        if days < 1 or days > 365:
            raise ValidationError(
                "days must be between 1 and 365", details={"days": days}
            )
        if page_size < 1 or page_size > 500:
            raise ValidationError(
                "page_size must be between 1 and 500",
                details={"page_size": page_size},
            )
        if max_pages < 1 or max_pages > 20:
            raise ValidationError(
                "max_pages must be between 1 and 20",
                details={"max_pages": max_pages},
            )

        # Resume from the highest captured ``lastUpdatedOn`` (ENG-381);
        # ``days`` is the first-run fallback.
        watermark = await self._ingest.max_payload_watermark(
            tenant_id, event_type=_APPOINTMENT_EVENT_TYPE
        )
        modified_since = resume_modified_since(
            watermark, default_since=datetime.now(UTC) - timedelta(days=days)
        )
        imported_count = 0
        unchanged_count = 0
        skipped_count = 0
        page_count = 0
        continue_token: str | None = None

        while page_count < max_pages:
            body = await self._carestack.list_appointments_modified_since(
                modified_since,
                page_size=page_size,
                continue_token=continue_token,
            )
            page_count += 1
            rows = _extract_appointment_rows(body)
            captured_stamps = await self._latest_captured_stamps(tenant_id, rows)
            for row in rows:
                appointment_id = _appointment_source_id(row)
                patient_id = _appointment_patient_id(row)
                if appointment_id is None or patient_id is None:
                    skipped_count += 1
                    continue
                stamp = row.get("lastUpdatedOn")
                if (
                    isinstance(stamp, str)
                    and captured_stamps.get(appointment_id) == stamp
                ):
                    unchanged_count += 1
                    continue
                outcome = await self._capture_appointment(
                    tenant_id,
                    row,
                    appointment_id,
                    patient_id,
                    notifier=notifier,
                    principal=principal,
                )
                if outcome == "imported":
                    imported_count += 1
                elif outcome == "unchanged":
                    unchanged_count += 1
                else:
                    skipped_count += 1

            continue_token = _continue_token(body)
            if not continue_token:
                break

        return CareStackAppointmentImportOut(
            imported_count=imported_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            page_count=page_count,
            next_continue_token=continue_token,
        )

    async def pull_all_since(
        self,
        tenant_id: TenantId,
        since: datetime,
        *,
        page_size: int = 500,
        page_safety_cap: int = 1000,
    ) -> CareStackAppointmentImportOut:
        """Full backfill of CareStack Appointments modified on or after ``since``.

        Follows ``continueToken`` until exhausted. Appointments whose patient
        is not yet linked are counted as skipped — re-running after a patient
        backfill resolves them. ``page_safety_cap`` defends against a runaway
        provider response.
        """
        if page_size < 1 or page_size > 500:
            raise ValidationError(
                "page_size must be between 1 and 500",
                details={"page_size": page_size},
            )
        if page_safety_cap < 1:
            raise ValidationError(
                "page_safety_cap must be >= 1",
                details={"page_safety_cap": page_safety_cap},
            )

        modified_since = (
            since if since.tzinfo is not None else since.replace(tzinfo=UTC)
        )
        imported_count = 0
        unchanged_count = 0
        skipped_count = 0
        page_count = 0
        continue_token: str | None = None
        while page_count < page_safety_cap:
            body = await self._carestack.list_appointments_modified_since(
                modified_since,
                page_size=page_size,
                continue_token=continue_token,
            )
            page_count += 1
            rows = _extract_appointment_rows(body)
            captured_stamps = await self._latest_captured_stamps(tenant_id, rows)
            for row in rows:
                appointment_id = _appointment_source_id(row)
                patient_id = _appointment_patient_id(row)
                if appointment_id is None or patient_id is None:
                    skipped_count += 1
                    continue
                stamp = row.get("lastUpdatedOn")
                if (
                    isinstance(stamp, str)
                    and captured_stamps.get(appointment_id) == stamp
                ):
                    unchanged_count += 1
                    continue
                outcome = await self._capture_appointment(
                    tenant_id, row, appointment_id, patient_id
                )
                if outcome == "imported":
                    imported_count += 1
                elif outcome == "unchanged":
                    unchanged_count += 1
                else:
                    skipped_count += 1
            continue_token = _continue_token(body)
            if not continue_token:
                break
        return CareStackAppointmentImportOut(
            imported_count=imported_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            page_count=page_count,
            next_continue_token=continue_token,
        )

    async def _latest_captured_stamps(
        self, tenant_id: TenantId, rows: list[dict[str, Any]]
    ) -> dict[str, str]:
        """Captured ``lastUpdatedOn`` per appointment id for a page of rows.

        Capture change-guard (ENG-381): rows whose stamp matches are
        healthy overlap re-reads — the caller skips them before any raw
        write or downstream processing.
        """
        candidate_ids = [
            appointment_id
            for row in rows
            if (appointment_id := _appointment_source_id(row)) is not None
        ]
        return await self._ingest.latest_payload_values(
            tenant_id,
            event_type=_APPOINTMENT_EVENT_TYPE,
            external_ids=candidate_ids,
            payload_key="lastUpdatedOn",
        )

    async def _capture_appointment(
        self,
        tenant_id: TenantId,
        row: dict[str, Any],
        appointment_id: str,
        patient_id: str,
        *,
        notifier: ConsultationNotifier | None = None,
        principal: Principal | None = None,
    ) -> str:
        """Capture raw + resolve identity + upsert consultation.

        Returns one of:

        * ``"imported"`` — the consultation row was created OR a
          meaningful field changed (status / scheduled_at / other).
        * ``"unchanged"`` — the consultation already existed and nothing
          changed (``was_created is False and was_changed is False``).
          HEALTHY idempotent re-pull, NOT a failure.
        * ``"skipped"`` — genuine non-import: the patient is not yet
          linked or the appointment lacks a scheduled timestamp. The
          raw_event is still captured.
        """
        raw_event = await self._ingest.capture(
            tenant_id,
            RawEventIn(
                source="carestack",
                event_type=_APPOINTMENT_EVENT_TYPE,
                external_id=appointment_id,
                received_at=datetime.now(UTC),
                payload=row,
            ),
        )

        # Resolve patientId → person_uid via the source_link from a prior
        # patient pull. Two-pass design — patient pull must run first.
        source_link = await self._identity_repo.find_source_link(
            tenant_id,
            source_system="carestack",
            source_instance="carestack-main",
            source_kind="patient",
            source_id=patient_id,
        )
        if source_link is None:
            logger.warning(
                "carestack.appointment.skipped: patient not yet linked",
                extra={
                    "appointment_id": appointment_id,
                    "patient_id": patient_id,
                    "tenant_id": str(tenant_id),
                },
            )
            return "skipped"

        scheduled_at = _appointment_scheduled_at(row)
        if scheduled_at is None:
            logger.warning(
                "carestack.appointment.skipped: no scheduled_at",
                extra={"appointment_id": appointment_id},
            )
            return "skipped"

        # ENG-465: resolve the real clinician name from the appointment's
        # provider id (via the injected actor-backed resolver) so the
        # consultation row stores the DOCTOR, not the source label. Falls back
        # to any name the payload happens to carry, then to None.
        provider_clinician_name = await self._resolve_provider_name(tenant_id, row)
        # ENG-543: capture the provider id verbatim so the reminder can resolve
        # the doctor's actor → Mattermost @mention. Same id the name resolver uses.
        provider_id = _first_provider_id(row)
        provider_carestack_id = str(provider_id) if provider_id is not None else None

        upsert = await self._ops.upsert_consultation_from_hint(
            tenant_id,
            ConsultationIn(
                person_uid=source_link.person_uid,
                source_provider="carestack",
                source_instance="carestack-main",
                external_id=appointment_id,
                scheduled_at=scheduled_at,
                provider_created_at=_appointment_provider_created_at(row),
                duration_minutes=_appointment_duration(row),
                status=_map_status(row.get("status")),
                source_status=_source_status(row.get("status")),
                consultation_kind=ConsultationKind.OTHER,
                location_id=await self._resolve_location_id(tenant_id, row),
                provider_clinician_name=provider_clinician_name,
                provider_carestack_id=provider_carestack_id,
                raw_event_id=raw_event.id,
            ),
        )
        # ENG-416 + ENG-417: resolve responsibility BEFORE the timeline
        # event emit so the join-table rows land atomically with the
        # event row. Also attaches the covering Opportunity link to the
        # consult row when one is found.
        provider_hint = _clinical_provider_hint(row)
        responsibilities, covering_opportunity_id = await self._resolve_consultation_responsibility(
            tenant_id,
            person_uid=source_link.person_uid,
            scheduled_at=scheduled_at,
            clinical_provider=provider_hint,
        )
        # Persist the consult <-> covering Opportunity link (ENG-417)
        # only when the consult actually exists in ops (was_created or
        # was_changed leaves a real row; a pure no-op upsert still has
        # the row from the prior pass).
        if covering_opportunity_id is not None or upsert.was_created:
            # Even when covering_opportunity_id is None we DON'T clear an
            # existing link — a later pull may have placed it via the
            # backfill. The condition above intentionally writes only
            # when we have something to set OR the consult is fresh.
            if covering_opportunity_id is not None:
                await self._ops.attach_consultation_to_opportunity(
                    tenant_id,
                    upsert.consultation.id,
                    covering_opportunity_id,
                )
        await emit_consultation_timeline_event(
            self._interaction,
            tenant_id,
            upsert,
            source_provider="carestack",
            source_kind="carestack_appointment",
            source_external_id=appointment_id,
            source_event_id=raw_event.id,
            responsibilities=responsibilities,
        )
        # ENG-457: announce a genuinely-new consultation to #scheduls. No-op
        # unless a notifier+principal were threaded in (recent pull only, never
        # backfill) and the upsert actually created the row.
        if notifier is not None and principal is not None and upsert.was_created:
            # ENG-460: resolve the real patient name at this boundary so the
            # #scheduls card is useful to staff (the messenger is an authorized
            # PHI surface). A missing person never blocks the notify — the card
            # still posts with whatever it has.
            person_name: str | None = None
            person_phone: str | None = None
            try:
                person = await self._identity.get_person(
                    tenant_id, PersonUID(source_link.person_uid)
                )
                person_name = (
                    person.display_name
                    or person.given_name
                    or person.family_name
                )
                person_phone = await self._identity.get_primary_phone(
                    tenant_id, PersonUID(source_link.person_uid)
                )
            except NotFoundError:
                logger.info(
                    "carestack.appointment.notify.person_unresolved",
                    extra={"person_uid": str(source_link.person_uid)},
                )
            # ENG-465: enrich the card with the resolved DOCTOR (already
            # computed above), the CLINIC name, and the TC OWNER (covering
            # Opportunity owner, falling back to the Lead owner). Each resolve
            # is defensive — a miss leaves the field empty and the renderer
            # prunes it, never blocking the notify.
            clinic_name = await self._resolve_clinic_name(tenant_id, row)
            owner_name = await self._resolve_owner_name(
                tenant_id, source_link.person_uid
            )
            await emit_consultation_scheduled_notification(
                notifier,
                tenant_id,
                upsert,
                source_provider="carestack",
                principal=principal,
                person_name=person_name,
                person_phone=person_phone,
                doctor_name=provider_clinician_name,
                clinic_name=clinic_name,
                owner_name=owner_name,
            )
        # ENG-329: a re-pull that upserts the SAME consultation with no
        # field change is an idempotent dedup, not a fresh import. Count
        # it as "unchanged" so the sync_run metric stops folding healthy
        # re-reads into the failed bucket.
        if upsert.was_created or upsert.was_changed:
            return "imported"
        return "unchanged"

    async def _resolve_consultation_responsibility(
        self,
        tenant_id: TenantId,
        *,
        person_uid: UUID,
        scheduled_at: datetime,
        clinical_provider: ProviderOwnerHint | None,
    ) -> tuple[list[ResponsibilityAssignmentIn], UUID | None]:
        """Run the funnel resolver for a consult; tolerate missing wiring.

        Returns ``(responsibilities, covering_opportunity_id)``. The
        consult event kind passed to the resolver is the lifecycle that
        the emitter will use — ``consultation_scheduled`` is correct for
        all four lifecycle kinds because they all attribute to the same
        Opportunity-owner / doctor pair (the kind only affects which
        :data:`_CONSULT_ONWARD_KINDS` branch fires, and all consult
        kinds share that branch).
        """
        if self._responsibility is None:
            return [], None
        resolved = await self._responsibility.resolve(
            tenant_id,
            event_kind="consultation_scheduled",
            person_uid=person_uid,
            occurred_at=scheduled_at,
            clinical_provider=clinical_provider,
        )
        return resolved.assignments, resolved.covering_opportunity_id

    async def _resolve_location_id(
        self, tenant_id: TenantId, row: dict[str, Any]
    ) -> UUID | None:
        carestack_location_id = _appointment_location_id(row)
        if carestack_location_id is None:
            return None
        location = await self._locations.find_by_carestack_id(
            tenant_id, carestack_location_id
        )
        if location is None:
            logger.warning(
                "carestack.appointment.location_unlinked",
                extra={
                    "tenant_id": str(tenant_id),
                    "carestack_location_id": carestack_location_id,
                },
            )
            return None
        return location.id

    async def _resolve_provider_name(
        self, tenant_id: TenantId, row: dict[str, Any]
    ) -> str | None:
        """Resolve the clinician name for the appointment's provider id.

        ENG-465: prefer the injected actor-backed resolver
        (``providerIds[0]`` → ``actor.actor.name``). Fall back to a name the
        payload happens to carry (legacy / on-demand feeds), then to ``None``.
        A resolver miss is non-fatal — the consultation keeps an empty
        ``provider_clinician_name`` until a later pull resolves it.
        """
        provider_id = _first_provider_id(row)
        if self._actor_names is not None and provider_id is not None:
            resolved = await self._actor_names.resolve_actor_name(
                tenant_id, _ACTOR_KIND_CS_PROVIDER, str(provider_id)
            )
            if resolved:
                return resolved
        return _provider_name(row)

    async def _resolve_clinic_name(
        self, tenant_id: TenantId, row: dict[str, Any]
    ) -> str | None:
        """Resolve the appointment's location id to a clinic display name."""
        carestack_location_id = _appointment_location_id(row)
        if carestack_location_id is None:
            return None
        location = await self._locations.find_by_carestack_id(
            tenant_id, carestack_location_id
        )
        return location.name if location is not None else None

    async def _resolve_owner_name(
        self,
        tenant_id: TenantId,
        person_uid: UUID,
    ) -> str | None:
        """Resolve the TC owner display name for the card (ENG-465).

        Operator decision: the consultation owner is the patient's funnel
        owner — the covering Opportunity owner (Phase-2 TC), falling back to
        the Lead owner. ``OpsService.get_current_funnel_owner`` already
        encodes that rule and returns the SF-stored ``owner_name`` when
        present; when only the SF ``owner_id`` is on file we resolve it to an
        ``actor.actor`` display name (kind ``salesforce_user_id``) through the
        injected resolver. A patient with no Lead and no Opportunity yields
        ``None`` and the card simply drops the Owner field.
        """
        try:
            owner = await self._ops.get_current_funnel_owner(tenant_id, person_uid)
        except Exception:  # noqa: BLE001 — owner is a nice-to-have, never fatal
            logger.info(
                "carestack.appointment.notify.owner_unresolved",
                extra={"person_uid": str(person_uid)},
            )
            return None
        if owner is None:
            return None
        if owner.owner_name:
            return owner.owner_name
        # Owner id on file but no cached name: resolve the SF user id to an
        # actor display name through the injected actor-backed resolver.
        if self._actor_names is not None and owner.external_id:
            resolved = await self._actor_names.resolve_actor_name(
                tenant_id, _ACTOR_KIND_SF_USER, owner.external_id
            )
            if resolved:
                return resolved
        return None


# ---------------------------------------------------------- payload helpers


def _extract_appointment_rows(body: dict[str, Any]) -> list[dict[str, Any]]:
    for key in _APPOINTMENT_LIST_KEYS:
        value = body.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def _continue_token(body: dict[str, Any]) -> str | None:
    for key in ("continueToken", "nextContinueToken", "continuationToken"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _appointment_source_id(row: dict[str, Any]) -> str | None:
    for key in ("id", "appointmentId", "AppointmentId"):
        value = row.get(key)
        if isinstance(value, str | int) and str(value).strip():
            return str(value)
    return None


def _appointment_patient_id(row: dict[str, Any]) -> str | None:
    for key in ("patientId", "PatientId"):
        value = row.get(key)
        if isinstance(value, str | int) and str(value).strip():
            return str(value)
    return None


def _appointment_location_id(row: dict[str, Any]) -> int | None:
    for key in ("locationId", "LocationId"):
        value = row.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    return None


def _appointment_scheduled_at(row: dict[str, Any]) -> datetime | None:
    # CareStack sync feed uses ``startDateTime`` (per spec) but examples in
    # the same doc page sometimes show ``startTime``; the on-demand resource
    # feed uses ``dateTime``. Read all three in priority order to be robust
    # to which feed seeded the row.
    for key in ("startDateTime", "startTime", "dateTime"):
        parsed = _parse_carestack_datetime(row.get(key))
        if parsed is not None:
            return parsed
    return None


def _appointment_provider_created_at(row: dict[str, Any]) -> datetime | None:
    """CareStack appointment payload exposes ``createdOn``; SF Event would
    use ``CreatedDate`` (handled by sf_event ingest). Returned value feeds
    ``ops.consultation.provider_created_at`` and is what the dashboard
    "created in window" filter walks."""
    return _parse_carestack_datetime(row.get("createdOn"))


def _appointment_duration(row: dict[str, Any]) -> int | None:
    value = row.get("duration")
    if isinstance(value, int) and value >= 0:
        return value
    return None


def _clinical_provider_hint(row: dict[str, Any]) -> ProviderOwnerHint | None:
    """Build a clinical-actor hint from a CareStack appointment payload.

    Strategy:
    - Prefer the first ``providerIds`` integer (per CareStack sync spec
      ``providerIds`` is a list of integer provider ids).
    - Fall back to a single-valued ``providerId`` / ``ProviderId`` key
      seen on the on-demand resource feed.
    - When nothing is supplied, return ``None`` and the resolver leaves
      the clinical role unattached (walk-in without a recorded doctor).
    Optional ``providerName`` (when the payload happens to carry it)
    seeds the ``name_hint`` so a brand-new actor row gets a friendly
    display name on first observation.
    """
    provider_id = _first_provider_id(row)
    if provider_id is None:
        return None
    return ProviderOwnerHint(
        source_provider="carestack",
        source_instance="carestack-main",
        external_id=str(provider_id),
        name_hint=_provider_name(row),
        role_hint="provider",
    )


def _first_provider_id(row: dict[str, Any]) -> int | str | None:
    """Pull the first provider id from any of the CareStack-spec keys."""
    provider_ids = row.get("providerIds") or row.get("ProviderIds")
    if isinstance(provider_ids, list):
        for value in provider_ids:
            if isinstance(value, int) and value > 0:
                return value
            if isinstance(value, str) and value.strip().isdigit():
                return value.strip()
    for key in ("providerId", "ProviderId"):
        value = row.get(key)
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return value.strip()
    return None


def _provider_name(row: dict[str, Any]) -> str | None:
    """Try to surface a marketing-safe clinician name from the payload.

    The CareStack sync feed sends ``providerIds`` as an int array; the
    names live in a separate Provider resource. PR-B' does not look them
    up — if the payload happens to carry a name string we use it,
    otherwise we leave the column empty. A future PR may wire a
    provider-name lookup once it is needed for the operator UI.
    """
    for key in ("providerName", "provider", "providerDisplayName"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _source_status(raw: Any) -> str | None:
    """Verbatim provider status, trimmed (ENG-487).

    The bucketed ``_map_status`` collapses the rich CareStack status (e.g.
    "Confirmed" → SCHEDULED). This keeps the original string so workflows that
    need the finer signal (T-15m reminder, ENG-486) can read it. Truncated to
    the column width; empty/non-string yields ``None``.
    """
    if not isinstance(raw, str):
        return None
    trimmed = raw.strip()
    return trimmed[:48] or None


def _map_status(raw: Any) -> ConsultationStatus:
    if not isinstance(raw, str):
        return ConsultationStatus.SCHEDULED
    # Normalise to a punctuation-free, lowercase key: CareStack emits the same
    # status with assorted separators ("Dr. Notes", "Office Check-Out",
    # "Un-Confirmed"), so we strip spaces, underscores, hyphens AND periods
    # before lookup. Map keys are stored in this normalised form.
    key = (
        raw.strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace(".", "")
    )
    mapped = _STATUS_MAP.get(key)
    if mapped is not None:
        return mapped
    logger.warning(
        "Contract drift: unknown CareStack appointment status — defaulting to scheduled",
        extra={"status": raw},
    )
    return ConsultationStatus.SCHEDULED


def _parse_carestack_datetime(value: object) -> datetime | None:
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
