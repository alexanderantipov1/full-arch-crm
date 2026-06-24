"""Pydantic DTOs for the interaction domain — Phase 1 subset."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Mirror of EVENT_KINDS / SOURCE_PROVIDERS in models.py — keeps API typing
# strict and forces a single point of update when the lists grow.
EventKind = Literal[
    "lead_created",
    "lead_updated",
    "consultation_scheduled",
    "consultation_created",
    "consultation_rescheduled",
    "consultation_cancelled",
    "consultation_completed",
    "consultation_no_show",
    "task_created",
    "task_completed",
    "call_logged",
    "call_reference_found",
    "treatment_proposed",
    "treatment_completed",
    "invoice_created",
    "case_opened",
    "case_closed",
    "opportunity_created",
    "opportunity_won",
    "opportunity_lost",
    "opportunity_stage_changed",
    "contact_created",
    "payment_recorded",
    "payment_refunded",
    "payment_reversed",
    "payment_applied",
    "treatment_accepted",
    "surgery_scheduled",
    "surgery_completed",
]
SourceProvider = Literal["salesforce", "carestack"]
DataClass = Literal[
    "public",
    "operational",
    "clinical_summary",
    "phi_protected",
    "billing",
    "call_recording_ref",
]
SourceKind = Literal[
    "salesforce_lead",
    "salesforce_event",
    "salesforce_task",
    "salesforce_opportunity",
    "salesforce_case",
    "salesforce_contact",
    "salesforce_account",
    "salesforce_opportunity_history",
    "carestack_appointment",
    "carestack_patient",
    "carestack_treatment_procedure",
    "carestack_invoice",
    "carestack_accounting_transaction",
    "carestack_treatment_plan",
]
ProjectionRefType = Literal[
    "ops_lead",
    "ops_consultation",
    "ops_followup_task",
]
ReviewStatus = Literal["auto", "pending_review", "reviewed", "rejected"]

# Mirror of ``packages.interaction.models.RESPONSIBILITY_ROLES`` — kept here
# so the route / ingest layer types responsibility entries strictly.
ResponsibilityRole = Literal["operational", "clinical"]

_SOURCE_KINDS_BY_PROVIDER: dict[str, set[str]] = {
    "salesforce": {
        "salesforce_lead",
        "salesforce_event",
        "salesforce_task",
        "salesforce_opportunity",
        "salesforce_case",
        "salesforce_contact",
        "salesforce_account",
        "salesforce_opportunity_history",
    },
    "carestack": {
        "carestack_appointment",
        "carestack_patient",
        "carestack_treatment_procedure",
        "carestack_invoice",
        "carestack_accounting_transaction",
        "carestack_treatment_plan",
    },
}


class ResponsibilityAssignmentIn(BaseModel):
    """One ``(actor_id, role)`` assignment for an event responsibility row.

    Ingest callers pass a list of these inside :class:`EventIn` so the
    event and its responsibility rows are written in the same UoW.
    """

    actor_id: uuid.UUID
    role: ResponsibilityRole


class EventIn(BaseModel):
    """Input shape for ``InteractionService.create_event``."""

    person_uid: uuid.UUID
    kind: EventKind
    source_provider: SourceProvider
    source_event_id: uuid.UUID | None = None
    data_class: DataClass
    source_kind: SourceKind | None = None
    source_external_id: str | None = Field(default=None, min_length=1, max_length=240)
    projection_ref_type: ProjectionRefType | None = None
    projection_ref_id: uuid.UUID | None = None
    review_status: ReviewStatus = "auto"
    occurred_at: datetime
    summary: str = Field(min_length=1, max_length=500)
    payload: dict[str, object] = Field(default_factory=dict)
    created_by_actor_id: uuid.UUID | None = None
    # Funnel responsibility assignments (ENG-416). Empty when the ingest
    # caller cannot resolve any responsible actor (e.g. a manual event
    # with no owner context). One row per (actor_id, role); duplicates
    # are deduplicated by ``InteractionService.create_event`` before the
    # insert, so the (event_id, actor_id, role) PK is never racing
    # itself.
    responsibilities: list[ResponsibilityAssignmentIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_workflow_references(self) -> EventIn:
        """Require provider source references and coherent projection refs."""
        if self.source_kind is None or self.source_external_id is None:
            raise ValueError("source_kind and source_external_id are required for provider events")

        allowed_source_kinds = _SOURCE_KINDS_BY_PROVIDER[self.source_provider]
        if self.source_kind not in allowed_source_kinds:
            raise ValueError(
                "source_kind must match source_provider",
            )

        if (self.projection_ref_type is None) != (self.projection_ref_id is None):
            raise ValueError("projection_ref_type and projection_ref_id must be provided together")
        return self


class EventOut(BaseModel):
    """Output shape — what the API/MCP returns to readers."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    person_uid: uuid.UUID
    kind: EventKind
    source_provider: SourceProvider
    source_event_id: uuid.UUID | None
    data_class: DataClass
    source_kind: SourceKind | None
    source_external_id: str | None
    projection_ref_type: ProjectionRefType | None
    projection_ref_id: uuid.UUID | None
    review_status: ReviewStatus
    occurred_at: datetime
    summary: str
    payload: dict[str, object]
    created_at: datetime
    created_by_actor_id: uuid.UUID | None


class OperationalTimelineProjectionSnapshot(BaseModel):
    """Allowlisted current-state snapshot for a referenced ops projection."""

    type: ProjectionRefType
    id: uuid.UUID
    status: str | None = None
    scheduled_at: datetime | None = None
    due_at: datetime | None = None


class OperationalTimelineResponsibleRef(BaseModel):
    """One ``(actor_id, role)`` ref for a timeline entry (ENG-418).

    The DTO carries only the actor id + role. Display-name resolution
    happens at the API route boundary (``apps/api/routers/persons.py``),
    which composes interaction reads with ``ActorService`` lookups. The
    ``interaction`` package is forbidden from importing ``actor`` per
    ``packages/CLAUDE.md`` matrix.
    """

    actor_id: uuid.UUID
    role: ResponsibilityRole


class OperationalTimelineEntry(BaseModel):
    """Safe person operational timeline entry.

    ``summary`` is the no-PII summary created at write time and STAYS
    no-PII. This DTO still excludes ``Event.payload``; it carries
    ``source_event_id`` — the FK to ``ingest.raw_event.id`` — purely as a
    drill-down LINK so the staff UI can lazily fetch the verbatim
    "what happened" detail on demand (the development-phase data
    visibility posture; see root ``CLAUDE.md``). The payload itself is
    never inlined here. ``None`` for derived events with no raw row
    (e.g. ``call_reference_found``).

    ENG-418: the optional ``responsibles`` list carries the
    ``event_responsibility`` rows for this event. Empty when the event
    was emitted before the W2 ingest wire-up landed (legacy rows) OR
    when the resolver could not attribute any actor (e.g. a manual
    event with no owner). The route composes display names from
    ``ActorService`` and stitches them into the API response shape.
    """

    kind: EventKind
    occurred_at: datetime
    source_provider: SourceProvider
    source_kind: SourceKind | None
    source_external_id: str | None
    source_event_id: uuid.UUID | None = None
    data_class: DataClass
    review_status: ReviewStatus
    summary: str
    projection: OperationalTimelineProjectionSnapshot | None = None
    responsibles: list[OperationalTimelineResponsibleRef] = Field(
        default_factory=list
    )


class TreatmentPaymentAggregateOut(BaseModel):
    """Dashboard-safe aggregate slice for CareStack treatment/payment events.

    ``collected_total`` is net cash collected:
    ``sum(payment_recorded.amount) − sum(payment_refunded +
    payment_reversed amounts)`` (ENG-283). The allocation-leg
    ``payment_applied`` kind is excluded from every aggregate field.
    ``payment_total_amount`` retains the historical invoice-amount
    aggregate so existing dashboard callers do not break.
    """

    treatment_presented_count: int = 0
    treatment_completed_count: int = 0
    invoice_count: int = 0
    payment_total_amount: float = 0.0
    collected_total: float = 0.0
    payment_event_count: int = 0
    first_payment_at: datetime | None = None
    last_payment_at: datetime | None = None


class CallVolumeOut(BaseModel):
    """Call-volume aggregate for the Calls dashboard (ENG-474).

    Built only from the two ingested call event kinds — ``call_logged`` and
    ``call_reference_found`` (a discovered recording/reference URL). The
    direction split and ``total_duration_seconds`` come from the PHI-free
    ``call_logged`` payload; ``avg_duration_seconds`` is the mean over calls
    that carry a non-zero duration (``None`` on a window with no such calls,
    so the UI renders ``"—"`` rather than ``0``). Disposition outcome,
    per-agent performance, QA scores, transcripts and sentiment are NOT here
    — those depend on the unbuilt Phase-3 telephony ingest.
    """

    call_logged: int = 0
    call_reference_found: int = 0
    inbound: int = 0
    outbound: int = 0
    unknown_direction: int = 0
    calls_with_duration: int = 0
    total_duration_seconds: int = 0
    avg_duration_seconds: float | None = None


class FieldValueBucketOut(BaseModel):
    """Top-value bucket for an allowlisted interaction field profile."""

    value: str
    count: int


class InteractionFieldProfileOut(BaseModel):
    """Aggregate-only field profile for Data Intelligence tooling."""

    row_count: int
    null_count: int
    top_values: list[FieldValueBucketOut]


# --- Funnel analytics (ENG-419) -----------------------------------------

# Stable funnel stage axis. Ordering matters — the drop-off attribution
# walks this list left-to-right per person to pick the highest stage they
# ever reached AND did not advance past.
FunnelStage = Literal[
    "lead_new",
    "lead_contacted",
    "consult_scheduled",
    "consult_no_show",
    "consult_completed",
    "opportunity_open",
    "opportunity_won",
    "opportunity_lost",
]

# Canonical stage ordering. Routes and aggregations iterate this so the
# funnel axis is rendered in the same order everywhere.
FUNNEL_STAGE_ORDER: tuple[FunnelStage, ...] = (
    "lead_new",
    "lead_contacted",
    "consult_scheduled",
    "consult_no_show",
    "consult_completed",
    "opportunity_open",
    "opportunity_won",
    "opportunity_lost",
)


class FunnelStageActorBucketOut(BaseModel):
    """One ``(stage × actor × role)`` aggregation bucket (ENG-419)."""

    stage: FunnelStage
    role: ResponsibilityRole
    actor_id: uuid.UUID
    event_count: int
    person_count: int


class FunnelStageAggregateOut(BaseModel):
    """Per-stage aggregate envelope (ENG-419).

    Carries the per-actor breakdown plus the totals so the dashboard
    can render a stage funnel chart without extra round-trips.
    """

    stage: FunnelStage
    person_count: int
    event_count: int
    by_actor: list[FunnelStageActorBucketOut]


class FunnelDropoffStageOut(BaseModel):
    """Drop-off attribution headline per funnel stage (ENG-419).

    A person is "dropped off at stage S" when S is the highest funnel
    stage they ever reached AND they have no later-stage event.

    ``operational_actor_id`` is the operational owner attributed to the
    drop-off person; when a person had multiple operational owners
    across the stage, the latest one wins. ``dollar_total`` follows the
    decision-log rule (D-W3-3).
    """

    stage: FunnelStage
    person_count: int
    dollar_total: float
    by_operational_actor: list[FunnelDropoffActorBucketOut]


class FunnelDropoffActorBucketOut(BaseModel):
    actor_id: uuid.UUID
    person_count: int
    dollar_total: float


# --- Service-level (route-internal) drop-off computation envelopes ------
# These DTOs carry the bucketed result of
# :meth:`InteractionService.compute_funnel_dropoff`. The route layer maps
# them to the public API DTOs after resolving actor display names via
# ``ActorService``. They live here (not in the route) so the dropoff
# business logic is owned by the interaction service per packages/CLAUDE.md.


class FunnelDropoffActorAggregate(BaseModel):
    """One ``(stage, operational_actor_id)`` aggregation bucket.

    ``actor_id`` is ``None`` when the drop-off event carried no
    ``operational`` responsibility row (legacy event pre-W2 wire-up).
    """

    actor_id: uuid.UUID | None
    person_count: int
    dollar_total: float


class FunnelDropoffStageComputed(BaseModel):
    """Per-stage drop-off aggregate from the service.

    ``person_count`` and ``dollar_total`` are the sums over
    ``by_actor`` so the route can map directly to the public DTO
    without re-totaling.
    """

    stage: FunnelStage
    person_count: int
    dollar_total: float
    by_actor: list[FunnelDropoffActorAggregate]


class FunnelOwnerActorOut(BaseModel):
    """Distinct responsibility actor for the picker (ENG-419)."""

    actor_id: uuid.UUID
    role: ResponsibilityRole


class FunnelRevenueByActorOut(BaseModel):
    """Net realized payment $ attributed to an actor (ENG-419).

    Reuses the PM Payments `recorded − refunded − reversed` formula so
    revenue slices reconcile.
    """

    actor_id: uuid.UUID
    role: ResponsibilityRole
    collected_total: float
    payment_count: int


class PaymentSummaryOut(BaseModel):
    """Window-wide totals for the PM Payments summary bar (ENG-302).

    Computed over the WHOLE selected window/filters (not the paginated page).
    ``collected_total`` is net cash (recorded − refunded − reversed);
    ``patient_count`` is distinct persons with a recorded payment.
    """

    collected_total: float = 0.0
    payment_count: int = 0
    patient_count: int = 0
