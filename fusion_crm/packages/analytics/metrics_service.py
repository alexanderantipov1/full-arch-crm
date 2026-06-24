"""Analytics metrics service — shared filter + derived-metric composition (ENG-507).

Thin read-only composition: resolve the shared time window, aggregate
``fact_patient_journey`` (own schema) under the global filters, pull ad spend
from ``MarketingService`` over the same window, and compute the derived-metric
layer once. The 14 pages compose onto this; the ``/dashboard/analytics/
journey-metrics`` smoke endpoint proves the contract.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from packages.core.types import TenantId
from packages.marketing.service import MarketingService
from packages.tenant.service import LocationService, TenantService

from .fact_repository import FactPatientJourneyRepository
from .filters import AnalyticsFilters, TimeRangePreset, resolve_time_range
from .metrics import StageAggregate, compute_derived_metrics, safe_div
from .models import FactPatientJourney
from .queries import (
    COHORT_HORIZONS,
    REVENUE_DIMENSIONS,
    FactAnalyticsQueries,
    FunnelAggregate,
    MarketingGroupRow,
)
from .schemas import (
    AnalyticsFiltersEchoOut,
    AnalyticsWindowOut,
    AttributionAnalyticsOut,
    AttributionDimensionOut,
    BottleneckEntityOut,
    BottleneckOut,
    BottlenecksOut,
    CallerGroupOut,
    CallerPerformanceOut,
    CohortAnalyticsOut,
    CohortRevenueOut,
    CohortRowOut,
    CoordinatorGroupOut,
    CoordinatorPerformanceOut,
    CostIntelligenceOut,
    CostMetricOut,
    DerivedMetricsOut,
    DoctorGroupOut,
    DoctorPerformanceOut,
    DrilldownMetric,
    ExecutiveOverviewOut,
    FactAggregateOut,
    FunnelStageOut,
    FunnelStagesOut,
    InfluenceRowOut,
    JourneyMetricsOut,
    JourneyStepOut,
    MarketingBreakdownOut,
    MarketingGroupOut,
    MarketingPerformanceOut,
    MetricDrilldownOut,
    PatientJourneyOut,
    RevenueDimensionOut,
    RevenueGroupOut,
    RevenueInfluenceMatrixOut,
    RevenueIntelligenceOut,
    RevenueWidgetOut,
    VendorGroupOut,
    VendorPerformanceOut,
)

# Drill-down bounds (ENG-508). ``HARD_CAP`` is the absolute ceiling on returned
# ``person_uid`` rows — the service clamps to it regardless of the requested
# limit, so the endpoint can never stream an unbounded patient list.
DRILLDOWN_DEFAULT_LIMIT = 500
DRILLDOWN_HARD_CAP = 1000


class AnalyticsMetricsService:
    """Resolve filters → fact aggregate + spend → derived metrics (ENG-507)."""

    def __init__(
        self,
        *,
        fact_repo: FactPatientJourneyRepository,
        marketing: MarketingService,
        tenant: TenantService,
        location: LocationService,
    ) -> None:
        self._fact_repo = fact_repo
        self._marketing = marketing
        self._tenant = tenant
        self._location = location

    async def _resolve_tz(
        self, tenant_id: TenantId, location_id: UUID | None
    ) -> str:
        """Per-location timezone (``timezone_override`` ?? tenant) for the window.

        Aggregate (no location) uses the tenant timezone; a per-location request
        uses that location's ``timezone_override`` falling back to the tenant.
        """
        tenant = await self._tenant.get_tenant(tenant_id)
        tz = tenant.timezone
        if location_id is not None:
            location = await self._location.get_location(tenant_id, location_id)
            tz = location.timezone_override or tenant.timezone
        return tz or "UTC"

    async def journey_metrics(
        self,
        tenant_id: TenantId,
        filters: AnalyticsFilters,
        *,
        now: datetime | None = None,
        tz: str | None = None,
    ) -> JourneyMetricsOut:
        """Compute the foundation metrics contract for one filter selection."""
        resolved_tz = tz or await self._resolve_tz(tenant_id, filters.location_id)
        window = filters.resolve_window(now=now, tz=resolved_tz)
        agg = await self._fact_repo.aggregate(window=window, filters=filters)

        # Ad spend over the same window (inclusive date bounds for marketing's
        # day-granular spend). ``None`` when no spend source is connected, so
        # cost/ROI render "—" rather than a fabricated 0.
        start_date = window.start.date()
        end_date = (window.end - timedelta(seconds=1)).date()
        totals = await self._marketing.ad_spend_totals(
            tenant_id, start_date=start_date, end_date=end_date
        )
        spend = totals.spend if totals.rows else None

        derived = compute_derived_metrics(
            StageAggregate(
                leads=agg.leads,
                contacts=agg.contacts,
                consults=agg.consults,
                shows=agg.shows,
                surgeries=agg.surgeries,
                revenue=agg.revenue,
                collected=agg.collected,
                spend=spend,
            )
        )

        return JourneyMetricsOut(
            window=AnalyticsWindowOut(
                preset=window.preset,
                start=window.start,
                end=window.end,
                tz=window.tz,
            ),
            filters=AnalyticsFiltersEchoOut(
                time_range=filters.time_range,
                location_id=filters.location_id,
                campaign_id=filters.campaign_id,
                source=filters.source,
                vendor_id=filters.vendor_id,
                caller_id=filters.caller_id,
                coordinator_id=filters.coordinator_id,
                doctor_id=filters.doctor_id,
            ),
            aggregate=FactAggregateOut(
                leads=agg.leads,
                contacts=agg.contacts,
                consults=agg.consults,
                shows=agg.shows,
                surgeries=agg.surgeries,
                patients=agg.patients,
                revenue=agg.revenue,
                collected=agg.collected,
                spend=spend,
            ),
            derived=DerivedMetricsOut(
                cost_per_lead=derived.cost_per_lead,
                cost_per_consult=derived.cost_per_consult,
                cost_per_show=derived.cost_per_show,
                cost_per_surgery=derived.cost_per_surgery,
                revenue_per_lead=derived.revenue_per_lead,
                revenue_per_show=derived.revenue_per_show,
                roi=derived.roi,
                lead_to_contact=derived.lead_to_contact,
                contact_to_consult=derived.contact_to_consult,
                consult_to_show=derived.consult_to_show,
                show_to_surgery=derived.show_to_surgery,
                surgery_to_revenue=derived.surgery_to_revenue,
            ),
        )


# Human labels for the eight funnel stages (market.md page 1/2 ladder).
_FUNNEL_STAGE_LABELS: dict[str, str] = {
    "leads": "Leads",
    "reached": "Reached",
    "consults": "Consults Scheduled",
    "shows": "Shows",
    "treatment_presented": "Treatment Plans Presented",
    "treatment_accepted": "Treatment Accepted",
    "surgery_scheduled": "Surgeries Scheduled",
    "surgery_completed": "Surgeries Completed",
}

# Realized-cash widget ladder for the Executive page (Today…YTD) + labels.
_REVENUE_WIDGETS: tuple[tuple[TimeRangePreset, str], ...] = (
    ("today", "Today"),
    ("yesterday", "Yesterday"),
    ("last_7_days", "Last 7 days"),
    ("last_30_days", "Last 30 days"),
    ("this_month", "Month to date"),
    ("this_quarter", "Quarter to date"),
    ("this_year", "Year to date"),
)

# Breakdown dimensions the fact can attribute today vs. those that stay
# "Unattributed" until B1.1/B1.2 (people) land. Campaign/source/location are
# resolved from canonical data; vendor/caller/coordinator/doctor are not yet.
_RESOLVED_DIMENSIONS: frozenset[str] = frozenset({"campaign", "source", "location"})

# Honest no-data note for vendor attribution (ENG-517 / ENG-525 / ENG-527).
# ``vendor_id`` is 100% NULL on the fact today (verified 2026-06-23: 0 of
# 115,715 rows populated). Vendor binding is owned by ENG-569. The query
# groups by vendor_id so the page lights up automatically once populated.
_VENDOR_ATTRIBUTION_NOTE = (
    "Vendor attribution is not yet wired to the analytics fact "
    "(vendor_id is NULL on all current rows). "
    "The vendor binding epic (ENG-569) will populate this column; "
    "until then only an 'Unassigned' bucket is shown. "
    "No per-vendor data is fabricated."
)

# Attribution dimensions for ENG-525 (ordered for display).
# campaign → resolved; vendor → unresolved (100% NULL today);
# caller / coordinator / doctor → partial coverage (NULL = Unassigned).
_ATTRIBUTION_DIMENSIONS: tuple[tuple[str, bool], ...] = (
    ("campaign", True),
    ("vendor", False),
    ("caller", True),
    ("coordinator", True),
    ("doctor", True),
)

# Role → fact column for the influence matrix (ENG-527).
# Vendor is included so the wiring is in place; rows will be empty today.
_INFLUENCE_ROLES: tuple[str, ...] = ("vendor", "caller", "coordinator", "doctor")

# Marketing-performance dimensions the fact cannot attribute yet (ENG-516). The
# fact carries no ad-set/ad column, so outcomes can't be tied to an ad set or
# ad — the page renders an explicit "no data" panel and the window-level
# spend_without_leads surfaces the ad spend that produced no attributed leads.
_MARKETING_UNRESOLVED_DIMENSIONS: tuple[str, ...] = ("ad_set", "ad")
_MARKETING_UNRESOLVED_NOTE = (
    "Ad-set / ad attribution isn't resolved on the patient-journey fact yet, so "
    "per-ad-set / per-ad outcomes can't be shown. The window's "
    "'spend without leads' surfaces ad spend that produced no attributed leads."
)


# Ordered patient-journey steps: fact stage column → label (ENG-523). The
# responsibility steps (caller/coordinator/doctor assigned) carry no date until
# B1, so they surface as ``responsible_employee = null`` on the dated steps.
_JOURNEY_STEPS: tuple[tuple[str, str], ...] = (
    ("lead_date", "Lead Created"),
    ("first_contact_date", "First Contact"),
    ("consult_scheduled_date", "Consult Scheduled"),
    ("show_date", "Show"),
    ("treatment_presented_date", "Treatment Presented"),
    ("treatment_accepted_date", "Treatment Accepted"),
    ("surgery_scheduled_date", "Surgery Scheduled"),
    ("surgery_completed_date", "Surgery Completed"),
    ("first_payment_date", "First Payment"),
)


def _funnel_stage_outs(
    agg: FunnelAggregate, spend: float | None
) -> list[FunnelStageOut]:
    """Funnel rows with per-stage conversion (vs previous) + cost (spend ÷ count).

    The entry stage has no previous, so its ``conversion`` is ``null``; any zero
    denominator (or missing spend) collapses to ``null`` via ``safe_div``.
    """
    outs: list[FunnelStageOut] = []
    prev_count: int | None = None
    for stage in agg.stages:
        conversion = None if prev_count is None else safe_div(stage.count, prev_count)
        outs.append(
            FunnelStageOut(
                key=stage.key,
                label=_FUNNEL_STAGE_LABELS[stage.key],
                count=stage.count,
                revenue=stage.revenue,
                collected=stage.collected,
                conversion=conversion,
                cost=safe_div(spend, stage.count),
            )
        )
        prev_count = stage.count
    return outs


class AnalyticsPagesService:
    """Read-only composition for the five B2 data-ready pages (ENG-514…523).

    Sits beside :class:`AnalyticsMetricsService` (left untouched) so the new
    pages add no regression surface to the foundation contract. Every page
    resolves the shared window in the per-location timezone, aggregates the fact
    via :class:`FactAnalyticsQueries`, and pulls ad spend from
    ``MarketingService`` over the same window for the cost/ROI layer.
    """

    def __init__(
        self,
        *,
        queries: FactAnalyticsQueries,
        marketing: MarketingService,
        tenant: TenantService,
        location: LocationService,
    ) -> None:
        self._queries = queries
        self._marketing = marketing
        self._tenant = tenant
        self._location = location

    async def _resolve_tz(
        self, tenant_id: TenantId, location_id: UUID | None
    ) -> str:
        """Per-location timezone (``timezone_override`` ?? tenant)."""
        tenant = await self._tenant.get_tenant(tenant_id)
        tz = tenant.timezone
        if location_id is not None:
            location = await self._location.get_location(tenant_id, location_id)
            tz = location.timezone_override or tenant.timezone
        return tz or "UTC"

    async def _spend(
        self, tenant_id: TenantId, *, start: datetime, end: datetime
    ) -> float | None:
        """Ad spend over the window (``None`` when no source is connected).

        Inclusive date bounds for marketing's day-granular spend; ``None`` (not
        0) when nothing is connected, so cost/ROI render "—".
        """
        start_date = start.date()
        end_date = (end - timedelta(seconds=1)).date()
        totals = await self._marketing.ad_spend_totals(
            tenant_id, start_date=start_date, end_date=end_date
        )
        return totals.spend if totals.rows else None

    def _window_out(self, window: object) -> AnalyticsWindowOut:
        return AnalyticsWindowOut(
            preset=window.preset,  # type: ignore[attr-defined]
            start=window.start,  # type: ignore[attr-defined]
            end=window.end,  # type: ignore[attr-defined]
            tz=window.tz,  # type: ignore[attr-defined]
        )

    def _filters_out(self, filters: AnalyticsFilters) -> AnalyticsFiltersEchoOut:
        return AnalyticsFiltersEchoOut(
            time_range=filters.time_range,
            location_id=filters.location_id,
            campaign_id=filters.campaign_id,
            source=filters.source,
            vendor_id=filters.vendor_id,
            caller_id=filters.caller_id,
            coordinator_id=filters.coordinator_id,
            doctor_id=filters.doctor_id,
        )

    async def executive_overview(
        self,
        tenant_id: TenantId,
        filters: AnalyticsFilters,
        *,
        now: datetime | None = None,
        tz: str | None = None,
    ) -> ExecutiveOverviewOut:
        """Executive Overview (ENG-514): funnel + cost/ROI + realized-cash cards."""
        resolved_tz = tz or await self._resolve_tz(tenant_id, filters.location_id)
        window = filters.resolve_window(now=now, tz=resolved_tz)
        agg = await self._queries.funnel(window=window, filters=filters)
        spend = await self._spend(tenant_id, start=window.start, end=window.end)

        stages = _funnel_stage_outs(agg, spend)
        counts = {s.key: s.count for s in agg.stages}
        derived = compute_derived_metrics(
            StageAggregate(
                leads=counts["leads"],
                contacts=counts["reached"],
                consults=counts["consults"],
                shows=counts["shows"],
                surgeries=counts["surgery_completed"],
                revenue=agg.revenue_total,
                collected=agg.collected_total,
                spend=spend,
            )
        )

        widgets: list[RevenueWidgetOut] = []
        for preset, label in _REVENUE_WIDGETS:
            w = resolve_time_range(
                preset, now=now or _utcnow(), tz=resolved_tz
            )
            money = await self._queries.realized_money(
                start=w.start, end=w.end, filters=filters
            )
            widgets.append(
                RevenueWidgetOut(
                    preset=preset,
                    label=label,
                    gross=money.gross,
                    collected=money.collected,
                    payers=money.payers,
                )
            )

        return ExecutiveOverviewOut(
            window=self._window_out(window),
            filters=self._filters_out(filters),
            funnel=stages,
            derived=DerivedMetricsOut(
                cost_per_lead=derived.cost_per_lead,
                cost_per_consult=derived.cost_per_consult,
                cost_per_show=derived.cost_per_show,
                cost_per_surgery=derived.cost_per_surgery,
                revenue_per_lead=derived.revenue_per_lead,
                revenue_per_show=derived.revenue_per_show,
                roi=derived.roi,
                lead_to_contact=derived.lead_to_contact,
                contact_to_consult=derived.contact_to_consult,
                consult_to_show=derived.consult_to_show,
                show_to_surgery=derived.show_to_surgery,
                surgery_to_revenue=derived.surgery_to_revenue,
            ),
            spend=spend,
            revenue_total=agg.revenue_total,
            collected_total=agg.collected_total,
            outstanding_total=agg.revenue_total - agg.collected_total,
            patients=agg.patients,
            revenue_widgets=widgets,
        )

    async def funnel_stages(
        self,
        tenant_id: TenantId,
        filters: AnalyticsFilters,
        *,
        now: datetime | None = None,
        tz: str | None = None,
    ) -> FunnelStagesOut:
        """Funnel Analytics (ENG-515): nine-point funnel over the shared fact."""
        resolved_tz = tz or await self._resolve_tz(tenant_id, filters.location_id)
        window = filters.resolve_window(now=now, tz=resolved_tz)
        agg = await self._queries.funnel(window=window, filters=filters)
        spend = await self._spend(tenant_id, start=window.start, end=window.end)
        return FunnelStagesOut(
            window=self._window_out(window),
            filters=self._filters_out(filters),
            stages=_funnel_stage_outs(agg, spend),
            spend=spend,
            patients=agg.patients,
            revenue_total=agg.revenue_total,
            collected_total=agg.collected_total,
        )

    async def revenue_intelligence(
        self,
        tenant_id: TenantId,
        filters: AnalyticsFilters,
        *,
        now: datetime | None = None,
        tz: str | None = None,
    ) -> RevenueIntelligenceOut:
        """Revenue Intelligence (ENG-521): revenue by all seven dimensions."""
        resolved_tz = tz or await self._resolve_tz(tenant_id, filters.location_id)
        window = filters.resolve_window(now=now, tz=resolved_tz)

        dimensions: list[RevenueDimensionOut] = []
        for dim in REVENUE_DIMENSIONS:
            rows = await self._queries.revenue_by_dimension(
                window=window, filters=filters, dimension=dim
            )
            groups = [
                RevenueGroupOut(
                    group_id=r.group_id,
                    group_label=r.group_label,
                    gross=r.gross,
                    collected=r.collected,
                    outstanding=r.outstanding,
                    case_count=r.case_count,
                    avg_case_value=safe_div(r.gross, r.case_count),
                )
                for r in rows
            ]
            dimensions.append(
                RevenueDimensionOut(
                    dimension=dim,
                    resolved=dim in _RESOLVED_DIMENSIONS,
                    groups=groups,
                )
            )

        # Any dimension partitions the same cohort, so summing one yields totals.
        source_dim = next(d for d in dimensions if d.dimension == "source")
        gross_total = sum(g.gross for g in source_dim.groups)
        collected_total = sum(g.collected for g in source_dim.groups)
        case_count = sum(g.case_count for g in source_dim.groups)

        return RevenueIntelligenceOut(
            window=self._window_out(window),
            filters=self._filters_out(filters),
            gross_total=gross_total,
            collected_total=collected_total,
            outstanding_total=gross_total - collected_total,
            avg_case_value=safe_div(gross_total, case_count),
            case_count=case_count,
            dimensions=dimensions,
        )

    async def marketing_performance(
        self,
        tenant_id: TenantId,
        filters: AnalyticsFilters,
        *,
        now: datetime | None = None,
        tz: str | None = None,
    ) -> MarketingPerformanceOut:
        """Marketing Performance (ENG-516) — ad spend ⇄ outcomes by campaign/source.

        Joins the cost-per-lead allocation (``marketing_cost_allocated`` on the
        fact) with the window's ground-truth ad spend from ``MarketingService``.
        Campaign / source breakdowns resolve from the fact; ad_set / ad come back
        ``resolved=false`` (the fact has no ad-set/ad dimension). The window-level
        ``spend_without_leads`` surfaces ad spend that produced no attributed
        leads, never hiding it.
        """
        resolved_tz = tz or await self._resolve_tz(tenant_id, filters.location_id)
        window = filters.resolve_window(now=now, tz=resolved_tz)

        # Ground-truth ad spend over the window (``None`` when no spend source is
        # connected → spend / ROI render "—" rather than a fabricated 0).
        start_date = window.start.date()
        end_date = (window.end - timedelta(seconds=1)).date()
        totals = await self._marketing.ad_spend_totals(
            tenant_id, start_date=start_date, end_date=end_date
        )
        connected = bool(totals.rows)
        total_spend = totals.spend if connected else None

        campaign_rows = await self._queries.marketing_breakdown(
            window=window, filters=filters, dimension="campaign"
        )
        source_rows = await self._queries.marketing_breakdown(
            window=window, filters=filters, dimension="source"
        )

        # Window totals: source partitions the whole cohort, so summing one
        # dimension yields the page totals (and the allocated-spend total).
        leads = sum(r.leads for r in source_rows)
        consults = sum(r.consults for r in source_rows)
        shows = sum(r.shows for r in source_rows)
        surgeries = sum(r.surgeries for r in source_rows)
        revenue_total = sum(r.revenue for r in source_rows)
        collected_total = sum(r.collected for r in source_rows)
        allocated_raw = sum(r.spend for r in source_rows)

        allocated_spend = allocated_raw if connected else None
        # ``totals.spend`` is always a float (0.0 when no rows); guarding on
        # ``connected`` keeps ``spend_without_leads`` null when no source is
        # connected without a None-subtraction.
        spend_without_leads = (
            max(totals.spend - allocated_raw, 0.0) if connected else None
        )

        breakdowns = [
            MarketingBreakdownOut(
                dimension="campaign",
                resolved=True,
                groups=[
                    self._marketing_group_out(r, connected) for r in campaign_rows
                ],
            ),
            MarketingBreakdownOut(
                dimension="source",
                resolved=True,
                groups=[
                    self._marketing_group_out(r, connected) for r in source_rows
                ],
            ),
        ]
        breakdowns.extend(
            MarketingBreakdownOut(
                dimension=dim,
                resolved=False,
                groups=[],
                note=_MARKETING_UNRESOLVED_NOTE,
            )
            for dim in _MARKETING_UNRESOLVED_DIMENSIONS
        )

        return MarketingPerformanceOut(
            window=self._window_out(window),
            filters=self._filters_out(filters),
            total_spend=total_spend,
            allocated_spend=allocated_spend,
            spend_without_leads=spend_without_leads,
            leads=leads,
            consults=consults,
            shows=shows,
            surgeries=surgeries,
            revenue_total=revenue_total,
            collected_total=collected_total,
            roi=safe_div(revenue_total, total_spend),
            breakdowns=breakdowns,
        )

    @staticmethod
    def _marketing_group_out(
        row: MarketingGroupRow, connected: bool
    ) -> MarketingGroupOut:
        """One breakdown row + derived ROI / cost-per-stage (div-by-zero → null).

        ``spend`` (and every spend-derived metric) is ``None`` when no ad-spend
        source is connected for the window, so the UI renders "—".
        """
        spend = row.spend if connected else None
        return MarketingGroupOut(
            group_id=row.group_id,
            group_label=row.group_label,
            spend=spend,
            leads=row.leads,
            consults=row.consults,
            shows=row.shows,
            surgeries=row.surgeries,
            revenue=row.revenue,
            collected=row.collected,
            roi=safe_div(row.revenue, spend),
            cost_per_lead=safe_div(spend, row.leads),
            cost_per_consult=safe_div(spend, row.consults),
            cost_per_show=safe_div(spend, row.shows),
            cost_per_surgery=safe_div(spend, row.surgeries),
        )

    async def cohort_analytics(
        self,
        tenant_id: TenantId,
        filters: AnalyticsFilters,
        *,
        now: datetime | None = None,
        tz: str | None = None,
    ) -> CohortAnalyticsOut:
        """Cohort Analytics (ENG-526): cumulative revenue by lead-creation month."""
        resolved_tz = tz or await self._resolve_tz(tenant_id, filters.location_id)
        window = filters.resolve_window(now=now, tz=resolved_tz)
        rows = await self._queries.cohorts(window=window, filters=filters)
        cohorts = [
            CohortRowOut(
                cohort_month=r.cohort_month,
                lead_count=r.lead_count,
                revenue=CohortRevenueOut(
                    d30=r.revenue_by_day[30],
                    d60=r.revenue_by_day[60],
                    d90=r.revenue_by_day[90],
                    d180=r.revenue_by_day[180],
                    d365=r.revenue_by_day[365],
                ),
                collected_total=r.collected_total,
            )
            for r in rows
        ]
        return CohortAnalyticsOut(
            window=self._window_out(window),
            filters=self._filters_out(filters),
            horizons=list(COHORT_HORIZONS),
            cohorts=cohorts,
        )

    async def patient_journey(
        self, tenant_id: TenantId, person_uid: UUID
    ) -> PatientJourneyOut:
        """Patient Journey (ENG-523): one person's stage timeline from the fact."""
        row = await self._queries.journey_row(person_uid)
        if row is None:
            return PatientJourneyOut(person_uid=person_uid, found=False, steps=[])

        steps: list[JourneyStepOut] = []
        for column, label in _JOURNEY_STEPS:
            occurred_at = getattr(row, column)
            revenue = (
                float(row.collected_amount)
                if column == "first_payment_date" and row.collected_amount is not None
                else None
            )
            steps.append(
                JourneyStepOut(
                    key=column,
                    label=label,
                    occurred_at=occurred_at,
                    # caller/coordinator/doctor unresolved until B1 → no data.
                    responsible_employee=None,
                    revenue=revenue,
                )
            )

        return PatientJourneyOut(
            person_uid=person_uid,
            found=True,
            campaign_id=row.campaign_id,
            campaign_name=row.campaign_name,
            source=row.source,
            location_id=row.location_id,
            revenue_amount=(
                float(row.revenue_amount) if row.revenue_amount is not None else None
            ),
            collected_amount=(
                float(row.collected_amount)
                if row.collected_amount is not None
                else None
            ),
            steps=steps,
        )

    async def metric_drilldown(
        self,
        tenant_id: TenantId,
        filters: AnalyticsFilters,
        *,
        metric: DrilldownMetric,
        limit: int = DRILLDOWN_DEFAULT_LIMIT,
        now: datetime | None = None,
        tz: str | None = None,
    ) -> MetricDrilldownOut:
        """Metric → underlying ``person_uid`` set for the active filters (ENG-508).

        Resolves the shared window in the per-location timezone, then asks the
        fact for the in-cohort persons matching the metric — same ``lead_date``
        cohort + dimension filters as the on-screen pages, so the list reconciles
        with the count. Deterministically ordered and clamped to
        :data:`DRILLDOWN_HARD_CAP`; ``truncated`` flags when more matched.
        """
        bounded = max(1, min(limit, DRILLDOWN_HARD_CAP))
        resolved_tz = tz or await self._resolve_tz(tenant_id, filters.location_id)
        window = filters.resolve_window(now=now, tz=resolved_tz)
        person_uids, total = await self._queries.metric_person_uids(
            window=window, filters=filters, metric=metric, limit=bounded
        )
        return MetricDrilldownOut(
            metric=metric,
            window=self._window_out(window),
            filters=self._filters_out(filters),
            total=total,
            returned=len(person_uids),
            truncated=total > len(person_uids),
            person_uids=person_uids,
        )


    # ------------------------------------------------------------------
    # ENG-518 / ENG-519 / ENG-520 — Actor Performance pages
    # ------------------------------------------------------------------

    async def caller_performance(
        self,
        tenant_id: TenantId,
        filters: AnalyticsFilters,
        *,
        now: datetime | None = None,
        tz: str | None = None,
    ) -> CallerPerformanceOut:
        """Caller Performance (ENG-518) — per-caller lead → contact → consult.

        Groups the lead-date cohort by ``caller_id``; NULL → "Unassigned".
        ``calls_made`` is ``None`` on every row (honest no-data: the fact
        carries no per-call-attempt count column; ``first_contact_date`` only
        records whether contact was made). Derived ratios use ``safe_div`` so
        a zero denominator renders "—", never a fabricated 0.
        """
        resolved_tz = tz or await self._resolve_tz(tenant_id, filters.location_id)
        window = filters.resolve_window(now=now, tz=resolved_tz)
        rows = await self._queries.caller_performance(window=window, filters=filters)

        callers = [
            CallerGroupOut(
                caller_id=r.caller_id,
                leads=r.leads,
                reached=r.reached,
                consults=r.consults,
                calls_made=None,  # honest no-data: no dialer count in the fact
                lead_to_contact=safe_div(r.reached, r.leads),
                lead_to_consult=safe_div(r.consults, r.leads),
                collected=r.collected,
                revenue_per_lead=safe_div(r.collected, r.leads),
                revenue_per_consult=safe_div(r.collected, r.consults),
            )
            for r in rows
        ]
        return CallerPerformanceOut(
            window=self._window_out(window),
            filters=self._filters_out(filters),
            callers=callers,
        )

    async def coordinator_performance(
        self,
        tenant_id: TenantId,
        filters: AnalyticsFilters,
        *,
        now: datetime | None = None,
        tz: str | None = None,
    ) -> CoordinatorPerformanceOut:
        """Coordinator Performance (ENG-519) — consult → show → surgery per TC.

        Groups the lead-date cohort by ``coordinator_id``; NULL → "Unassigned".
        Conversions: ``scheduled_to_show`` = shows / consults_assigned;
        ``show_to_surgery`` = surgery_completed / shows;
        ``revenue_per_consult`` = collected / consults_assigned.
        All ``null`` on a zero denominator via ``safe_div``.
        """
        resolved_tz = tz or await self._resolve_tz(tenant_id, filters.location_id)
        window = filters.resolve_window(now=now, tz=resolved_tz)
        rows = await self._queries.coordinator_performance(
            window=window, filters=filters
        )

        coordinators = [
            CoordinatorGroupOut(
                coordinator_id=r.coordinator_id,
                consults_assigned=r.consults_assigned,
                shows=r.shows,
                treatment_presented=r.treatment_presented,
                surgery_scheduled=r.surgery_scheduled,
                surgery_completed=r.surgery_completed,
                collected=r.collected,
                scheduled_to_show=safe_div(r.shows, r.consults_assigned),
                show_to_surgery=safe_div(r.surgery_completed, r.shows),
                revenue_per_consult=safe_div(r.collected, r.consults_assigned),
            )
            for r in rows
        ]
        return CoordinatorPerformanceOut(
            window=self._window_out(window),
            filters=self._filters_out(filters),
            coordinators=coordinators,
        )

    async def doctor_performance(
        self,
        tenant_id: TenantId,
        filters: AnalyticsFilters,
        *,
        now: datetime | None = None,
        tz: str | None = None,
    ) -> DoctorPerformanceOut:
        """Doctor Performance (ENG-520) — consult → treatment → surgery per doctor.

        Groups the lead-date cohort by ``doctor_id``; NULL → "Unassigned".
        Conversions: ``consult_to_accepted`` = treatment_accepted / consults;
        ``accepted_to_surgery`` = surgery_completed / treatment_accepted.
        Revenue: ``revenue_per_consult`` = collected / consults;
        ``revenue_per_surgery`` = collected / surgery_completed.
        All ``null`` on a zero denominator via ``safe_div``.
        """
        resolved_tz = tz or await self._resolve_tz(tenant_id, filters.location_id)
        window = filters.resolve_window(now=now, tz=resolved_tz)
        rows = await self._queries.doctor_performance(window=window, filters=filters)

        doctors = [
            DoctorGroupOut(
                doctor_id=r.doctor_id,
                consults=r.consults,
                treatment_presented=r.treatment_presented,
                treatment_accepted=r.treatment_accepted,
                surgery_completed=r.surgery_completed,
                collected=r.collected,
                consult_to_accepted=safe_div(r.treatment_accepted, r.consults),
                accepted_to_surgery=safe_div(r.surgery_completed, r.treatment_accepted),
                revenue_per_consult=safe_div(r.collected, r.consults),
                revenue_per_surgery=safe_div(r.collected, r.surgery_completed),
            )
            for r in rows
        ]
        return DoctorPerformanceOut(
            window=self._window_out(window),
            filters=self._filters_out(filters),
            doctors=doctors,
        )


    async def cost_intelligence(
        self,
        tenant_id: TenantId,
        filters: AnalyticsFilters,
        *,
        now: datetime | None = None,
        tz: str | None = None,
    ) -> CostIntelligenceOut:
        """Cost Intelligence (ENG-522) — marketing cost per funnel stage.

        Spend = ground-truth window ad spend from ``MarketingService`` (the same
        source ``marketing_performance`` uses — never from the per-lead allocation
        column). When spend is ``None`` (no ad-spend source connected) every
        spend-derived metric is ``None`` and renders "—".

        Marketing cost metrics (computable):
        - cost_per_lead        = spend / leads
        - cost_per_consult     = spend / consults_scheduled
        - cost_per_show        = spend / shows
        - cost_per_surgery     = spend / surgeries_completed
        - cost_per_revenue_dollar = spend / collected (efficiency of spend)

        Operational cost metrics (honest no-data — inputs not yet captured):
        - cost_per_caller_conversion — requires caller operational cost data
        - cost_per_coordinator_conversion — requires coordinator cost data

        All marketing metrics use ``safe_div`` so a zero denominator yields
        ``None`` (renders "—") instead of a fabricated 0. Cohort anchor =
        ``lead_date`` in window so counts reconcile with the funnel page.
        """
        resolved_tz = tz or await self._resolve_tz(tenant_id, filters.location_id)
        window = filters.resolve_window(now=now, tz=resolved_tz)
        agg = await self._queries.funnel(window=window, filters=filters)
        spend = await self._spend(tenant_id, start=window.start, end=window.end)

        counts = {s.key: s.count for s in agg.stages}
        leads = counts["leads"]
        consults = counts["consults"]
        shows = counts["shows"]
        surgeries = counts["surgery_completed"]
        collected = agg.collected_total

        no_spend_note = (
            "No ad-spend source connected for this window — "
            "connect a marketing data source to see cost metrics."
        )
        no_operational_note = (
            "Operational cost inputs (staff salary / cost-per-hour) "
            "are not yet captured in the system."
        )

        def _mkt_metric(label: str, denom: int | float) -> CostMetricOut:
            """Marketing cost metric: spend / denom, or null with reason."""
            if spend is None:
                return CostMetricOut(label=label, value=None, note=no_spend_note)
            value = safe_div(spend, denom)
            note = (
                f"No {label.lower().split('per ')[-1]}s in this cohort."
                if value is None
                else None
            )
            return CostMetricOut(label=label, value=value, note=note)

        return CostIntelligenceOut(
            window=self._window_out(window),
            filters=self._filters_out(filters),
            spend=spend,
            leads=leads,
            consults=consults,
            shows=shows,
            surgeries=surgeries,
            collected=collected,
            cost_per_lead=_mkt_metric("Cost per Lead", leads),
            cost_per_consult=_mkt_metric("Cost per Consultation", consults),
            cost_per_show=_mkt_metric("Cost per Show", shows),
            cost_per_surgery=_mkt_metric("Cost per Surgery", surgeries),
            cost_per_revenue_dollar=CostMetricOut(
                label="Cost per Revenue Dollar",
                value=safe_div(spend, collected) if spend is not None else None,
                note=no_spend_note if spend is None else None,
            ),
            cost_per_caller_conversion=CostMetricOut(
                label="Cost per Caller Conversion",
                value=None,
                note=no_operational_note,
            ),
            cost_per_coordinator_conversion=CostMetricOut(
                label="Cost per Coordinator Conversion",
                value=None,
                note=no_operational_note,
            ),
        )

    async def bottleneck_detection(
        self,
        tenant_id: TenantId,
        filters: AnalyticsFilters,
        *,
        now: datetime | None = None,
        tz: str | None = None,
    ) -> BottlenecksOut:
        """Bottleneck Detection (ENG-524) — rule-based funnel bottleneck finder.

        Fetches the existing per-actor breakdown aggregates (caller / coordinator /
        doctor) and the campaign marketing breakdown, then applies a set of named
        rule functions. Each rule:
        1. Requires a minimum sample size (entities below the threshold are
           skipped — no findings invented from noise).
        2. Compares each entity's conversion rate to the cohort median.
        3. Emits a ``BottleneckOut`` only when the deviation exceeds the threshold.

        Revenue-loss estimation formula (documented per rule in the helpers below):
        - ``_campaign_show_rate_rule``:
          lost_leads = entity_leads * (median_show_rate - entity_show_rate)
          lost_revenue = lost_leads * (cohort_collected / max(cohort_leads, 1))
        - ``_coordinator_surgery_rule``:
          lost_surgeries = consults * (median_show_to_surgery - entity_show_to_surgery)
          lost_revenue = lost_surgeries * (cohort_collected / max(cohort_surgeries, 1))
        - ``_doctor_acceptance_rule``:
          lost_treatments = consults * (median_acceptance - entity_acceptance)
          lost_revenue = lost_treatments * (cohort_collected / max(cohort_accepted, 1))
        - ``_caller_booking_rule``:
          lost_consults = leads * (median_booking - entity_booking)
          lost_revenue = lost_consults * (cohort_collected / max(cohort_consults, 1))

        All revenue-loss estimates use safe_div. ``None`` when either denominator
        is 0 or the cohort median cannot be computed.
        """
        resolved_tz = tz or await self._resolve_tz(tenant_id, filters.location_id)
        window = filters.resolve_window(now=now, tz=resolved_tz)

        # Fetch the breakdowns sequentially: they share one AsyncSession, which
        # is NOT safe for concurrent operations (asyncio.gather over a single
        # session raises IllegalStateChangeError). Five aggregate reads are
        # cheap, so serial execution is the correct, safe choice.
        agg = await self._queries.funnel(window=window, filters=filters)
        callers = await self._queries.caller_performance(
            window=window, filters=filters
        )
        coordinators = await self._queries.coordinator_performance(
            window=window, filters=filters
        )
        doctors = await self._queries.doctor_performance(
            window=window, filters=filters
        )
        mkt_groups = await self._queries.marketing_breakdown(
            window=window, filters=filters, dimension="campaign"
        )

        counts = {s.key: s.count for s in agg.stages}
        cohort_leads = counts["leads"]
        cohort_consults = counts["consults"]
        cohort_surgeries = counts["surgery_completed"]
        cohort_accepted = counts["treatment_accepted"]
        cohort_collected = agg.collected_total

        findings: list[BottleneckOut] = []

        # Campaign show-rate rule: many leads but poor show rate.
        findings.extend(
            _campaign_show_rate_rule(
                mkt_groups,
                cohort_leads=cohort_leads,
                cohort_collected=cohort_collected,
            )
        )
        # Coordinator show→surgery conversion rule.
        findings.extend(
            _coordinator_surgery_rule(
                coordinators,
                cohort_surgeries=cohort_surgeries,
                cohort_collected=cohort_collected,
            )
        )
        # Doctor consultation→treatment acceptance rule.
        findings.extend(
            _doctor_acceptance_rule(
                doctors,
                cohort_accepted=cohort_accepted,
                cohort_collected=cohort_collected,
            )
        )
        # Caller lead→consultation booking rule.
        findings.extend(
            _caller_booking_rule(
                callers,
                cohort_consults=cohort_consults,
                cohort_collected=cohort_collected,
            )
        )

        # Sort: high severity first, then by estimated loss desc (None last).
        sev_order = {"high": 0, "medium": 1, "low": 2}
        findings.sort(
            key=lambda f: (
                sev_order[f.severity],
                -(f.estimated_revenue_loss or 0.0),
            )
        )

        return BottlenecksOut(
            window=self._window_out(window),
            filters=self._filters_out(filters),
            findings=findings,
        )


    # ------------------------------------------------------------------
    # ENG-517 — Vendor Performance
    # ------------------------------------------------------------------

    async def vendor_performance(
        self,
        tenant_id: TenantId,
        filters: AnalyticsFilters,
        *,
        now: datetime | None = None,
        tz: str | None = None,
    ) -> VendorPerformanceOut:
        """Vendor Performance (ENG-517) — per-vendor lead-to-revenue ranking.

        Groups the lead-date cohort by ``vendor_id``; NULL → "Unassigned".
        ``vendor_attribution_wired`` is ``False`` today because ``vendor_id``
        is 100% NULL on the fact (verified 2026-06-23: 0 of 115,715 rows).
        Vendor attribution is owned by ENG-569; this page will light up
        automatically once that epic populates the column — the SQL is stable.

        ``spend_managed`` is ``None`` on every row: there is no vendor→spend
        mapping on the fact column (a separate data layer owns vendor costs +
        claims). ``roi`` is therefore also ``None``.
        """
        resolved_tz = tz or await self._resolve_tz(tenant_id, filters.location_id)
        window = filters.resolve_window(now=now, tz=resolved_tz)
        rows = await self._queries.vendor_performance(window=window, filters=filters)

        # Determine if vendor attribution is wired: any non-NULL vendor_id row.
        attribution_wired = any(r.vendor_id is not None for r in rows)

        vendors = [
            VendorGroupOut(
                vendor_id=r.vendor_id,
                leads=r.leads,
                consults=r.consults,
                shows=r.shows,
                surgeries=r.surgeries,
                revenue=r.revenue,
                collected=r.collected,
                spend_managed=None,  # no vendor→spend mapping on the fact yet
                roi=None,  # null without spend
            )
            for r in rows
        ]
        return VendorPerformanceOut(
            window=self._window_out(window),
            filters=self._filters_out(filters),
            vendor_attribution_wired=attribution_wired,
            note=None if attribution_wired else _VENDOR_ATTRIBUTION_NOTE,
            vendors=vendors,
        )

    # ------------------------------------------------------------------
    # ENG-525 — Attribution Analytics
    # ------------------------------------------------------------------

    async def attribution_analytics(
        self,
        tenant_id: TenantId,
        filters: AnalyticsFilters,
        *,
        now: datetime | None = None,
        tz: str | None = None,
    ) -> AttributionAnalyticsOut:
        """Attribution Analytics (ENG-525) — revenue by attribution dimension.

        Reuses ``revenue_by_dimension`` for campaign/caller/coordinator/doctor
        (same helper as Revenue Intelligence). Vendor is surfaced as
        ``resolved=False`` (100% NULL today — see ENG-569) with an honest note.
        Totals are derived from the campaign dimension (same cohort anchor so
        they reconcile). ``collected_total`` / ``case_count`` are window totals.
        """
        resolved_tz = tz or await self._resolve_tz(tenant_id, filters.location_id)
        window = filters.resolve_window(now=now, tz=resolved_tz)

        dimensions: list[AttributionDimensionOut] = []
        for dim, is_resolved in _ATTRIBUTION_DIMENSIONS:
            if not is_resolved:
                # Vendor: honest no-data — don't run a query that returns
                # only Unassigned; surface the note instead.
                dimensions.append(
                    AttributionDimensionOut(
                        dimension=dim,
                        resolved=False,
                        note=_VENDOR_ATTRIBUTION_NOTE,
                        groups=[],
                    )
                )
                continue

            rows = await self._queries.revenue_by_dimension(
                window=window, filters=filters, dimension=dim
            )
            groups = [
                RevenueGroupOut(
                    group_id=r.group_id,
                    group_label=r.group_label,
                    gross=r.gross,
                    collected=r.collected,
                    outstanding=r.outstanding,
                    case_count=r.case_count,
                    avg_case_value=safe_div(r.gross, r.case_count),
                )
                for r in rows
            ]
            dimensions.append(
                AttributionDimensionOut(
                    dimension=dim,
                    resolved=True,
                    note=None,
                    groups=groups,
                )
            )

        # Totals from campaign dimension (same cohort → reconciles cross-page).
        campaign_dim = next(d for d in dimensions if d.dimension == "campaign")
        collected_total = sum(g.collected for g in campaign_dim.groups)
        case_count = sum(g.case_count for g in campaign_dim.groups)

        return AttributionAnalyticsOut(
            window=self._window_out(window),
            filters=self._filters_out(filters),
            collected_total=collected_total,
            case_count=case_count,
            dimensions=dimensions,
        )

    # ------------------------------------------------------------------
    # ENG-527 — Revenue Influence Matrix
    # ------------------------------------------------------------------

    async def revenue_influence_matrix(
        self,
        tenant_id: TenantId,
        filters: AnalyticsFilters,
        *,
        now: datetime | None = None,
        tz: str | None = None,
    ) -> RevenueInfluenceMatrixOut:
        """Revenue Influence Matrix (ENG-527) — employee × role × revenue.

        For each role (vendor / caller / coordinator / doctor) groups the
        lead-date cohort by the corresponding fact column and sums
        ``collected_amount`` as "revenue influenced". The result is a flat
        list of (employee_id, employee_label, role, revenue_influenced, case_count)
        rows ordered by role then revenue_influenced desc.

        DOUBLE-COUNTING: the same patient's revenue is counted once per role
        they touch. A $5,000 patient with both a caller and a coordinator
        appears in both the Caller slice and the Coordinator slice. This is
        intentional per the ENG-527 spec — the matrix measures influence per
        role dimension, not additive attribution. The output MUST NOT be summed
        across roles.

        Vendor rows are returned but will be empty today (vendor_id 100% NULL).
        """
        resolved_tz = tz or await self._resolve_tz(tenant_id, filters.location_id)
        window = filters.resolve_window(now=now, tz=resolved_tz)

        _role_columns = {
            "vendor": FactPatientJourney.vendor_id,
            "caller": FactPatientJourney.caller_id,
            "coordinator": FactPatientJourney.coordinator_id,
            "doctor": FactPatientJourney.doctor_id,
        }

        all_rows: list[InfluenceRowOut] = []
        for role in _INFLUENCE_ROLES:
            group_col = _role_columns[role]
            influence_rows = await self._queries.influence_by_role(
                window=window,
                filters=filters,
                role=role,
                group_col=group_col,
            )
            for r in influence_rows:
                uid = r.actor_id
                label = (
                    str(uid)[:8] if uid is not None else "Unassigned"
                )
                all_rows.append(
                    InfluenceRowOut(
                        employee_id=uid,
                        employee_label=label,
                        role=role,
                        revenue_influenced=r.revenue_influenced,
                        case_count=r.case_count,
                    )
                )

        return RevenueInfluenceMatrixOut(
            window=self._window_out(window),
            filters=self._filters_out(filters),
            rows=all_rows,
        )

# ---------------------------------------------------------------------------
# Bottleneck rule constants and helpers (ENG-524).
#
# Each constant is named and documented so thresholds are auditable and easy
# to tune without touching logic. "Minimum sample" guards prevent flagging
# entities with too few observations (e.g. a caller with 1 lead who didn't
# book a consult would score 0% — that's noise, not a bottleneck).
# ---------------------------------------------------------------------------

# --- Sample-size minimums ---------------------------------------------------
# Minimum leads/consults for an entity to be eligible for flagging.
# Below this threshold: skip — too few observations to distinguish noise.
_MIN_CAMPAIGN_LEADS = 10  # campaign: at least 10 leads in cohort
_MIN_COORDINATOR_CONSULTS = 5  # coordinator: at least 5 consults assigned
_MIN_DOCTOR_CONSULTS = 5  # doctor: at least 5 consultations
_MIN_CALLER_LEADS = 10  # caller: at least 10 leads assigned

# --- Relative-shortfall flag threshold --------------------------------------
# An entity is flagged when its rate is at least ``_RELATIVE_DROP`` *fraction*
# below the cohort median — i.e. ``rate <= median * (1 - _RELATIVE_DROP)``.
# This is base-rate-AGNOSTIC: a caller booking 0% on a cohort whose median is
# only 5.88% is still 100% below the typical peer and therefore a real
# bottleneck. The earlier ABSOLUTE 15-pp gap (``median - 0.15``) went negative
# on low-base funnel stages, so NO entity could ever be flagged — the bug this
# replaces (ENG-524 real-data validation, 2026-06-23).
_RELATIVE_DROP = 0.40  # flag when entity is ≥ 40% below the cohort median

# --- Absolute floor ---------------------------------------------------------
# A tiny absolute guard so entities that are trivially close to the median at
# HIGH base rates aren't flagged on relative grounds alone (e.g. 0.49 vs a 0.80
# median is a 39% relative drop but only matters if the absolute gap is real).
# Require (median - rate) >= this floor in addition to the relative test.
_ABSOLUTE_FLOOR = 0.02  # require ≥ 2 pp absolute gap as well

# --- Severity bands (by RELATIVE shortfall ratio) ---------------------------
# s = (median - rate) / median  (fraction below the typical peer):
#   high   = s ≥ 0.75 — at least 75% below median, critical
#   medium = s ≥ 0.55 — 55–75% below median, investigate
#   low    = otherwise (s in [_RELATIVE_DROP, 0.55)) — noticeable, monitor
_SEV_HIGH_SHORTFALL = 0.75  # s ≥ 0.75 → high
_SEV_MED_SHORTFALL = 0.55   # s ≥ 0.55 → medium (< 0.75)


def _relative_severity(median_rate: float, rate: float) -> str:
    """Map a relative shortfall ``s = (median - rate)/median`` to a severity.

    Base-rate-agnostic: a 0% entity against any positive median scores s = 1.0
    (high), regardless of whether the median is 5% or 80%.

    Bands:
    - ``high``   — s ≥ 0.75: at least 75% below the typical peer, critical
    - ``medium`` — s ≥ 0.55: 55–75% below, investigate
    - ``low``    — otherwise: noticeable, monitor

    ``median_rate`` is assumed > 0 (callers guard against a zero/None median
    before invoking this, since there is nothing to compare against then).
    """
    shortfall = (median_rate - rate) / median_rate
    if shortfall >= _SEV_HIGH_SHORTFALL:
        return "high"
    if shortfall >= _SEV_MED_SHORTFALL:
        return "medium"
    return "low"


def _is_bottleneck(median_rate: float | None, rate: float) -> bool:
    """True when ``rate`` is a flaggable bottleneck vs ``median_rate``.

    Requires BOTH:
    1. relative test — ``rate <= median * (1 - _RELATIVE_DROP)`` (≥ 40% below), and
    2. absolute floor — ``(median - rate) >= _ABSOLUTE_FLOOR`` (≥ 2 pp gap).

    Returns ``False`` when the median is ``None`` or ``0`` (nothing to compare
    against — no division by zero, no findings).
    """
    if median_rate is None or median_rate <= 0:
        return False
    if rate > median_rate * (1 - _RELATIVE_DROP):
        return False
    return (median_rate - rate) >= _ABSOLUTE_FLOOR


def _median(values: list[float]) -> float | None:
    """Median of a list of floats; ``None`` for an empty list."""
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def _entity_label(entity_id: UUID | None, prefix: str) -> str:
    """Short display label for an entity: 8-char UUID prefix or 'Unassigned'."""
    if entity_id is None:
        return "Unassigned"
    return f"{prefix} {str(entity_id)[:8]}"


def _campaign_show_rate_rule(
    mkt_groups: list[MarketingGroupRow],
    *,
    cohort_leads: int,
    cohort_collected: float,
) -> list[BottleneckOut]:
    """Flag campaigns with many leads but a show rate far below the cohort median.

    Flagging (base-rate-agnostic, via ``_is_bottleneck``):
        flag when entity_show_rate <= median * (1 - _RELATIVE_DROP)
        AND (median - entity_show_rate) >= _ABSOLUTE_FLOOR.
    No findings when the median is 0/None (nothing to compare against).

    Severity by relative shortfall ``s = (median - rate)/median`` (see
    ``_relative_severity``): s ≥ 0.75 high, s ≥ 0.55 medium, else low.

    Revenue-loss formula (unchanged, None-safe):
        lost_leads = entity_leads * (median_show_rate − entity_show_rate)
        rev_per_lead = cohort_collected / cohort_leads   (None on zero denom)
        estimated_loss = lost_leads * rev_per_lead
    """
    # Filter eligible entities: min sample, non-null id (Unassigned not flagged)
    eligible = [
        r
        for r in mkt_groups
        if r.group_id is not None and r.leads >= _MIN_CAMPAIGN_LEADS
    ]
    if not eligible:
        return []

    # Compute per-campaign show rate = shows / leads
    rates = [safe_div(r.shows, r.leads) for r in eligible]
    rates_valid = [r for r in rates if r is not None]
    median_rate = _median(rates_valid)
    if median_rate is None or median_rate <= 0:
        return []

    rev_per_lead = safe_div(cohort_collected, cohort_leads)

    findings: list[BottleneckOut] = []
    for row, rate in zip(eligible, rates, strict=False):
        if rate is None:
            continue
        if not _is_bottleneck(median_rate, rate):
            continue
        deviation = median_rate - rate
        lost_leads = row.leads * deviation
        est_loss = (lost_leads * rev_per_lead) if rev_per_lead is not None else None

        findings.append(
            BottleneckOut(
                category="campaign_low_show",
                description=(
                    f"Campaign '{row.group_label or str(row.group_id)[:8]}' has a "
                    f"show rate of {rate * 100:.1f}% vs. cohort median "
                    f"{median_rate * 100:.1f}% ({row.leads} leads)."
                ),
                severity=_relative_severity(median_rate, rate),  # type: ignore[arg-type]
                estimated_revenue_loss=est_loss,
                suggested_action=(
                    "Review lead quality and pre-appointment nurture for this "
                    "campaign. Consider pausing spend until show-rate improves."
                ),
                entity=BottleneckEntityOut(
                    id=row.group_id,
                    label=row.group_label or str(row.group_id)[:8],
                ),
            )
        )
    return findings


def _coordinator_surgery_rule(
    coordinators: list,
    *,
    cohort_surgeries: int,
    cohort_collected: float,
) -> list[BottleneckOut]:
    """Flag coordinators with poor show→surgery conversion.

    Flagging is base-rate-agnostic via ``_is_bottleneck`` (relative ≥40% below
    median + ≥2 pp absolute floor; no findings when median is 0/None). Severity
    by relative shortfall ``s = (median - rate)/median``.

    Revenue-loss formula (unchanged, None-safe):
        lost_surgeries = shows * (median_show_to_surgery − entity_rate)
        rev_per_surgery = cohort_collected / cohort_surgeries  (None on zero denom)
        estimated_loss = lost_surgeries * rev_per_surgery
    """
    eligible = [
        r
        for r in coordinators
        if r.coordinator_id is not None
        and r.consults_assigned >= _MIN_COORDINATOR_CONSULTS
    ]
    if not eligible:
        return []

    rates = [safe_div(r.surgery_completed, r.shows) for r in eligible]
    rates_valid = [r for r in rates if r is not None]
    median_rate = _median(rates_valid)
    if median_rate is None or median_rate <= 0:
        return []

    rev_per_surgery = safe_div(cohort_collected, cohort_surgeries)

    findings: list[BottleneckOut] = []
    for row, rate in zip(eligible, rates, strict=False):
        if rate is None:
            continue
        if not _is_bottleneck(median_rate, rate):
            continue
        deviation = median_rate - rate
        lost = row.shows * deviation
        est_loss = (lost * rev_per_surgery) if rev_per_surgery is not None else None

        findings.append(
            BottleneckOut(
                category="coordinator_low_surgery_conversion",
                description=(
                    f"Coordinator {_entity_label(row.coordinator_id, 'Coordinator')} "
                    f"has a show→surgery rate of {rate * 100:.1f}% vs. median "
                    f"{median_rate * 100:.1f}% ({row.consults_assigned} consults)."
                ),
                severity=_relative_severity(median_rate, rate),  # type: ignore[arg-type]
                estimated_revenue_loss=est_loss,
                suggested_action=(
                    "Review treatment plan presentation quality and follow-up "
                    "cadence for this coordinator. Schedule coaching session."
                ),
                entity=BottleneckEntityOut(
                    id=row.coordinator_id,
                    label=_entity_label(row.coordinator_id, "Coordinator"),
                ),
            )
        )
    return findings


def _doctor_acceptance_rule(
    doctors: list,
    *,
    cohort_accepted: int,
    cohort_collected: float,
) -> list[BottleneckOut]:
    """Flag doctors with poor consult→treatment acceptance.

    Flagging is base-rate-agnostic via ``_is_bottleneck`` (relative ≥40% below
    median + ≥2 pp absolute floor; no findings when median is 0/None). Severity
    by relative shortfall ``s = (median - rate)/median``.

    Revenue-loss formula (unchanged, None-safe):
        lost_accepted = consults * (median_acceptance − entity_rate)
        rev_per_accepted = cohort_collected / cohort_accepted  (None on zero denom)
        estimated_loss = lost_accepted * rev_per_accepted
    """
    eligible = [
        r
        for r in doctors
        if r.doctor_id is not None and r.consults >= _MIN_DOCTOR_CONSULTS
    ]
    if not eligible:
        return []

    rates = [safe_div(r.treatment_accepted, r.consults) for r in eligible]
    rates_valid = [r for r in rates if r is not None]
    median_rate = _median(rates_valid)
    if median_rate is None or median_rate <= 0:
        return []

    rev_per_accepted = safe_div(cohort_collected, cohort_accepted)

    findings: list[BottleneckOut] = []
    for row, rate in zip(eligible, rates, strict=False):
        if rate is None:
            continue
        if not _is_bottleneck(median_rate, rate):
            continue
        deviation = median_rate - rate
        lost = row.consults * deviation
        est_loss = (lost * rev_per_accepted) if rev_per_accepted is not None else None

        findings.append(
            BottleneckOut(
                category="doctor_low_acceptance",
                description=(
                    f"Doctor {_entity_label(row.doctor_id, 'Doctor')} "
                    f"has a consult→acceptance rate of {rate * 100:.1f}% vs. median "
                    f"{median_rate * 100:.1f}% ({row.consults} consults)."
                ),
                severity=_relative_severity(median_rate, rate),  # type: ignore[arg-type]
                estimated_revenue_loss=est_loss,
                suggested_action=(
                    "Review case presentation technique and patient communication "
                    "for this doctor. Consider peer-review of treatment plans."
                ),
                entity=BottleneckEntityOut(
                    id=row.doctor_id,
                    label=_entity_label(row.doctor_id, "Doctor"),
                ),
            )
        )
    return findings


def _caller_booking_rule(
    callers: list,
    *,
    cohort_consults: int,
    cohort_collected: float,
) -> list[BottleneckOut]:
    """Flag callers with poor lead→consultation booking rate.

    Flagging is base-rate-agnostic via ``_is_bottleneck`` (relative ≥40% below
    median + ≥2 pp absolute floor; no findings when median is 0/None). This is
    the exact rule the ENG-524 real-data bug broke: on a caller cohort whose
    lead→consult median is only ~5.88%, a caller booking 0% is 100% below the
    typical peer and is now correctly flagged. Severity by relative shortfall
    ``s = (median - rate)/median``.

    Revenue-loss formula (unchanged, None-safe):
        lost_consults = leads * (median_booking − entity_rate)
        rev_per_consult = cohort_collected / cohort_consults  (None on zero denom)
        estimated_loss = lost_consults * rev_per_consult
    """
    eligible = [
        r
        for r in callers
        if r.caller_id is not None and r.leads >= _MIN_CALLER_LEADS
    ]
    if not eligible:
        return []

    rates = [safe_div(r.consults, r.leads) for r in eligible]
    rates_valid = [r for r in rates if r is not None]
    median_rate = _median(rates_valid)
    if median_rate is None or median_rate <= 0:
        return []

    rev_per_consult = safe_div(cohort_collected, cohort_consults)

    findings: list[BottleneckOut] = []
    for row, rate in zip(eligible, rates, strict=False):
        if rate is None:
            continue
        if not _is_bottleneck(median_rate, rate):
            continue
        deviation = median_rate - rate
        lost = row.leads * deviation
        est_loss = (lost * rev_per_consult) if rev_per_consult is not None else None

        findings.append(
            BottleneckOut(
                category="caller_low_booking",
                description=(
                    f"Caller {_entity_label(row.caller_id, 'Caller')} "
                    f"has a lead→consult rate of {rate * 100:.1f}% vs. median "
                    f"{median_rate * 100:.1f}% ({row.leads} leads)."
                ),
                severity=_relative_severity(median_rate, rate),  # type: ignore[arg-type]
                estimated_revenue_loss=est_loss,
                suggested_action=(
                    "Review call scripts and scheduling availability for this "
                    "caller. Additional training or script A/B testing recommended."
                ),
                entity=BottleneckEntityOut(
                    id=row.caller_id,
                    label=_entity_label(row.caller_id, "Caller"),
                ),
            )
        )
    return findings


def _utcnow() -> datetime:
    """Current UTC instant (kept local so callers can inject ``now`` in tests)."""
    return datetime.now(tz=UTC)
