"""Derived-metric tests — values + divide-by-zero → None (ENG-507)."""

from __future__ import annotations

import pytest

from packages.analytics.metrics import (
    StageAggregate,
    compute_derived_metrics,
    safe_div,
)


@pytest.mark.parametrize(
    ("num", "den", "expected"),
    [
        (100.0, 4, 25.0),
        (0.0, 4, 0.0),  # a genuine 0 numerator stays 0
        (None, 4, None),  # missing numerator (e.g. no spend) → None, not 0
        (100.0, 0, None),  # divide-by-zero → None
        (100.0, None, None),
        (None, 0, None),
    ],
)
def test_safe_div(num, den, expected) -> None:  # type: ignore[no-untyped-def]
    assert safe_div(num, den) == expected


def test_full_metrics() -> None:
    agg = StageAggregate(
        leads=100,
        contacts=80,
        consults=40,
        shows=20,
        surgeries=10,
        revenue=50_000.0,
        collected=50_000.0,
        spend=10_000.0,
    )
    m = compute_derived_metrics(agg)
    assert m.cost_per_lead == 100.0
    assert m.cost_per_consult == 250.0
    assert m.cost_per_show == 500.0
    assert m.cost_per_surgery == 1000.0
    assert m.revenue_per_lead == 500.0
    assert m.revenue_per_show == 2500.0
    assert m.roi == 5.0
    assert m.lead_to_contact == 0.8
    assert m.contact_to_consult == 0.5
    assert m.consult_to_show == 0.5
    assert m.show_to_surgery == 0.5
    assert m.surgery_to_revenue == 5000.0


def test_zero_denominators_yield_none() -> None:
    # No leads / consults / shows / surgeries, no spend.
    agg = StageAggregate()
    m = compute_derived_metrics(agg)
    assert m.cost_per_lead is None
    assert m.cost_per_consult is None
    assert m.cost_per_show is None
    assert m.cost_per_surgery is None
    assert m.revenue_per_lead is None
    assert m.revenue_per_show is None
    assert m.roi is None
    assert m.lead_to_contact is None
    assert m.contact_to_consult is None
    assert m.consult_to_show is None
    assert m.show_to_surgery is None
    assert m.surgery_to_revenue is None


def test_no_spend_kills_cost_and_roi_only() -> None:
    # Counts present but no ad spend → cost/ROI None, conversions still computed.
    agg = StageAggregate(leads=10, consults=5, shows=2, surgeries=1, spend=None)
    m = compute_derived_metrics(agg)
    assert m.cost_per_lead is None
    assert m.roi is None
    assert m.consult_to_show == 0.4
    assert m.show_to_surgery == 0.5
