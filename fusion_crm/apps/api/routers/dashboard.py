"""Dashboard HTTP route — single-shot summary aggregation for the staff UI.

Matches the Zod ``DashboardSummarySchema`` in
``apps/web/lib/api/schemas/dashboard.ts``. The route is a thin composer:
every count and every list is produced by an existing domain service, the
route only stitches the responses into one DTO.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import (
    get_analytics_export_service,
    get_analytics_metrics_service,
    get_analytics_pages_service,
    get_db,
    get_fact_enrichment_service,
    get_full_funnel_service,
    get_identity_service,
    get_ingest_service,
    get_integration_service,
    get_interaction_service,
    get_marketing_service,
    get_ops_service,
    get_phi_service,
    get_principal_with_tenant,
)
from packages.analytics.enrichment_service import FactEnrichmentService
from packages.analytics.export_service import AnalyticsExportService
from packages.analytics.filters import AnalyticsFilters, TimeRangePreset
from packages.analytics.full_funnel import FullFunnelService
from packages.analytics.metrics_service import (
    DRILLDOWN_DEFAULT_LIMIT,
    DRILLDOWN_HARD_CAP,
    AnalyticsMetricsService,
    AnalyticsPagesService,
)
from packages.analytics.schemas import (
    AnalyticsExportFormat,
    AnalyticsExportPage,
    AttributionAnalyticsOut,
    BottlenecksOut,
    CallerPerformanceOut,
    CohortAnalyticsOut,
    CoordinatorPerformanceOut,
    CostIntelligenceOut,
    DoctorPerformanceOut,
    DrilldownMetric,
    ExecutiveOverviewOut,
    FactOverrideIn,
    FactOverrideOut,
    FullFunnelV2Out,
    FunnelStagesOut,
    JourneyMetricsOut,
    MarketingPerformanceOut,
    MetricDrilldownOut,
    PatientJourneyOut,
    RevenueInfluenceMatrixOut,
    RevenueIntelligenceOut,
    VendorPerformanceOut,
)
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.identity.schemas import PersonSummaryOut
from packages.identity.service import IdentityService
from packages.ingest.service import IngestService
from packages.integrations.service import IntegrationService
from packages.interaction.schemas import OperationalTimelineEntry
from packages.interaction.service import InteractionService
from packages.marketing.service import MarketingService
from packages.ops.models import ConsultationStatus, LeadStatus
from packages.ops.schemas import LeadSourceNodeOut
from packages.ops.service import (
    OpsService,
    explorer_source_label_for_lead,
    owner_label_for_lead,
)
from packages.phi.service import PhiService
from packages.tenant.service import LocationService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_RECENT_PERSON_LIMIT = 10
_PM_LEADS_CANDIDATE_LIMIT = 5000
# Statuses excluded from "active pipeline" — a Lead in the lost bucket is
# no longer in flight. Same logic the UI applied client-side on the MSW
# fixture; lifting it server-side keeps the contract authoritative.
_PIPELINE_EXCLUDE_STATUSES = frozenset({LeadStatus.LOST.value})


class DashboardSummaryOut(BaseModel):
    lead_counts: dict[str, int]
    consultations_today: int
    consultations_this_week: int
    recent_persons: list[PersonSummaryOut]
    pipeline_total: int


class DashboardAppliedFiltersOut(BaseModel):
    from_: datetime | None = Field(default=None, serialization_alias="from")
    to: datetime | None = None
    source_provider: Literal["salesforce", "carestack"] | None = None
    lead_source: str | None = None
    location_id: UUID | None = None
    q: str | None = None
    # ENG-408 PM Payments resource filter: the selected lead-source explorer
    # node (channel → source → medium → campaign, explorer last-touch
    # labels). ``lead_source`` doubles as the node's source level here.
    lead_channel: str | None = None
    lead_medium: str | None = None
    lead_campaign: str | None = None


class DashboardKpiOut(BaseModel):
    key: str
    label: str
    value: int
    hint: str | None = None


class DashboardBucketOut(BaseModel):
    key: str
    label: str
    count: int


class DashboardFunnelStageOut(BaseModel):
    key: str
    label: str
    count: int
    hint: str | None = None


class DashboardBreakdownOut(BaseModel):
    key: str
    label: str
    items: list[DashboardBucketOut]


class DashboardSyncRunOut(BaseModel):
    provider: str
    object_scope: str | None
    status: str
    started_at: datetime
    finished_at: datetime | None
    records_total: int
    records_succeeded: int
    records_failed: int
    error: str | None = None


class DashboardSemanticMetricOut(BaseModel):
    key: str
    label: str
    value: float


class DashboardSemanticReadModelOut(BaseModel):
    query_id: str
    read_model_id: str
    title: str
    data_classes: list[str]
    definition_versions: dict[str, str]
    row_count: int
    drilldown_available: bool
    export_available: bool
    metrics: list[DashboardSemanticMetricOut]


class DashboardReadinessOut(BaseModel):
    status: Literal["available", "contract_ready", "not_started"]
    message: str


class DashboardTreatmentPaymentsOut(DashboardReadinessOut):
    treatment_presented_count: int = 0
    treatment_completed_count: int = 0
    invoice_count: int = 0
    payment_total_amount: float = 0.0
    collected_total: float = 0.0
    payment_event_count: int = 0
    outstanding_total: float = 0.0
    outstanding_patient_count: int = 0
    has_partial_payments: bool = False
    first_payment_at: datetime | None = None
    last_payment_at: datetime | None = None
    ar_risk_count: int | None = None


class DashboardPmLeadOut(BaseModel):
    id: UUID
    person_uid: UUID
    display_name: str
    given_name: str | None = None
    family_name: str | None = None
    email: str | None = None
    phone: str | None = None
    status: str
    lead_source: str | None = None
    source_provider: Literal["salesforce", "carestack", "manual", "unknown"]
    source_external_id: str | None = None
    created_at: datetime
    updated_at: datetime
    source_providers: list[str] = Field(default_factory=list)
    consultation_status: str | None = None
    consultation_scheduled_at: datetime | None = None
    consultation_provider_created_at: datetime | None = None
    consultation_provider: str | None = None
    location_name: str | None = None


class DashboardPmLeadListOut(BaseModel):
    items: list[DashboardPmLeadOut]
    total: int
    limit: int
    offset: int
    has_next: bool
    has_previous: bool
    filters: DashboardAppliedFiltersOut


class DashboardPmLeadSourceBucketOut(BaseModel):
    key: str
    count: int


class DashboardPmLeadSourceProviderOut(BaseModel):
    provider: Literal["salesforce", "carestack"]
    total: int
    sources: list[DashboardPmLeadSourceBucketOut]


class DashboardPmLeadSourcesOut(BaseModel):
    providers: list[DashboardPmLeadSourceProviderOut]


class DashboardPmPaymentOut(BaseModel):
    """Per-row safe projection for the PM Payments page.

    All fields are dashboard-safe: identifiers, the resolved person display
    name (no PHI), the structured no-PII workflow-ready event payload bits
    (amount, transaction_type, location_id) and the foreign key to the raw
    event for the drilldown. NO clinical free text, NO patient identifiers
    beyond ``person_uid`` / display name (same safety level as the existing
    leads list).
    """

    id: UUID
    person_uid: UUID
    display_name: str
    lead_status: str | None = None
    consultation_status: str | None = None
    # ENG-408: acquisition attribution for the row's person — the lead's
    # explorer source label (lowercased, last-touch first; same chain as the
    # /dev/lead-sources tree) and the SF Lead owner (Owner.Name mirror,
    # falling back to the raw OwnerId until the next lead re-pull backfills
    # names). ``None`` when the person has no lead.
    lead_source_label: str | None = None
    lead_owner: str | None = None
    amount: float | None = None
    kind: Literal[
        "payment_recorded",
        "payment_refunded",
        "payment_reversed",
        "payment_applied",
    ]
    transaction_type: str | None = None
    occurred_at: datetime
    source_provider: Literal["salesforce", "carestack"]
    source_external_id: str | None = None
    location_id: UUID | None = None
    location_name: str | None = None
    raw_event_id: UUID | None = None
    # ENG-303: which CareStack invoice this payment is applied to. invoice_id
    # is the internal id (join key); invoice_number is the human number staff
    # see; invoice_date is the invoice's date (YYYY-MM-DD). number/date are
    # resolved from the invoice raw rows and may be absent (≈16% of payments
    # reference an invoice we have not captured).
    invoice_id: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    # ENG-306: latest authoritative outstanding balance for the row's
    # patient (sum of patient + insurance from the most recent
    # carestack.payment_summary.snapshot per CareStack patient id linked
    # to the row's person). ``None`` when no snapshot has been captured
    # for the person yet — the UI renders ``"—"`` instead of ``"$0"``.
    balance: float | None = None
    # ENG-547: what this payment was for + who performed it, resolved from the
    # accounting-transaction raw payload's optional ``procedureCodeId`` /
    # ``providerId`` scalars. operation_code is the CDT code (e.g. "D6010"),
    # operation_description its catalog description; doctor_name is the
    # performing provider's display name ("Dr First Last"); doctor_provider_id
    # is the CareStack provider id (trace/debug). Direct transaction fields
    # only — ``None`` for advances / unallocated legs / adjustments, and the UI
    # renders ``"—"``. NO invoice-provider fallback, NO clinical free text.
    operation_code: str | None = None
    operation_description: str | None = None
    doctor_name: str | None = None
    doctor_provider_id: int | None = None


class DashboardPmPaymentListOut(BaseModel):
    items: list[DashboardPmPaymentOut]
    total: int
    limit: int
    offset: int
    has_next: bool
    has_previous: bool
    filters: DashboardAppliedFiltersOut


class DashboardPmPaymentGroupOut(BaseModel):
    """One same-day payment group for the PM Payments page (ENG-410).

    CareStack splits one real-world payment into per-invoice legs; the
    group collapses them by ``(person, kind, clinic-local day)``. Person-
    level fields mirror the leg row shape; ``legs`` are full
    :class:`DashboardPmPaymentOut` rows (newest-first) so the expanded
    view is byte-identical to the flat list.
    """

    person_uid: UUID
    display_name: str
    lead_status: str | None = None
    consultation_status: str | None = None
    lead_source_label: str | None = None
    lead_owner: str | None = None
    balance: float | None = None
    kind: Literal[
        "payment_recorded",
        "payment_refunded",
        "payment_reversed",
        "payment_applied",
    ]
    # Clinic-local calendar day (YYYY-MM-DD) the legs share.
    day: str
    # Sum of the legs' amounts; occurred_at is the NEWEST leg's timestamp
    # (groups sort by it, newest-first).
    amount: float
    leg_count: int
    occurred_at: datetime
    legs: list[DashboardPmPaymentOut]


class DashboardPmPaymentGroupListOut(BaseModel):
    items: list[DashboardPmPaymentGroupOut]
    total: int
    limit: int
    offset: int
    has_next: bool
    has_previous: bool
    filters: DashboardAppliedFiltersOut


class DashboardPmPaymentSummaryOut(BaseModel):
    """Window-wide totals for the PM Payments summary bar (ENG-302).

    Aggregated over the WHOLE selected window/filters, not the paginated
    page. ``collected_total`` is net cash collected (recorded − refunded −
    reversed); ``patient_count`` is distinct persons with a recorded payment.
    """

    collected_total: float
    payment_count: int
    patient_count: int
    filters: DashboardAppliedFiltersOut


class DashboardPmOut(BaseModel):
    filters: DashboardAppliedFiltersOut
    kpis: list[DashboardKpiOut]
    funnel: list[DashboardFunnelStageOut]
    breakdowns: list[DashboardBreakdownOut]
    semantic_analytics: list[DashboardSemanticReadModelOut]
    recent_activity: list[OperationalTimelineEntry]
    sync_health: list[DashboardSyncRunOut]
    treatment_payments: DashboardTreatmentPaymentsOut


# ---------------------------------------------------------------------------
# Analytics dashboards (ENG-468). Anchor: Marketing / Ad-spend (ENG-470).
# These endpoints live under ``/dashboard/analytics/*`` and follow the same
# thin-composer contract as ``/dashboard/pm/*``: aggregation logic lives in the
# owning domain services (MarketingService for spend, OpsService for leads),
# the route only stitches the cross-domain pieces into one DTO.
# ---------------------------------------------------------------------------


class MarketingKpiOut(BaseModel):
    """One headline marketing KPI.

    ``value`` is ``None`` when the metric has no connected source (e.g. a
    derived ratio whose denominator is zero); the UI renders ``"—"`` rather
    than a misleading ``0``. ``format`` tells the UI how to render the number.
    """

    key: str
    label: str
    value: float | None = None
    format: Literal["currency", "integer", "percent", "ratio"]
    hint: str | None = None


class MarketingDailyPointOut(BaseModel):
    """One (day, provider) point of the daily spend/clicks trend."""

    metric_date: date
    provider: str
    spend: float
    impressions: int
    clicks: int
    conversions: float


class MarketingProviderSplitOut(BaseModel):
    """Window totals for one ad provider (provider-split tile)."""

    provider: str
    spend: float
    impressions: int
    clicks: int
    conversions: float


class MarketingCampaignRowOut(BaseModel):
    """One campaign's performance over the window (campaign table)."""

    provider: str
    campaign_external_id: str
    campaign_name: str | None = None
    spend: float
    impressions: int
    clicks: int
    conversions: float


class MarketingAnalyticsWindowOut(BaseModel):
    """The resolved date window the response was computed over (YYYY-MM-DD)."""

    start_date: date
    end_date: date


class MarketingAnalyticsOut(BaseModel):
    """Marketing / ad-spend analytics dashboard read model (ENG-470).

    A read-only composition over ``MarketingService`` (ad spend) and
    ``OpsService`` (lead counts + the UTM lead-source tree). ``total_leads``
    and the derived ``cpl`` come from ops; everything else from the marketing
    schema. Metrics without an ingested source are surfaced as KPIs with a
    ``None`` value (UI renders ``"—"``), never as fabricated zeros.
    """

    window: MarketingAnalyticsWindowOut
    kpis: list[MarketingKpiOut]
    daily: list[MarketingDailyPointOut]
    providers: list[MarketingProviderSplitOut]
    campaigns: list[MarketingCampaignRowOut]
    # Lead attribution by raw UTM source → medium → campaign, reused from the
    # ops lead-source explorer tree (channels limited to google/facebook/other
    # per the shipped resolver; richer channels deferred to ENG-475).
    lead_sources: list[LeadSourceNodeOut]


# ---------------------------------------------------------------------------
# Full Funnel v2 (ENG-481). The person-anchored report shape now lives in
# ``packages/analytics`` (``FullFunnelV2Out`` + ``FullFunnelService``); the
# route is a thin composer over that service. ``FullFunnelNotConfiguredOut``
# stays here — it is reused by the SEO and follow-up not-configured tiles.
# ---------------------------------------------------------------------------


class FullFunnelNotConfiguredOut(BaseModel):
    """Marker for a dimension we cannot break down yet (ENG-475).

    The UI renders an explicit "not configured" tile instead of fabricating
    zeros. ``ticket`` points at the deferral so the affordance is honest.
    """

    configured: Literal[False] = False
    reason: str
    ticket: str = "ENG-475"


# ---------------------------------------------------------------------------
# SEO / Web Analytics dashboard (ENG-471). Two connected tabs — GA4 (web
# traffic) and GSC (organic search) — read from the ``marketing`` schema
# (``ga_metric_daily`` / ``gsc_query_daily``) via MarketingService aggregation
# reads. Everything else the legacy Replit SEO page showed (Semrush, Microsoft
# Clarity, PageSpeed/Lighthouse, site crawler) is NOT ingested and is surfaced
# as explicit "not connected" sources, never fabricated zeros.
#
# Thin composer: MarketingService owns both window aggregations; the route only
# reuses the marketing KPI value=None convention for derived/absent metrics.
# ---------------------------------------------------------------------------

# Web-analytics sources the legacy SEO page covered that we do NOT ingest. The
# UI renders an explicit "not connected" card for each, instead of a fake 0.
_SEO_NOT_CONNECTED_SOURCES: tuple[str, ...] = (
    "Semrush",
    "Microsoft Clarity",
    "PageSpeed / Lighthouse",
    "Backlinks / Crawler",
)


class SeoGaDailyPointOut(BaseModel):
    """One day of the GA4 traffic trend (summed across captured properties)."""

    metric_date: date
    sessions: int
    total_users: int
    new_users: int
    screen_page_views: int
    conversions: float


class SeoGaChannelRowOut(BaseModel):
    """One acquisition channel's window totals (GA4 channel split, ENG-478)."""

    channel: str
    sessions: int
    total_users: int
    new_users: int
    screen_page_views: int
    conversions: float


class SeoGaPageRowOut(BaseModel):
    """One page's window totals (GA4 top-pages table, ENG-478)."""

    page_path: str
    sessions: int
    total_users: int
    new_users: int
    screen_page_views: int
    conversions: float


class SeoGaOut(BaseModel):
    """GA4 tab — window totals (as KPIs) + the daily traffic trend.

    ``kpis`` carry sessions / total users / new users / page views /
    conversions. ``engagement_kpis`` carry the engagement rollup (ENG-478):
    engaged sessions, engagement rate, avg session duration, bounce rate, event
    count — each ``value=None`` (UI "—") when not captured for the window.
    ``channels`` is the organic/paid/direct split; ``top_pages`` is the top
    landing pages by sessions. Both are empty lists when nothing is ingested.
    """

    connected: bool
    kpis: list[MarketingKpiOut]
    engagement_kpis: list[MarketingKpiOut]
    daily: list[SeoGaDailyPointOut]
    channels: list[SeoGaChannelRowOut]
    top_pages: list[SeoGaPageRowOut]


class SeoGscQueryRowOut(BaseModel):
    """One search query's window totals (GSC top-queries table)."""

    query: str
    clicks: int
    impressions: int
    # Impression-weighted; ``None`` when the query had zero impressions.
    ctr: float | None = None
    position: float | None = None


class SeoGscOut(BaseModel):
    """GSC tab — window totals (as KPIs) + the top-queries table.

    ``kpis`` carry total clicks, total impressions, impression-weighted CTR and
    average position (``value=None`` → UI ``"—"`` on a zero-impression window),
    and the distinct query count. ``top_queries`` is ordered by clicks.
    ``top_pages`` is ``not_configured``: page-level GSC data is not ingested
    (no ``page`` column and the ``extra`` JSONB carries no page rows), so the
    page table is surfaced as a not-connected marker rather than guessed.
    """

    connected: bool
    kpis: list[MarketingKpiOut]
    top_queries: list[SeoGscQueryRowOut]
    top_pages: FullFunnelNotConfiguredOut


class SeoAnalyticsWindowOut(BaseModel):
    """The resolved date window the response was computed over (YYYY-MM-DD)."""

    start_date: date
    end_date: date


class SeoAnalyticsOut(BaseModel):
    """Web Analytics / SEO dashboard read model (ENG-471).

    A read-only composition over ``MarketingService`` GA4 + GSC window
    aggregations. ``ga`` / ``gsc`` carry the two connected tabs; ``not_connected``
    lists the web-analytics sources the legacy SEO page showed that we do not
    ingest (Semrush / Clarity / PageSpeed / crawler), so the UI renders an
    explicit placeholder for each instead of a fabricated zero.
    """

    window: SeoAnalyticsWindowOut
    ga: SeoGaOut
    gsc: SeoGscOut
    not_connected: list[str]


# ---------------------------------------------------------------------------
# Sales Pipeline dashboard (ENG-473). Pipeline value / active opps / close
# rate / won revenue / total Collected, plus pipeline-by-stage, a TC
# leaderboard, and a consultations table.
#
# Thin composer: OpsService owns every opportunity/consultation aggregation
# (won/closed read the ``extra.is_closed`` / ``extra.is_won`` JSON booleans —
# NOT the free-form ``stage`` string; the pipeline-by-stage view groups the
# raw ``stage`` dynamically). InteractionService.collected_by_person is read
# once and bridged into the per-TC / per-consultation aggregation at the route
# (ops never imports interaction, exactly like the full-funnel report). The
# consultations table joins identity for the patient display name (staff
# frontend PHI policy permits it). The patient follow-up call/text/email split
# is PARTIAL — only ``call_logged`` events are ingested (no SMS/email kinds),
# so that breakdown is surfaced as a not-configured marker.
# ---------------------------------------------------------------------------

# Cap on the consultations table so a busy tenant can't pull tens of thousands
# of rows into one dashboard response.
_SALES_CONSULTATIONS_LIMIT = 200


def _ratio_kpi_value(numerator: float, denominator: float) -> float | None:
    """Return ``numerator / denominator``, or ``None`` on a zero base.

    Reuses the marketing ``value=None`` convention so the UI renders ``"—"``
    for a close-rate with no closed opportunities rather than a misleading 0.
    """
    if denominator <= 0:
        return None
    return numerator / denominator


class SalesPipelineStageOut(BaseModel):
    """One opportunity ``stage`` bucket for the pipeline-by-stage chart.

    ``stage`` is the raw free-form ``opportunity.stage`` string (grouped
    dynamically — no hardcoded ladder). ``value`` sums ``amount`` for the
    bucket.
    """

    stage: str
    count: int
    value: float


class SalesTcLeaderboardRowOut(BaseModel):
    """One treatment-coordinator row of the Sales TC leaderboard.

    Grouped by ``opportunity.extra->>'owner_name'``. ``close_rate`` is won ÷
    (won + lost) and is ``None`` when the TC has no closed opportunities (UI
    renders ``"—"``). ``collected`` is net Collected cash of the persons behind
    the TC's opportunities (interaction-domain math bridged in by the route).
    """

    tc: str
    opps: int
    won: int
    lost: int
    close_rate: float | None = None
    value: float
    won_revenue: float
    collected: float


class SalesConsultationOut(BaseModel):
    """One consultation row of the Sales consultations table.

    ``patient`` is the identity display name (staff-frontend PHI policy
    permits it); ``None`` when identity has no record. ``tc`` / ``stage`` /
    ``opp_value`` / ``close_date`` come from the covering opportunity and are
    ``None`` when none is linked. ``paid`` is the person's net Collected cash;
    ``balance`` is ``opp_value − paid`` (``None`` when there is no opportunity
    value to bill against).
    """

    consultation_id: UUID
    patient: str | None = None
    tc: str | None = None
    status: ConsultationStatus
    scheduled_at: datetime
    stage: str | None = None
    opp_value: float | None = None
    paid: float
    balance: float | None = None
    close_date: datetime | None = None


class SalesAnalyticsOut(BaseModel):
    """Sales Pipeline dashboard read model (ENG-473).

    A read-only composition over ``OpsService`` (opportunity / consultation
    aggregations) and ``InteractionService`` (net Collected cash, bridged into
    the per-TC and per-consultation views by the route — ops never imports
    interaction). ``kpis`` reuse the marketing ``value=None`` convention for
    ratios on a zero base. ``followups`` is a not-configured marker: only
    ``call_logged`` interaction events are ingested, so the legacy
    calls/texts/emails follow-up split cannot be reproduced.
    """

    kpis: list[MarketingKpiOut]
    pipeline_by_stage: list[SalesPipelineStageOut]
    tc_leaderboard: list[SalesTcLeaderboardRowOut]
    consultations: list[SalesConsultationOut]
    followups: FullFunnelNotConfiguredOut


# ---------------------------------------------------------------------------
# Calls dashboard (ENG-474). The lowest-priority analytics ticket: almost the
# entire legacy call-center page depends on the unbuilt Phase-3 telephony
# ingest (RingCentral / CallRail). The only call signal we ingest today is the
# two interaction.event kinds ``call_logged`` / ``call_reference_found``, whose
# PHI-free payload carries direction + a (frequently zero) duration. So this
# page renders a small "call volume" KPI set + a cheap booking-rate tile, and
# marks every richer section (per-agent performance, connected/voicemail/missed
# disposition, recordings, transcripts, sentiment, QA scores) explicitly
# pending Phase-3 comms ingest — never as a fabricated zero.
#
# Thin composer: InteractionService owns the call-event aggregation
# (get_call_volume) and the consultation_scheduled count that feeds the
# booking-rate denominator; the route only assembles KPIs (reusing the
# marketing value=None convention for the booking ratio on a zero-call window)
# and lists the pending sections. Default window: trailing 30 days.
# ---------------------------------------------------------------------------

_CALLS_DEFAULT_WINDOW_DAYS = 30

# Legacy call-center sections that need the unbuilt Phase-3 telephony feed.
# Rendered as explicit "pending" cards so the gap is honest, never a fake 0.
_CALLS_PENDING_SECTIONS: tuple[str, ...] = (
    "Call disposition (connected / voicemail / missed)",
    "Per-agent performance & scorecards",
    "Average QA score",
    "Call recordings playback",
    "Transcripts",
    "Sentiment analysis",
    "Backfill / transcription stats",
)


class CallsAnalyticsWindowOut(BaseModel):
    """The resolved date window the response was computed over (YYYY-MM-DD)."""

    start_date: date
    end_date: date


class CallsAnalyticsOut(BaseModel):
    """Calls dashboard read model (ENG-474).

    A read-only composition over ``InteractionService`` call-event reads.
    ``kpis`` reuse the marketing ``MarketingKpiOut`` shape (``value=None`` →
    UI ``"—"``): call volume, inbound/outbound split, average talk time, and a
    booking rate (``consultation_scheduled`` ÷ ``call_logged`` in the window,
    ``None`` on a zero-call window). ``connected`` is ``True`` once any call
    event exists in the window so the UI can show an empty state instead of
    fake numbers. ``pending`` lists the legacy call-center sections that need
    the unbuilt Phase-3 telephony ingest (RingCentral / CallRail) — the UI
    renders an explicit "pending Phase 3 comms ingest" card for each.
    """

    window: CallsAnalyticsWindowOut
    connected: bool
    kpis: list[MarketingKpiOut]
    pending: list[str]


def _start_of_today_utc() -> datetime:
    now = datetime.now(tz=UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _bucket_items(
    raw: dict[str, int], labels: dict[str, str] | None = None
) -> list[DashboardBucketOut]:
    labels = labels or {}
    return [
        DashboardBucketOut(
            key=key,
            label=labels.get(key, key.replace("_", " ").title()),
            count=count,
        )
        for key, count in raw.items()
    ]


@router.get("/summary", response_model=DashboardSummaryOut)
async def summary(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    ops: Annotated[OpsService, Depends(get_ops_service)],
    phi: Annotated[PhiService, Depends(get_phi_service)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
) -> DashboardSummaryOut:
    tenant_id = principal.require_tenant()

    start_today = _start_of_today_utc()
    start_tomorrow = start_today + timedelta(days=1)
    start_next_week = start_today + timedelta(days=7)

    lead_counts = await ops.get_lead_status_counts(tenant_id)
    consultations_today = await phi.count_consultations_between(
        tenant_id, start_today, start_tomorrow
    )
    consultations_this_week = await phi.count_consultations_between(
        tenant_id, start_today, start_next_week
    )

    persons = await identity.list_recent(tenant_id, _RECENT_PERSON_LIMIT)
    person_uids = [p.id for p in persons]
    lead_uids = await ops.has_lead_for(tenant_id, person_uids)
    consultation_uids = await phi.person_uids_with_consultation(tenant_id, person_uids)
    sources_map = await identity.source_providers_for(tenant_id, person_uids)

    recent_persons = [
        PersonSummaryOut(
            id=p.id,
            display_name=p.display_name
            or " ".join(s for s in (p.given_name, p.family_name) if s)
            or "Unknown",
            email=next((i.value for i in p.identifiers if i.kind == "email"), None),
            phone=next((i.value for i in p.identifiers if i.kind == "phone"), None),
            has_lead=p.id in lead_uids,
            has_consultation=p.id in consultation_uids,
            last_activity_at=p.updated_at,
            source_providers=sources_map.get(p.id, []),
        )
        for p in persons
    ]

    pipeline_total = sum(
        count for status, count in lead_counts.items() if status not in _PIPELINE_EXCLUDE_STATUSES
    )

    return DashboardSummaryOut(
        lead_counts=lead_counts,
        consultations_today=consultations_today,
        consultations_this_week=consultations_this_week,
        recent_persons=recent_persons,
        pipeline_total=pipeline_total,
    )


@router.get("/pm", response_model=DashboardPmOut)
async def pm_dashboard(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    ops: Annotated[OpsService, Depends(get_ops_service)],
    interaction: Annotated[InteractionService, Depends(get_interaction_service)],
    integrations: Annotated[IntegrationService, Depends(get_integration_service)],
    ingest: Annotated[IngestService, Depends(get_ingest_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    source_provider: Annotated[Literal["salesforce", "carestack"] | None, Query()] = None,
    lead_source: Annotated[str | None, Query(max_length=120)] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
) -> DashboardPmOut:
    """Return the Project Manager dashboard read model.

    This is a read-only composition over existing CRM-safe projections. It
    intentionally returns operational summaries and aggregate counters, not raw
    provider payloads or clinical free text.
    """
    tenant_id = principal.require_tenant()
    clean_q = q.strip() if q is not None else None
    if clean_q == "":
        clean_q = None

    # Resolve location labels + soft-match needles up front so the lead
    # aggregates (which use Lead.extra->>'assigned_center' LIKE matching)
    # can run with the same scoped filter as consultation aggregates.
    location_service = LocationService(db)
    location_rows = await location_service.list_locations(tenant_id)
    location_labels: dict[str, str] = {}
    location_match: list[str] | None = None
    for loc in location_rows:
        label = loc.short_name or loc.name or str(loc.id)[:8]
        if loc.city:
            label = f"{label} · {loc.city}"
        location_labels[str(loc.id)] = label
        if location_id is not None and loc.id == location_id:
            location_match = [
                s for s in (loc.short_name, loc.name, loc.city) if s
            ]

    now = datetime.now(tz=UTC)
    lead_source_profile = await ops.get_lead_source_profile(
        tenant_id,
        created_from=from_,
        created_to=to,
        source_provider=source_provider,
        location_match=location_match,
        limit=10,
    )
    lead_conversion = await ops.get_conversion_funnel_analytics(
        tenant_id,
        created_from=from_,
        created_to=to,
        source_provider=source_provider,
        lead_source=lead_source,
        location_match=location_match,
        location_id=location_id,
    )
    paid_leads = await ops.get_paid_leads_analytics(
        tenant_id,
        created_from=from_,
        created_to=to,
        source_provider=source_provider,
        location_match=location_match,
        limit=10,
    )
    consultation_followup = await ops.get_consultation_followup_analytics(
        tenant_id,
        scheduled_from=from_,
        scheduled_to=to,
        source_provider=source_provider,
        location_id=location_id,
        now=now,
    )
    consultation_source_counts = await ops.get_consultation_source_counts(
        tenant_id,
        scheduled_from=from_,
        scheduled_to=to,
        location_id=location_id,
    )
    consultation_location_counts = await ops.get_consultation_location_counts(
        tenant_id,
        scheduled_from=from_,
        scheduled_to=to,
        source_provider=source_provider,
    )

    recent_activity = await interaction.list_recent_operational_events(
        tenant_id,
        limit=25,
        occurred_from=from_,
        occurred_to=to,
        source_provider=source_provider,
        query=clean_q,
    )
    treatment_payment_aggregate = await interaction.get_treatment_payment_aggregate(
        tenant_id,
        occurred_from=from_,
        occurred_to=to,
        source_provider=source_provider,
        location_id=location_id,
    )
    if source_provider in (None, "carestack"):
        outstanding_balances = await ingest.latest_payment_summary_balances(tenant_id)
    else:
        outstanding_balances = None
    latest_runs = await integrations.list_latest_runs_for_tenant(
        tenant_id,
        provider=source_provider,
        limit=10,
    )

    lead_counts = {bucket.key: bucket.count for bucket in lead_conversion.lead_status}
    consultation_counts = {
        bucket.key: bucket.count for bucket in lead_conversion.consultation_status
    }
    lead_source_counts = {
        bucket.key: bucket.count for bucket in lead_source_profile.sources
    }
    pipeline_total = lead_conversion.pipeline_total
    consultations_total = lead_conversion.consultations_total
    completed_consultations = lead_conversion.completed_consultations
    open_followups = consultation_followup.open_followups
    overdue_followups = consultation_followup.overdue_followups

    lead_labels = {str(status): status.value.replace("_", " ").title() for status in LeadStatus}
    consultation_labels = {
        str(status): status.value.replace("_", " ").title() for status in ConsultationStatus
    }

    return DashboardPmOut(
        filters=DashboardAppliedFiltersOut(
            from_=from_,
            to=to,
            source_provider=source_provider,
            lead_source=lead_source,
            location_id=location_id,
            q=clean_q,
        ),
        kpis=[
            DashboardKpiOut(
                key="pipeline_total",
                label="Pipeline",
                value=pipeline_total,
                hint="Active leads excluding lost",
            ),
            DashboardKpiOut(
                key="consultations_total",
                label="Consultations",
                value=consultations_total,
                hint="Scheduled records in the selected window",
            ),
            DashboardKpiOut(
                key="completed_consultations",
                label="Completed consults",
                value=completed_consultations,
            ),
            DashboardKpiOut(
                key="open_followups",
                label="Open followups",
                value=open_followups,
            ),
            DashboardKpiOut(
                key="overdue_followups",
                label="Overdue followups",
                value=overdue_followups,
            ),
        ],
        funnel=[
            DashboardFunnelStageOut(
                key="lead_new",
                label="New leads",
                count=lead_counts.get(str(LeadStatus.NEW), 0),
                hint="SF leads with status=new created in the window",
            ),
            DashboardFunnelStageOut(
                key="lead_qualified",
                label="Qualified",
                count=lead_counts.get(str(LeadStatus.QUALIFIED), 0),
                hint="SF leads that moved to status=qualified",
            ),
            DashboardFunnelStageOut(
                key="lead_contacted",
                label="Contacted",
                count=lead_counts.get(str(LeadStatus.CONTACTED), 0),
                hint="SF leads with status=contacted (call/email logged)",
            ),
            DashboardFunnelStageOut(
                key="lead_booked",
                label="Booked",
                count=lead_counts.get(str(LeadStatus.BOOKED), 0),
                hint="SF leads with status=booked (consult requested)",
            ),
            DashboardFunnelStageOut(
                key="consultation_scheduled",
                label="Consult scheduled",
                count=consultation_counts.get(str(ConsultationStatus.SCHEDULED), 0),
                hint="Consultations created in the window with status=scheduled",
            ),
            DashboardFunnelStageOut(
                key="consultation_completed",
                label="Consult completed",
                count=completed_consultations,
                hint="Consultations created in the window with status=completed",
            ),
        ],
        breakdowns=[
            DashboardBreakdownOut(
                key="lead_status",
                label="Lead status",
                items=_bucket_items(lead_counts, lead_labels),
            ),
            DashboardBreakdownOut(
                key="consultation_status",
                label="Consultation status",
                items=_bucket_items(consultation_counts, consultation_labels),
            ),
            DashboardBreakdownOut(
                key="lead_source",
                label="Lead source",
                items=_bucket_items(lead_source_counts),
            ),
            DashboardBreakdownOut(
                key="source_provider",
                label="Source provider",
                items=_bucket_items(consultation_source_counts),
            ),
            DashboardBreakdownOut(
                key="location",
                label="Consultations by location",
                items=_bucket_items(
                    {
                        (loc_id if loc_id is not None else "no_location"): count
                        for loc_id, count in consultation_location_counts.items()
                    },
                    {
                        **location_labels,
                        "no_location": "No location set",
                    },
                ),
            ),
        ],
        semantic_analytics=[
            _semantic_read_model(
                query_id="lead_source_profile.v1",
                read_model_id="lead_source_profile",
                title="Lead source profile",
                data_classes=["ops", "integration_metadata"],
                definition_versions={"lead_source": "v1", "source_provider": "v1"},
                row_count=len(lead_source_profile.sources),
                metrics=[
                    DashboardSemanticMetricOut(
                        key="total_leads",
                        label="Total leads",
                        value=lead_source_profile.total_leads,
                    )
                ],
            ),
            _semantic_read_model(
                query_id="lead_conversion_funnel.v1",
                read_model_id="lead_conversion",
                title="Lead conversion",
                data_classes=["ops", "integration_metadata"],
                definition_versions={
                    "lead_source": "v1",
                    "consultation_scheduled": "v1",
                    "consultation_completed": "v1",
                },
                row_count=len(lead_conversion.lead_status)
                + len(lead_conversion.consultation_status),
                metrics=[
                    DashboardSemanticMetricOut(
                        key="pipeline_total",
                        label="Pipeline",
                        value=pipeline_total,
                    ),
                    DashboardSemanticMetricOut(
                        key="consultations_total",
                        label="Consultations",
                        value=consultations_total,
                    ),
                    DashboardSemanticMetricOut(
                        key="completed_consultations",
                        label="Completed",
                        value=completed_consultations,
                    ),
                ],
            ),
            _semantic_read_model(
                query_id="paid_leads_by_source.v1",
                read_model_id="paid_leads",
                title="Paid leads",
                data_classes=["ops", "integration_metadata"],
                definition_versions={"paid_lead": "v1", "lead_source": "v1"},
                row_count=len(paid_leads.sources),
                metrics=[
                    DashboardSemanticMetricOut(
                        key="total_paid_leads",
                        label="Paid leads",
                        value=paid_leads.total_paid_leads,
                    )
                ],
            ),
            _semantic_read_model(
                query_id="consultation_followup_worklist.v1",
                read_model_id="consultation_followup",
                title="Consultation follow-up",
                data_classes=["ops", "integration_metadata"],
                definition_versions={
                    "consultation_completed": "v1",
                    "stale_followup": "v1",
                },
                row_count=len(consultation_followup.consultation_status),
                metrics=[
                    DashboardSemanticMetricOut(
                        key="open_followups",
                        label="Open",
                        value=open_followups,
                    ),
                    DashboardSemanticMetricOut(
                        key="overdue_followups",
                        label="Overdue",
                        value=overdue_followups,
                    ),
                ],
            ),
            _semantic_read_model(
                query_id="treatment_revenue_evidence.v1",
                read_model_id="treatment_revenue",
                title="Treatment revenue",
                data_classes=["billing", "integration_metadata"],
                definition_versions={"payment_received": "v1", "revenue_evidence": "v1"},
                row_count=0,
                metrics=[
                    DashboardSemanticMetricOut(
                        key="collected_total",
                        label="Collected",
                        value=treatment_payment_aggregate.collected_total,
                    ),
                    DashboardSemanticMetricOut(
                        key="payment_event_count",
                        label="Payments",
                        value=treatment_payment_aggregate.payment_event_count,
                    ),
                ],
            ),
        ],
        recent_activity=recent_activity,
        sync_health=[
            DashboardSyncRunOut(
                provider=provider,
                object_scope=str(run.meta.get("object_scope") or run.sf_object or ""),
                status=run.status,
                started_at=run.started_at,
                finished_at=run.finished_at,
                records_total=run.records_total,
                records_succeeded=run.records_succeeded,
                records_failed=run.records_failed,
                error=run.error,
            )
            for run, provider in latest_runs
        ],
        treatment_payments=DashboardTreatmentPaymentsOut(
            status="available",
            message=_treatment_payment_message(source_provider),
            treatment_presented_count=(
                treatment_payment_aggregate.treatment_presented_count
            ),
            treatment_completed_count=(
                treatment_payment_aggregate.treatment_completed_count
            ),
            invoice_count=treatment_payment_aggregate.invoice_count,
            payment_total_amount=treatment_payment_aggregate.payment_total_amount,
            collected_total=treatment_payment_aggregate.collected_total,
            payment_event_count=treatment_payment_aggregate.payment_event_count,
            outstanding_total=(
                outstanding_balances.outstanding_total
                if outstanding_balances is not None
                else 0.0
            ),
            outstanding_patient_count=(
                outstanding_balances.patient_count
                if outstanding_balances is not None
                else 0
            ),
            has_partial_payments=(
                treatment_payment_aggregate.payment_event_count > 0
                and (
                    outstanding_balances is not None
                    and outstanding_balances.outstanding_total > 0.0
                )
            ),
            first_payment_at=treatment_payment_aggregate.first_payment_at,
            last_payment_at=treatment_payment_aggregate.last_payment_at,
            ar_risk_count=(
                outstanding_balances.ar_risk_count
                if outstanding_balances is not None
                else None
            ),
        ),
    )


def _semantic_read_model(
    *,
    query_id: str,
    read_model_id: str,
    title: str,
    data_classes: list[str],
    definition_versions: dict[str, str],
    row_count: int,
    metrics: list[DashboardSemanticMetricOut],
) -> DashboardSemanticReadModelOut:
    return DashboardSemanticReadModelOut(
        query_id=query_id,
        read_model_id=read_model_id,
        title=title,
        data_classes=data_classes,
        definition_versions=definition_versions,
        row_count=row_count,
        drilldown_available=False,
        export_available=True,
        metrics=metrics,
    )


# Distinct lead-source values are vendor-defined but few (tens, not
# thousands); this cap only guards against pathological data.
_PM_LEAD_SOURCE_BUCKET_LIMIT = 100


@router.get("/pm/lead-sources", response_model=DashboardPmLeadSourcesOut)
async def pm_lead_sources(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    ops: Annotated[OpsService, Depends(get_ops_service)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
) -> DashboardPmLeadSourcesOut:
    """Return lead-source filter options grouped by provider.

    Salesforce buckets use the same coalesced source label the dashboard
    aggregates group by, so each option's count matches what an ``exact``
    ``lead_source`` filter on ``/pm/leads`` returns. CareStack rows on the
    leads page are patient source links and carry no lead source yet, so
    that provider exposes only its total.
    """
    tenant_id = principal.require_tenant()
    sf_buckets = await ops.get_lead_source_counts(
        tenant_id,
        created_from=from_,
        created_to=to,
        source_provider="salesforce",
        limit=_PM_LEAD_SOURCE_BUCKET_LIMIT,
    )
    cs_total = await identity.count_source_links_for_dashboard(
        tenant_id,
        source_system="carestack",
        source_kind="patient",
        first_seen_from=from_,
        first_seen_to=to,
    )
    return DashboardPmLeadSourcesOut(
        providers=[
            DashboardPmLeadSourceProviderOut(
                provider="salesforce",
                total=sum(sf_buckets.values()),
                sources=[
                    DashboardPmLeadSourceBucketOut(key=key, count=count)
                    for key, count in sf_buckets.items()
                ],
            ),
            DashboardPmLeadSourceProviderOut(
                provider="carestack",
                total=cs_total,
                sources=[],
            ),
        ]
    )


@router.get("/pm/leads", response_model=DashboardPmLeadListOut)
async def pm_leads(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
    ops: Annotated[OpsService, Depends(get_ops_service)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    source_provider: Annotated[Literal["salesforce", "carestack"] | None, Query()] = None,
    lead_source: Annotated[str | None, Query(max_length=120)] = None,
    lead_source_match: Annotated[Literal["contains", "exact"], Query()] = "contains",
    status: Annotated[str | None, Query(max_length=64)] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    linked_only: Annotated[bool, Query()] = False,
    location_tab: Annotated[
        Literal["galleria", "fusion", "el_dorado", "cosmo"] | None, Query()
    ] = None,
    sort: Annotated[Literal["lead", "appointment"], Query()] = "lead",
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DashboardPmLeadListOut:
    """Return individual lead rows for the Project Manager workspace.

    ``location_tab`` (ENG-560) buckets each person into exactly one clinic
    tab and keeps only rows whose resolved tab matches. The classifier lives
    in :meth:`OpsService.classify_location_tabs` (latest consultation wins,
    else SF ``assigned_center``). It is a pure server-side filter — the row
    DTO is unchanged. When ``None`` the handler behaves exactly as before.
    """
    tenant_id = principal.require_tenant()
    clean_q = q.strip() if q is not None else None
    if clean_q == "":
        clean_q = None

    clean_status = status.strip() if status is not None else None
    if clean_status == "":
        clean_status = None

    include_salesforce = source_provider in (None, "salesforce")
    include_carestack = source_provider in (None, "carestack")
    # A location_tab filter post-filters candidates per person, so it cannot
    # use the page-sized light fetch + count_override path (same as q/status).
    light_page = (
        not linked_only
        and clean_q is None
        and clean_status is None
        and location_tab is None
    )
    candidate_limit = offset + limit if light_page else _PM_LEADS_CANDIDATE_LIMIT
    total_override: int | None = None

    if light_page:
        salesforce_total = (
            await ops.count_leads_for_dashboard(
                tenant_id,
                created_from=from_,
                created_to=to,
                lead_source=lead_source,
                lead_source_match=lead_source_match,
                source_provider="salesforce",
            )
            if include_salesforce
            else 0
        )
        carestack_total = (
            await identity.count_source_links_for_dashboard(
                tenant_id,
                source_system="carestack",
                source_kind="patient",
                first_seen_from=from_,
                first_seen_to=to,
            )
            if include_carestack and lead_source is None
            else 0
        )
        total_override = salesforce_total + carestack_total

    rows = (
        await ops.list_leads_for_dashboard(
            tenant_id,
            created_from=from_,
            created_to=to,
            status=clean_status,
            lead_source=lead_source,
            lead_source_match=lead_source_match,
            source_provider="salesforce",
            limit=candidate_limit,
        )
        if include_salesforce
        else []
    )
    carestack_links = (
        await identity.source_links_for_dashboard(
            tenant_id,
            source_system="carestack",
            source_kind="patient",
            first_seen_from=from_,
            first_seen_to=to,
            limit=candidate_limit,
        )
        if include_carestack and lead_source is None
        else []
    )

    person_uids = [row.person_uid for row in rows] + [link.person_uid for link in carestack_links]
    persons = await identity.list_by_ids(tenant_id, person_uids)
    person_by_uid = {person.id: person for person in persons}
    sources_map = await identity.source_providers_for(tenant_id, person_uids)
    all_person_uids_for_consult = person_uids
    latest_consultations = await ops.latest_consultations_for_persons(
        tenant_id,
        all_person_uids_for_consult,
    )
    # ENG-560: resolve each person's single clinic tab once, reusing the
    # consultations already fetched above. Empty when no tab filter is active.
    location_tabs_by_uid = (
        await ops.classify_location_tabs(
            tenant_id,
            all_person_uids_for_consult,
            latest_consultations=latest_consultations,
        )
        if location_tab is not None
        else {}
    )
    location_svc = LocationService(db)
    locations_cache: dict[UUID, str] = {}

    async def _location_name(location_id: UUID | None) -> str | None:
        if location_id is None:
            return None
        if location_id in locations_cache:
            return locations_cache[location_id]
        try:
            loc = await location_svc.get_location(tenant_id, location_id)
            # Two locations can share the same name (Roseville + El Dorado
            # Hills both as "Fusion Dental Implants"); append city when
            # available so operators can tell them apart at a glance.
            base = loc.name or "Unknown"
            if loc.city:
                base = f"{base} · {loc.city}"
            locations_cache[location_id] = base
        except Exception:
            locations_cache[location_id] = "Unknown"
        return locations_cache[location_id]

    items: list[DashboardPmLeadOut] = []
    for row in rows:
        if location_tab is not None and location_tabs_by_uid.get(row.person_uid) != location_tab:
            continue
        person = person_by_uid.get(row.person_uid)
        display_name = (
            person.display_name if person is not None and person.display_name else "Unknown"
        )
        email = (
            next((i.value for i in person.identifiers if i.kind == "email"), None)
            if person is not None
            else None
        )
        phone = (
            next((i.value for i in person.identifiers if i.kind == "phone"), None)
            if person is not None
            else None
        )
        source_external_id = _string_or_none(row.extra.get("sf_lead_id"))
        source_provider_out: Literal["salesforce", "carestack", "manual", "unknown"]
        if source_external_id:
            source_provider_out = "salesforce"
        elif row.source:
            source_provider_out = "manual"
        else:
            source_provider_out = "unknown"

        consult = latest_consultations.get(row.person_uid)
        item = DashboardPmLeadOut(
            id=row.id,
            person_uid=row.person_uid,
            display_name=display_name,
            given_name=person.given_name if person is not None else None,
            family_name=person.family_name if person is not None else None,
            email=email,
            phone=phone,
            status=str(row.status),
            # ENG-382 effective source: same coalesce chain as the
            # repository's _lead_source_label, materialised per row.
            lead_source=row.source
            or _string_or_none(row.extra.get("lead_source"))
            or _string_or_none(row.extra.get("hubspot_lead_source"))
            or _string_or_none(row.extra.get("utm_source")),
            source_provider=source_provider_out,
            source_external_id=source_external_id,
            created_at=_parse_sf_iso_or_none(row.extra.get("sf_created_at")) or row.created_at,
            updated_at=row.updated_at,
            source_providers=sources_map.get(row.person_uid, []),
            consultation_status=str(consult.status) if consult else None,
            consultation_scheduled_at=consult.scheduled_at if consult else None,
            consultation_provider_created_at=consult.provider_created_at if consult else None,
            consultation_provider=consult.source_provider if consult else None,
            location_name=await _location_name(consult.location_id if consult else None),
        )
        if clean_q and not _lead_matches_query(item, clean_q):
            continue
        if linked_only and not _has_salesforce_and_carestack_links(item.source_providers):
            continue
        items.append(item)

    for link in carestack_links:
        if location_tab is not None and location_tabs_by_uid.get(link.person_uid) != location_tab:
            continue
        person = person_by_uid.get(link.person_uid)
        display_name = (
            person.display_name if person is not None and person.display_name else "Unknown"
        )
        email = (
            next((i.value for i in person.identifiers if i.kind == "email"), None)
            if person is not None
            else None
        )
        phone = (
            next((i.value for i in person.identifiers if i.kind == "phone"), None)
            if person is not None
            else None
        )
        latest_consultation = latest_consultations.get(link.person_uid)
        carestack_status = (
            str(latest_consultation.status)
            if latest_consultation is not None
            else "carestack_patient"
        )
        item = DashboardPmLeadOut(
            id=link.id,
            person_uid=link.person_uid,
            display_name=display_name,
            given_name=person.given_name if person is not None else None,
            family_name=person.family_name if person is not None else None,
            email=email,
            phone=phone,
            status=carestack_status,
            lead_source="CareStack patient",
            source_provider="carestack",
            source_external_id=link.source_id,
            created_at=link.first_seen_at,
            updated_at=link.last_seen_at,
            source_providers=sources_map.get(link.person_uid, []),
            consultation_status=str(latest_consultation.status) if latest_consultation else None,
            consultation_scheduled_at=latest_consultation.scheduled_at if latest_consultation else None,
            consultation_provider_created_at=latest_consultation.provider_created_at if latest_consultation else None,
            consultation_provider=latest_consultation.source_provider if latest_consultation else None,
            location_name=await _location_name(latest_consultation.location_id if latest_consultation else None),
        )
        if clean_status and item.status != clean_status:
            continue
        if clean_q and not _lead_matches_query(item, clean_q):
            continue
        if linked_only and not _has_salesforce_and_carestack_links(item.source_providers):
            continue
        items.append(item)

    if linked_only:
        grouped: dict[UUID, list[DashboardPmLeadOut]] = {}
        for item in items:
            grouped.setdefault(item.person_uid, []).append(item)

        for uid, group in list(grouped.items()):
            providers_in_group = {i.source_provider for i in group}
            first = group[0]
            consult = latest_consultations.get(uid)

            if "salesforce" not in providers_in_group:
                sf_lead = await ops.get_lead_for_person(tenant_id, uid)
                if sf_lead is not None:
                    sf_id = _string_or_none(sf_lead.extra.get("sf_lead_id"))
                    group.append(DashboardPmLeadOut(
                        id=sf_lead.id,
                        person_uid=uid,
                        display_name=first.display_name,
                        given_name=first.given_name,
                        family_name=first.family_name,
                        email=first.email,
                        phone=first.phone,
                        status=str(sf_lead.status),
                        lead_source=sf_lead.source,
                        source_provider="salesforce",
                        source_external_id=sf_id,
                        created_at=_parse_sf_iso_or_none(sf_lead.extra.get("sf_created_at"))
                        or sf_lead.created_at,
                        updated_at=sf_lead.updated_at,
                        source_providers=sources_map.get(uid, []),
                        consultation_status=str(consult.status) if consult else None,
                        consultation_scheduled_at=consult.scheduled_at if consult else None,
                        consultation_provider_created_at=consult.provider_created_at if consult else None,
                        consultation_provider=consult.source_provider if consult else None,
                        location_name=await _location_name(consult.location_id if consult else None),
                    ))

            if "carestack" not in providers_in_group:
                cs_link = await identity.find_source_link(
                    tenant_id,
                    source_system="carestack",
                    source_kind="patient",
                    person_uid=uid,
                )
                if cs_link is not None:
                    cs_consultation = latest_consultations.get(uid)
                    carestack_status = (
                        str(cs_consultation.status) if cs_consultation else "carestack_patient"
                    )
                    group.append(DashboardPmLeadOut(
                        id=cs_link.id,
                        person_uid=uid,
                        display_name=first.display_name,
                        given_name=first.given_name,
                        family_name=first.family_name,
                        email=first.email,
                        phone=first.phone,
                        status=carestack_status,
                        lead_source="CareStack patient",
                        source_provider="carestack",
                        source_external_id=cs_link.source_id,
                        created_at=cs_link.first_seen_at,
                        updated_at=cs_link.last_seen_at,
                        source_providers=sources_map.get(uid, []),
                        consultation_status=str(cs_consultation.status) if cs_consultation else None,
                        consultation_scheduled_at=cs_consultation.scheduled_at if cs_consultation else None,
                        consultation_provider_created_at=cs_consultation.provider_created_at if cs_consultation else None,
                        consultation_provider=cs_consultation.source_provider if cs_consultation else None,
                        location_name=await _location_name(cs_consultation.location_id if cs_consultation else None),
                    ))

        flat: list[DashboardPmLeadOut] = []
        for uid in sorted(
            grouped,
            key=lambda u: max(
                (i.consultation_provider_created_at or datetime.min.replace(tzinfo=UTC))
                for i in grouped[u]
            ),
            reverse=True,
        ):
            flat.extend(
                sorted(grouped[uid], key=lambda i: i.source_provider)
            )
        items = flat
        total = len(grouped)
        sorted_uids = sorted(
            grouped,
            key=lambda u: max(
                (i.consultation_provider_created_at or datetime.min.replace(tzinfo=UTC))
                for i in grouped[u]
            ),
            reverse=True,
        )
        page_person_uids = set(sorted_uids[offset : offset + limit])
        page_items = [i for i in items if i.person_uid in page_person_uids]
    elif location_tab is not None:
        # Location tabs render ONE unified card per person, so paginate by PERSON,
        # not by row: a Salesforce+CareStack person is two rows but one card, and
        # row-level pagination would double-count them in `total`, consume two page
        # slots, and split them across pages. Mirrors the linked_only grouping.
        # Person order defaults to lead/funnel date ("who came in"); sort=appointment
        # flips to appointment-creation time so recently-booked persons (and
        # lead->appointment doubles) surface. created_at = sf_created_at / lead
        # created / CareStack first_seen (ENG-559).
        grouped_tab: dict[UUID, list[DashboardPmLeadOut]] = {}
        for item in items:
            grouped_tab.setdefault(item.person_uid, []).append(item)

        def _tab_person_key(uid: UUID) -> datetime:
            if sort == "appointment":
                return max(
                    (i.consultation_provider_created_at or datetime.min.replace(tzinfo=UTC))
                    for i in grouped_tab[uid]
                )
            return max(
                (i.created_at or datetime.min.replace(tzinfo=UTC)) for i in grouped_tab[uid]
            )

        sorted_uids = sorted(grouped_tab, key=_tab_person_key, reverse=True)
        items = [
            row
            for uid in sorted_uids
            for row in sorted(grouped_tab[uid], key=lambda i: i.source_provider)
        ]
        total = len(grouped_tab)
        page_person_uids = set(sorted_uids[offset : offset + limit])
        page_items = [i for i in items if i.person_uid in page_person_uids]
    else:
        items = sorted(
            items,
            key=lambda item: item.consultation_provider_created_at
            or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        total = total_override if total_override is not None else len(items)
        page_items = items[offset : offset + limit]

    return DashboardPmLeadListOut(
        items=page_items,
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_previous=offset > 0,
        filters=DashboardAppliedFiltersOut(
            from_=from_,
            to=to,
            source_provider=source_provider,
            lead_source=lead_source,
            location_id=None,
            q=clean_q,
        ),
    )


async def _build_payment_items(
    *,
    db: AsyncSession,
    ops: OpsService,
    identity: IdentityService,
    ingest: IngestService,
    tenant_id: TenantId,
    events: list[Any],
) -> list[DashboardPmPaymentOut]:
    """Project interaction payment events into PM Payments row DTOs.

    Shared by the flat list and the ENG-410 same-day groups endpoint so the
    leg rows inside a group are byte-identical to the flat rows. Batched
    lookups only (identity, leads, consults, balances, invoices, locations)
    — no per-row N+1.
    """
    person_uids = list({event.person_uid for event in events})
    persons = await identity.list_by_ids(tenant_id, person_uids) if person_uids else []
    person_by_uid = {person.id: person for person in persons}
    leads_by_uid = (
        await ops.latest_leads_for_persons(tenant_id, person_uids)
        if person_uids
        else {}
    )
    consults_by_uid = (
        await ops.latest_consultations_for_persons(tenant_id, person_uids)
        if person_uids
        else {}
    )

    # ENG-306: resolve a per-person authoritative balance for the row's
    # pill. One identity round-trip for the page's persons, one ingest
    # round-trip across all CareStack patient ids — no per-row N+1.
    source_links_by_uid = (
        await identity.source_links_for_persons(tenant_id, person_uids)
        if person_uids
        else {}
    )
    carestack_patient_ids_by_person: dict[UUID, list[str]] = {}
    all_carestack_patient_ids: set[str] = set()
    for person_uid, links in source_links_by_uid.items():
        per_person_ids = [
            link.source_id
            for link in links
            if link.source_system == "carestack"
            and link.source_kind == "patient"
            and link.source_id is not None
        ]
        if per_person_ids:
            carestack_patient_ids_by_person[person_uid] = per_person_ids
            all_carestack_patient_ids.update(per_person_ids)
    balance_by_patient = (
        await ingest.latest_balance_by_patient(
            tenant_id, sorted(all_carestack_patient_ids)
        )
        if all_carestack_patient_ids
        else {}
    )

    # ENG-303: resolve each payment's invoice (number + date) from the
    # captured CareStack invoice raw rows. invoice_id lives on the payment
    # event payload; number/date come from the invoice feed.
    invoice_ids = list(
        {
            inv
            for event in events
            if (inv := _string_or_none((event.payload or {}).get("invoice_id")))
            is not None
        }
    )
    invoice_refs = (
        await ingest.get_carestack_invoice_refs(tenant_id, invoice_ids)
        if invoice_ids
        else {}
    )

    # ENG-547: resolve each payment's operation code + performing doctor from
    # the accounting-transaction raw payload (procedureCodeId / providerId).
    # Keyed by the raw_event PK each payment was projected from (1:1 link);
    # one batched ingest round-trip across the page, no per-row N+1.
    payment_raw_ids = list(
        {event.source_event_id for event in events if event.source_event_id is not None}
    )
    procedure_doctor_refs = (
        await ingest.get_payment_procedure_doctor_refs(tenant_id, payment_raw_ids)
        if payment_raw_ids
        else {}
    )

    location_svc = LocationService(db)
    locations_cache: dict[UUID, str] = {}

    async def _location_name(loc_id: UUID | None) -> str | None:
        if loc_id is None:
            return None
        if loc_id in locations_cache:
            return locations_cache[loc_id]
        try:
            loc = await location_svc.get_location(tenant_id, loc_id)
            base = loc.name or "Unknown"
            if loc.city:
                base = f"{base} · {loc.city}"
            locations_cache[loc_id] = base
        except Exception:
            locations_cache[loc_id] = "Unknown"
        return locations_cache[loc_id]

    items: list[DashboardPmPaymentOut] = []
    for event in events:
        payload = event.payload or {}
        person = person_by_uid.get(event.person_uid)
        display_name = (
            person.display_name
            if person is not None and person.display_name
            else "Unknown"
        )
        lead = leads_by_uid.get(event.person_uid)
        consult = consults_by_uid.get(event.person_uid)

        payload_location = _uuid_or_none(payload.get("location_id"))
        amount_value = _float_or_none(payload.get("amount"))
        transaction_type = _string_or_none(payload.get("transaction_type"))
        invoice_id = _string_or_none(payload.get("invoice_id"))
        invoice_ref = invoice_refs.get(invoice_id) if invoice_id else None

        # Pydantic validates source_provider against the Literal union below,
        # so cast through ``str`` first; an unexpected provider in the DB
        # would surface as a 500 here (safer than silently rendering it).
        provider_value = event.source_provider
        if provider_value not in ("salesforce", "carestack"):
            # Defensive: event.source_provider is constrained at write time,
            # but if a legacy row sneaks in we drop it from the dashboard.
            continue
        provider_literal: Literal["salesforce", "carestack"] = provider_value  # type: ignore[assignment]

        # ENG-306: derive the per-row balance from the latest snapshot.
        # Sum across patient ids when one person has multiple CS links.
        # Absent patient ids (no snapshot yet) → ``None`` so the UI pill
        # renders ``"—"`` rather than misleading ``"$0"``.
        row_patient_ids = carestack_patient_ids_by_person.get(event.person_uid, [])
        row_balance_pieces = [
            balance_by_patient[pid]
            for pid in row_patient_ids
            if pid in balance_by_patient
        ]
        row_balance = sum(row_balance_pieces) if row_balance_pieces else None

        # ENG-547: operation code + performing doctor for this payment leg.
        proc_doctor = (
            procedure_doctor_refs.get(event.source_event_id)
            if event.source_event_id is not None
            else None
        ) or {}

        items.append(
            DashboardPmPaymentOut(
                id=event.id,
                person_uid=event.person_uid,
                display_name=display_name,
                lead_status=str(lead.status) if lead is not None else None,
                consultation_status=str(consult.status) if consult is not None else None,
                lead_source_label=(
                    explorer_source_label_for_lead(lead) if lead is not None else None
                ),
                lead_owner=owner_label_for_lead(lead) if lead is not None else None,
                amount=amount_value,
                kind=event.kind,  # type: ignore[arg-type]
                transaction_type=transaction_type,
                occurred_at=event.occurred_at,
                source_provider=provider_literal,
                source_external_id=event.source_external_id,
                location_id=payload_location,
                location_name=await _location_name(payload_location),
                raw_event_id=event.source_event_id,
                invoice_id=invoice_id,
                invoice_number=invoice_ref.get("invoice_number")
                if invoice_ref
                else None,
                invoice_date=invoice_ref.get("invoice_date")
                if invoice_ref
                else None,
                balance=row_balance,
                operation_code=proc_doctor.get("operation_code"),
                operation_description=proc_doctor.get("operation_description"),
                doctor_name=proc_doctor.get("doctor_name"),
                doctor_provider_id=proc_doctor.get("doctor_provider_id"),
            )
        )

    return items


@router.get("/pm/payments", response_model=DashboardPmPaymentListOut)
async def pm_payments(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
    ops: Annotated[OpsService, Depends(get_ops_service)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    interaction: Annotated[InteractionService, Depends(get_interaction_service)],
    ingest: Annotated[IngestService, Depends(get_ingest_service)],
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    source_provider: Annotated[Literal["salesforce", "carestack"] | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    include_applied: Annotated[bool, Query()] = False,
    lead_channel: Annotated[str | None, Query(max_length=200)] = None,
    lead_source: Annotated[str | None, Query(max_length=200)] = None,
    lead_medium: Annotated[str | None, Query(max_length=200)] = None,
    lead_campaign: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DashboardPmPaymentListOut:
    """Return individual payment rows for the Project Manager Payments page.

    Mirrors ``pm_leads`` in spirit: the row pipeline is owned by the
    interaction-domain read model (``InteractionService.list_payment_events_for_dashboard``)
    and identity/ops/location lookups are composed in the route layer to
    avoid cross-domain imports (``packages/CLAUDE.md`` matrix). Every
    returned field is dashboard-safe; raw provider payloads are only
    reachable through the separate ``/ingest/dev/inspector/raw-events/{id}``
    drilldown which reuses the existing local-dev Inspector carve-out.

    ``lead_channel`` / ``lead_source`` / ``lead_medium`` / ``lead_campaign``
    (ENG-408) select one lead-source explorer node (explorer last-touch
    labels — NOT the PM leads ``lead_source`` chain) and scope the rows to
    payments by that node's persons. The window still applies to the
    PAYMENT date, so the page answers "which resources produced cash in
    this period" even when the leads themselves are years old.
    """
    tenant_id = principal.require_tenant()
    clean_q = q.strip() if q is not None else None
    if clean_q == "":
        clean_q = None

    node_person_uids = await _resolve_lead_source_node_persons(
        ops,
        tenant_id,
        lead_channel=lead_channel,
        lead_source=lead_source,
        lead_medium=lead_medium,
        lead_campaign=lead_campaign,
    )

    events = await interaction.list_payment_events_for_dashboard(
        tenant_id,
        occurred_from=from_,
        occurred_to=to,
        source_provider=source_provider,
        location_id=location_id,
        query=clean_q,
        include_applied=include_applied,
        person_uids=node_person_uids,
        limit=limit,
        offset=offset,
    )
    total = await interaction.count_payment_events_for_dashboard(
        tenant_id,
        occurred_from=from_,
        occurred_to=to,
        source_provider=source_provider,
        location_id=location_id,
        query=clean_q,
        include_applied=include_applied,
        person_uids=node_person_uids,
    )

    items = await _build_payment_items(
        db=db,
        ops=ops,
        identity=identity,
        ingest=ingest,
        tenant_id=tenant_id,
        events=events,
    )

    return DashboardPmPaymentListOut(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + len(events) < total,
        has_previous=offset > 0,
        filters=DashboardAppliedFiltersOut(
            from_=from_,
            to=to,
            source_provider=source_provider,
            lead_source=lead_source,
            location_id=location_id,
            q=clean_q,
            lead_channel=lead_channel,
            lead_medium=lead_medium,
            lead_campaign=lead_campaign,
        ),
    )


async def _resolve_lead_source_node_persons(
    ops: OpsService,
    tenant_id: TenantId,
    *,
    lead_channel: str | None,
    lead_source: str | None,
    lead_medium: str | None,
    lead_campaign: str | None,
) -> list[UUID] | None:
    """Resolve the ENG-408 lead-source node filter to its person_uids.

    ``None`` means "filter not active" (no node params supplied) and the
    payment queries stay un-scoped. An empty list is a real answer — the
    node has no persons — and matches no payments downstream.
    """
    if (
        lead_channel is None
        and lead_source is None
        and lead_medium is None
        and lead_campaign is None
    ):
        return None
    return await ops.person_uids_for_lead_source_node(
        tenant_id,
        channel=lead_channel,
        source=lead_source,
        medium=lead_medium,
        campaign=lead_campaign,
    )


@router.get(
    "/pm/payments/groups", response_model=DashboardPmPaymentGroupListOut
)
async def pm_payment_groups(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
    ops: Annotated[OpsService, Depends(get_ops_service)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    interaction: Annotated[InteractionService, Depends(get_interaction_service)],
    ingest: Annotated[IngestService, Depends(get_ingest_service)],
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    source_provider: Annotated[Literal["salesforce", "carestack"] | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    include_applied: Annotated[bool, Query()] = False,
    lead_channel: Annotated[str | None, Query(max_length=200)] = None,
    lead_source: Annotated[str | None, Query(max_length=200)] = None,
    lead_medium: Annotated[str | None, Query(max_length=200)] = None,
    lead_campaign: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DashboardPmPaymentGroupListOut:
    """Same-day payment groups for the PM Payments page (ENG-410).

    Same filter surface as ``/pm/payments``, but rows collapse by
    ``(person, kind, clinic-local day)`` — CareStack splits one real-world
    payment into per-invoice legs minutes apart, and the PM wants to read
    "this person paid $919 on Jun 11", not three fragments. Pagination
    counts GROUPS; each group embeds its legs (full row shape, including
    per-leg invoice and raw drill-down).
    """
    tenant_id = principal.require_tenant()
    clean_q = q.strip() if q is not None else None
    if clean_q == "":
        clean_q = None

    node_person_uids = await _resolve_lead_source_node_persons(
        ops,
        tenant_id,
        lead_channel=lead_channel,
        lead_source=lead_source,
        lead_medium=lead_medium,
        lead_campaign=lead_campaign,
    )

    groups = await interaction.list_payment_event_groups_for_dashboard(
        tenant_id,
        occurred_from=from_,
        occurred_to=to,
        source_provider=source_provider,
        location_id=location_id,
        query=clean_q,
        include_applied=include_applied,
        person_uids=node_person_uids,
        limit=limit,
        offset=offset,
    )
    total = await interaction.count_payment_event_groups_for_dashboard(
        tenant_id,
        occurred_from=from_,
        occurred_to=to,
        source_provider=source_provider,
        location_id=location_id,
        query=clean_q,
        include_applied=include_applied,
        person_uids=node_person_uids,
    )

    # One shared projection pass over ALL legs on the page, then re-bucket
    # by event id — keeps leg rows byte-identical to the flat list.
    all_events = [event for group in groups for event in group["legs"]]
    leg_items = await _build_payment_items(
        db=db,
        ops=ops,
        identity=identity,
        ingest=ingest,
        tenant_id=tenant_id,
        events=all_events,
    )
    item_by_id = {item.id: item for item in leg_items}

    items: list[DashboardPmPaymentGroupOut] = []
    for group in groups:
        legs = [
            item_by_id[event.id]
            for event in group["legs"]
            if event.id in item_by_id
        ]
        if not legs:
            # Defensive: every leg was dropped by the provider guard.
            continue
        head = legs[0]
        items.append(
            DashboardPmPaymentGroupOut(
                person_uid=head.person_uid,
                display_name=head.display_name,
                lead_status=head.lead_status,
                consultation_status=head.consultation_status,
                lead_source_label=head.lead_source_label,
                lead_owner=head.lead_owner,
                balance=head.balance,
                kind=group["kind"],
                day=group["local_day"].isoformat(),
                amount=float(group["total_amount"]),
                leg_count=int(group["leg_count"]),
                occurred_at=group["last_occurred_at"],
                legs=legs,
            )
        )

    return DashboardPmPaymentGroupListOut(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + len(groups) < total,
        has_previous=offset > 0,
        filters=DashboardAppliedFiltersOut(
            from_=from_,
            to=to,
            source_provider=source_provider,
            lead_source=lead_source,
            location_id=location_id,
            q=clean_q,
            lead_channel=lead_channel,
            lead_medium=lead_medium,
            lead_campaign=lead_campaign,
        ),
    )


@router.get(
    "/pm/payments/summary", response_model=DashboardPmPaymentSummaryOut
)
async def pm_payments_summary(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    interaction: Annotated[InteractionService, Depends(get_interaction_service)],
    ops: Annotated[OpsService, Depends(get_ops_service)],
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    source_provider: Annotated[Literal["salesforce", "carestack"] | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    lead_channel: Annotated[str | None, Query(max_length=200)] = None,
    lead_source: Annotated[str | None, Query(max_length=200)] = None,
    lead_medium: Annotated[str | None, Query(max_length=200)] = None,
    lead_campaign: Annotated[str | None, Query(max_length=200)] = None,
) -> DashboardPmPaymentSummaryOut:
    """Window-wide payment totals for the PM Payments summary bar.

    Honours the same window/provider/location/search as the row list, but
    aggregates the ENTIRE window — so "Collected / Payments / Patients" reflect
    the selected dates, not just the current page. No pagination, no
    ``include_applied`` (it is a cash aggregate; the allocation leg never
    contributes to Collected). The ENG-408 lead-source node params scope the
    aggregate to the node's persons, turning the bar into "cash this period
    from this resource".
    """
    tenant_id = principal.require_tenant()
    clean_q = q.strip() if q is not None else None
    if clean_q == "":
        clean_q = None

    node_person_uids = await _resolve_lead_source_node_persons(
        ops,
        tenant_id,
        lead_channel=lead_channel,
        lead_source=lead_source,
        lead_medium=lead_medium,
        lead_campaign=lead_campaign,
    )

    summary = await interaction.summarize_payment_events_for_dashboard(
        tenant_id,
        occurred_from=from_,
        occurred_to=to,
        source_provider=source_provider,
        location_id=location_id,
        query=clean_q,
        person_uids=node_person_uids,
    )
    return DashboardPmPaymentSummaryOut(
        collected_total=summary.collected_total,
        payment_count=summary.payment_count,
        patient_count=summary.patient_count,
        filters=DashboardAppliedFiltersOut(
            from_=from_,
            to=to,
            source_provider=source_provider,
            lead_source=lead_source,
            location_id=location_id,
            q=clean_q,
            lead_channel=lead_channel,
            lead_medium=lead_medium,
            lead_campaign=lead_campaign,
        ),
    )


# Default marketing window when the caller passes no dates: trailing 30 days
# (inclusive of today). Ad-platform data is day-granular, so the window is a
# closed [start_date, end_date] date range, not a half-open datetime range.
_MARKETING_DEFAULT_WINDOW_DAYS = 30


def _ratio(numerator: float, denominator: float) -> float | None:
    """Safe ratio for derived KPIs — ``None`` (UI ``"—"``) on a zero base."""
    if denominator == 0:
        return None
    return numerator / denominator


@router.get("/analytics/marketing", response_model=MarketingAnalyticsOut)
async def analytics_marketing(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    marketing: Annotated[MarketingService, Depends(get_marketing_service)],
    ops: Annotated[OpsService, Depends(get_ops_service)],
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    provider: Annotated[Literal["google_ads", "meta_ads", "tiktok_ads"] | None, Query()] = None,
) -> MarketingAnalyticsOut:
    """Marketing / ad-spend analytics dashboard (ENG-470).

    Thin composer: ``MarketingService.spend_breakdown`` owns the spend
    aggregation (daily trend, provider split, campaign table, totals);
    ``OpsService`` owns the lead count and the raw-UTM lead-source tree. The
    route only wires the two services together and derives the cross-domain
    ratios (CPL, CTR, CPC, CPM). The window is a closed date range; it defaults
    to the trailing 30 days when no dates are supplied.
    """
    tenant_id = principal.require_tenant()

    resolved_end = end_date or datetime.now(tz=UTC).date()
    resolved_start = start_date or (
        resolved_end - timedelta(days=_MARKETING_DEFAULT_WINDOW_DAYS)
    )

    breakdown = await marketing.spend_breakdown(
        tenant_id,
        start_date=resolved_start,
        end_date=resolved_end,
        provider=provider,
    )

    # Lead count + lead-source tree use the lead's created_at (datetime), so
    # widen the date window to the full UTC day span [start 00:00, end 24:00).
    created_from = datetime.combine(resolved_start, time.min, tzinfo=UTC)
    created_to = datetime.combine(
        resolved_end + timedelta(days=1), time.min, tzinfo=UTC
    )
    total_leads = await ops.count_leads_for_dashboard(
        tenant_id,
        created_from=created_from,
        created_to=created_to,
    )
    lead_tree = await ops.get_lead_source_tree(
        tenant_id,
        created_from=created_from,
        created_to=created_to,
    )

    ctr = _ratio(breakdown.clicks, breakdown.impressions)
    cpc = _ratio(breakdown.spend, breakdown.clicks)
    # CPM = cost per 1,000 impressions.
    cpm = _ratio(breakdown.spend * 1000.0, breakdown.impressions)
    cpl = _ratio(breakdown.spend, total_leads)

    kpis = [
        MarketingKpiOut(
            key="spend",
            label="Total spend",
            value=breakdown.spend,
            format="currency",
            hint="Ad spend across connected providers in the window",
        ),
        MarketingKpiOut(
            key="impressions",
            label="Impressions",
            value=float(breakdown.impressions),
            format="integer",
        ),
        MarketingKpiOut(
            key="clicks",
            label="Clicks",
            value=float(breakdown.clicks),
            format="integer",
        ),
        MarketingKpiOut(
            key="conversions",
            label="Conversions",
            value=breakdown.conversions,
            format="integer",
            hint="Provider-reported conversions",
        ),
        MarketingKpiOut(
            key="total_leads",
            label="Total leads",
            value=float(total_leads),
            format="integer",
            hint="Leads created in the window (ops.lead)",
        ),
        MarketingKpiOut(
            key="ctr",
            label="CTR",
            value=ctr,
            format="percent",
            hint="Clicks ÷ impressions",
        ),
        MarketingKpiOut(
            key="cpc",
            label="CPC",
            value=cpc,
            format="currency",
            hint="Spend ÷ clicks",
        ),
        MarketingKpiOut(
            key="cpm",
            label="CPM",
            value=cpm,
            format="currency",
            hint="Spend per 1,000 impressions",
        ),
        MarketingKpiOut(
            key="cpl",
            label="CPL",
            value=cpl,
            format="currency",
            hint="Spend ÷ leads created in the window",
        ),
    ]

    return MarketingAnalyticsOut(
        window=MarketingAnalyticsWindowOut(
            start_date=resolved_start, end_date=resolved_end
        ),
        kpis=kpis,
        daily=[
            MarketingDailyPointOut(
                metric_date=point.metric_date,
                provider=point.provider,
                spend=point.spend,
                impressions=point.impressions,
                clicks=point.clicks,
                conversions=point.conversions,
            )
            for point in breakdown.daily
        ],
        providers=[
            MarketingProviderSplitOut(
                provider=row.provider,
                spend=row.spend,
                impressions=row.impressions,
                clicks=row.clicks,
                conversions=row.conversions,
            )
            for row in breakdown.providers
        ],
        campaigns=[
            MarketingCampaignRowOut(
                provider=row.provider,
                campaign_external_id=row.campaign_external_id,
                campaign_name=row.campaign_name,
                spend=row.spend,
                impressions=row.impressions,
                clicks=row.clicks,
                conversions=row.conversions,
            )
            for row in breakdown.campaigns
        ],
        lead_sources=lead_tree.sources,
    )


@router.get("/analytics/full-funnel", response_model=FullFunnelV2Out)
async def analytics_full_funnel(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    full_funnel: Annotated[FullFunnelService, Depends(get_full_funnel_service)],
    audience: Annotated[Literal["all", "marketing"], Query()] = "all",
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
) -> FullFunnelV2Out:
    """Full Funnel v2 (ENG-481) — person-anchored funnel by ``audience``.

    Thin composer. ``FullFunnelService`` (read-only composition over
    OpsService + IdentityService + InteractionService + MarketingService) owns
    the person-anchored read model: leads = distinct persons in
    ``ops.lead`` ∪ ``identity.source_link(carestack/patient)``; consults /
    showed / no-show from ``ops.consultation`` (CareStack truth);
    closed-won (money) + revenue = Net Collected from ``interaction.event``;
    monthly ad spend mapped provider→channel from ``marketing``.

    Each stage is windowed and month-bucketed on its OWN timestamp. The
    ``audience`` toggle (``all`` | ``marketing``) filters every stage through
    one shared person→channel map, so ``marketing ⊆ all`` holds for every
    stage and month. The window defaults to the trailing 6 months; optional
    ``start_date`` / ``end_date`` override it.
    """
    tenant_id = principal.require_tenant()
    return await full_funnel.compute(
        tenant_id,
        audience=audience,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/analytics/journey-metrics", response_model=JourneyMetricsOut)
async def analytics_journey_metrics(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    metrics: Annotated[
        AnalyticsMetricsService, Depends(get_analytics_metrics_service)
    ],
    time_range: Annotated[TimeRangePreset, Query()] = "last_30_days",
    custom_start: Annotated[datetime | None, Query()] = None,
    custom_end: Annotated[datetime | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[UUID | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=128)] = None,
    vendor_id: Annotated[UUID | None, Query()] = None,
    caller_id: Annotated[UUID | None, Query()] = None,
    coordinator_id: Annotated[UUID | None, Query()] = None,
    doctor_id: Annotated[UUID | None, Query()] = None,
) -> JourneyMetricsOut:
    """Foundation analytics contract (ENG-507) — shared filter + derived metrics.

    Smoke endpoint proving the global filter DTO + time-range resolver + a
    ``fact_patient_journey`` aggregate + the derived-metric layer (cost/revenue
    per stage, ROI, conversions). Thin composer — ``AnalyticsMetricsService``
    owns the logic. ``location_id`` omitted = aggregate over all locations; a
    value scopes per-location (window resolved in that location's timezone).
    NOT one of the 14 pages — those compose onto this contract later.
    """
    tenant_id = principal.require_tenant()
    filters = AnalyticsFilters(
        time_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end,
        location_id=location_id,
        campaign_id=campaign_id,
        source=source,
        vendor_id=vendor_id,
        caller_id=caller_id,
        coordinator_id=coordinator_id,
        doctor_id=doctor_id,
    )
    return await metrics.journey_metrics(tenant_id, filters)


@router.post(
    "/analytics/fact-override",
    response_model=FactOverrideOut,
)
async def analytics_fact_override(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    body: FactOverrideIn,
    enrichment: Annotated[
        FactEnrichmentService, Depends(get_fact_enrichment_service)
    ],
) -> FactOverrideOut:
    """Set/correct one ``fact_patient_journey`` field for a person (ENG-513).

    The single manual-enrichment write path: records a ``record_annotation``
    row (+ audit) and applies the value into the fact row with provenance
    ``method='manual'`` (which a builder rebuild preserves: manual > auto >
    unresolved). Thin composer — ``FactEnrichmentService`` owns the logic.
    """
    tenant_id = principal.require_tenant()
    return await enrichment.set_override(
        tenant_id,
        person_uid=body.person_uid,
        field=body.field,
        value=body.value,
        principal=principal,
        note=body.note,
        author_actor_id=body.author_actor_id,
    )


def _analytics_filters(
    *,
    time_range: TimeRangePreset,
    custom_start: datetime | None,
    custom_end: datetime | None,
    location_id: UUID | None,
    campaign_id: UUID | None,
    source: str | None,
    vendor_id: UUID | None,
    caller_id: UUID | None,
    coordinator_id: UUID | None,
    doctor_id: UUID | None,
) -> AnalyticsFilters:
    """Build the shared global-filter DTO from query params (wiring only).

    The B2 data-ready pages all consume the same filter bar, so the route just
    maps query params onto ``AnalyticsFilters``; the validation (custom-range
    requirement) lives in the DTO, the aggregation in ``packages/analytics``.
    """
    return AnalyticsFilters(
        time_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end,
        location_id=location_id,
        campaign_id=campaign_id,
        source=source,
        vendor_id=vendor_id,
        caller_id=caller_id,
        coordinator_id=coordinator_id,
        doctor_id=doctor_id,
    )


@router.get("/analytics/executive", response_model=ExecutiveOverviewOut)
async def analytics_executive(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    pages: Annotated[AnalyticsPagesService, Depends(get_analytics_pages_service)],
    time_range: Annotated[TimeRangePreset, Query()] = "last_30_days",
    custom_start: Annotated[datetime | None, Query()] = None,
    custom_end: Annotated[datetime | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[UUID | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=128)] = None,
    vendor_id: Annotated[UUID | None, Query()] = None,
    caller_id: Annotated[UUID | None, Query()] = None,
    coordinator_id: Annotated[UUID | None, Query()] = None,
    doctor_id: Annotated[UUID | None, Query()] = None,
) -> ExecutiveOverviewOut:
    """Executive Overview (ENG-514) — owner dashboard over the shared fact.

    Thin composer. ``AnalyticsPagesService`` owns the funnel + cost/ROI +
    realized-cash widgets; cost/ROI and B1-unresolved stages render "—"/0 until
    enablement lands. ``location_id`` omitted = aggregate over all locations.
    """
    tenant_id = principal.require_tenant()
    filters = _analytics_filters(
        time_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end,
        location_id=location_id,
        campaign_id=campaign_id,
        source=source,
        vendor_id=vendor_id,
        caller_id=caller_id,
        coordinator_id=coordinator_id,
        doctor_id=doctor_id,
    )
    return await pages.executive_overview(tenant_id, filters)


@router.get("/analytics/funnel-stages", response_model=FunnelStagesOut)
async def analytics_funnel_stages(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    pages: Annotated[AnalyticsPagesService, Depends(get_analytics_pages_service)],
    time_range: Annotated[TimeRangePreset, Query()] = "last_30_days",
    custom_start: Annotated[datetime | None, Query()] = None,
    custom_end: Annotated[datetime | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[UUID | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=128)] = None,
    vendor_id: Annotated[UUID | None, Query()] = None,
    caller_id: Annotated[UUID | None, Query()] = None,
    coordinator_id: Annotated[UUID | None, Query()] = None,
    doctor_id: Annotated[UUID | None, Query()] = None,
) -> FunnelStagesOut:
    """Funnel Analytics (ENG-515) — nine-point patient funnel over the fact.

    Served alongside the existing Full-Funnel v2 (``/analytics/full-funnel``),
    not replacing it, so v2's numbers do not regress. New stages
    (treatment_accepted, surgery_*) report honest zeros until B1.3.
    """
    tenant_id = principal.require_tenant()
    filters = _analytics_filters(
        time_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end,
        location_id=location_id,
        campaign_id=campaign_id,
        source=source,
        vendor_id=vendor_id,
        caller_id=caller_id,
        coordinator_id=coordinator_id,
        doctor_id=doctor_id,
    )
    return await pages.funnel_stages(tenant_id, filters)


@router.get("/analytics/revenue", response_model=RevenueIntelligenceOut)
async def analytics_revenue(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    pages: Annotated[AnalyticsPagesService, Depends(get_analytics_pages_service)],
    time_range: Annotated[TimeRangePreset, Query()] = "last_30_days",
    custom_start: Annotated[datetime | None, Query()] = None,
    custom_end: Annotated[datetime | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[UUID | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=128)] = None,
    vendor_id: Annotated[UUID | None, Query()] = None,
    caller_id: Annotated[UUID | None, Query()] = None,
    coordinator_id: Annotated[UUID | None, Query()] = None,
    doctor_id: Annotated[UUID | None, Query()] = None,
) -> RevenueIntelligenceOut:
    """Revenue Intelligence (ENG-521) — revenue by all seven dimensions.

    Cohort revenue (``lead_date`` in window) so totals reconcile with the
    funnel. Dimensions the fact cannot attribute yet (vendor/caller/coordinator/
    doctor) come back as a single "Unattributed" bucket (``resolved=false``).
    """
    tenant_id = principal.require_tenant()
    filters = _analytics_filters(
        time_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end,
        location_id=location_id,
        campaign_id=campaign_id,
        source=source,
        vendor_id=vendor_id,
        caller_id=caller_id,
        coordinator_id=coordinator_id,
        doctor_id=doctor_id,
    )
    return await pages.revenue_intelligence(tenant_id, filters)


@router.get(
    "/analytics/marketing-performance", response_model=MarketingPerformanceOut
)
async def analytics_marketing_performance(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    pages: Annotated[AnalyticsPagesService, Depends(get_analytics_pages_service)],
    time_range: Annotated[TimeRangePreset, Query()] = "last_30_days",
    custom_start: Annotated[datetime | None, Query()] = None,
    custom_end: Annotated[datetime | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[UUID | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=128)] = None,
    vendor_id: Annotated[UUID | None, Query()] = None,
    caller_id: Annotated[UUID | None, Query()] = None,
    coordinator_id: Annotated[UUID | None, Query()] = None,
    doctor_id: Annotated[UUID | None, Query()] = None,
) -> MarketingPerformanceOut:
    """Marketing Performance (ENG-516) — ad spend ⇄ outcomes by campaign/source.

    Thin composer. ``AnalyticsPagesService`` joins the cost-per-lead allocation
    on the shared fact with the window's ground-truth ad spend; campaign / source
    breakdowns carry the full metric set + ROI, ad_set / ad come back "no data",
    and ``spend_without_leads`` surfaces ad spend with no attributed leads.
    ``location_id`` omitted = aggregate over all locations.
    """
    tenant_id = principal.require_tenant()
    filters = _analytics_filters(
        time_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end,
        location_id=location_id,
        campaign_id=campaign_id,
        source=source,
        vendor_id=vendor_id,
        caller_id=caller_id,
        coordinator_id=coordinator_id,
        doctor_id=doctor_id,
    )
    return await pages.marketing_performance(tenant_id, filters)


@router.get("/analytics/cohort", response_model=CohortAnalyticsOut)
async def analytics_cohort(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    pages: Annotated[AnalyticsPagesService, Depends(get_analytics_pages_service)],
    time_range: Annotated[TimeRangePreset, Query()] = "this_year",
    custom_start: Annotated[datetime | None, Query()] = None,
    custom_end: Annotated[datetime | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[UUID | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=128)] = None,
    vendor_id: Annotated[UUID | None, Query()] = None,
    caller_id: Annotated[UUID | None, Query()] = None,
    coordinator_id: Annotated[UUID | None, Query()] = None,
    doctor_id: Annotated[UUID | None, Query()] = None,
) -> CohortAnalyticsOut:
    """Cohort Analytics (ENG-526) — cumulative revenue by lead-creation month.

    Person-anchored cohorts (``lead_date`` month) so bulk-import patients do not
    distort the curve; each cell is cumulative ``collected_amount`` within N days
    of the lead date. Defaults to a year-to-date window (multiple monthly cohorts).
    """
    tenant_id = principal.require_tenant()
    filters = _analytics_filters(
        time_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end,
        location_id=location_id,
        campaign_id=campaign_id,
        source=source,
        vendor_id=vendor_id,
        caller_id=caller_id,
        coordinator_id=coordinator_id,
        doctor_id=doctor_id,
    )
    return await pages.cohort_analytics(tenant_id, filters)


@router.get("/analytics/caller", response_model=CallerPerformanceOut)
async def analytics_caller(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    pages: Annotated[AnalyticsPagesService, Depends(get_analytics_pages_service)],
    time_range: Annotated[TimeRangePreset, Query()] = "last_30_days",
    custom_start: Annotated[datetime | None, Query()] = None,
    custom_end: Annotated[datetime | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[UUID | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=128)] = None,
    vendor_id: Annotated[UUID | None, Query()] = None,
    caller_id: Annotated[UUID | None, Query()] = None,
    coordinator_id: Annotated[UUID | None, Query()] = None,
    doctor_id: Annotated[UUID | None, Query()] = None,
) -> CallerPerformanceOut:
    """Caller Performance (ENG-518) — per-caller lead → contact → consult metrics.

    Groups the lead-date cohort by ``caller_id``; NULL caller → "Unassigned".
    ``calls_made`` is ``null`` on every row (honest no-data: the fact has no
    per-call-attempt count; ``first_contact_date`` only records contact made).
    Thin composer over ``AnalyticsPagesService.caller_performance``.
    """
    tenant_id = principal.require_tenant()
    filters = _analytics_filters(
        time_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end,
        location_id=location_id,
        campaign_id=campaign_id,
        source=source,
        vendor_id=vendor_id,
        caller_id=caller_id,
        coordinator_id=coordinator_id,
        doctor_id=doctor_id,
    )
    return await pages.caller_performance(tenant_id, filters)


@router.get("/analytics/coordinator", response_model=CoordinatorPerformanceOut)
async def analytics_coordinator(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    pages: Annotated[AnalyticsPagesService, Depends(get_analytics_pages_service)],
    time_range: Annotated[TimeRangePreset, Query()] = "last_30_days",
    custom_start: Annotated[datetime | None, Query()] = None,
    custom_end: Annotated[datetime | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[UUID | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=128)] = None,
    vendor_id: Annotated[UUID | None, Query()] = None,
    caller_id: Annotated[UUID | None, Query()] = None,
    coordinator_id: Annotated[UUID | None, Query()] = None,
    doctor_id: Annotated[UUID | None, Query()] = None,
) -> CoordinatorPerformanceOut:
    """Coordinator Performance (ENG-519) — per-coordinator consult → surgery funnel.

    Groups the lead-date cohort by ``coordinator_id``; NULL → "Unassigned".
    Thin composer over ``AnalyticsPagesService.coordinator_performance``.
    """
    tenant_id = principal.require_tenant()
    filters = _analytics_filters(
        time_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end,
        location_id=location_id,
        campaign_id=campaign_id,
        source=source,
        vendor_id=vendor_id,
        caller_id=caller_id,
        coordinator_id=coordinator_id,
        doctor_id=doctor_id,
    )
    return await pages.coordinator_performance(tenant_id, filters)


@router.get("/analytics/doctor", response_model=DoctorPerformanceOut)
async def analytics_doctor(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    pages: Annotated[AnalyticsPagesService, Depends(get_analytics_pages_service)],
    time_range: Annotated[TimeRangePreset, Query()] = "last_30_days",
    custom_start: Annotated[datetime | None, Query()] = None,
    custom_end: Annotated[datetime | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[UUID | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=128)] = None,
    vendor_id: Annotated[UUID | None, Query()] = None,
    caller_id: Annotated[UUID | None, Query()] = None,
    coordinator_id: Annotated[UUID | None, Query()] = None,
    doctor_id: Annotated[UUID | None, Query()] = None,
) -> DoctorPerformanceOut:
    """Doctor Performance (ENG-520) — consult → treatment → surgery per doctor.

    Groups the lead-date cohort by ``doctor_id``; NULL → "Unassigned".
    Thin composer over ``AnalyticsPagesService.doctor_performance``.
    """
    tenant_id = principal.require_tenant()
    filters = _analytics_filters(
        time_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end,
        location_id=location_id,
        campaign_id=campaign_id,
        source=source,
        vendor_id=vendor_id,
        caller_id=caller_id,
        coordinator_id=coordinator_id,
        doctor_id=doctor_id,
    )
    return await pages.doctor_performance(tenant_id, filters)


@router.get("/analytics/vendor", response_model=VendorPerformanceOut)
async def analytics_vendor(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    pages: Annotated[AnalyticsPagesService, Depends(get_analytics_pages_service)],
    time_range: Annotated[TimeRangePreset, Query()] = "last_30_days",
    custom_start: Annotated[datetime | None, Query()] = None,
    custom_end: Annotated[datetime | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[UUID | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=128)] = None,
    vendor_id: Annotated[UUID | None, Query()] = None,
    caller_id: Annotated[UUID | None, Query()] = None,
    coordinator_id: Annotated[UUID | None, Query()] = None,
    doctor_id: Annotated[UUID | None, Query()] = None,
) -> VendorPerformanceOut:
    """Vendor Performance (ENG-517) — per-vendor lead-to-revenue ranking.

    Groups the lead-date cohort by ``vendor_id``; NULL → "Unassigned".
    ``vendor_attribution_wired`` is ``False`` today (``vendor_id`` is 100% NULL
    on the fact). The query is stable: when ENG-569 populates vendor_id the
    page lights up with no code change. ``spend_managed`` / ``roi`` are ``null``
    (no vendor→spend column on the fact). Thin composer over
    ``AnalyticsPagesService.vendor_performance``.
    """
    tenant_id = principal.require_tenant()
    filters = _analytics_filters(
        time_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end,
        location_id=location_id,
        campaign_id=campaign_id,
        source=source,
        vendor_id=vendor_id,
        caller_id=caller_id,
        coordinator_id=coordinator_id,
        doctor_id=doctor_id,
    )
    return await pages.vendor_performance(tenant_id, filters)


@router.get("/analytics/attribution", response_model=AttributionAnalyticsOut)
async def analytics_attribution(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    pages: Annotated[AnalyticsPagesService, Depends(get_analytics_pages_service)],
    time_range: Annotated[TimeRangePreset, Query()] = "last_30_days",
    custom_start: Annotated[datetime | None, Query()] = None,
    custom_end: Annotated[datetime | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[UUID | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=128)] = None,
    vendor_id: Annotated[UUID | None, Query()] = None,
    caller_id: Annotated[UUID | None, Query()] = None,
    coordinator_id: Annotated[UUID | None, Query()] = None,
    doctor_id: Annotated[UUID | None, Query()] = None,
) -> AttributionAnalyticsOut:
    """Attribution Analytics (ENG-525) — revenue by attribution dimension.

    Shows collected revenue + case counts per campaign / vendor / caller /
    coordinator / doctor for in-cohort persons (``lead_date`` in window).
    Campaign has good data; caller/coordinator/doctor have partial coverage
    (NULL = "Unassigned"); vendor is ``resolved=False`` (100% NULL today).
    Thin composer over ``AnalyticsPagesService.attribution_analytics``.
    """
    tenant_id = principal.require_tenant()
    filters = _analytics_filters(
        time_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end,
        location_id=location_id,
        campaign_id=campaign_id,
        source=source,
        vendor_id=vendor_id,
        caller_id=caller_id,
        coordinator_id=coordinator_id,
        doctor_id=doctor_id,
    )
    return await pages.attribution_analytics(tenant_id, filters)


@router.get("/analytics/revenue-influence", response_model=RevenueInfluenceMatrixOut)
async def analytics_revenue_influence(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    pages: Annotated[AnalyticsPagesService, Depends(get_analytics_pages_service)],
    time_range: Annotated[TimeRangePreset, Query()] = "last_30_days",
    custom_start: Annotated[datetime | None, Query()] = None,
    custom_end: Annotated[datetime | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[UUID | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=128)] = None,
    vendor_id: Annotated[UUID | None, Query()] = None,
    caller_id: Annotated[UUID | None, Query()] = None,
    coordinator_id: Annotated[UUID | None, Query()] = None,
    doctor_id: Annotated[UUID | None, Query()] = None,
) -> RevenueInfluenceMatrixOut:
    """Revenue Influence Matrix (ENG-527) — employee × role × revenue influenced.

    Flat list of (employee_id, employee_label, role, revenue_influenced,
    case_count) rows. Roles: vendor / caller / coordinator / doctor. For each
    role the lead-date cohort is grouped by the corresponding id column and
    SUM(collected_amount) is returned as revenue influenced.

    DOUBLE-COUNTING: the same patient's revenue is counted once per role they
    touch (intentional per-spec — measures influence, not additive attribution).
    Vendor rows will be empty today (vendor_id 100% NULL — see ENG-517/569).
    Thin composer over ``AnalyticsPagesService.revenue_influence_matrix``.
    """
    tenant_id = principal.require_tenant()
    filters = _analytics_filters(
        time_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end,
        location_id=location_id,
        campaign_id=campaign_id,
        source=source,
        vendor_id=vendor_id,
        caller_id=caller_id,
        coordinator_id=coordinator_id,
        doctor_id=doctor_id,
    )
    return await pages.revenue_influence_matrix(tenant_id, filters)


@router.get(
    "/analytics/patient-journey/{person_uid}", response_model=PatientJourneyOut
)
async def analytics_patient_journey(
    person_uid: UUID,
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    pages: Annotated[AnalyticsPagesService, Depends(get_analytics_pages_service)],
) -> PatientJourneyOut:
    """Patient Journey (ENG-523) — one person's stage timeline from the fact.

    Drill-down target from the other pages. Returns the fact-derived stage
    timeline; the granular operational-timeline (ENG-235) is fetched separately
    and merged on the page. Responsible employee stays "no data" until B1.
    """
    tenant_id = principal.require_tenant()
    return await pages.patient_journey(tenant_id, person_uid)


@router.get("/analytics/cost", response_model=CostIntelligenceOut)
async def analytics_cost(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    pages: Annotated[AnalyticsPagesService, Depends(get_analytics_pages_service)],
    time_range: Annotated[TimeRangePreset, Query()] = "last_30_days",
    custom_start: Annotated[datetime | None, Query()] = None,
    custom_end: Annotated[datetime | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[UUID | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=128)] = None,
    vendor_id: Annotated[UUID | None, Query()] = None,
    caller_id: Annotated[UUID | None, Query()] = None,
    coordinator_id: Annotated[UUID | None, Query()] = None,
    doctor_id: Annotated[UUID | None, Query()] = None,
) -> CostIntelligenceOut:
    """Cost Intelligence (ENG-522) — marketing cost per funnel stage.

    Spend = ground-truth window ad spend from ``MarketingService`` (same source
    as the Marketing Performance page). Cost metrics are ``null`` when no spend
    source is connected. Operational cost metrics (cost per caller / coordinator
    conversion) are always ``null`` — inputs not yet captured, surfaced honestly.
    """
    tenant_id = principal.require_tenant()
    filters = _analytics_filters(
        time_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end,
        location_id=location_id,
        campaign_id=campaign_id,
        source=source,
        vendor_id=vendor_id,
        caller_id=caller_id,
        coordinator_id=coordinator_id,
        doctor_id=doctor_id,
    )
    return await pages.cost_intelligence(tenant_id, filters)


@router.get("/analytics/bottlenecks", response_model=BottlenecksOut)
async def analytics_bottlenecks(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    pages: Annotated[AnalyticsPagesService, Depends(get_analytics_pages_service)],
    time_range: Annotated[TimeRangePreset, Query()] = "last_30_days",
    custom_start: Annotated[datetime | None, Query()] = None,
    custom_end: Annotated[datetime | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[UUID | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=128)] = None,
    vendor_id: Annotated[UUID | None, Query()] = None,
    caller_id: Annotated[UUID | None, Query()] = None,
    coordinator_id: Annotated[UUID | None, Query()] = None,
    doctor_id: Annotated[UUID | None, Query()] = None,
) -> BottlenecksOut:
    """Bottleneck Detection (ENG-524) — rule-based funnel bottleneck finder.

    Applies four rule sets (campaign show rate, coordinator show→surgery,
    doctor consult→acceptance, caller lead→consult) over the shared fact.
    Only entities with meaningful sample sizes are evaluated (minimum thresholds
    documented in the service). Returns an empty ``findings`` list when the
    cohort is too sparse — no findings invented from noise.
    """
    tenant_id = principal.require_tenant()
    filters = _analytics_filters(
        time_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end,
        location_id=location_id,
        campaign_id=campaign_id,
        source=source,
        vendor_id=vendor_id,
        caller_id=caller_id,
        coordinator_id=coordinator_id,
        doctor_id=doctor_id,
    )
    return await pages.bottleneck_detection(tenant_id, filters)


@router.get("/analytics/drilldown", response_model=MetricDrilldownOut)
async def analytics_drilldown(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    pages: Annotated[AnalyticsPagesService, Depends(get_analytics_pages_service)],
    metric: Annotated[DrilldownMetric, Query()],
    time_range: Annotated[TimeRangePreset, Query()] = "last_30_days",
    custom_start: Annotated[datetime | None, Query()] = None,
    custom_end: Annotated[datetime | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[UUID | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=128)] = None,
    vendor_id: Annotated[UUID | None, Query()] = None,
    caller_id: Annotated[UUID | None, Query()] = None,
    coordinator_id: Annotated[UUID | None, Query()] = None,
    doctor_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[
        int, Query(ge=1, le=DRILLDOWN_HARD_CAP)
    ] = DRILLDOWN_DEFAULT_LIMIT,
) -> MetricDrilldownOut:
    """Metric → underlying ``person_uid`` set (ENG-508) for the active filters.

    Thin composer: maps the shared filter bar onto ``AnalyticsFilters`` and asks
    ``AnalyticsPagesService`` for the in-cohort persons behind one metric — same
    ``lead_date`` cohort + dimension filters as the pages, so the list reconciles
    with the count. Deterministically ordered and hard-capped; only ``person_uid``
    crosses the boundary (no PHI). Resolve a single uid via Patient Journey.
    """
    tenant_id = principal.require_tenant()
    filters = _analytics_filters(
        time_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end,
        location_id=location_id,
        campaign_id=campaign_id,
        source=source,
        vendor_id=vendor_id,
        caller_id=caller_id,
        coordinator_id=coordinator_id,
        doctor_id=doctor_id,
    )
    return await pages.metric_drilldown(tenant_id, filters, metric=metric, limit=limit)


@router.get("/analytics/export/{page}")
async def analytics_export(
    page: AnalyticsExportPage,
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    export: Annotated[
        AnalyticsExportService, Depends(get_analytics_export_service)
    ],
    export_format: Annotated[AnalyticsExportFormat, Query(alias="format")] = "csv",
    time_range: Annotated[TimeRangePreset, Query()] = "last_30_days",
    custom_start: Annotated[datetime | None, Query()] = None,
    custom_end: Annotated[datetime | None, Query()] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[UUID | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=128)] = None,
    vendor_id: Annotated[UUID | None, Query()] = None,
    caller_id: Annotated[UUID | None, Query()] = None,
    coordinator_id: Annotated[UUID | None, Query()] = None,
    doctor_id: Annotated[UUID | None, Query()] = None,
) -> Response:
    """CSV/XLSX export of one fact-backed page (ENG-508).

    Thin composer: maps the shared filter bar onto ``AnalyticsFilters`` and hands
    it to ``AnalyticsExportService``, which wraps ``AnalyticsPagesService`` so the
    file is byte-for-byte the on-screen page for the same filters (location
    included). Marketing-page export is a documented gap until ENG-516 ships its
    page. Returns the bytes with a download ``Content-Disposition``.
    """
    tenant_id = principal.require_tenant()
    filters = _analytics_filters(
        time_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end,
        location_id=location_id,
        campaign_id=campaign_id,
        source=source,
        vendor_id=vendor_id,
        caller_id=caller_id,
        coordinator_id=coordinator_id,
        doctor_id=doctor_id,
    )
    result = await export.export_page(
        tenant_id, page=page, fmt=export_format, filters=filters
    )
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"'
        },
    )


# Default SEO window when the caller passes no dates: trailing 30 days
# (inclusive of today). GA4/GSC data is day-granular, so the window is a
# closed [start_date, end_date] date range.
_SEO_DEFAULT_WINDOW_DAYS = 30


@router.get("/analytics/seo", response_model=SeoAnalyticsOut)
async def analytics_seo(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    marketing: Annotated[MarketingService, Depends(get_marketing_service)],
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
) -> SeoAnalyticsOut:
    """Web Analytics / SEO dashboard (ENG-471) — GA4 + GSC tabs.

    Thin composer: ``MarketingService.ga_metric_totals`` owns the GA4 window
    rollup (sessions/users/new_users/pageviews/conversions + daily trend);
    ``MarketingService.gsc_query_totals`` owns the GSC window rollup (clicks /
    impressions / impression-weighted CTR + position / distinct queries + top
    queries). The route only assembles KPIs (reusing the marketing
    ``value=None`` convention for impression-weighted ratios on an empty
    window) and lists the not-ingested sources. The window is a closed date
    range; it defaults to the trailing 30 days when no dates are supplied.
    """
    tenant_id = principal.require_tenant()

    resolved_end = end_date or datetime.now(tz=UTC).date()
    resolved_start = start_date or (
        resolved_end - timedelta(days=_SEO_DEFAULT_WINDOW_DAYS)
    )

    ga = await marketing.ga_metric_totals(
        tenant_id, start_date=resolved_start, end_date=resolved_end
    )
    gsc = await marketing.gsc_query_totals(
        tenant_id, start_date=resolved_start, end_date=resolved_end
    )

    ga_kpis = [
        MarketingKpiOut(
            key="sessions",
            label="Sessions",
            value=float(ga.sessions),
            format="integer",
            hint="GA4 sessions across captured properties in the window",
        ),
        MarketingKpiOut(
            key="total_users",
            label="Total users",
            value=float(ga.total_users),
            format="integer",
            hint="Day-summed GA4 users (not deduplicated unique users)",
        ),
        MarketingKpiOut(
            key="new_users",
            label="New users",
            value=float(ga.new_users),
            format="integer",
        ),
        MarketingKpiOut(
            key="screen_page_views",
            label="Page views",
            value=float(ga.screen_page_views),
            format="integer",
        ),
        MarketingKpiOut(
            key="conversions",
            label="Conversions",
            value=ga.conversions,
            format="integer",
            hint="GA4-reported conversions",
        ),
    ]

    # Engagement KPIs (ENG-478) — value=None → UI "—" when not captured for the
    # window (rows pulled before ENG-478 have NULL engagement columns).
    ga_engagement_kpis = [
        MarketingKpiOut(
            key="engaged_sessions",
            label="Engaged sessions",
            value=(
                float(ga.engagement.engaged_sessions)
                if ga.engagement.engaged_sessions is not None
                else None
            ),
            format="integer",
            hint="GA4 engaged sessions in the window",
        ),
        MarketingKpiOut(
            key="engagement_rate",
            label="Engagement rate",
            value=ga.engagement.engagement_rate,
            format="percent",
            hint="Session-weighted GA4 engagement rate",
        ),
        MarketingKpiOut(
            key="avg_session_duration",
            label="Avg session duration",
            value=ga.engagement.avg_session_duration,
            format="ratio",
            hint="Session-weighted average session duration (seconds)",
        ),
        MarketingKpiOut(
            key="bounce_rate",
            label="Bounce rate",
            value=ga.engagement.bounce_rate,
            format="percent",
            hint="Session-weighted GA4 bounce rate",
        ),
        MarketingKpiOut(
            key="event_count",
            label="Events",
            value=(
                float(ga.engagement.event_count)
                if ga.engagement.event_count is not None
                else None
            ),
            format="integer",
            hint="GA4 event count in the window",
        ),
    ]

    gsc_kpis = [
        MarketingKpiOut(
            key="clicks",
            label="Clicks",
            value=float(gsc.clicks),
            format="integer",
            hint="Total organic-search clicks in the window",
        ),
        MarketingKpiOut(
            key="impressions",
            label="Impressions",
            value=float(gsc.impressions),
            format="integer",
        ),
        MarketingKpiOut(
            key="ctr",
            label="Avg CTR",
            value=gsc.ctr,
            format="percent",
            hint="Impression-weighted: clicks ÷ impressions",
        ),
        MarketingKpiOut(
            key="avg_position",
            label="Avg position",
            value=gsc.avg_position,
            format="ratio",
            hint="Impression-weighted average search position",
        ),
        MarketingKpiOut(
            key="distinct_queries",
            label="Queries",
            value=float(gsc.distinct_queries),
            format="integer",
            hint="Distinct search queries in the window",
        ),
    ]

    return SeoAnalyticsOut(
        window=SeoAnalyticsWindowOut(
            start_date=resolved_start, end_date=resolved_end
        ),
        ga=SeoGaOut(
            connected=ga.sessions > 0 or len(ga.daily) > 0,
            kpis=ga_kpis,
            engagement_kpis=ga_engagement_kpis,
            daily=[
                SeoGaDailyPointOut(
                    metric_date=point.metric_date,
                    sessions=point.sessions,
                    total_users=point.total_users,
                    new_users=point.new_users,
                    screen_page_views=point.screen_page_views,
                    conversions=point.conversions,
                )
                for point in ga.daily
            ],
            channels=[
                SeoGaChannelRowOut(
                    channel=row.channel,
                    sessions=row.sessions,
                    total_users=row.total_users,
                    new_users=row.new_users,
                    screen_page_views=row.screen_page_views,
                    conversions=row.conversions,
                )
                for row in ga.channels
            ],
            top_pages=[
                SeoGaPageRowOut(
                    page_path=row.page_path,
                    sessions=row.sessions,
                    total_users=row.total_users,
                    new_users=row.new_users,
                    screen_page_views=row.screen_page_views,
                    conversions=row.conversions,
                )
                for row in ga.top_pages
            ],
        ),
        gsc=SeoGscOut(
            connected=gsc.impressions > 0 or len(gsc.top_queries) > 0,
            kpis=gsc_kpis,
            top_queries=[
                SeoGscQueryRowOut(
                    query=row.query,
                    clicks=row.clicks,
                    impressions=row.impressions,
                    ctr=row.ctr,
                    position=row.position,
                )
                for row in gsc.top_queries
            ],
            top_pages=FullFunnelNotConfiguredOut(
                reason=(
                    "Page-level GSC data is not ingested — gsc_query_daily "
                    "keeps query rows only, with no page dimension."
                ),
                ticket="ENG-471",
            ),
        ),
        not_connected=list(_SEO_NOT_CONNECTED_SOURCES),
    )


@router.get("/analytics/sales", response_model=SalesAnalyticsOut)
async def analytics_sales(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    ops: Annotated[OpsService, Depends(get_ops_service)],
    interaction: Annotated[InteractionService, Depends(get_interaction_service)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
) -> SalesAnalyticsOut:
    """Sales Pipeline dashboard (ENG-473).

    Thin composer. ``OpsService.get_sales_pipeline_summary`` /
    ``get_pipeline_by_stage`` / ``get_tc_leaderboard`` /
    ``list_sales_consultations`` own every opportunity & consultation
    aggregation (won/closed read the ``extra.is_closed`` / ``extra.is_won``
    JSON booleans; pipeline-by-stage groups the raw ``stage`` dynamically).
    ``InteractionService.collected_by_person`` is read once and bridged into
    the per-TC and per-consultation views so Collected cash is attributed
    without ops importing interaction. The consultations table joins identity
    for the patient display name (staff-frontend PHI policy permits it). The
    patient follow-up calls/texts/emails split is not configured — only
    ``call_logged`` interaction events are ingested.
    """
    tenant_id = principal.require_tenant()

    summary = await ops.get_sales_pipeline_summary(tenant_id)
    stages = await ops.get_pipeline_by_stage(tenant_id)
    tc_rows = await ops.get_tc_leaderboard(tenant_id)
    consult_rows = await ops.list_sales_consultations(
        tenant_id, limit=_SALES_CONSULTATIONS_LIMIT
    )

    # Net Collected per person (interaction domain). Read once; attribute into
    # the per-TC and per-consultation views (ops never imports interaction).
    collected_by_person = await interaction.collected_by_person(tenant_id)
    total_collected = round(sum(collected_by_person.values()), 2)

    kpis = [
        MarketingKpiOut(
            key="pipeline_value",
            label="Pipeline value",
            value=summary.pipeline_value,
            format="currency",
            hint="Σ amount of open (not-closed) opportunities",
        ),
        MarketingKpiOut(
            key="active_opps",
            label="Active opps",
            value=float(summary.active_opps),
            format="integer",
            hint="Opportunities not marked closed",
        ),
        MarketingKpiOut(
            key="close_rate",
            label="Avg close rate",
            value=_ratio_kpi_value(summary.won_opps, summary.closed_opps),
            format="percent",
            hint="Won ÷ closed opportunities (— when nothing is closed yet)",
        ),
        MarketingKpiOut(
            key="won_revenue",
            label="Won revenue",
            value=summary.won_revenue,
            format="currency",
            hint="Σ amount of won opportunities",
        ),
        MarketingKpiOut(
            key="total_collected",
            label="Total collected",
            value=total_collected,
            format="currency",
            hint="Net Collected cash (recorded − refunded/reversed)",
        ),
    ]

    pipeline_by_stage = [
        SalesPipelineStageOut(stage=row.stage, count=row.count, value=row.value)
        for row in stages
    ]

    tc_leaderboard = [
        SalesTcLeaderboardRowOut(
            tc=row.tc,
            opps=row.opps,
            won=row.won,
            lost=row.lost,
            close_rate=_ratio_kpi_value(row.won, row.won + row.lost),
            value=row.value,
            won_revenue=row.won_revenue,
            collected=round(
                sum(collected_by_person.get(uid, 0.0) for uid in row.person_uids),
                2,
            ),
        )
        for row in tc_rows
    ]

    # One batched identity lookup for the consultations table — never N+1.
    persons = await identity.list_by_ids(
        tenant_id, [row.person_uid for row in consult_rows]
    )
    name_by_uid = {person.id: person.display_name for person in persons}

    consultations = []
    for row in consult_rows:
        paid = round(collected_by_person.get(row.person_uid, 0.0), 2)
        balance = (
            round(row.opp_value - paid, 2) if row.opp_value is not None else None
        )
        consultations.append(
            SalesConsultationOut(
                consultation_id=row.consultation_id,
                patient=name_by_uid.get(row.person_uid),
                tc=row.tc,
                status=row.status,
                scheduled_at=row.scheduled_at,
                stage=row.stage,
                opp_value=row.opp_value,
                paid=paid,
                balance=balance,
                close_date=row.close_date,
            )
        )

    return SalesAnalyticsOut(
        kpis=kpis,
        pipeline_by_stage=pipeline_by_stage,
        tc_leaderboard=tc_leaderboard,
        consultations=consultations,
        followups=FullFunnelNotConfiguredOut(
            reason=(
                "Patient follow-up calls/texts/emails split is not connected: "
                "only call_logged interaction events are ingested (no SMS or "
                "email event kinds), and followup_task carries no channel "
                "split."
            ),
            ticket="ENG-473",
        ),
    )


@router.get("/analytics/calls", response_model=CallsAnalyticsOut)
async def analytics_calls(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    interaction: Annotated[InteractionService, Depends(get_interaction_service)],
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
) -> CallsAnalyticsOut:
    """Calls dashboard (ENG-474) — call volume from logged interaction events.

    Thin composer: ``InteractionService.get_call_volume`` owns the call-event
    aggregation (per-kind counts + direction/duration from the PHI-free
    ``call_logged`` payload) and ``count_events_by_kind`` supplies the
    ``consultation_scheduled`` booking-rate denominator, both scoped to the
    window. The route only assembles KPIs (reusing the marketing ``value=None``
    convention for the booking ratio on a zero-call window) and lists the
    legacy sections pending the unbuilt Phase-3 telephony ingest. The window is
    a closed date range defaulting to the trailing 30 days.
    """
    tenant_id = principal.require_tenant()

    resolved_end = end_date or datetime.now(tz=UTC).date()
    resolved_start = start_date or (
        resolved_end - timedelta(days=_CALLS_DEFAULT_WINDOW_DAYS)
    )
    # Half-open [start, end+1day) window so the inclusive end date is covered.
    occurred_from = datetime.combine(resolved_start, time.min, tzinfo=UTC)
    occurred_to = datetime.combine(
        resolved_end + timedelta(days=1), time.min, tzinfo=UTC
    )

    volume = await interaction.get_call_volume(
        tenant_id, occurred_from=occurred_from, occurred_to=occurred_to
    )
    consult_counts = await interaction.count_events_by_kind(
        tenant_id,
        ["consultation_scheduled"],
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )
    consults_scheduled = consult_counts.get("consultation_scheduled", 0)

    kpis = [
        MarketingKpiOut(
            key="call_logged",
            label="Calls logged",
            value=float(volume.call_logged),
            format="integer",
            hint="Logged call activity events in the window (not a telephony feed)",
        ),
        MarketingKpiOut(
            key="inbound",
            label="Inbound",
            value=float(volume.inbound),
            format="integer",
            hint="call_logged events with payload direction=inbound",
        ),
        MarketingKpiOut(
            key="outbound",
            label="Outbound",
            value=float(volume.outbound),
            format="integer",
            hint="call_logged events with payload direction=outbound",
        ),
        MarketingKpiOut(
            key="avg_duration_seconds",
            label="Avg talk time (s)",
            value=volume.avg_duration_seconds,
            format="ratio",
            hint=(
                "Mean call_duration_seconds over calls with a non-zero "
                "duration (— when none carry one)"
            ),
        ),
        MarketingKpiOut(
            key="booking_rate",
            label="Booking rate",
            value=_ratio_kpi_value(consults_scheduled, volume.call_logged),
            format="percent",
            hint=(
                "Consultations scheduled ÷ calls logged in the window "
                "(— on a zero-call window). Coarse: not call-attributed."
            ),
        ),
        MarketingKpiOut(
            key="call_reference_found",
            label="Recording refs",
            value=float(volume.call_reference_found),
            format="integer",
            hint=(
                "Discovered call recording/reference URLs (reference only — "
                "playback/transcript pending Phase 3)"
            ),
        ),
    ]

    return CallsAnalyticsOut(
        window=CallsAnalyticsWindowOut(
            start_date=resolved_start, end_date=resolved_end
        ),
        connected=volume.call_logged > 0 or volume.call_reference_found > 0,
        kpis=kpis,
        pending=list(_CALLS_PENDING_SECTIONS),
    )


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_sf_iso_or_none(value: object) -> datetime | None:
    """Parse SF SOQL ISO timestamp ("2025-10-01T07:20:08.000+0000") to datetime.

    SF emits the timezone offset without the colon ("+0000"); Python's
    ``fromisoformat`` accepts "+00:00". Normalise before parsing.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.replace("Z", "+00:00")
    if len(candidate) >= 5 and candidate[-5] in ("+", "-") and candidate[-3] != ":":
        candidate = candidate[:-2] + ":" + candidate[-2:]
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _uuid_or_none(value: object) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return UUID(text)
        except ValueError:
            return None
    return None


def _lead_matches_query(item: DashboardPmLeadOut, query: str) -> bool:
    needle = query.casefold()
    haystack = (
        item.display_name,
        item.given_name,
        item.family_name,
        item.email,
        item.phone,
        item.lead_source,
        item.source_external_id,
        item.status,
    )
    return any(value is not None and needle in value.casefold() for value in haystack)


def _has_salesforce_and_carestack_links(source_providers: list[str]) -> bool:
    providers = set(source_providers)
    return "salesforce" in providers and "carestack" in providers


def _treatment_payment_message(
    source_provider: Literal["salesforce", "carestack"] | None,
) -> str:
    if source_provider == "salesforce":
        return (
            "CareStack treatment/payment aggregates are available, but the "
            "current provider filter is Salesforce-only."
        )
    return (
        "Read-only CareStack treatment/payment aggregates from workflow-ready "
        "events; raw payloads and clinical detail are excluded."
    )
