"""Typed contracts for semantic analytics catalog proposal review."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CatalogProposalStatus = Literal["proposed", "approved", "rejected", "unresolved"]
CatalogProposalSourceType = Literal["agent", "manual", "import"]


class CatalogProposalImpactOut(BaseModel):
    """Affected analytics surface preview for a proposal."""

    affected_questions: list[str] = Field(default_factory=list)
    affected_reports: list[str] = Field(default_factory=list)
    affected_read_models: list[str] = Field(default_factory=list)
    affected_dashboard_panels: list[str] = Field(default_factory=list)
    affected_chat_answers: list[str] = Field(default_factory=list)
    affected_agent_briefs: list[str] = Field(default_factory=list)


class CatalogProposalBase(BaseModel):
    """Editable human-review fields for a proposed catalog mapping."""

    raw_value: str = Field(min_length=1, max_length=512)
    source_system: str = Field(min_length=1, max_length=128)
    source_field: str = Field(min_length=1, max_length=256)
    suggested_term: str = Field(min_length=1, max_length=256)
    definition: str = Field(min_length=1, max_length=2000)
    synonyms: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=2000)
    reviewer_note: str = Field(default="", max_length=2000)
    affected_questions: list[str] = Field(default_factory=list)
    affected_read_models: list[str] = Field(default_factory=list)


class CatalogProposalCreateIn(CatalogProposalBase):
    """Create a manual or ingestion-sourced proposal draft."""

    source_type: CatalogProposalSourceType = "manual"
    source_reference_id: str | None = Field(default=None, max_length=256)


class CatalogProposalUpdateIn(BaseModel):
    """Patch editable proposal fields without performing a review transition."""

    raw_value: str | None = Field(default=None, min_length=1, max_length=512)
    source_system: str | None = Field(default=None, min_length=1, max_length=128)
    source_field: str | None = Field(default=None, min_length=1, max_length=256)
    suggested_term: str | None = Field(default=None, min_length=1, max_length=256)
    definition: str | None = Field(default=None, min_length=1, max_length=2000)
    synonyms: list[str] | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str | None = Field(default=None, min_length=1, max_length=2000)
    reviewer_note: str | None = Field(default=None, max_length=2000)
    affected_questions: list[str] | None = None
    affected_read_models: list[str] | None = None


class CatalogProposalReviewIn(BaseModel):
    """Human review transition request."""

    status: CatalogProposalStatus
    reviewer_note: str = Field(default="", max_length=2000)
    reason: str = Field(min_length=1, max_length=2000)


class CatalogProposalOut(CatalogProposalBase):
    """Review proposal returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    status: CatalogProposalStatus
    source_type: CatalogProposalSourceType
    source_reference_id: str | None = None
    created_by_actor_id: UUID | None = None
    reviewed_by_actor_id: UUID | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CatalogProposalListOut(BaseModel):
    """List response for frontend proposal draft replacement."""

    items: list[CatalogProposalOut]


class CatalogProposalIngestionSkippedOut(BaseModel):
    """One review-only ingestion candidate that was intentionally skipped."""

    source_reference_id: str
    registry_status: str
    source_system: str
    source_field: str
    suggested_term: str
    blockers: list[str] = Field(default_factory=list)


class CatalogProposalIngestionOut(BaseModel):
    """Summary of service-owned proposal ingestion from DIA outputs."""

    source: str
    created_count: int
    skipped_count: int
    created: list[CatalogProposalOut] = Field(default_factory=list)
    skipped: list[CatalogProposalIngestionSkippedOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CatalogProposalReviewOut(BaseModel):
    """Review transition response."""

    proposal: CatalogProposalOut
    impact: CatalogProposalImpactOut
    catalog_version_id: UUID | None = None


class CatalogProposalHistoryEventOut(BaseModel):
    """Review-history event for one catalog proposal."""

    action: str
    status: CatalogProposalStatus
    actor_id: UUID | None = None
    occurred_at: datetime
    reason: str | None = None
    reviewer_note: str | None = None
    catalog_version_id: UUID | None = None


class CatalogProposalHistoryOut(BaseModel):
    """Review-history response for one catalog proposal."""

    proposal_id: UUID
    items: list[CatalogProposalHistoryEventOut]


class CatalogVersionHistoryEntryOut(BaseModel):
    """Approved immutable semantic catalog version."""

    id: UUID
    tenant_id: UUID
    term: str
    version: int
    review_status: str
    definition: str
    synonyms: list[str]
    allowed_data_sources: list[str]
    data_classes: list[str]
    allowed_outputs: list[str]
    canonical_fields: list[str]
    row_level_fields: list[str]
    aggregate_metrics: list[str]
    used_by: list[str]
    source_references: list[dict[str, object]]
    previous_version_id: UUID | None = None
    proposal_id: UUID | None = None
    previous_value: dict[str, object] | None = None
    new_value: dict[str, object]
    reason: str
    affected_questions: list[str]
    affected_read_models: list[str]
    affected_reports: list[str]
    affected_dashboard_panels: list[str]
    affected_chat_answers: list[str]
    affected_agent_briefs: list[str]
    approved_by_actor_id: UUID | None = None
    approved_at: datetime
    created_at: datetime
    updated_at: datetime


class CatalogVersionHistoryOut(BaseModel):
    """Version-history response for one semantic term."""

    term: str
    items: list[CatalogVersionHistoryEntryOut]


class CatalogProposalImpactPreviewOut(BaseModel):
    """Preview response for the selected proposal before approval."""

    proposal_id: UUID
    impact: CatalogProposalImpactOut
    can_approve: bool
    blockers: list[str] = Field(default_factory=list)


class CatalogDraftPatchIn(BaseModel):
    """Request a draft catalog patch from approved proposals."""

    proposal_ids: list[UUID] = Field(default_factory=list)


class CatalogDraftPatchOut(BaseModel):
    """Draft catalog patch generated from approved proposal contracts."""

    proposal_ids: list[UUID]
    patch: list[dict[str, object]]
    catalog_version_id: UUID | None = None


# ---------------------------------------------------------------------------
# Full Funnel v2 — person-anchored funnel report (ENG-481).
#
# Canonical backend contract for GET /dashboard/analytics/full-funnel. The
# frontend Zod schema (ENG-482) mirrors these field names exactly. A metric
# with no connected source renders "—" (null), never a fabricated 0; ``spend``
# is null for the ``other`` channel and for any month with no ingested ad
# spend. ``closed_won`` stays month-level (opportunity→channel attribution
# deferred) and is omitted from the per-channel rows.
# ---------------------------------------------------------------------------

FullFunnelAudience = Literal["all", "marketing"]
FullFunnelChannel = Literal["google", "facebook", "other"]


class FullFunnelV2HeadlineOut(BaseModel):
    """Window totals.

    ``leads`` and ``closed_won`` are distinct persons; ``revenue`` is summed
    cash. The consult stages are APPOINTMENT counts (one per
    ``ops.consultation`` row, not distinct persons), so they balance:
    ``consults_scheduled = showed + no_show + cancelled + rescheduled +
    pending``.
    """

    leads: int = 0
    consults_scheduled: int = 0
    showed: int = 0
    no_show: int = 0
    cancelled: int = 0
    rescheduled: int = 0
    pending: int = 0
    closed_won: int = 0
    revenue: float = 0.0


class FullFunnelV2MonthOut(BaseModel):
    """One ``YYYY-MM`` row of the person-anchored funnel.

    Each metric buckets on its own stage timestamp, so the same person may
    appear in different months at different stages. ``spend`` is null when no
    ad spend was ingested for the month. The consult stages are APPOINTMENT
    counts and balance:
    ``consults_scheduled = showed + no_show + cancelled + rescheduled +
    pending``.
    """

    month: str
    spend: float | None = None
    leads: int
    consults_scheduled: int
    showed: int
    no_show: int
    cancelled: int = 0
    rescheduled: int = 0
    pending: int = 0
    closed_won: int
    revenue: float


class FullFunnelV2ChannelRowOut(BaseModel):
    """One ``month × channel`` row. ``closed_won`` is month-level only.

    The consult stages are APPOINTMENT counts and balance:
    ``consults_scheduled = showed + no_show + cancelled + rescheduled +
    pending``.
    """

    month: str
    channel: FullFunnelChannel
    spend: float | None = None
    leads: int
    consults_scheduled: int
    showed: int
    no_show: int
    cancelled: int = 0
    rescheduled: int = 0
    pending: int = 0
    revenue: float


class FullFunnelV2WindowOut(BaseModel):
    """The resolved inclusive month window (``YYYY-MM`` bounds)."""

    start_month: str
    end_month: str


class FullFunnelV2Out(BaseModel):
    """Person-anchored Full Funnel report (ENG-481).

    ``audience`` echoes the request toggle; ``marketing`` keeps only persons
    whose lead resolves to an ad channel (``marketing ⊆ all`` for every stage
    and month). ``channels`` is the fixed google/facebook/other ladder.
    """

    audience: FullFunnelAudience
    window: FullFunnelV2WindowOut
    channels: list[str]
    headline: FullFunnelV2HeadlineOut
    by_month: list[FullFunnelV2MonthOut]
    by_channel: list[FullFunnelV2ChannelRowOut]


# ---------------------------------------------------------------------------
# Shared analytics filter + derived-metric contract (ENG-507).
#
# The global filter bar, resolved time window, fact aggregate, and derived
# metrics every Revenue-Intelligence page consumes. Money is float dollars;
# a derived metric with no denominator is ``null`` (renders "—"), never a
# fabricated 0. The frontend Zod schema (apps/web/lib/api/schemas/
# journeyMetrics.ts) mirrors these field names exactly.
# ---------------------------------------------------------------------------

AnalyticsTimeRangePreset = Literal[
    "today",
    "yesterday",
    "last_7_days",
    "last_30_days",
    "last_90_days",
    "this_month",
    "this_quarter",
    "this_year",
    "custom",
]


class AnalyticsWindowOut(BaseModel):
    """The resolved half-open ``[start, end)`` window (tz-aware datetimes)."""

    preset: AnalyticsTimeRangePreset
    start: datetime
    end: datetime
    tz: str


class AnalyticsFiltersEchoOut(BaseModel):
    """The applied filter selection, echoed back for the page header."""

    time_range: AnalyticsTimeRangePreset
    location_id: UUID | None = None
    campaign_id: UUID | None = None
    source: str | None = None
    vendor_id: UUID | None = None
    caller_id: UUID | None = None
    coordinator_id: UUID | None = None
    doctor_id: UUID | None = None


class FactAggregateOut(BaseModel):
    """Per-window stage counts + money over ``fact_patient_journey``.

    Counts are in-cohort persons (lead_date in window) with a non-null stage
    date; ``revenue`` / ``collected`` are summed dollars; ``spend`` is ad spend
    over the same window (``null`` when no spend source is connected).
    """

    leads: int
    contacts: int
    consults: int
    shows: int
    surgeries: int
    patients: int
    revenue: float
    collected: float
    spend: float | None = None


class DerivedMetricsOut(BaseModel):
    """Cost-per-stage / revenue-per-stage / ROI / conversion ratios.

    Every field is ``null`` when its denominator is 0 (divide-by-zero → null).
    """

    cost_per_lead: float | None = None
    cost_per_consult: float | None = None
    cost_per_show: float | None = None
    cost_per_surgery: float | None = None
    revenue_per_lead: float | None = None
    revenue_per_show: float | None = None
    roi: float | None = None
    lead_to_contact: float | None = None
    contact_to_consult: float | None = None
    consult_to_show: float | None = None
    show_to_surgery: float | None = None
    surgery_to_revenue: float | None = None


class JourneyMetricsOut(BaseModel):
    """Smoke contract proving the shared filter DTO + a fact aggregate (ENG-507).

    Resolved ``window`` + echoed ``filters`` + the ``aggregate`` over
    ``fact_patient_journey`` + the ``derived`` metric layer. This is the
    foundation contract the 14 pages compose onto — not a page itself.
    """

    window: AnalyticsWindowOut
    filters: AnalyticsFiltersEchoOut
    aggregate: FactAggregateOut
    derived: DerivedMetricsOut


# --- Manual enrichment of fact fields (ENG-513) ----------------------------

# The fact columns an operator may set/correct by hand. A focused subset of
# ``fact_patient_journey`` — the people dimensions, attribution, the
# treatment/surgery milestones, and the marketing cost. Keep in sync with
# ``FactEnrichmentService._OVERRIDABLE``.
FactOverridableField = Literal[
    "caller_id",
    "coordinator_id",
    "doctor_id",
    "campaign_id",
    "campaign_name",
    "vendor_id",
    "case_type",
    "treatment_accepted_date",
    "surgery_scheduled_date",
    "surgery_completed_date",
    "marketing_cost_allocated",
]


class FactOverrideIn(BaseModel):
    """One operator override of a fact field for a person (ENG-513).

    ``value`` is the new value as a string (UUID / ISO-8601 datetime / decimal)
    or ``null`` to clear the field. The service coerces it to the column type
    and writes provenance ``method='manual'``. ``note`` is an optional human
    note; ``author_actor_id`` records who set it (the staff actor).
    """

    person_uid: UUID
    field: FactOverridableField
    value: str | float | int | None = None
    note: str | None = None
    author_actor_id: UUID | None = None


class FactFieldProvenanceOut(BaseModel):
    """One field's value + provenance after a manual override (ENG-513)."""

    model_config = ConfigDict(extra="forbid")

    field: str
    value: str | None
    method: Literal["unresolved", "auto", "manual"]
    source: str
    confidence: float | None = None
    resolved_at: datetime | None = None


class FactOverrideOut(BaseModel):
    """Result of a manual override: the person + the updated field state."""

    person_uid: UUID
    applied: FactFieldProvenanceOut
# ---------------------------------------------------------------------------
# B2 data-ready page contracts (ENG-514 / 515 / 521 / 526 / 523).
#
# Five staff pages composed read-only over ``fact_patient_journey`` + the shared
# filter/derived-metric layer. Every money figure is float dollars; a metric
# with no denominator (or a B1-unresolved input) is ``null`` → renders "—",
# never a fabricated 0. Counts for B1-unresolved stages (treatment_accepted,
# surgery_*) are honest zeros. Each page's frontend Zod schema mirrors these
# field-for-field.
# ---------------------------------------------------------------------------


class FunnelStageOut(BaseModel):
    """One patient-funnel stage: count + money + derived cost/conversion.

    ``count`` = in-cohort persons (``lead_date`` in window) reaching this stage;
    ``revenue`` / ``collected`` = money those persons carry. ``conversion`` is the
    share of the previous stage (``null`` for the entry stage and on a zero
    denominator); ``cost`` is ad spend ÷ count (``null`` when no spend source is
    connected). B1-unresolved stages report ``count = 0``.
    """

    key: str
    label: str
    count: int
    revenue: float
    collected: float
    conversion: float | None = None
    cost: float | None = None


class RevenueWidgetOut(BaseModel):
    """Realized cash for one fixed preset window (Executive "Today…YTD").

    Anchored on ``first_payment_date`` — money counted in the period it was
    collected. Independent of the page's selected time range.
    """

    preset: AnalyticsTimeRangePreset
    label: str
    gross: float
    collected: float
    payers: int


class ExecutiveOverviewOut(BaseModel):
    """Executive Overview page (ENG-514) — single-screen owner dashboard.

    ``funnel`` is the eight-stage patient funnel over the selected window;
    ``derived`` carries cost-per-stage / ROI / conversions (reusing the shared
    metric layer); ``revenue_widgets`` are the seven realized-cash cards. Cost /
    ROI are ``null`` until an ad-spend source is connected (B1.*).
    """

    window: AnalyticsWindowOut
    filters: AnalyticsFiltersEchoOut
    funnel: list[FunnelStageOut]
    derived: DerivedMetricsOut
    spend: float | None = None
    revenue_total: float
    collected_total: float
    outstanding_total: float
    patients: int
    revenue_widgets: list[RevenueWidgetOut]


class FunnelStagesOut(BaseModel):
    """Funnel Analytics page (ENG-515) — full nine-point patient funnel.

    The shared-fact funnel added alongside the existing Full-Funnel v2 view (it
    does not replace it, so v2's numbers do not regress). Per stage:
    count / conversion / cost / revenue. New stages (treatment_accepted,
    surgery_*) report honest zeros until B1.3.
    """

    window: AnalyticsWindowOut
    filters: AnalyticsFiltersEchoOut
    stages: list[FunnelStageOut]
    spend: float | None = None
    patients: int
    revenue_total: float
    collected_total: float


class RevenueGroupOut(BaseModel):
    """Revenue for one value of a breakdown dimension.

    ``group_id`` is the UUID key (``null`` for the source dimension, which keys
    on a string, and for the "Unattributed" bucket); ``group_label`` is the
    display name where the fact carries one (campaign / source). ``avg_case_value``
    = gross ÷ case_count (``null`` when no cases).
    """

    group_id: UUID | None = None
    group_label: str | None = None
    gross: float
    collected: float
    outstanding: float
    case_count: int
    avg_case_value: float | None = None


class RevenueDimensionOut(BaseModel):
    """All groups for one breakdown dimension.

    ``resolved`` is ``False`` for dimensions the fact cannot attribute yet
    (vendor / caller / coordinator / doctor are B1-unresolved) — the page renders
    those as a single "Unattributed" bucket with a note.
    """

    dimension: str
    resolved: bool
    groups: list[RevenueGroupOut]


class RevenueIntelligenceOut(BaseModel):
    """Revenue Intelligence page (ENG-521) — revenue by seven dimensions.

    Cohort revenue (``lead_date`` in window) so totals reconcile with the funnel.
    ``gross`` = presented case value (``revenue_amount``); ``collected`` =
    Net-Collected (ENG-283); ``outstanding`` = gross − collected.
    """

    window: AnalyticsWindowOut
    filters: AnalyticsFiltersEchoOut
    gross_total: float
    collected_total: float
    outstanding_total: float
    avg_case_value: float | None = None
    case_count: int
    dimensions: list[RevenueDimensionOut]


class CohortRevenueOut(BaseModel):
    """Cumulative collected revenue at each horizon (days after lead_date)."""

    d30: float
    d60: float
    d90: float
    d180: float
    d365: float


class CohortRowOut(BaseModel):
    """One lead-creation-month cohort row."""

    cohort_month: str
    lead_count: int
    revenue: CohortRevenueOut
    collected_total: float


class CohortAnalyticsOut(BaseModel):
    """Cohort Analytics page (ENG-526) — long-term lead value by cohort month.

    Cohorts are months of ``lead_date`` (person-anchored, so bulk-import patients
    do not distort the curve); each cell is cumulative ``collected_amount`` for
    persons whose ``first_payment_date`` lands within N days of their lead date.
    """

    window: AnalyticsWindowOut
    filters: AnalyticsFiltersEchoOut
    horizons: list[int]
    cohorts: list[CohortRowOut]


class JourneyStepOut(BaseModel):
    """One step of a person's revenue journey.

    ``occurred_at`` is the fact stage date (``null`` when the person never
    reached the stage); ``responsible_employee`` stays ``null`` until B1.1/B1.2
    resolve caller/coordinator/doctor; ``revenue`` is populated only on the
    payment step.
    """

    key: str
    label: str
    occurred_at: datetime | None = None
    responsible_employee: str | None = None
    revenue: float | None = None


class PatientJourneyOut(BaseModel):
    """Patient Journey page (ENG-523) — one person's full journey from the fact.

    Drill-down target from the other pages. ``found`` is ``False`` when the
    person has no fact row. The granular operational-timeline (ENG-235) is
    fetched separately by the page and merged client-side.
    """

    person_uid: UUID
    found: bool
    campaign_id: UUID | None = None
    campaign_name: str | None = None
    source: str | None = None
    location_id: UUID | None = None
    revenue_amount: float | None = None
    collected_amount: float | None = None
    steps: list[JourneyStepOut]


# ---------------------------------------------------------------------------
# B0.4 export + metric→patient drill-down contracts (ENG-508).
#
# CSV/XLSX export of the fact-backed pages and a metric→``person_uid`` drill-down,
# both honoring the same ``AnalyticsFilters`` (incl. location) as the on-screen
# pages. Aggregates + ``person_uid`` only — never PHI or raw provider payloads.
# ---------------------------------------------------------------------------

# The fact-backed pages that export to a tabular file. Marketing (ENG-516) is a
# documented gap — its page does not exist yet, so it has no export.
AnalyticsExportPage = Literal["executive", "funnel", "revenue", "cohort"]

AnalyticsExportFormat = Literal["csv", "xlsx"]

# Metrics a person can be drilled into, anchored on the shared ``lead_date``
# cohort so the list reconciles with the on-screen count. The funnel-stage keys
# plus the whole cohort (``patients``) and the paid-case set (``paid``). Mirrors
# ``packages.analytics.queries.DRILLDOWN_METRICS``.
DrilldownMetric = Literal[
    "leads",
    "reached",
    "consults",
    "shows",
    "treatment_presented",
    "treatment_accepted",
    "surgery_scheduled",
    "surgery_completed",
    "patients",
    "paid",
]


class MetricDrilldownOut(BaseModel):
    """Metric → underlying ``person_uid`` set for one filter selection (ENG-508).

    ``total`` is the full count of in-cohort persons matching the metric;
    ``person_uids`` is the deterministically ordered, hard-capped slice actually
    returned (``truncated`` is ``True`` when ``total`` exceeded the cap). Only
    ``person_uid`` — no names, dates, or money — crosses this boundary; the
    Patient Journey endpoint resolves a single uid to its timeline.
    """

    metric: DrilldownMetric
    window: AnalyticsWindowOut
    filters: AnalyticsFiltersEchoOut
    total: int
    returned: int
    truncated: bool
    person_uids: list[UUID]


# ---------------------------------------------------------------------------
# Marketing Performance page contract (ENG-516, B2.3).
#
# Ad spend ⇄ outcomes by Campaign and Source over the shared fact. Each group
# carries the full metric set (Spend, Leads, Consultations, Shows, Surgeries,
# Revenue) + derived ROI / cost-per-stage. Spend per group is the cost-per-lead
# allocation (``fact_patient_journey.marketing_cost_allocated``, ENG-512) — the
# spend that resolved to leads in that group. ``spend`` / derived metrics are
# ``null`` when no ad-spend source is connected for the window (renders "—",
# never a fabricated 0). ``Ad Set`` / ``Ad`` are surfaced as ``resolved=false``
# ("no data"): the fact carries no ad-set/ad dimension, so outcomes cannot be
# tied to them — the window-level ``spend_without_leads`` instead surfaces the
# spend that produced no attributed leads (allocator surplus), never hiding it.
# The frontend Zod schema mirrors these field-for-field.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Actor Performance pages (ENG-518 / ENG-519 / ENG-520).
#
# Three actor-focused read models over ``fact_patient_journey``. Each groups
# the same lead-date cohort by a people-dimension column so counts reconcile
# with the funnel and revenue pages. NULL actor → "Unassigned" (surfaced
# honestly, not hidden). Every derived ratio uses ``safe_div`` so a zero
# denominator renders "—", never a fabricated 0.
# ---------------------------------------------------------------------------


class CallerGroupOut(BaseModel):
    """One caller's cohort outcomes (ENG-518 — Caller Performance).

    ``leads`` = in-cohort persons with this caller assigned;
    ``reached`` = persons with ``first_contact_date`` non-null;
    ``consults`` = persons with ``consult_scheduled_date`` non-null;
    ``calls_made`` is **None** (honest no-data): the fact records whether
    contact was made (``first_contact_date``) but carries no per-call
    attempt count. Do not fabricate from the contact flag.

    Conversions: ``lead_to_contact`` = reached / leads;
    ``lead_to_consult`` = consults / leads (``null`` on zero denominator).
    Revenue: ``collected`` = SUM(collected_amount);
    ``revenue_per_lead`` = collected / leads;
    ``revenue_per_consult`` = collected / consults.
    """

    caller_id: UUID | None = None
    leads: int
    reached: int
    consults: int
    calls_made: None = None  # honest no-data: no per-call count in the fact
    lead_to_contact: float | None = None
    lead_to_consult: float | None = None
    collected: float
    revenue_per_lead: float | None = None
    revenue_per_consult: float | None = None


class CallerPerformanceOut(BaseModel):
    """Caller Performance page (ENG-518) — per-caller lead-to-revenue metrics.

    Cohort anchor = ``lead_date`` so counts reconcile with funnel / revenue.
    ``callers`` is ordered by consults desc, then collected desc. ``calls_made``
    is ``None`` on every row (honest no-data — the fact carries no dialer call
    count; ``first_contact_date`` records whether contact was made, not attempts).
    """

    window: AnalyticsWindowOut
    filters: AnalyticsFiltersEchoOut
    callers: list[CallerGroupOut]


class CoordinatorGroupOut(BaseModel):
    """One coordinator's cohort outcomes (ENG-519 — Coordinator Performance).

    ``consults_assigned`` = persons with ``consult_scheduled_date`` non-null;
    each subsequent stage is persons reaching it. ``collected`` = SUM.
    Conversions: ``scheduled_to_show`` = shows / consults_assigned;
    ``show_to_surgery`` = surgery_completed / shows;
    ``show_to_revenue`` = (persons with collected > 0) / shows — computed
    as collected > 0 proxy via ``safe_div(collected, shows)`` at count level;
    here we surface the ratio field so the UI can derive it from the counts.
    All ``null`` on a zero denominator.
    """

    coordinator_id: UUID | None = None
    consults_assigned: int
    shows: int
    treatment_presented: int
    surgery_scheduled: int
    surgery_completed: int
    collected: float
    scheduled_to_show: float | None = None
    show_to_surgery: float | None = None
    revenue_per_consult: float | None = None


class CoordinatorPerformanceOut(BaseModel):
    """Coordinator Performance page (ENG-519) — consult → surgery funnel per TC.

    Cohort anchor = ``lead_date``. ``coordinators`` is ordered by
    consults_assigned desc, then collected desc.
    """

    window: AnalyticsWindowOut
    filters: AnalyticsFiltersEchoOut
    coordinators: list[CoordinatorGroupOut]


class DoctorGroupOut(BaseModel):
    """One doctor's cohort outcomes (ENG-520 — Doctor Performance).

    ``consults`` = persons with ``consult_scheduled_date`` non-null;
    ``treatment_accepted`` = persons with ``treatment_accepted_date`` non-null;
    ``surgery_completed`` = persons with ``surgery_completed_date`` non-null.
    ``collected`` = SUM(collected_amount). Conversions:
    ``consult_to_accepted`` = treatment_accepted / consults;
    ``accepted_to_surgery`` = surgery_completed / treatment_accepted.
    Revenue: ``revenue_per_consult`` = collected / consults;
    ``revenue_per_surgery`` = collected / surgery_completed.
    All ``null`` on a zero denominator.
    """

    doctor_id: UUID | None = None
    consults: int
    treatment_presented: int
    treatment_accepted: int
    surgery_completed: int
    collected: float
    consult_to_accepted: float | None = None
    accepted_to_surgery: float | None = None
    revenue_per_consult: float | None = None
    revenue_per_surgery: float | None = None


class DoctorPerformanceOut(BaseModel):
    """Doctor Performance page (ENG-520) — consult → surgery → revenue per doctor.

    Cohort anchor = ``lead_date``. ``doctors`` is ordered by surgery_completed
    desc, then collected desc.
    """

    window: AnalyticsWindowOut
    filters: AnalyticsFiltersEchoOut
    doctors: list[DoctorGroupOut]


# ---------------------------------------------------------------------------
# ENG-517 — Vendor Performance page contract (B2.4).
#
# Ranking table grouped by ``vendor_id`` on the patient-journey fact.
#
# CRITICAL NO-DATA FACT (verified 2026-06-23 on production dataset):
# ``vendor_id`` is 100% NULL across all 115,715 fact rows — vendor
# attribution to the fact is owned by a separate epic (ENG-569 / vendor-
# binding) and is not yet wired. Today the query produces a single
# "Unassigned" bucket (vendor_id=NULL). The moment vendor_id gets populated
# the page lights up automatically because the SQL groups by vendor_id.
#
# The frontend renders a resolved=false "no per-vendor data" note alongside
# the Unassigned bucket to make the situation honest and visible.
# ---------------------------------------------------------------------------


class VendorGroupOut(BaseModel):
    """One vendor's cohort outcomes (ENG-517 — Vendor Performance).

    ``vendor_id`` is ``None`` for the "Unassigned" bucket (all rows today,
    because ``vendor_id`` is 100% NULL on the fact — vendor attribution is
    not yet wired; see ENG-569). ``spend_managed`` is ``None`` because there
    is no vendor→spend mapping on the fact yet (would require joining vendor
    costs, which is a separate data layer). ``roi`` is ``None`` without spend.
    All other counts are honest zeros when vendor_id is unresolved.
    """

    vendor_id: UUID | None = None
    leads: int
    consults: int
    shows: int
    surgeries: int
    revenue: float
    collected: float
    spend_managed: None = None  # no vendor→spend mapping on the fact yet
    roi: None = None  # null without spend


class VendorPerformanceOut(BaseModel):
    """Vendor Performance page (ENG-517) — per-vendor lead-to-revenue ranking.

    ``vendor_attribution_wired`` is ``False`` today because ``vendor_id`` is
    100% NULL on the fact (all 115,715 rows). The query groups by vendor_id
    so the page will light up automatically the moment the attribution epic
    (ENG-569) populates the column. Until then the table contains only an
    "Unassigned" bucket and the frontend shows a prominent no-data note.

    ``note`` carries the human-readable reason for the unresolved state so
    the UI can surface it next to the table.
    """

    window: AnalyticsWindowOut
    filters: AnalyticsFiltersEchoOut
    vendor_attribution_wired: bool
    note: str | None = None
    vendors: list[VendorGroupOut]


# ---------------------------------------------------------------------------
# ENG-525 — Attribution Analytics page contract (B2.12).
#
# Revenue attribution view: per-dimension collected revenue + case counts for
# persons in the cohort with a non-null ``revenue_amount``. Reuses the
# ``revenue_by_dimension`` helper for campaign/caller/coordinator/doctor and
# surfaces vendor as honest no-data (vendor_id=NULL today). Each dimension
# carries ``resolved=True/False`` so the UI can show a note where data is
# absent. Cohort anchor = ``lead_date`` in window.
# ---------------------------------------------------------------------------


class AttributionDimensionOut(BaseModel):
    """Revenue attribution for one grouping dimension.

    ``resolved`` is ``False`` when the dimension is not yet wired on the fact
    (vendor today; caller/coordinator/doctor have partial coverage — rows with
    NULL are "Unassigned"). ``note`` carries the reason for unresolved dims.
    ``groups`` are the per-value rows ordered by collected desc.
    """

    dimension: str
    resolved: bool
    note: str | None = None
    groups: list[RevenueGroupOut]


class AttributionAnalyticsOut(BaseModel):
    """Attribution Analytics page (ENG-525) — revenue attribution by dimension.

    Shows collected revenue + case counts per campaign / vendor / caller /
    coordinator / doctor for in-cohort persons (``lead_date`` in window).
    Campaign has good data; caller/coordinator/doctor have partial coverage
    (NULL = "Unassigned"); vendor is unresolved today (100% NULL — see
    ENG-517 / ENG-569). ``collected_total`` / ``case_count`` are totals
    derived from the source dimension (same cohort).
    """

    window: AnalyticsWindowOut
    filters: AnalyticsFiltersEchoOut
    collected_total: float
    case_count: int
    dimensions: list[AttributionDimensionOut]


# ---------------------------------------------------------------------------
# ENG-527 — Revenue Influence Matrix page contract (B2.14).
#
# Matrix of (employee × role) → Revenue Influenced. For each role dimension
# (Vendor / Caller / Coordinator / Doctor) the fact is grouped by the
# corresponding id column and SUM(collected_amount) is returned as
# "revenue_influenced". One employee may appear in multiple roles (e.g. a
# person is both caller and coordinator for different patients) — each
# (employee, role) pair is one row.
#
# DOUBLE-COUNTING CAVEAT (intentional, per-spec):
#   The same patient's collected revenue is counted once per role dimension.
#   If a patient has both a caller and a coordinator, the $5,000 they paid
#   appears in the Caller row AND the Coordinator row. This is by design —
#   "Revenue Influenced" measures the influence each employee had, not an
#   additive breakdown that sums to a single total. The matrix is not a
#   pie-chart; it cannot be summed across roles to yield collected revenue.
#
# Vendor role rows are empty today (vendor_id 100% NULL) — honest, not hidden.
# ---------------------------------------------------------------------------


class InfluenceRowOut(BaseModel):
    """One (employee, role) → revenue-influenced row in the matrix (ENG-527).

    ``employee_id`` is the fact column value (UUID or ``None`` for Unassigned);
    ``employee_label`` is a short display label (first 8 chars of UUID or
    "Unassigned" — full name resolution is ENG-578, not built here).
    ``role`` is one of "vendor" / "caller" / "coordinator" / "doctor".
    ``revenue_influenced`` = SUM(collected_amount) for the cohort patients
    where this employee held that role.

    The same patient's revenue may appear under multiple roles simultaneously
    (e.g. Caller row + Coordinator row). This is intentional — it is
    "influence", not additive attribution. See the ENG-527 contract note.
    """

    employee_id: UUID | None = None
    employee_label: str
    role: str
    revenue_influenced: float
    case_count: int


class RevenueInfluenceMatrixOut(BaseModel):
    """Revenue Influence Matrix (ENG-527) — employee × role × revenue influenced.

    ``rows`` is the flat list of (employee, role) pairs ordered by role then
    revenue_influenced desc. Each role dimension (vendor/caller/coordinator/
    doctor) contributes its own slice. Vendor rows are empty today (vendor_id
    is 100% NULL on the fact — see ENG-517). Caller has good coverage;
    coordinator and doctor have partial coverage.

    DOUBLE-COUNTING NOTE: the same collected revenue is counted once per role
    dimension. A $5,000 patient with both a caller and a coordinator assigned
    contributes $5,000 to the Caller slice AND $5,000 to the Coordinator slice.
    This is intentional per-spec: the matrix measures influence, not additive
    attribution. It must not be summed across roles.
    """

    window: AnalyticsWindowOut
    filters: AnalyticsFiltersEchoOut
    rows: list[InfluenceRowOut]


class MarketingGroupOut(BaseModel):
    """One value of a marketing breakdown dimension (campaign / source).

    ``group_id`` is the UUID key (campaign node id; ``null`` for the source
    dimension, which keys on a string, and for the "Unattributed" bucket);
    ``group_label`` is the display name (campaign name / source string).
    ``spend`` is the cost-per-lead allocation summed for the group (``null``
    when no ad-spend source is connected). Counts are in-cohort persons
    (``lead_date`` in window) reaching each stage; ``revenue`` / ``collected``
    are summed dollars. Derived ROI / cost-per-stage are ``null`` on a zero
    (or missing-spend) denominator.
    """

    group_id: UUID | None = None
    group_label: str | None = None
    spend: float | None = None
    leads: int
    consults: int
    shows: int
    surgeries: int
    revenue: float
    collected: float
    roi: float | None = None
    cost_per_lead: float | None = None
    cost_per_consult: float | None = None
    cost_per_show: float | None = None
    cost_per_surgery: float | None = None


class MarketingBreakdownOut(BaseModel):
    """All groups for one marketing breakdown dimension.

    ``resolved`` is ``False`` for dimensions the fact cannot attribute yet
    (``ad_set`` / ``ad`` — the fact has no ad-set/ad column), which the page
    renders as an explicit "no data" panel. ``note`` carries the honest reason
    when unresolved.
    """

    dimension: str
    resolved: bool
    groups: list[MarketingGroupOut]
    note: str | None = None


class MarketingPerformanceOut(BaseModel):
    """Marketing Performance page (ENG-516) — ad spend ⇄ outcomes.

    Cohort outcomes (``lead_date`` in window, so counts reconcile with the
    funnel) joined to the cost-per-lead allocation. ``total_spend`` is the
    window's ground-truth ad spend from ``marketing.*``; ``allocated_spend`` is
    the portion the allocator tied to leads; ``spend_without_leads`` =
    ``total_spend`` − ``allocated_spend`` (floored at 0) — ad spend that
    produced no attributed leads, surfaced not hidden. All three are ``null``
    when no ad-spend source is connected. ``breakdowns`` are the campaign /
    source (resolved) and ad_set / ad (``resolved=false``) cuts.
    """

    window: AnalyticsWindowOut
    filters: AnalyticsFiltersEchoOut
    total_spend: float | None = None
    allocated_spend: float | None = None
    spend_without_leads: float | None = None
    leads: int
    consults: int
    shows: int
    surgeries: int
    revenue_total: float
    collected_total: float
    roi: float | None = None
    breakdowns: list[MarketingBreakdownOut]


# ---------------------------------------------------------------------------
# Cost Intelligence page contract (ENG-522, B2.9).
#
# Marketing costs computable from the window ad spend (ground-truth from
# MarketingService.ad_spend_totals) and the shared funnel stage counts.
# Operational cost metrics (cost per caller conversion, cost per coordinator
# conversion) require staff/operational cost inputs not yet captured — they
# are surfaced as honest no-data (``null`` + note) rather than fabricated 0s.
# All metrics respect the global filters including location.
# ---------------------------------------------------------------------------

OperationalCostStatus = Literal["no_data", "available"]


class CostMetricOut(BaseModel):
    """One cost metric: a computed value or an honest null with a note.

    ``value`` is ``null`` when:
    - the denominator stage count is 0 (divide-by-zero → null via safe_div), or
    - no ad-spend source is connected for the window (spend is None), or
    - the metric requires operational cost inputs not yet captured.
    In every null case ``note`` explains why.
    """

    label: str
    value: float | None = None
    note: str | None = None


class CostIntelligenceOut(BaseModel):
    """Cost Intelligence page (ENG-522) — marketing cost per funnel stage.

    ``spend`` is the window ground-truth ad spend from ``MarketingService``
    (the same source ``marketing_performance`` uses). It is ``null`` when no
    ad-spend source is connected — all spend-derived metrics are then ``null``
    and render "—".

    Marketing costs (computable from spend + funnel counts):
    - ``cost_per_lead``: spend / leads
    - ``cost_per_consult``: spend / consults
    - ``cost_per_show``: spend / shows
    - ``cost_per_surgery``: spend / surgery_completed
    - ``cost_per_revenue_dollar``: spend / collected_amount (efficiency of spend)

    Operational costs (``null`` + note — inputs not yet captured):
    - ``cost_per_caller_conversion``: needs caller operational cost
    - ``cost_per_coordinator_conversion``: needs coordinator operational cost
    """

    window: AnalyticsWindowOut
    filters: AnalyticsFiltersEchoOut
    spend: float | None = None
    leads: int
    consults: int
    shows: int
    surgeries: int
    collected: float
    cost_per_lead: CostMetricOut
    cost_per_consult: CostMetricOut
    cost_per_show: CostMetricOut
    cost_per_surgery: CostMetricOut
    cost_per_revenue_dollar: CostMetricOut
    cost_per_caller_conversion: CostMetricOut
    cost_per_coordinator_conversion: CostMetricOut


# ---------------------------------------------------------------------------
# Bottleneck Detection page contract (ENG-524, B2.11).
#
# Rule-based detector over the shared fact + existing breakdown aggregates.
# Each detected bottleneck carries a description, category, severity, an
# estimated revenue loss (where defensibly computable), a suggested action,
# and the entity it refers to. When sample size is too small (below minimum
# thresholds) no finding is emitted — we do not invent from noise.
# ---------------------------------------------------------------------------

BottleneckSeverity = Literal["low", "medium", "high"]
BottleneckCategory = Literal[
    "campaign_low_show",
    "coordinator_low_surgery_conversion",
    "doctor_low_acceptance",
    "caller_low_booking",
]


class BottleneckEntityOut(BaseModel):
    """The entity a bottleneck refers to (campaign, coordinator, doctor, caller).

    ``id`` is the UUID of the entity (``null`` for the "Unassigned" bucket, which
    is never flagged). ``label`` is a display-ready string (entity id short form
    or a human label when available).
    """

    id: UUID | None = None
    label: str


class BottleneckOut(BaseModel):
    """One detected bottleneck.

    ``category`` is a machine-readable type; ``description`` is a one-sentence
    summary. ``severity`` is low / medium / high based on the deviation from the
    cohort median. ``estimated_revenue_loss`` is a defensible estimate of revenue
    foregone vs. a median performer (``null`` when the estimate is not
    computable). ``suggested_action`` is a plain-language recommendation.
    ``entity`` is the entity the bottleneck refers to.
    """

    category: BottleneckCategory
    description: str
    severity: BottleneckSeverity
    estimated_revenue_loss: float | None = None
    suggested_action: str
    entity: BottleneckEntityOut


class BottlenecksOut(BaseModel):
    """Bottleneck Detection page (ENG-524) — rule-based funnel bottlenecks.

    ``findings`` is empty when the cohort is too sparse to detect reliably
    (all entities below minimum sample thresholds). No findings are invented
    from noise. ``window`` and ``filters`` echo the request so the page header
    shows what cohort was analysed.
    """

    window: AnalyticsWindowOut
    filters: AnalyticsFiltersEchoOut
    findings: list[BottleneckOut]
