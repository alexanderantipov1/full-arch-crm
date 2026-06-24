"""InteractionService — public surface for the interaction domain.

Phase 1 responsibilities:
  * Build no-PII summary strings (:func:`summary_for_event`).
  * Append events idempotently (catches partial-UNIQUE collisions, returns
    the existing row on replay rather than raising).
  * Return per-Person timeline slices.

The full interaction package (event_content, transcripts, message
artifacts) lives in ``FUS-16`` for M3.

Every public method takes ``tenant_id: TenantId`` as the first positional
argument (ENG-128).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId

from .models import EVENT_KINDS, RESPONSIBILITY_ROLES, SOURCE_PROVIDERS, Event
from .repository import InteractionRepository
from .schemas import (
    FUNNEL_STAGE_ORDER,
    CallVolumeOut,
    EventIn,
    FieldValueBucketOut,
    FunnelDropoffActorAggregate,
    FunnelDropoffStageComputed,
    FunnelStage,
    InteractionFieldProfileOut,
    OperationalTimelineEntry,
    OperationalTimelineProjectionSnapshot,
    OperationalTimelineResponsibleRef,
    PaymentSummaryOut,
    ResponsibilityAssignmentIn,
    ResponsibilityRole,
    TreatmentPaymentAggregateOut,
)

# Display names for the provider in summary strings. Provider key stays
# lowercase in the DB; the display name is for human-readable summaries.
_PROVIDER_DISPLAY: dict[str, str] = {
    "salesforce": "Salesforce",
    "carestack": "CareStack",
}

# Mapping of kind -> (verb phrase, preposition). The preposition differs per
# provider semantics: leads come "from" Salesforce, consultations happen
# "in" CareStack.
_KIND_VERB: dict[str, tuple[str, str]] = {
    "lead_created": ("Lead created", "from"),
    "lead_updated": ("Lead updated", "in"),
    "consultation_scheduled": ("Consultation scheduled", "in"),
    "consultation_created": ("Consultation created", "in"),
    "consultation_rescheduled": ("Consultation rescheduled", "in"),
    "consultation_cancelled": ("Consultation cancelled", "in"),
    "consultation_completed": ("Consultation completed", "in"),
    "consultation_no_show": ("Consultation no-show", "in"),
    "task_created": ("Task created", "in"),
    "task_completed": ("Task completed", "in"),
    "call_logged": ("Call logged", "in"),
    "call_reference_found": ("Call reference found", "in"),
    "treatment_proposed": ("Treatment proposed", "in"),
    "treatment_completed": ("Treatment completed", "in"),
    "treatment_accepted": ("Treatment accepted", "in"),
    "surgery_scheduled": ("Surgery scheduled", "in"),
    "surgery_completed": ("Surgery completed", "in"),
    "invoice_created": ("Invoice created", "in"),
    "case_opened": ("Case opened", "in"),
    "case_closed": ("Case closed", "in"),
    "opportunity_created": ("Opportunity created", "in"),
    "opportunity_won": ("Opportunity won", "in"),
    "opportunity_lost": ("Opportunity lost", "in"),
    "opportunity_stage_changed": ("Opportunity stage changed", "in"),
    "contact_created": ("Contact created", "in"),
    "payment_recorded": ("Payment recorded", "in"),
    "payment_refunded": ("Payment refunded", "in"),
    "payment_reversed": ("Payment reversed", "in"),
    "payment_applied": ("Payment applied", "in"),
}

_PROJECTION_ALLOWLIST = frozenset({"status", "scheduled_at", "due_at"})


@dataclass(frozen=True, slots=True)
class EventEmissionResult:
    """Outcome of an idempotent ``create_event`` call (ENG-269).

    ``event`` is always the row that now exists in the database for the
    requested ``(tenant_id, source_provider, source_kind,
    source_external_id, kind)`` tuple. ``was_created`` is ``True`` when
    this call inserted a new row, and ``False`` when an earlier row
    already covered the key and the cross-pull partial UNIQUE turned
    this call into a no-op. CareStack ingest callers count
    ``was_created=False`` as ``skipped`` so dashboard counters stay
    truthful across re-pulls.
    """

    event: Event
    was_created: bool


class OperationalProjectionReader(Protocol):
    """Narrow projection reader implemented outside ``interaction``.

    ``packages.interaction`` must not import ``packages.ops``. The API wiring
    provides an adapter/service that satisfies this protocol.
    """

    async def get_operational_timeline_projection(
        self,
        tenant_id: TenantId,
        projection_ref_type: str,
        projection_ref_id: UUID,
    ) -> Mapping[str, object] | None:
        """Return allowlist-candidate projection fields for a ref."""


def summary_for_event(
    *,
    kind: str,
    source_provider: str,
    source_id: str | None = None,
) -> str:
    """Build a no-PII summary string for an :class:`Event`.

    Contract: action verb + provider display name + optional non-PII
    ``source_id`` (the provider's stable record id). NEVER name, email,
    phone, DOB, address, MRN, clinical free-text.

    The function intentionally accepts ONLY these three fields. Adding a
    name/email/phone parameter would require a code-review event and a
    documented exception to the no-PII rule.

    Examples:
        summary_for_event(kind="lead_created", source_provider="salesforce")
            -> "Lead created from Salesforce"
        summary_for_event(kind="consultation_rescheduled",
                          source_provider="carestack", source_id="12345")
            -> "Consultation rescheduled in CareStack (id=12345)"
    """
    if kind not in _KIND_VERB:
        raise ValidationError(
            "unknown event kind",
            details={"kind": kind, "allowed": list(EVENT_KINDS)},
        )
    if source_provider not in _PROVIDER_DISPLAY:
        raise ValidationError(
            "unknown source_provider",
            details={
                "source_provider": source_provider,
                "allowed": list(SOURCE_PROVIDERS),
            },
        )

    verb, preposition = _KIND_VERB[kind]
    display = _PROVIDER_DISPLAY[source_provider]
    base = f"{verb} {preposition} {display}"
    if source_id is not None:
        # Strip whitespace; reject nothing else here. The caller is
        # responsible for ensuring source_id is the provider's stable
        # record id (not, say, a user-supplied free-text field).
        sid = source_id.strip()
        if sid:
            base = f"{base} (id={sid})"
    return base


class InteractionService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        operational_projection_reader: OperationalProjectionReader | None = None,
    ) -> None:
        self._session = session
        self._repo = InteractionRepository(session)
        self._operational_projection_reader = operational_projection_reader

    async def create_event(self, tenant_id: TenantId, payload: EventIn) -> Event:
        """Append an :class:`Event` to a Person's timeline.

        Idempotent against the two partial UNIQUE indexes on
        ``interaction.event`` (the single-pipeline-run replay index on
        ``(source_provider, source_event_id)`` and the cross-pull
        ENG-269 index on ``(tenant_id, source_provider, source_kind,
        source_external_id, kind)``). On either collision the existing
        row is returned instead of raising. This method drops the
        ``was_created`` signal from :class:`EventEmissionResult` —
        callers that count imported vs skipped (CareStack ingest)
        should use :meth:`create_event_idempotent` instead.

        ``EventIn`` validation already enforces:
          * ``kind`` in EVENT_KINDS
          * ``source_provider`` in SOURCE_PROVIDERS
          * ``summary`` non-empty, <= 500 chars

        The no-PII contract for ``summary`` and ``payload`` is enforced by
        construction (callers use :func:`summary_for_event` and pass only
        non-PII payload dicts) -- there is no run-time scrubber. Tests
        verify the helper output and the worker payload allowlists.
        """
        result = await self.create_event_idempotent(tenant_id, payload)
        return result.event

    async def create_event_idempotent(
        self, tenant_id: TenantId, payload: EventIn
    ) -> EventEmissionResult:
        """Append an :class:`Event`; report whether the row was new.

        Returns :class:`EventEmissionResult`. ``was_created=True`` means
        this call inserted a fresh row; ``was_created=False`` means an
        earlier row already covered the dedup key and the partial UNIQUE
        turned this call into a no-op (the existing row is returned).

        The insert runs inside a ``SAVEPOINT``
        (``AsyncSession.begin_nested``) so an ``IntegrityError`` on the
        UNIQUE indexes only rolls back the failed flush — any
        already-flushed work in the outer transaction (most importantly
        the ``ingest.raw_event`` forensic capture from the same ingest
        call) survives. Without the savepoint, a re-pull conflict would
        also undo the raw_event capture.

        When ``payload.responsibilities`` is non-empty AND the row was
        newly created, this method also writes the corresponding
        ``event_responsibility`` rows (ENG-416). For dedup-hit
        ``was_created=False`` paths the responsibilities are NOT
        rewritten — the existing event already has its own owner
        history; rewriting would race the PK and confuse audit.
        """
        event = Event(
            tenant_id=tenant_id,
            person_uid=payload.person_uid,
            kind=payload.kind,
            source_provider=payload.source_provider,
            source_event_id=payload.source_event_id,
            data_class=payload.data_class,
            source_kind=payload.source_kind,
            source_external_id=payload.source_external_id,
            projection_ref_type=payload.projection_ref_type,
            projection_ref_id=payload.projection_ref_id,
            review_status=payload.review_status,
            occurred_at=payload.occurred_at,
            summary=payload.summary,
            payload=dict(payload.payload),
            created_by_actor_id=payload.created_by_actor_id,
        )

        savepoint = await self._session.begin_nested()
        try:
            inserted = await self._repo.add_event(event)
        except IntegrityError:
            # Either partial UNIQUE fired. Roll back JUST this insert
            # (savepoint, not the outer transaction) so raw_event etc.
            # stay intact, then resolve which row exists.
            await savepoint.rollback()
            existing = await self._find_existing_after_conflict(tenant_id, payload)
            if existing is None:
                # Constraint fired but we cannot find the colliding row —
                # surface the original IntegrityError rather than silently
                # swallowing a real constraint failure.
                raise
            return EventEmissionResult(event=existing, was_created=False)
        else:
            await savepoint.commit()
            if payload.responsibilities:
                await self._write_responsibilities(
                    tenant_id, inserted.id, payload.responsibilities
                )
            return EventEmissionResult(event=inserted, was_created=True)

    async def _write_responsibilities(
        self,
        tenant_id: TenantId,
        event_id: UUID,
        assignments: list[ResponsibilityAssignmentIn],
    ) -> None:
        """Persist ``event_responsibility`` rows for a freshly created event.

        Dedupes ``(actor_id, role)`` pairs in-call so two ingest sources
        passing the same operational owner twice in one payload do not
        trigger the composite PK. The DB-level PK still backstops any
        cross-UoW races (rare; tests cover the path).
        """
        seen: set[tuple[UUID, str]] = set()
        deduped: list[tuple[UUID, str]] = []
        for entry in assignments:
            key = (entry.actor_id, entry.role)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(key)
        if not deduped:
            return
        await self._repo.add_responsibilities(tenant_id, event_id, deduped)

    async def set_responsibilities_idempotent(
        self,
        tenant_id: TenantId,
        event_id: UUID,
        assignments: list[ResponsibilityAssignmentIn],
    ) -> int:
        """Backfill helper — write only assignments not yet on the event.

        Returns the count of rows actually inserted. Idempotent across
        runs: existing ``(event_id, actor_id, role)`` rows are skipped,
        new ones are added. The backfill script uses this so partial /
        re-run executions converge without raising PK violations.

        Validates each role against :data:`RESPONSIBILITY_ROLES` so a
        typo in the caller surface fails fast rather than fighting the
        DB CHECK constraint at flush time.
        """
        if not assignments:
            return 0
        inserted = 0
        for entry in assignments:
            if entry.role not in RESPONSIBILITY_ROLES:
                raise ValidationError(
                    "unknown responsibility role",
                    details={
                        "role": entry.role,
                        "allowed": list(RESPONSIBILITY_ROLES),
                    },
                )
            existing = await self._repo.find_existing_responsibility(
                tenant_id, event_id, entry.actor_id, entry.role
            )
            if existing is not None:
                continue
            await self._repo.add_responsibilities(
                tenant_id, event_id, [(entry.actor_id, entry.role)]
            )
            inserted += 1
        return inserted

    async def list_responsibilities_for_event(
        self, tenant_id: TenantId, event_id: UUID
    ) -> list[ResponsibilityAssignmentIn]:
        """Return ``(actor_id, role)`` rows for an event as DTOs.

        Used by tests and by the backfill script's diff check. The DTO
        shape mirrors the input contract so the same object can flow in
        either direction.
        """
        rows = await self._repo.list_responsibilities_for_event(tenant_id, event_id)
        return [
            ResponsibilityAssignmentIn(actor_id=row.actor_id, role=row.role)  # type: ignore[arg-type]
            for row in rows
        ]

    async def list_events_missing_responsibility(
        self,
        tenant_id: TenantId,
        *,
        limit: int = 500,
        after_occurred_at: datetime | None = None,
        kinds: tuple[str, ...] | None = None,
        expected_roles: tuple[str, ...] | None = None,
    ) -> list[Event]:
        """Backfill helper — paged scan of events with missing responsibility rows.

        When ``expected_roles`` is ``None`` the scan returns events with zero
        responsibility rows (legacy contract). When provided, it returns events
        missing AT LEAST ONE of the expected roles — required for re-runs that
        repair partially-seeded events (e.g. ``operational`` written by a
        previous pass but ``clinical`` still missing).

        Validates roles against :data:`RESPONSIBILITY_ROLES` so a typo in the
        caller surface fails fast rather than scanning the whole table for a
        role the DB CHECK constraint would reject.
        """
        if limit <= 0 or limit > 5000:
            raise ValidationError(
                "limit must be between 1 and 5000",
                details={"limit": limit},
            )
        if expected_roles is not None:
            unknown = [r for r in expected_roles if r not in RESPONSIBILITY_ROLES]
            if unknown:
                raise ValidationError(
                    "unknown responsibility role",
                    details={
                        "roles": unknown,
                        "allowed": list(RESPONSIBILITY_ROLES),
                    },
                )
        return await self._repo.list_events_missing_responsibility(
            tenant_id,
            limit=limit,
            after_occurred_at=after_occurred_at,
            kinds=kinds,
            expected_roles=expected_roles,
        )

    async def _find_existing_after_conflict(
        self, tenant_id: TenantId, payload: EventIn
    ) -> Event | None:
        """Resolve which row collided on a partial-UNIQUE insert.

        Tries the cross-pull key first because re-pulls are the common
        case (and they intentionally carry a fresh ``source_event_id``
        every pull, which would defeat the legacy lookup). Falls back
        to the legacy ``(source_provider, source_event_id)`` lookup so
        the rarer single-pipeline-run replay path still resolves.
        """
        if (
            payload.source_external_id is not None
            and payload.source_kind is not None
        ):
            cross_pull = await self._repo.find_provider_event_by_external_id(
                tenant_id,
                source_provider=payload.source_provider,
                source_kind=payload.source_kind,
                source_external_id=payload.source_external_id,
                kind=payload.kind,
            )
            if cross_pull is not None:
                return cross_pull
        if payload.source_event_id is not None:
            return await self._repo.find_event_by_source(
                tenant_id, payload.source_provider, payload.source_event_id
            )
        return None

    async def find_provider_event_by_external_id(
        self,
        tenant_id: TenantId,
        *,
        source_provider: str,
        source_kind: str,
        source_external_id: str,
        kind: str,
    ) -> Event | None:
        """Return an existing provider event by stable source object id."""
        return await self._repo.find_provider_event_by_external_id(
            tenant_id,
            source_provider=source_provider,
            source_kind=source_kind,
            source_external_id=source_external_id,
            kind=kind,
        )

    async def list_provider_events_by_external_id(
        self,
        tenant_id: TenantId,
        *,
        source_provider: str,
        source_kind: str,
        source_external_id: str,
        kind: str,
    ) -> list[Event]:
        """Return provider events by stable source object id and kind."""
        return await self._repo.list_provider_events_by_external_id(
            tenant_id,
            source_provider=source_provider,
            source_kind=source_kind,
            source_external_id=source_external_id,
            kind=kind,
        )

    async def list_for_person(
        self,
        tenant_id: TenantId,
        person_uid: UUID,
        *,
        limit: int = 50,
        before: datetime | None = None,
    ) -> list[Event]:
        """Return events for a person, newest-first; cursor on ``occurred_at``."""
        if limit <= 0 or limit > 500:
            _raise_invalid_limit(limit)
        return await self._repo.list_for_person(tenant_id, person_uid, limit=limit, before=before)

    async def count_for_person(self, tenant_id: TenantId, person_uid: UUID) -> int:
        """Return total events for a person."""
        return await self._repo.count_for_person(tenant_id, person_uid)

    async def count_events_by_kind(
        self,
        tenant_id: TenantId,
        kinds: list[str],
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
    ) -> dict[str, int]:
        """Return ``{kind: count}`` for ``kinds`` over an optional window.

        Each entry of ``kinds`` is validated against :data:`EVENT_KINDS` so a
        typo fails fast rather than silently returning a zero count forever.
        Kinds with no rows are absent from the result. Used by the Calls
        dashboard for the booking-rate denominator/numerator
        (``consultation_scheduled`` vs ``call_logged``) over the window.
        """
        for kind in kinds:
            if kind not in EVENT_KINDS:
                raise ValidationError(
                    "unknown event kind",
                    details={"kind": kind, "allowed": list(EVENT_KINDS)},
                )
        return await self._repo.count_events_by_kind(
            tenant_id,
            kinds,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
        )

    async def get_call_volume(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
    ) -> CallVolumeOut:
        """Return the Calls-dashboard call-volume aggregate (ENG-474).

        Composes the per-kind counts (``call_logged`` /
        ``call_reference_found``) with the ``call_logged`` direction +
        duration aggregate, both scoped to the optional ``[from, to)`` window.
        ``avg_duration_seconds`` is derived here so a window with no
        duration-bearing calls yields ``None`` (UI ``"—"``) instead of a
        misleading ``0``. This is the only call read the dashboard needs —
        everything richer is gated on the unbuilt Phase-3 comms ingest.
        """
        counts = await self._repo.count_events_by_kind(
            tenant_id,
            ["call_logged", "call_reference_found"],
            occurred_from=occurred_from,
            occurred_to=occurred_to,
        )
        volume = await self._repo.call_volume_aggregate(
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
        )
        with_duration = int(volume["with_duration"])
        total_seconds = int(volume["total_duration_seconds"])
        avg_duration = total_seconds / with_duration if with_duration > 0 else None
        return CallVolumeOut(
            call_logged=counts.get("call_logged", 0),
            call_reference_found=counts.get("call_reference_found", 0),
            inbound=int(volume["inbound"]),
            outbound=int(volume["outbound"]),
            unknown_direction=int(volume["unknown_direction"]),
            calls_with_duration=with_duration,
            total_duration_seconds=total_seconds,
            avg_duration_seconds=avg_duration,
        )

    async def max_event_occurred_at(
        self, tenant_id: TenantId, *, kind: str
    ) -> datetime | None:
        """Return the latest ``Event.occurred_at`` for ``kind`` in a tenant.

        Powers the payment-freshness facet of ``GET /health/ingest``
        (ENG-327). ``None`` means the tenant has zero events of that kind
        — callers report that as ``status="unknown"``.

        ``kind`` is validated against :data:`EVENT_KINDS` so a typo in the
        caller surface fails fast rather than silently returning ``None``
        forever.
        """
        if kind not in EVENT_KINDS:
            raise ValidationError(
                "unknown event kind",
                details={"kind": kind, "allowed": list(EVENT_KINDS)},
            )
        return await self._repo.max_event_occurred_at(tenant_id, kind)

    async def list_recent_operational_events(
        self,
        tenant_id: TenantId,
        *,
        limit: int = 25,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        query: str | None = None,
    ) -> list[OperationalTimelineEntry]:
        """Return dashboard-safe recent events across the tenant."""
        if limit <= 0 or limit > 100:
            _raise_invalid_limit(limit)
        clean_query = query.strip() if query is not None else None
        if clean_query == "":
            clean_query = None

        events = await self._repo.list_recent_for_tenant(
            tenant_id,
            limit=limit,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            query=clean_query,
        )
        return [
            OperationalTimelineEntry(
                kind=event.kind,
                occurred_at=event.occurred_at,
                source_provider=event.source_provider,
                source_kind=event.source_kind,
                source_external_id=event.source_external_id,
                source_event_id=event.source_event_id,
                data_class=event.data_class,
                review_status=event.review_status,
                summary=event.summary,
                projection=await self._projection_snapshot_for_event(tenant_id, event),
            )
            for event in events
        ]

    async def list_payment_events_for_dashboard(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
        query: str | None = None,
        include_applied: bool = False,
        person_uids: list[UUID] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Event]:
        """Return raw payment :class:`Event` rows for the PM Payments page.

        Returns the ORM rows directly so the route layer can compose them
        with identity / ops / location lookups (mirrors how ``pm_leads``
        composes ``ops.list_leads_for_dashboard`` with identity + location
        in the route). The returned ``Event.payload`` dict is the structured
        no-PII workflow-ready dict written by the CareStack accounting-
        transaction ingest (``amount``, ``transaction_type``,
        ``location_id``) — NOT the verbatim provider payload, which lives
        only in ``ingest.raw_event`` and is read separately by the row
        drilldown.

        ``include_applied=False`` (default) excludes the ``payment_applied``
        allocation leg so the page shows real cash movements (ENG-301);
        ``offset`` slices the windowed result for pagination.
        """
        if limit <= 0 or limit > 500:
            _raise_invalid_limit(limit)
        if offset < 0:
            _raise_invalid_offset(offset)
        clean_query = query.strip() if query is not None else None
        if clean_query == "":
            clean_query = None

        return await self._repo.list_payment_events_for_dashboard(
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
            query=clean_query,
            include_applied=include_applied,
            person_uids=person_uids,
            limit=limit,
            offset=offset,
        )

    async def summarize_payment_events_for_dashboard(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
        query: str | None = None,
        person_uids: list[UUID] | None = None,
    ) -> PaymentSummaryOut:
        """Window-wide totals for the PM Payments summary bar (ENG-302).

        Same window/provider/location/query as
        :meth:`list_payment_events_for_dashboard`; returns net Collected plus
        the payment and distinct-patient counts over the whole window (not the
        paginated page).
        """
        clean_query = query.strip() if query is not None else None
        if clean_query == "":
            clean_query = None

        raw = await self._repo.summarize_payment_events_for_dashboard(
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
            query=clean_query,
            person_uids=person_uids,
        )
        return PaymentSummaryOut(
            collected_total=_float_from_db(raw["collected_total"]),
            payment_count=_int_from_db(raw["payment_count"]),
            patient_count=_int_from_db(raw["patient_count"]),
        )

    async def count_payment_events_for_dashboard(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
        query: str | None = None,
        include_applied: bool = False,
        person_uids: list[UUID] | None = None,
    ) -> int:
        """Total payment events matching the PM Payments filters (window-wide).

        Drives honest pagination on the PM Payments page — the same filters
        as :meth:`list_payment_events_for_dashboard`, without limit/offset.
        """
        clean_query = query.strip() if query is not None else None
        if clean_query == "":
            clean_query = None

        return await self._repo.count_payment_events_for_dashboard(
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
            query=clean_query,
            include_applied=include_applied,
            person_uids=person_uids,
        )

    async def list_payment_event_groups_for_dashboard(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
        query: str | None = None,
        include_applied: bool = False,
        person_uids: list[UUID] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Same-day payment groups for the PM Payments page (ENG-410).

        Groups by ``(person_uid, kind, clinic-local day)`` with the
        underlying legs embedded; same filter surface as
        :meth:`list_payment_events_for_dashboard`.
        """
        if limit <= 0 or limit > 500:
            _raise_invalid_limit(limit)
        if offset < 0:
            _raise_invalid_offset(offset)
        clean_query = query.strip() if query is not None else None
        if clean_query == "":
            clean_query = None
        return await self._repo.list_payment_event_groups_for_dashboard(
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
            query=clean_query,
            include_applied=include_applied,
            person_uids=person_uids,
            limit=limit,
            offset=offset,
        )

    async def count_payment_event_groups_for_dashboard(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
        query: str | None = None,
        include_applied: bool = False,
        person_uids: list[UUID] | None = None,
    ) -> int:
        """Window-wide same-day group count for grouped pagination (ENG-410)."""
        clean_query = query.strip() if query is not None else None
        if clean_query == "":
            clean_query = None
        return await self._repo.count_payment_event_groups_for_dashboard(
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
            query=clean_query,
            include_applied=include_applied,
            person_uids=person_uids,
        )

    # --- Funnel analytics (ENG-419) ----------------------------------

    async def funnel_aggregate(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
        role: str | None = None,
    ) -> list[dict[str, object]]:
        """Per ``(stage × actor × role)`` aggregate; ENG-419 endpoint engine.

        Returns the raw aggregation rows; the route layer composes them
        into the ``FunnelStageAggregateOut`` envelope after attaching
        actor display names from ``ActorService`` (per the matrix).
        """
        if role is not None and role not in RESPONSIBILITY_ROLES:
            raise ValidationError(
                "unknown responsibility role",
                details={"role": role, "allowed": list(RESPONSIBILITY_ROLES)},
            )
        return await self._repo.funnel_aggregate_by_actor(
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
            role=role,
        )

    async def funnel_totals(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
    ) -> dict[str, dict[str, int]]:
        """Per-stage totals; pairs with :meth:`funnel_aggregate`."""
        return await self._repo.funnel_aggregate_totals(
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
        )

    async def funnel_dropoff_by_person(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
    ) -> list[dict[str, object]]:
        """Per-person drop-off stage + latest operational owner.

        The route layer joins this against ``OpsService`` to attach the
        ``$ basis`` per stage (Opportunity.amount for non-won, net
        realized payments for won) and ``ActorService`` for display
        names — ``interaction`` cannot reach either domain directly.
        """
        return await self._repo.funnel_dropoff_by_person(
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
        )

    async def funnel_revenue_by_actor(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
        role: str | None = None,
    ) -> list[dict[str, object]]:
        """Net realized $ attributed to each actor (ENG-419 revenue slice)."""
        if role is not None and role not in RESPONSIBILITY_ROLES:
            raise ValidationError(
                "unknown responsibility role",
                details={"role": role, "allowed": list(RESPONSIBILITY_ROLES)},
            )
        return await self._repo.funnel_revenue_by_actor(
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
            role=role,
        )

    async def funnel_distinct_actors(
        self,
        tenant_id: TenantId,
        *,
        role: str | None = None,
    ) -> list[dict[str, object]]:
        """Distinct ``(actor_id, role)`` rows for the dashboard picker."""
        if role is not None and role not in RESPONSIBILITY_ROLES:
            raise ValidationError(
                "unknown responsibility role",
                details={"role": role, "allowed": list(RESPONSIBILITY_ROLES)},
            )
        return await self._repo.funnel_distinct_actors(tenant_id, role=role)

    async def funnel_revenue_by_person(
        self,
        tenant_id: TenantId,
        *,
        person_uids: list[UUID],
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
    ) -> dict[UUID, float]:
        """Per-person net realized $ for a specific person set (ENG-418 fix).

        Used by :meth:`compute_funnel_dropoff` for the ``opportunity_won``
        bucket so the $ matches the EXACT persons who dropped at won.
        Persons with no payment events in the window are absent from
        the dict.
        """
        return await self._repo.funnel_revenue_by_person(
            tenant_id,
            person_uids=person_uids,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
        )

    async def compute_funnel_dropoff(
        self,
        tenant_id: TenantId,
        *,
        opp_amount_by_person: Mapping[UUID, float],
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
    ) -> list[FunnelDropoffStageComputed]:
        """Bucketed drop-off attribution per stage × operational actor.

        ENG-418 fix (HIGH-#4): the dropoff grouping, won-vs-non-won $
        basis selection, actor bucketing, and stage totalling all live
        here so the API route stays a thin DTO-stitcher.

        Per decision-log D-W3-3:
          - non-won stages use ``Opportunity.amount`` per person
            (caller passes the lookup as ``opp_amount_by_person`` — the
            ops query lives in the route because ``interaction`` cannot
            import ``ops``).
          - ``opportunity_won`` uses net realized payments
            (``recorded − refunded − reversed``) SCOPED TO THE EXACT
            persons who dropped at that stage — NOT the actor-wide
            aggregate (which would double-count persons across actors
            and credit revenue to non-dropoff persons).

        Returns one envelope per stage in :data:`FUNNEL_STAGE_ORDER`,
        even empty ones, so the route renders a stable axis. The
        ``actor_id`` inside each bucket is ``None`` for drop-off events
        without an operational responsibility row (legacy pre-W2 ingest).
        """
        rows = await self._repo.funnel_dropoff_by_person(
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
        )

        # Person-scoped revenue for the won bucket: only the persons
        # whose drop-off stage is opportunity_won contribute, and only
        # their own payment events count toward their bucket.
        won_persons = [
            UUID(str(row["person_uid"]))
            for row in rows
            if row["stage"] == "opportunity_won"
        ]
        person_revenue = await self.funnel_revenue_by_person(
            tenant_id,
            person_uids=won_persons,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            source_provider=source_provider,
            location_id=location_id,
        )

        # Group drop-off persons by (stage, operational_actor_id).
        by_stage: dict[FunnelStage, dict[UUID | None, list[UUID]]] = {
            stage: {} for stage in FUNNEL_STAGE_ORDER
        }
        for row in rows:
            stage_value = row["stage"]
            if stage_value not in by_stage:
                continue
            stage_typed = cast(FunnelStage, stage_value)
            actor_id_raw = row.get("operational_actor_id")
            actor_id = (
                UUID(str(actor_id_raw)) if actor_id_raw is not None else None
            )
            by_stage[stage_typed].setdefault(actor_id, []).append(
                UUID(str(row["person_uid"]))
            )

        out: list[FunnelDropoffStageComputed] = []
        for stage in FUNNEL_STAGE_ORDER:
            buckets = by_stage[stage]
            actor_aggs: list[FunnelDropoffActorAggregate] = []
            stage_persons = 0
            stage_dollars = 0.0
            for actor_id, persons in buckets.items():
                person_count = len(persons)
                if stage == "opportunity_won":
                    dollar_total = sum(
                        person_revenue.get(p, 0.0) for p in persons
                    )
                else:
                    dollar_total = sum(
                        opp_amount_by_person.get(p, 0.0) for p in persons
                    )
                stage_persons += person_count
                stage_dollars += dollar_total
                actor_aggs.append(
                    FunnelDropoffActorAggregate(
                        actor_id=actor_id,
                        person_count=person_count,
                        dollar_total=dollar_total,
                    )
                )
            # Worst-offender first so the FE table reads top-down.
            actor_aggs.sort(key=lambda b: b.person_count, reverse=True)
            out.append(
                FunnelDropoffStageComputed(
                    stage=stage,
                    person_count=stage_persons,
                    dollar_total=stage_dollars,
                    by_actor=actor_aggs,
                )
            )
        return out

    async def get_treatment_payment_aggregate(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
    ) -> TreatmentPaymentAggregateOut:
        """Return the minimum dashboard-safe CareStack treatment/payment aggregate.

        This aggregates only safe workflow-ready event fields and the
        allowlisted invoice amount copied into ``Event.payload`` by the ingest
        service. It never reads or returns raw CareStack payloads, clinical
        procedure text, tooth/surface data, notes, or patient identifiers.

        When ``location_id`` is set, the aggregate is scoped to events whose
        payload carries the matching ``location_id`` UUID (ENG-267) — events
        without a payload location, or with a different location, are
        excluded.
        """
        if source_provider not in (None, "carestack"):
            return TreatmentPaymentAggregateOut()

        raw = await self._repo.get_treatment_payment_aggregate(
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            location_id=location_id,
        )
        return TreatmentPaymentAggregateOut(
            treatment_presented_count=_int_from_db(
                raw["treatment_presented_count"]
            ),
            treatment_completed_count=_int_from_db(
                raw["treatment_completed_count"]
            ),
            invoice_count=_int_from_db(raw["invoice_count"]),
            payment_total_amount=_float_from_db(raw["payment_total_amount"]),
            collected_total=_float_from_db(raw["collected_total"]),
            payment_event_count=_int_from_db(raw["payment_event_count"]),
            first_payment_at=_datetime_from_db(raw["first_payment_at"]),
            last_payment_at=_datetime_from_db(raw["last_payment_at"]),
        )

    async def get_treatment_payment_quality_evidence(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
    ) -> dict[str, object]:
        """Return aggregate quality evidence for treatment revenue read models."""
        if source_provider not in (None, "carestack"):
            return {
                "refs": ["billing.payment_recorded"],
                "metrics": [],
                "caveats": [],
                "blockers": [],
            }

        raw = await self._repo.get_treatment_payment_quality_metrics(
            tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            location_id=location_id,
        )
        total = int(raw.get("payment_event_count", 0))
        linked = int(raw.get("identity_linked_payment_count", 0))
        attributed = int(raw.get("source_attributed_payment_count", 0))
        unmatched = int(raw.get("unmatched_payment_count", 0))
        applied_excluded = int(raw.get("payment_applied_excluded_count", 0))
        identity_coverage = _coverage_ratio(linked, total)
        source_coverage = _coverage_ratio(attributed, total)
        caveats: list[str] = []
        blockers: list[str] = []
        if total > 0 and linked < total:
            blockers.append(
                "Billing read-model identity linkage coverage is incomplete; manager answer generation is blocked."
            )
        if unmatched > 0:
            caveats.append(
                f"{unmatched} payment aggregate events lack provider transaction attribution."
            )
        if applied_excluded > 0:
            caveats.append(
                f"{applied_excluded} CareStack payment_applied allocation events were excluded from collected revenue totals."
            )
        return {
            "refs": [
                "billing.payment_recorded",
                "billing.payment_kind",
                "payment_applied_exclusion.aggregate",
            ],
            "metrics": [
                _quality_ratio_metric(
                    "identity_linkage_coverage",
                    "Identity linkage coverage",
                    identity_coverage,
                    numerator=linked,
                    denominator=total,
                    evidence_ref="billing.payment_recorded",
                    status="blocked" if total > 0 and linked < total else "ok",
                ),
                _quality_ratio_metric(
                    "source_attribution_coverage",
                    "Source attribution coverage",
                    source_coverage,
                    numerator=attributed,
                    denominator=total,
                    evidence_ref="billing.payment_kind",
                    status="caveat" if unmatched > 0 else "ok",
                ),
                _quality_count_metric(
                    "unmatched_payment_count",
                    "Unmatched payment count",
                    unmatched,
                    evidence_ref="billing.payment_kind",
                    status="caveat" if unmatched > 0 else "ok",
                ),
                _quality_count_metric(
                    "payment_applied_excluded_count",
                    "Payment applied excluded count",
                    applied_excluded,
                    evidence_ref="payment_applied_exclusion.aggregate",
                    status="caveat" if applied_excluded > 0 else "ok",
                ),
            ],
            "caveats": caveats,
            "blockers": blockers,
        }

    async def collected_by_person(self, tenant_id: TenantId) -> dict[UUID, float]:
        """Net collected cash per person (Collected semantics, ENG-391)."""
        return await self._repo.sum_collected_by_person(tenant_id)

    async def collected_by_person_month(
        self,
        tenant_id: TenantId,
        *,
        occurred_from: datetime,
        occurred_to: datetime,
    ) -> list[tuple[UUID, str, float]]:
        """Net collected per ``(person_uid, YYYY-MM)`` in window (ENG-481).

        Same Collected semantics as :meth:`collected_by_person`, but bucketed
        by payment month and restricted to the occurred-at window so the Full
        Funnel report attributes revenue and paying persons to the month the
        cash actually arrived (the stage's own timestamp).
        """
        return await self._repo.sum_collected_by_person_month(
            tenant_id, occurred_from=occurred_from, occurred_to=occurred_to
        )

    async def earliest_event_at_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, datetime]:
        """``person_uid → MIN(event.occurred_at)`` for every person (ENG-481).

        One GROUP BY aggregate, used by the Full Funnel composition layer to
        date CareStack-direct persons by their earliest real activity (consult
        else timeline event) instead of the meaningless bulk-import
        ``source_link.first_seen_at``. Persons with no event are absent.
        """
        return await self._repo.earliest_event_at_by_person(tenant_id)

    async def analytics_event_milestones_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, tuple[datetime | None, datetime | None]]:
        """``person_uid → (treatment_presented_date, first_payment_date)``.

        For the analytics fact builder (ENG-506): earliest ``treatment_proposed``
        and earliest ``payment_recorded`` / ``invoice_created`` event per person.
        Persons with neither milestone are absent.
        """
        return await self._repo.analytics_event_milestones_by_person(tenant_id)

    async def analytics_surgery_stage_milestones_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, tuple[datetime | None, datetime | None, datetime | None]]:
        """``person_uid → (treatment_accepted, surgery_scheduled, surgery_completed)``.

        For the analytics fact builder (ENG-511, B1.3): earliest
        ``treatment_accepted`` (CareStack TreatmentPlan StatusId=3), earliest
        ``surgery_scheduled`` and earliest ``surgery_completed`` (implant-surgery
        treatment procedure statusId 2 / 8) event per person. Persons with none
        of the three milestones are absent.
        """
        return await self._repo.analytics_surgery_stage_milestones_by_person(
            tenant_id
        )

    async def analytics_clinical_actor_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, UUID]:
        """``person_uid → doctor actor_id`` for the analytics fact builder.

        The clinical (doctor) actor on the person's earliest clinical event —
        the CareStack appointment-provider actor resolved during ingest
        (ENG-417). The builder maps it to ``doctor_id`` with provenance
        ``method='auto'``. Persons with no clinical responsibility are absent
        (NULL doctor, method=unresolved). See ENG-510.
        """
        return await self._repo.analytics_clinical_actor_by_person(tenant_id)

    async def get_payment_event_field_profile(
        self,
        tenant_id: TenantId,
        *,
        field: str,
        limit: int = 50,
    ) -> InteractionFieldProfileOut:
        """Return an aggregate-only profile for an allowlisted billing event field."""
        if field != "payment_kind":
            raise ValidationError(
                "unsupported payment event field profile",
                details={"field": field},
            )
        raw = await self._repo.profile_payment_event_field(tenant_id, field=field, limit=limit)
        return _field_profile_from_raw(raw)

    async def get_payment_event_masked_samples(
        self,
        tenant_id: TenantId,
        *,
        limit: int = 25,
    ) -> list[dict[str, object]]:
        """Return bounded, masked billing event samples for Data Intelligence tooling."""
        if limit < 1 or limit > 100:
            raise ValidationError("limit must be between 1 and 100", details={"limit": limit})
        rows = await self._repo.list_payment_event_samples(tenant_id, limit=limit)
        return [_payment_event_masked_sample(row) for row in rows]

    async def list_operational_timeline(
        self,
        tenant_id: TenantId,
        person_uid: UUID,
        *,
        limit: int = 200,
    ) -> list[OperationalTimelineEntry]:
        """Return an allowlisted operational timeline for a person.

        The returned DTOs never include ``Event.payload`` or raw provider
        payload fields. Projection enrichment is limited to current
        ``status``, ``scheduled_at``, and ``due_at``.

        ENG-418: each entry carries the ``event_responsibility`` rows
        for the event so the chain UI can label each node with the
        actor responsible at that stage. The names are resolved at the
        API route boundary via ``ActorService`` — this method emits
        only the ``(actor_id, role)`` tuple per the package import
        matrix.
        """
        if limit <= 0 or limit > 500:
            _raise_invalid_limit(limit)

        events = await self._repo.list_for_person(tenant_id, person_uid, limit=limit)
        responsibilities = await self._repo.list_responsibilities_for_events(
            tenant_id, [event.id for event in events]
        )
        responsibilities_by_event: dict[UUID, list[OperationalTimelineResponsibleRef]] = {}
        for row in responsibilities:
            responsibilities_by_event.setdefault(row.event_id, []).append(
                OperationalTimelineResponsibleRef(
                    actor_id=row.actor_id,
                    role=cast(ResponsibilityRole, row.role),
                )
            )

        return [
            OperationalTimelineEntry(
                kind=event.kind,
                occurred_at=event.occurred_at,
                source_provider=event.source_provider,
                source_kind=event.source_kind,
                source_external_id=event.source_external_id,
                source_event_id=event.source_event_id,
                data_class=event.data_class,
                review_status=event.review_status,
                summary=event.summary,
                projection=await self._projection_snapshot_for_event(tenant_id, event),
                responsibles=responsibilities_by_event.get(event.id, []),
            )
            for event in events
        ]

    async def _projection_snapshot_for_event(
        self, tenant_id: TenantId, event: Event
    ) -> OperationalTimelineProjectionSnapshot | None:
        if (
            self._operational_projection_reader is None
            or event.projection_ref_type is None
            or event.projection_ref_id is None
        ):
            return None

        raw_snapshot = (
            await self._operational_projection_reader.get_operational_timeline_projection(
                tenant_id,
                event.projection_ref_type,
                event.projection_ref_id,
            )
        )
        if raw_snapshot is None:
            return None

        allowed = {
            key: value for key, value in raw_snapshot.items() if key in _PROJECTION_ALLOWLIST
        }
        return OperationalTimelineProjectionSnapshot(
            type=event.projection_ref_type,
            id=event.projection_ref_id,
            **allowed,
        )


def _raise_invalid_limit(limit: int) -> None:
    raise ValidationError(
        "limit must be between 1 and 500",
        details={"limit": limit},
    )


def _raise_invalid_offset(offset: int) -> None:
    raise ValidationError(
        "offset must be non-negative",
        details={"offset": offset},
    )


def _int_from_db(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    return int(str(value))


def _field_profile_from_raw(raw: dict[str, object]) -> InteractionFieldProfileOut:
    top_values = raw.get("top_values")
    if not isinstance(top_values, list):
        top_values = []
    return InteractionFieldProfileOut(
        row_count=_raw_int(raw.get("row_count")),
        null_count=_raw_int(raw.get("null_count")),
        top_values=[
            FieldValueBucketOut(
                value=str(item.get("value")),
                count=_raw_int(item.get("count")),
            )
            for item in top_values
            if isinstance(item, dict)
        ],
    )


def _coverage_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return round(numerator / denominator, 4)


def _quality_ratio_metric(
    metric_id: str,
    label: str,
    value: float,
    *,
    numerator: int,
    denominator: int,
    evidence_ref: str,
    status: str,
) -> dict[str, object]:
    return {
        "id": metric_id,
        "label": label,
        "value": value,
        "unit": "ratio",
        "numerator": numerator,
        "denominator": denominator,
        "status": status,
        "evidence_ref": evidence_ref,
    }


def _quality_count_metric(
    metric_id: str,
    label: str,
    value: int,
    *,
    evidence_ref: str,
    status: str,
) -> dict[str, object]:
    return {
        "id": metric_id,
        "label": label,
        "value": value,
        "unit": "count",
        "status": status,
        "evidence_ref": evidence_ref,
    }


def _raw_int(value: object) -> int:
    return int(str(value or 0))


def _payment_event_masked_sample(row: Event) -> dict[str, object]:
    amount = _float_from_db(row.payload.get("amount"))
    return {
        "person_uid_masked": _mask_identifier(row.person_uid),
        "payment_kind": row.kind,
        "payment_date": row.occurred_at.isoformat(),
        "amount_bucket": _amount_bucket(amount),
        "source_external_id_masked": _mask_optional_identifier(row.source_external_id),
        "location_id": row.payload.get("location_id"),
    }


def _amount_bucket(amount: float) -> str:
    if amount < 0:
        return "negative"
    if amount == 0:
        return "0"
    if amount < 100:
        return "1-99"
    if amount < 500:
        return "100-499"
    if amount < 1000:
        return "500-999"
    if amount < 5000:
        return "1000-4999"
    return "5000+"


def _mask_optional_identifier(value: object) -> str | None:
    if value is None:
        return None
    return _mask_identifier(value)


def _mask_identifier(value: object) -> str:
    text = str(value)
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}...{text[-4:]}"


def _float_from_db(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    return float(str(value))


def _datetime_from_db(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None
