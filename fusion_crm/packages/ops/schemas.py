"""Pydantic schemas for the ops domain.

These schemas are PHI-FREE by construction. Anything sent to ops API consumers
or AI tools comes through one of these models.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    ConsultationKind,
    ConsultationStatus,
    FollowupStatus,
    LeadStatus,
    RelationshipKind,
    RelationshipStatus,
)


class LeadIn(BaseModel):
    person_uid: UUID
    source: str | None = None
    notes: str | None = None
    extra: dict = Field(default_factory=dict)


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_uid: UUID
    source: str | None
    status: LeadStatus
    notes: str | None
    extra: dict
    created_at: datetime
    updated_at: datetime


class FollowupTaskIn(BaseModel):
    person_uid: UUID
    title: str = Field(..., min_length=1, max_length=240)
    description: str | None = None
    due_at: datetime | None = None
    assigned_to: UUID | None = None


class FollowupTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_uid: UUID
    title: str
    description: str | None
    due_at: datetime | None
    status: FollowupStatus
    assigned_to: UUID | None
    created_at: datetime
    updated_at: datetime


class OpsPersonSnapshot(BaseModel):
    """PHI-free profile suitable for staff/agent use.

    This is the canonical "safe" view used by the ops surface and by AI tools
    that don't have clinical access. Build it via ``OpsService.snapshot``.
    """

    person_uid: UUID
    display_name: str | None
    open_followups: int
    last_lead_status: LeadStatus | None


class AnalyticsBucketOut(BaseModel):
    """PHI-free aggregate bucket for approved analytics queries."""

    key: str
    label: str
    count: int


class FieldValueBucketOut(BaseModel):
    """Top-value bucket for an allowlisted operational field profile."""

    value: str
    count: int


class OpsFieldProfileOut(BaseModel):
    """Aggregate-only field profile for Data Intelligence tooling."""

    row_count: int
    null_count: int
    top_values: list[FieldValueBucketOut]


class LeadSourceProfileOut(BaseModel):
    """Top lead-source profile for manager analytics."""

    total_leads: int
    sources: list[AnalyticsBucketOut]


class ConversionFunnelOut(BaseModel):
    """Lead-to-consultation funnel counts for manager analytics."""

    lead_status: list[AnalyticsBucketOut]
    consultation_status: list[AnalyticsBucketOut]
    pipeline_total: int
    consultations_total: int
    completed_consultations: int


class LeadSourceNodeOut(BaseModel):
    """One node of the lead-source explorer tree (ENG-391).

    ``key`` is the slash-joined label path from the root ("source",
    "source/medium", "source/medium/campaign") — stable across reloads
    and unique among siblings, suitable for UI row keys and drill-down
    requests.
    """

    key: str
    label: str
    level: str  # "source" | "medium" | "campaign"
    leads: int
    consults_scheduled: int
    consults_attended: int
    # Net Collected cash (recorded − refunded/reversed) of the persons
    # behind this node's leads. Interaction-domain math, attached by the
    # route layer.
    collected_amount: float = 0.0
    children: list[LeadSourceNodeOut] = Field(default_factory=list)


class LeadSourceTreeOut(BaseModel):
    """Hierarchical per-source funnel counts for the DEV explorer."""

    total_leads: int
    consults_scheduled: int
    consults_attended: int
    collected_amount: float = 0.0
    sources: list[LeadSourceNodeOut]


class OpportunityMonthOutcomeOut(BaseModel):
    """Per-month opportunity outcome counts for the full-funnel report (ENG-472).

    ``month`` is the ``close_date`` calendar month (``"YYYY-MM"``). All
    counts bucket off ``close_date``: ``closed`` are opportunities marked
    ``is_closed`` that closed in the month, ``won`` are the ``is_won`` subset,
    and ``carryover`` are closed opportunities whose covering consultation was
    scheduled in a *different* month (a deal closed this month from an earlier
    consult).
    """

    month: str
    closed: int
    won: int
    carryover: int


class SalesPipelineSummaryOut(BaseModel):
    """Headline sales-pipeline counts for the Sales dashboard (ENG-473).

    All flags read the JSON booleans on ``opportunity.extra`` (``is_closed`` /
    ``is_won``), NOT the free-form ``stage`` string. ``pipeline_value`` sums
    ``amount`` over open (not-closed) opportunities; ``won_revenue`` sums
    ``amount`` over won opportunities. Counts are raw integers; close-rate and
    revenue attribution are derived by the route (the route also bridges in
    interaction-domain Collected cash — ops never imports interaction).
    """

    active_opps: int
    closed_opps: int
    won_opps: int
    pipeline_value: float
    won_revenue: float


class SalesStageRowOut(BaseModel):
    """One opportunity ``stage`` bucket (Sales pipeline-by-stage tile).

    ``stage`` is the raw free-form ``opportunity.stage`` string (grouped
    dynamically — there is no hardcoded stage ladder). ``value`` sums
    ``amount`` for the bucket.
    """

    stage: str
    count: int
    value: float


class SalesTcRowOut(BaseModel):
    """One treatment-coordinator row for the Sales TC leaderboard (ENG-473).

    Grouped by ``opportunity.extra->>'owner_name'`` (free text; the only TC
    input we have). Counts use the ``is_closed`` / ``is_won`` JSON booleans.
    ``value`` is total opportunity ``amount`` for the TC; ``won_revenue`` is
    the ``is_won`` subset's ``amount``. ``person_uids`` are the distinct
    persons behind this TC's opportunities so the route can attribute net
    Collected cash via ``InteractionService.collected_by_person`` — close-rate
    and ``collected`` are filled in by the route, not here.
    """

    tc: str
    opps: int
    won: int
    lost: int
    value: float
    won_revenue: float
    person_uids: list[UUID] = Field(default_factory=list)


class SalesConsultationRowOut(BaseModel):
    """One consultation row for the Sales consultations table (ENG-473).

    Joins ``consultation`` → its covering ``opportunity``
    (``covering_opportunity_id``) for TC / stage / opportunity value, and
    carries ``person_uid`` so the route can attach the patient's identity
    display name (staff-frontend PHI policy permits it) and net Collected
    cash. ``opp_value`` / ``tc`` / ``stage`` / ``close_date`` are ``None``
    when the consultation has no covering opportunity. ``paid`` and
    ``balance`` are computed by the route from Collected cash vs ``opp_value``.
    """

    consultation_id: UUID
    person_uid: UUID
    status: ConsultationStatus
    scheduled_at: datetime
    tc: str | None = None
    stage: str | None = None
    opp_value: float | None = None
    close_date: datetime | None = None


class LeadSourceLeadItemOut(BaseModel):
    """One drill-down lead row behind a lead-source explorer node.

    ``attribution`` carries the allowlisted marketing-safe subset of
    ``Lead.extra`` (UTM/touch/conversion mirrors); free-text ``notes``
    are deliberately excluded. ``display_name``/``email``/``phone`` come
    from identity (staff-frontend PHI policy of 2026-06-01 permits them;
    same surface the PM Leads page renders).
    """

    id: UUID
    person_uid: UUID
    display_name: str | None = None
    email: str | None = None
    phone: str | None = None
    # Net Collected cash of this person (same interaction-domain math as
    # the tree nodes); 0.0 when the person has no payments.
    collected_amount: float = 0.0
    # ENG-400: raw SF assigned_center plus a flag set when the row entered
    # the location scope only via consultation evidence (stale center).
    assigned_center: str | None = None
    location_mismatch: bool = False
    status: LeadStatus
    source_label: str
    utm_medium: str | None
    utm_campaign: str | None
    created_at: datetime
    provider_created_at: datetime | None
    attribution: dict


class LeadSourceLeadListOut(BaseModel):
    """Paginated drill-down list for one lead-source explorer node."""

    total: int
    items: list[LeadSourceLeadItemOut]


class PaidLeadsOut(BaseModel):
    """Paid-source lead profile using CRM-safe source/campaign evidence."""

    total_paid_leads: int
    sources: list[AnalyticsBucketOut]
    classification_terms: list[str]


class ConsultationFollowupOut(BaseModel):
    """Consultation and follow-up workload profile for manager analytics."""

    consultation_status: list[AnalyticsBucketOut]
    open_followups: int
    overdue_followups: int


class ConsultationIn(BaseModel):
    """Upsert input for a CareStack appointment / Salesforce Event.

    The provider-side puller (ENG-218 / ENG-219) builds one of these per
    pulled row and hands it to ``OpsService.upsert_consultation_from_hint``.
    PHI fields (clinical notes, treatment plan, diagnosis) MUST NOT be
    surfaced here — they stay in the provider source and ``phi.*`` (M3+).
    """

    person_uid: UUID
    source_provider: str = Field(..., min_length=1, max_length=32)
    source_instance: str = Field(..., min_length=1, max_length=96)
    external_id: str = Field(..., min_length=1, max_length=240)
    scheduled_at: datetime
    # Provider-side creation timestamp (CareStack ``createdOn`` / Salesforce
    # Event ``CreatedDate``). The dashboard date window filters on this
    # rather than ``scheduled_at`` so "consultations created in the last 30
    # days" reflects when the booking record landed at the provider.
    provider_created_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    status: ConsultationStatus = ConsultationStatus.SCHEDULED
    consultation_kind: ConsultationKind = ConsultationKind.OTHER
    location_id: UUID | None = None
    provider_clinician_name: str | None = Field(default=None, max_length=240)
    # ENG-543: CareStack provider id the appointment was booked under — links the
    # consultation to the doctor's actor for the reminder @mention.
    provider_carestack_id: str | None = Field(default=None, max_length=64)
    # ENG-487: verbatim provider status (e.g. CareStack "Confirmed"); the
    # bucketed ``status`` above collapses it. NULL for sources without one.
    source_status: str | None = Field(default=None, max_length=48)
    raw_event_id: UUID | None = None


class ConsultationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_uid: UUID
    source_provider: str
    source_instance: str
    external_id: str
    scheduled_at: datetime
    duration_minutes: int | None
    status: ConsultationStatus
    consultation_kind: ConsultationKind
    location_id: UUID | None
    provider_clinician_name: str | None
    # ENG-543: CareStack provider id → doctor actor → reminder @mention.
    provider_carestack_id: str | None = None
    source_status: str | None = None
    raw_event_id: UUID | None
    provider_created_at: datetime | None = None
    # ENG-417: link to the SF Opportunity that covers this consult's
    # scheduled moment. NULL for walk-ins / pre-Opportunity consults.
    covering_opportunity_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ConsultationUpsertResult(BaseModel):
    """Result envelope for ``OpsService.upsert_consultation_from_hint``.

    Mirrors ``UpsertLeadResult`` so callers can decide whether to emit
    lifecycle timeline events without inspecting raw provider payloads.
    """

    consultation: ConsultationOut
    was_created: bool
    was_changed: bool
    was_status_change: bool = False
    was_scheduled_at_change: bool = False


class PersonLocationProfileOut(BaseModel):
    """PHI-free per-location relationship projection for one person."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_uid: UUID
    location_id: UUID
    relationship_kind: RelationshipKind
    relationship_status: RelationshipStatus
    last_evidence_provider: str | None
    last_evidence_source_instance: str | None
    last_evidence_external_id: str | None
    last_evidence_at: datetime | None
    last_consultation_id: UUID | None
    last_raw_event_id: UUID | None
    created_at: datetime
    updated_at: datetime


# --- Opportunity (ENG-414) ---


class OpportunityIn(BaseModel):
    """Upsert input for an SF Opportunity ingest pass.

    ``source_provider``/``source_instance``/``external_id`` is the
    idempotency key. ``person_uid`` is optional because the AccountId
    fallback chain may miss on the first pull and succeed later; the
    row is still useful for the ENG-414 owner-resolution flow.
    """

    person_uid: UUID | None = None
    source_provider: str = Field(..., min_length=1, max_length=32)
    source_instance: str = Field(..., min_length=1, max_length=96)
    external_id: str = Field(..., min_length=1, max_length=240)
    name: str | None = Field(default=None, max_length=240)
    stage: str | None = Field(default=None, max_length=64)
    amount: float | None = None
    close_date: datetime | None = None
    provider_created_at: datetime | None = None
    raw_event_id: UUID | None = None
    extra: dict[str, object] = Field(default_factory=dict)


class OpportunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_uid: UUID | None
    source_provider: str
    source_instance: str
    external_id: str
    name: str | None
    stage: str | None
    amount: float | None
    close_date: datetime | None
    provider_created_at: datetime | None
    raw_event_id: UUID | None
    extra: dict[str, object]
    created_at: datetime
    updated_at: datetime


class OpportunityUpsertResult(BaseModel):
    """Result envelope for ``OpsService.upsert_opportunity``.

    Mirrors :class:`ConsultationUpsertResult`.

    ``was_changed`` is true whenever the row was inserted OR a watched
    field (``stage``, ``amount``, ``close_date``, ``extra.owner_id``,
    ``extra.owner_name``) actually differed from what we had on file.
    """

    opportunity: OpportunityOut
    was_created: bool
    was_changed: bool
    was_owner_change: bool = False
    was_stage_change: bool = False
