"""Read-only page aggregates over ``analytics.fact_patient_journey`` (ENG-514).

Data-only repository for the B2 data-ready pages (Executive / Funnel / Revenue /
Cohort / Patient Journey). Every method is a pure read over the fact table — the
fact is the single source for these pages, so the numbers reconcile across pages
(same cohort anchor, same money columns). Nothing here writes; the builder
(``fact_repository.py``) remains the only writer.

Anchoring (documented once, applied consistently so pages reconcile):

* **Funnel counts / cohort membership** anchor on ``lead_date`` (the funnel
  entry) — the same cohort anchor the foundation aggregate uses, so the
  Executive funnel and the Funnel page agree for the same window.
* **Realized-cash widgets** (Executive "Today…YTD") anchor on
  ``first_payment_date`` — money is counted in the window it was collected.
* **Cohort revenue-after-N-days** is cumulative ``collected_amount`` for persons
  whose ``first_payment_date`` lands within N days of their ``lead_date``.

B1-unresolved columns (caller / coordinator / doctor, treatment_accepted,
surgery_*) are simply NULL today, so their counts are honest zeros and their
breakdown groups collapse to "Unattributed" — no fabrication, no special-casing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .filters import AnalyticsFilters, ResolvedWindow
from .models import FactPatientJourney

# Cumulative-revenue horizons (days after lead_date) for the cohort page.
COHORT_HORIZONS: tuple[int, ...] = (30, 60, 90, 180, 365)

# Revenue-Intelligence breakdown dimensions → fact column. ``campaign`` and
# ``source`` carry a human label; the id-only dimensions resolve to
# "Unattributed" when NULL (and stay NULL-keyed until B1.* fills them).
_DIMENSION_COLUMNS: dict[str, Any] = {
    "campaign": FactPatientJourney.campaign_id,
    "source": FactPatientJourney.source,
    "vendor": FactPatientJourney.vendor_id,
    "caller": FactPatientJourney.caller_id,
    "coordinator": FactPatientJourney.coordinator_id,
    "doctor": FactPatientJourney.doctor_id,
    "location": FactPatientJourney.location_id,
}

REVENUE_DIMENSIONS: tuple[str, ...] = tuple(_DIMENSION_COLUMNS.keys())


@dataclass(frozen=True)
class FunnelStageRow:
    """One funnel stage: persons reaching it + revenue they generated.

    ``count`` is in-cohort persons with this stage's date non-null;
    ``collected`` / ``revenue`` are the money those persons carry (lifetime
    totals on the fact row). Cost and conversion are derived in the service.
    """

    key: str
    count: int
    revenue: float
    collected: float


@dataclass(frozen=True)
class FunnelAggregate:
    """All eight funnel stages over one window + cohort totals."""

    stages: list[FunnelStageRow]
    patients: int
    revenue_total: float
    collected_total: float


@dataclass(frozen=True)
class MoneyWindowRow:
    """Realized money over a window anchored on ``first_payment_date``."""

    gross: float
    collected: float
    payers: int


@dataclass(frozen=True)
class RevenueGroupRow:
    """Revenue for one value of a breakdown dimension."""

    group_id: UUID | None
    group_label: str | None
    gross: float
    collected: float
    outstanding: float
    case_count: int


@dataclass(frozen=True)
class CohortRow:
    """One lead-creation-month cohort with cumulative revenue by horizon."""

    cohort_month: str
    lead_count: int
    revenue_by_day: dict[int, float]
    collected_total: float


@dataclass(frozen=True)
class MarketingGroupRow:
    """Ad spend ⇄ outcomes for one value of a marketing breakdown dimension.

    ``spend`` is the summed ``marketing_cost_allocated`` (the cost-per-lead
    allocation, ENG-512) for the group's persons; the stage counts are in-cohort
    persons (``lead_date`` in window) reaching each stage; ``revenue`` /
    ``collected`` are the money those persons carry. Derived ROI / cost-per-stage
    are computed in the service.
    """

    group_id: UUID | None
    group_label: str | None
    spend: float
    leads: int
    consults: int
    shows: int
    surgeries: int
    revenue: float
    collected: float


@dataclass(frozen=True)
class CallerGroupRow:
    """Per-caller cohort outcomes for the Caller Performance page (ENG-518).

    ``leads`` = in-cohort persons with this caller; ``reached`` = persons with
    ``first_contact_date`` non-null; ``consults`` = persons with
    ``consult_scheduled_date`` non-null; ``collected`` = SUM(collected_amount).

    Note: ``calls_made`` (dialer count) has **no column** in the fact table —
    the fact records ``first_contact_date`` (whether contact was made) but does
    not record how many calls were attempted. That metric is honest no-data
    (rendered as ``None`` → "—" on the UI) until a telephony-count column is
    added to the fact. Do NOT fabricate it from the fact's contact flag.
    """

    caller_id: UUID | None
    leads: int
    reached: int
    consults: int
    collected: float


@dataclass(frozen=True)
class CoordinatorGroupRow:
    """Per-coordinator cohort outcomes for the Coordinator Performance page (ENG-519).

    ``consults_assigned`` = persons with ``consult_scheduled_date`` non-null for
    this coordinator; every subsequent stage is persons reaching that stage.
    ``collected`` = SUM(collected_amount). All counts anchor on ``lead_date``
    cohort (same window as every other page) so they reconcile cross-page.
    """

    coordinator_id: UUID | None
    consults_assigned: int
    shows: int
    treatment_presented: int
    surgery_scheduled: int
    surgery_completed: int
    collected: float


@dataclass(frozen=True)
class DoctorGroupRow:
    """Per-doctor cohort outcomes for the Doctor Performance page (ENG-520).

    Counts are in-cohort persons (``lead_date`` in window) reaching each stage
    with this doctor. ``collected`` = SUM(collected_amount). Derives
    Revenue per Consultation / per Surgery in the service via ``safe_div``.
    """

    doctor_id: UUID | None
    consults: int
    treatment_presented: int
    treatment_accepted: int
    surgery_completed: int
    collected: float


@dataclass(frozen=True)
class VendorGroupRow:
    """Per-vendor cohort outcomes for the Vendor Performance page (ENG-517).

    Groups in-cohort persons (``lead_date`` in window) by ``vendor_id``.
    NULL ``vendor_id`` → "Unassigned" bucket. Today (2026-06-23) all 115,715
    fact rows have ``vendor_id=NULL`` — vendor attribution is not yet wired
    (ENG-569 owns that epic). The query groups by the column so the page
    lights up automatically the moment vendor_id gets populated.

    ``spend_managed`` is not computed here — there is no vendor→spend column
    on the fact; a separate data layer (vendor costs + claims) owns that.
    """

    vendor_id: UUID | None
    leads: int
    consults: int
    shows: int
    surgeries: int
    revenue: float
    collected: float


@dataclass(frozen=True)
class InfluenceRow:
    """One (actor_id, role) → revenue influenced row (ENG-527 matrix).

    ``actor_id`` is the raw fact column value (NULL → Unassigned).
    ``role`` is one of "vendor" / "caller" / "coordinator" / "doctor".
    ``revenue_influenced`` = SUM(collected_amount) for cohort patients where
    this actor held the role. Case count = count of persons in the group.

    The same patient's revenue appears once per role they touch, so rows
    across roles MUST NOT be summed (double-counting is intentional —
    it measures influence, not additive attribution).
    """

    actor_id: UUID | None
    role: str
    revenue_influenced: float
    case_count: int


# Marketing-performance breakdown dimensions the fact CAN attribute → fact
# column. ``ad_set`` / ``ad`` are intentionally absent: the fact carries no
# ad-set/ad dimension, so the page surfaces them as a "no data" panel instead.
_MARKETING_DIMENSION_COLUMNS: dict[str, Any] = {
    "campaign": FactPatientJourney.campaign_id,
    "source": FactPatientJourney.source,
}

MARKETING_DIMENSIONS: tuple[str, ...] = tuple(_MARKETING_DIMENSION_COLUMNS.keys())


# Ordered funnel stages: label key → fact stage-date column. Drives the funnel
# page and the executive funnel widget. "reached" = first_contact_date; the last
# three are B1-unresolved today (honest zeros).
_FUNNEL_STAGES: tuple[tuple[str, Any], ...] = (
    ("leads", FactPatientJourney.lead_date),
    ("reached", FactPatientJourney.first_contact_date),
    ("consults", FactPatientJourney.consult_scheduled_date),
    ("shows", FactPatientJourney.show_date),
    ("treatment_presented", FactPatientJourney.treatment_presented_date),
    ("treatment_accepted", FactPatientJourney.treatment_accepted_date),
    ("surgery_scheduled", FactPatientJourney.surgery_scheduled_date),
    ("surgery_completed", FactPatientJourney.surgery_completed_date),
)

# Drill-down metric → the fact predicate that selects its in-cohort persons
# (ENG-508). Every metric anchors on the same ``lead_date`` cohort the funnel
# uses, so a drill-down list reconciles with the on-screen count. ``patients`` is
# the whole cohort (no extra predicate); ``paid`` mirrors the revenue page's
# ``case_count`` (a non-null ``revenue_amount``). The funnel-stage metrics select
# persons whose stage date is non-null.
DRILLDOWN_METRICS: tuple[str, ...] = (
    *(key for key, _ in _FUNNEL_STAGES),
    "patients",
    "paid",
)


def _drilldown_predicate(metric: str) -> Any | None:
    """Fact predicate for a drill-down ``metric`` (``None`` = whole cohort)."""
    if metric == "patients":
        return None
    if metric == "paid":
        return FactPatientJourney.revenue_amount.is_not(None)
    for key, stage_col in _FUNNEL_STAGES:
        if key == metric:
            return stage_col.is_not(None)
    raise ValueError(f"unknown drill-down metric: {metric!r}")


def _apply_dimension_filters[S: Select[Any]](
    stmt: S, filters: AnalyticsFilters
) -> S:
    """Append the shared equality dimension filters (``None`` = don't filter)."""
    m = FactPatientJourney
    for column, value in (
        (m.location_id, filters.location_id),
        (m.campaign_id, filters.campaign_id),
        (m.source, filters.source),
        (m.vendor_id, filters.vendor_id),
        (m.caller_id, filters.caller_id),
        (m.coordinator_id, filters.coordinator_id),
        (m.doctor_id, filters.doctor_id),
    ):
        if value is not None:
            stmt = stmt.where(column == value)
    return stmt


class FactAnalyticsQueries:
    """Read-only page aggregates over the patient-journey fact (data-only)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def funnel(
        self, *, window: ResolvedWindow, filters: AnalyticsFilters
    ) -> FunnelAggregate:
        """Eight-stage funnel over the ``lead_date`` cohort + per-stage money.

        Each stage count is the number of in-cohort persons with that stage's
        date non-null; the per-stage ``collected`` / ``revenue`` sum the money
        those persons carry. Totals are the whole cohort's money.
        """
        m = FactPatientJourney

        columns: list[Any] = []
        for key, stage_col in _FUNNEL_STAGES:
            reached = stage_col.is_not(None)
            columns.append(func.count(stage_col).label(f"{key}_count"))
            columns.append(
                func.coalesce(
                    func.sum(sa.case((reached, m.revenue_amount), else_=0)), 0
                ).label(f"{key}_revenue")
            )
            columns.append(
                func.coalesce(
                    func.sum(sa.case((reached, m.collected_amount), else_=0)), 0
                ).label(f"{key}_collected")
            )
        columns.append(func.count().label("patients"))
        columns.append(
            func.coalesce(func.sum(m.revenue_amount), 0).label("revenue_total")
        )
        columns.append(
            func.coalesce(func.sum(m.collected_amount), 0).label("collected_total")
        )

        stmt = select(*columns).where(
            m.lead_date >= window.start, m.lead_date < window.end
        )
        stmt = _apply_dimension_filters(stmt, filters)
        row = (await self._session.execute(stmt)).one()

        stages = [
            FunnelStageRow(
                key=key,
                count=int(getattr(row, f"{key}_count")),
                revenue=float(getattr(row, f"{key}_revenue")),
                collected=float(getattr(row, f"{key}_collected")),
            )
            for key, _ in _FUNNEL_STAGES
        ]
        return FunnelAggregate(
            stages=stages,
            patients=int(row.patients),
            revenue_total=float(row.revenue_total),
            collected_total=float(row.collected_total),
        )

    async def realized_money(
        self, *, start: datetime, end: datetime, filters: AnalyticsFilters
    ) -> MoneyWindowRow:
        """Gross / collected / payer count for cash realized in ``[start, end)``.

        Anchored on ``first_payment_date`` — the window a person's money landed
        in — so the executive revenue cards answer "cash this period", not "cash
        from leads created this period".
        """
        m = FactPatientJourney
        stmt = select(
            func.coalesce(func.sum(m.revenue_amount), 0).label("gross"),
            func.coalesce(func.sum(m.collected_amount), 0).label("collected"),
            func.count(m.first_payment_date).label("payers"),
        ).where(m.first_payment_date >= start, m.first_payment_date < end)
        stmt = _apply_dimension_filters(stmt, filters)
        row = (await self._session.execute(stmt)).one()
        return MoneyWindowRow(
            gross=float(row.gross),
            collected=float(row.collected),
            payers=int(row.payers),
        )

    async def revenue_by_dimension(
        self,
        *,
        window: ResolvedWindow,
        filters: AnalyticsFilters,
        dimension: str,
    ) -> list[RevenueGroupRow]:
        """Cohort revenue grouped by one breakdown dimension (``lead_date``).

        Gross = summed ``revenue_amount``; collected = summed
        ``collected_amount``; outstanding = gross − collected; case count =
        persons with a non-null ``revenue_amount``. NULL group keys (e.g. the
        B1-unresolved people dimensions) collapse to a single "Unattributed"
        row. Ordered by gross descending.
        """
        m = FactPatientJourney
        group_col = _DIMENSION_COLUMNS[dimension]
        label_col = (
            m.campaign_name
            if dimension == "campaign"
            else (group_col if dimension == "source" else sa.null())
        )

        gross = func.coalesce(func.sum(m.revenue_amount), 0)
        collected = func.coalesce(func.sum(m.collected_amount), 0)
        case_count = func.count(m.revenue_amount)

        stmt = (
            select(
                group_col.label("group_key"),
                func.max(label_col).label("group_label"),
                gross.label("gross"),
                collected.label("collected"),
                case_count.label("case_count"),
            )
            .where(m.lead_date >= window.start, m.lead_date < window.end)
            .group_by(group_col)
            .order_by(gross.desc())
        )
        stmt = _apply_dimension_filters(stmt, filters)
        rows = (await self._session.execute(stmt)).all()

        out: list[RevenueGroupRow] = []
        for r in rows:
            key = r.group_key
            # campaign/location/people dimensions key on a UUID; source on a str.
            group_id = key if isinstance(key, UUID) else None
            if dimension == "source":
                group_label = key if isinstance(key, str) else None
            else:
                group_label = r.group_label
            g = float(r.gross)
            c = float(r.collected)
            out.append(
                RevenueGroupRow(
                    group_id=group_id,
                    group_label=group_label,
                    gross=g,
                    collected=c,
                    outstanding=g - c,
                    case_count=int(r.case_count),
                )
            )
        return out

    async def marketing_breakdown(
        self,
        *,
        window: ResolvedWindow,
        filters: AnalyticsFilters,
        dimension: str,
    ) -> list[MarketingGroupRow]:
        """Ad spend ⇄ outcomes grouped by one marketing dimension (``lead_date``).

        ``dimension`` is ``campaign`` or ``source``. ``spend`` sums
        ``marketing_cost_allocated`` (the cost-per-lead allocation); the stage
        counts are in-cohort persons (``lead_date`` in window) reaching each
        stage; ``revenue`` / ``collected`` sum the money those persons carry.
        NULL group keys collapse to a single "Unattributed" row. Ordered by
        spend descending, then leads descending. Cohort-anchored on ``lead_date``
        so the counts reconcile with the funnel / revenue pages for the window.
        """
        m = FactPatientJourney
        group_col = _MARKETING_DIMENSION_COLUMNS[dimension]
        label_col = (
            m.campaign_name if dimension == "campaign" else m.source
        )

        spend = func.coalesce(func.sum(m.marketing_cost_allocated), 0)
        leads = func.count(m.lead_date)
        consults = func.count(m.consult_scheduled_date)
        shows = func.count(m.show_date)
        surgeries = func.count(m.surgery_completed_date)
        revenue = func.coalesce(func.sum(m.revenue_amount), 0)
        collected = func.coalesce(func.sum(m.collected_amount), 0)

        stmt = (
            select(
                group_col.label("group_key"),
                func.max(label_col).label("group_label"),
                spend.label("spend"),
                leads.label("leads"),
                consults.label("consults"),
                shows.label("shows"),
                surgeries.label("surgeries"),
                revenue.label("revenue"),
                collected.label("collected"),
            )
            .where(m.lead_date >= window.start, m.lead_date < window.end)
            .group_by(group_col)
            .order_by(spend.desc(), leads.desc())
        )
        stmt = _apply_dimension_filters(stmt, filters)
        rows = (await self._session.execute(stmt)).all()

        out: list[MarketingGroupRow] = []
        for r in rows:
            key = r.group_key
            # campaign keys on a UUID; source keys on a str.
            group_id = key if isinstance(key, UUID) else None
            if dimension == "source":
                group_label = key if isinstance(key, str) else None
            else:
                group_label = r.group_label
            out.append(
                MarketingGroupRow(
                    group_id=group_id,
                    group_label=group_label,
                    spend=float(r.spend),
                    leads=int(r.leads),
                    consults=int(r.consults),
                    shows=int(r.shows),
                    surgeries=int(r.surgeries),
                    revenue=float(r.revenue),
                    collected=float(r.collected),
                )
            )
        return out

    async def cohorts(
        self, *, window: ResolvedWindow, filters: AnalyticsFilters
    ) -> list[CohortRow]:
        """Lead-creation-month cohorts with cumulative revenue by horizon.

        Cohort = ``date_trunc('month', lead_date)``. For each horizon N, revenue
        is the summed ``collected_amount`` of persons whose ``first_payment_date``
        is within N days of their own ``lead_date`` — so a bulk-import cohort
        with no real payment lag shows no false spike. Ordered by month ascending.
        """
        m = FactPatientJourney
        month = func.date_trunc("month", m.lead_date)

        horizon_cols: list[Any] = []
        for n in COHORT_HORIZONS:
            within = sa.and_(
                m.first_payment_date.is_not(None),
                m.first_payment_date < m.lead_date + sa.text(f"interval '{n} days'"),
            )
            horizon_cols.append(
                func.coalesce(
                    func.sum(sa.case((within, m.collected_amount), else_=0)), 0
                ).label(f"rev_{n}")
            )

        stmt = (
            select(
                month.label("cohort_month"),
                func.count().label("lead_count"),
                func.coalesce(func.sum(m.collected_amount), 0).label("collected_total"),
                *horizon_cols,
            )
            .where(m.lead_date >= window.start, m.lead_date < window.end)
            .group_by(month)
            .order_by(month.asc())
        )
        stmt = _apply_dimension_filters(stmt, filters)
        rows = (await self._session.execute(stmt)).all()

        out: list[CohortRow] = []
        for r in rows:
            cohort_dt: datetime = r.cohort_month
            out.append(
                CohortRow(
                    cohort_month=cohort_dt.strftime("%Y-%m"),
                    lead_count=int(r.lead_count),
                    revenue_by_day={
                        n: float(getattr(r, f"rev_{n}")) for n in COHORT_HORIZONS
                    },
                    collected_total=float(r.collected_total),
                )
            )
        return out

    async def journey_row(self, person_uid: UUID) -> FactPatientJourney | None:
        """One person's fact row for the patient-journey timeline (or ``None``)."""
        stmt = select(FactPatientJourney).where(
            FactPatientJourney.person_uid == person_uid
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------------------
    # ENG-518 / ENG-519 / ENG-520 — Actor-performance queries
    # ------------------------------------------------------------------

    async def caller_performance(
        self,
        *,
        window: ResolvedWindow,
        filters: AnalyticsFilters,
    ) -> list[CallerGroupRow]:
        """Per-caller cohort outcomes (ENG-518).

        Groups in-cohort persons (``lead_date`` in window) by ``caller_id``.
        NULL ``caller_id`` → "Unassigned" bucket. Ordered by consults desc,
        then collected desc. "Calls Made" is honest no-data (the fact carries
        no per-call count column) — that field is computed in the service layer.
        """
        m = FactPatientJourney
        group_col = m.caller_id

        leads = func.count(m.lead_date)
        reached = func.count(m.first_contact_date)
        consults = func.count(m.consult_scheduled_date)
        collected = func.coalesce(func.sum(m.collected_amount), 0)

        stmt = (
            select(
                group_col.label("caller_id"),
                leads.label("leads"),
                reached.label("reached"),
                consults.label("consults"),
                collected.label("collected"),
            )
            .where(m.lead_date >= window.start, m.lead_date < window.end)
            .group_by(group_col)
            .order_by(consults.desc(), collected.desc())
        )
        stmt = _apply_dimension_filters(stmt, filters)
        rows = (await self._session.execute(stmt)).all()

        return [
            CallerGroupRow(
                caller_id=r.caller_id,
                leads=int(r.leads),
                reached=int(r.reached),
                consults=int(r.consults),
                collected=float(r.collected),
            )
            for r in rows
        ]

    async def coordinator_performance(
        self,
        *,
        window: ResolvedWindow,
        filters: AnalyticsFilters,
    ) -> list[CoordinatorGroupRow]:
        """Per-coordinator cohort outcomes (ENG-519).

        Groups in-cohort persons (``lead_date`` in window) by
        ``coordinator_id``. NULL → "Unassigned". Ordered by consults_assigned
        desc, then collected desc. "Shows" uses ``show_date``, so the
        Scheduled→Show rate is honest even when it's zero until B1 fills data.
        """
        m = FactPatientJourney
        group_col = m.coordinator_id

        consults_assigned = func.count(m.consult_scheduled_date)
        shows = func.count(m.show_date)
        treatment_presented = func.count(m.treatment_presented_date)
        surgery_scheduled = func.count(m.surgery_scheduled_date)
        surgery_completed = func.count(m.surgery_completed_date)
        collected = func.coalesce(func.sum(m.collected_amount), 0)

        stmt = (
            select(
                group_col.label("coordinator_id"),
                consults_assigned.label("consults_assigned"),
                shows.label("shows"),
                treatment_presented.label("treatment_presented"),
                surgery_scheduled.label("surgery_scheduled"),
                surgery_completed.label("surgery_completed"),
                collected.label("collected"),
            )
            .where(m.lead_date >= window.start, m.lead_date < window.end)
            .group_by(group_col)
            .order_by(consults_assigned.desc(), collected.desc())
        )
        stmt = _apply_dimension_filters(stmt, filters)
        rows = (await self._session.execute(stmt)).all()

        return [
            CoordinatorGroupRow(
                coordinator_id=r.coordinator_id,
                consults_assigned=int(r.consults_assigned),
                shows=int(r.shows),
                treatment_presented=int(r.treatment_presented),
                surgery_scheduled=int(r.surgery_scheduled),
                surgery_completed=int(r.surgery_completed),
                collected=float(r.collected),
            )
            for r in rows
        ]

    async def doctor_performance(
        self,
        *,
        window: ResolvedWindow,
        filters: AnalyticsFilters,
    ) -> list[DoctorGroupRow]:
        """Per-doctor cohort outcomes (ENG-520).

        Groups in-cohort persons (``lead_date`` in window) by ``doctor_id``.
        NULL → "Unassigned". Ordered by surgery_completed desc, then collected
        desc. Revenue columns are ``collected_amount`` (Net Collected) for
        per-surgery / per-consultation Revenue metrics.
        """
        m = FactPatientJourney
        group_col = m.doctor_id

        consults = func.count(m.consult_scheduled_date)
        treatment_presented = func.count(m.treatment_presented_date)
        treatment_accepted = func.count(m.treatment_accepted_date)
        surgery_completed = func.count(m.surgery_completed_date)
        collected = func.coalesce(func.sum(m.collected_amount), 0)

        stmt = (
            select(
                group_col.label("doctor_id"),
                consults.label("consults"),
                treatment_presented.label("treatment_presented"),
                treatment_accepted.label("treatment_accepted"),
                surgery_completed.label("surgery_completed"),
                collected.label("collected"),
            )
            .where(m.lead_date >= window.start, m.lead_date < window.end)
            .group_by(group_col)
            .order_by(surgery_completed.desc(), collected.desc())
        )
        stmt = _apply_dimension_filters(stmt, filters)
        rows = (await self._session.execute(stmt)).all()

        return [
            DoctorGroupRow(
                doctor_id=r.doctor_id,
                consults=int(r.consults),
                treatment_presented=int(r.treatment_presented),
                treatment_accepted=int(r.treatment_accepted),
                surgery_completed=int(r.surgery_completed),
                collected=float(r.collected),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # ENG-517 / ENG-525 / ENG-527 — Vendor / Attribution / Influence
    # ------------------------------------------------------------------

    async def vendor_performance(
        self,
        *,
        window: ResolvedWindow,
        filters: AnalyticsFilters,
    ) -> list[VendorGroupRow]:
        """Per-vendor cohort outcomes (ENG-517).

        Groups in-cohort persons (``lead_date`` in window) by ``vendor_id``.
        NULL ``vendor_id`` collapses to the "Unassigned" bucket. Today
        (2026-06-23) all fact rows have vendor_id=NULL, so only one bucket
        is returned. The query structure is stable so results light up
        automatically the moment vendor_id gets populated (ENG-569).
        Ordered by collected desc (will sort meaningfully once populated).
        """
        m = FactPatientJourney
        group_col = m.vendor_id

        leads = func.count(m.lead_date)
        consults = func.count(m.consult_scheduled_date)
        shows = func.count(m.show_date)
        surgeries = func.count(m.surgery_completed_date)
        revenue = func.coalesce(func.sum(m.revenue_amount), 0)
        collected = func.coalesce(func.sum(m.collected_amount), 0)

        stmt = (
            select(
                group_col.label("vendor_id"),
                leads.label("leads"),
                consults.label("consults"),
                shows.label("shows"),
                surgeries.label("surgeries"),
                revenue.label("revenue"),
                collected.label("collected"),
            )
            .where(m.lead_date >= window.start, m.lead_date < window.end)
            .group_by(group_col)
            .order_by(collected.desc(), leads.desc())
        )
        stmt = _apply_dimension_filters(stmt, filters)
        rows = (await self._session.execute(stmt)).all()

        return [
            VendorGroupRow(
                vendor_id=r.vendor_id,
                leads=int(r.leads),
                consults=int(r.consults),
                shows=int(r.shows),
                surgeries=int(r.surgeries),
                revenue=float(r.revenue),
                collected=float(r.collected),
            )
            for r in rows
        ]

    async def influence_by_role(
        self,
        *,
        window: ResolvedWindow,
        filters: AnalyticsFilters,
        role: str,
        group_col: Any,
    ) -> list[InfluenceRow]:
        """Collected revenue by one role dimension for the influence matrix (ENG-527).

        Groups in-cohort persons (``lead_date`` in window) by ``group_col``
        (vendor_id / caller_id / coordinator_id / doctor_id). Each row is one
        (actor, role) pair; revenue_influenced = SUM(collected_amount).

        DOUBLE-COUNTING NOTE: the same patient's revenue will appear in the
        returned rows for every role they are attributed to. This is intentional
        per the ENG-527 spec — the matrix measures influence, not additive
        attribution. Callers of this method must NOT sum across roles.
        """
        m = FactPatientJourney
        revenue_influenced = func.coalesce(func.sum(m.collected_amount), 0)
        case_count = func.count(m.lead_date)

        stmt = (
            select(
                group_col.label("actor_id"),
                revenue_influenced.label("revenue_influenced"),
                case_count.label("case_count"),
            )
            .where(m.lead_date >= window.start, m.lead_date < window.end)
            .group_by(group_col)
            .order_by(revenue_influenced.desc())
        )
        stmt = _apply_dimension_filters(stmt, filters)
        rows = (await self._session.execute(stmt)).all()

        return [
            InfluenceRow(
                actor_id=r.actor_id,
                role=role,
                revenue_influenced=float(r.revenue_influenced),
                case_count=int(r.case_count),
            )
            for r in rows
        ]

    async def metric_person_uids(
        self,
        *,
        window: ResolvedWindow,
        filters: AnalyticsFilters,
        metric: str,
        limit: int,
    ) -> tuple[list[UUID], int]:
        """Person UIDs composing a metric + the unbounded cohort total (ENG-508).

        Drill-down from a metric to the underlying people: the in-cohort persons
        (``lead_date`` in window, same shared dimension filters) matching the
        metric's predicate. Deterministically ordered by ``person_uid`` and hard
        capped at ``limit`` rows; ``total`` is the full matching count (so the
        caller can flag truncation). Read-only — never writes the fact.
        """
        m = FactPatientJourney
        predicate = _drilldown_predicate(metric)

        base = select(m.person_uid).where(
            m.lead_date >= window.start, m.lead_date < window.end
        )
        base = _apply_dimension_filters(base, filters)
        if predicate is not None:
            base = base.where(predicate)

        total_stmt = select(func.count()).select_from(base.subquery())
        total = int((await self._session.execute(total_stmt)).scalar_one())

        rows_stmt = base.order_by(m.person_uid.asc()).limit(limit)
        person_uids = list((await self._session.execute(rows_stmt)).scalars().all())
        return person_uids, total
