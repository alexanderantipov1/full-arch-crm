"""Derived analytics metrics — single source of truth (ENG-507).

Pure functions over a stage aggregate + ad spend, so every page computes
cost-per-stage / revenue-per-stage / ROI / conversion ratios the SAME way (no
drift). The cardinal rule: **divide-by-zero → ``None``, never an error and never
a fabricated 0** — a metric with no denominator renders "—", consistent with the
rest of the analytics surface.
"""

from __future__ import annotations

from dataclasses import dataclass


def safe_div(numerator: float | None, denominator: float | None) -> float | None:
    """``numerator / denominator`` or ``None`` on a missing/zero input.

    ``None`` when the denominator is 0/None (divide-by-zero) OR when the
    numerator is ``None`` (a missing input — e.g. ``spend=None`` means "no ad
    spend connected", so cost-per-stage is unknown, NOT 0). Stage counts are
    real ints (a genuine 0 stays 0); only spend is ever ``None``.
    """
    if not denominator or numerator is None:
        return None
    return numerator / denominator


@dataclass(frozen=True)
class StageAggregate:
    """Per-window stage counts + money over ``fact_patient_journey``.

    Counts are persons reaching each stage (a non-null stage date); ``revenue``
    / ``collected`` are summed money. ``spend`` is ad spend over the same window
    from ``marketing.*`` (``None`` when no spend is connected).
    """

    leads: int = 0
    contacts: int = 0
    consults: int = 0
    shows: int = 0
    surgeries: int = 0
    revenue: float = 0.0
    collected: float = 0.0
    spend: float | None = None


@dataclass(frozen=True)
class DerivedMetrics:
    """Computed metrics; every field is ``None`` when its denominator is 0."""

    cost_per_lead: float | None
    cost_per_consult: float | None
    cost_per_show: float | None
    cost_per_surgery: float | None
    revenue_per_lead: float | None
    revenue_per_show: float | None
    roi: float | None
    lead_to_contact: float | None
    contact_to_consult: float | None
    consult_to_show: float | None
    show_to_surgery: float | None
    surgery_to_revenue: float | None


def compute_derived_metrics(agg: StageAggregate) -> DerivedMetrics:
    """Compute every derived metric from a stage aggregate (div-by-zero → None)."""
    spend = agg.spend
    return DerivedMetrics(
        # Cost per stage = spend / count reaching that stage.
        cost_per_lead=safe_div(spend, agg.leads),
        cost_per_consult=safe_div(spend, agg.consults),
        cost_per_show=safe_div(spend, agg.shows),
        cost_per_surgery=safe_div(spend, agg.surgeries),
        # Revenue per stage.
        revenue_per_lead=safe_div(agg.revenue, agg.leads),
        revenue_per_show=safe_div(agg.revenue, agg.shows),
        # Return on ad spend.
        roi=safe_div(agg.revenue, spend),
        # Conversion ratios along the funnel.
        lead_to_contact=safe_div(agg.contacts, agg.leads),
        contact_to_consult=safe_div(agg.consults, agg.contacts),
        consult_to_show=safe_div(agg.shows, agg.consults),
        show_to_surgery=safe_div(agg.surgeries, agg.shows),
        surgery_to_revenue=safe_div(agg.revenue, agg.surgeries),
    )
