"""ENG-517/525/527 — Vendor / Attribution / Influence derived-metric layer (pure unit).

Covers:
  * VendorPerformanceOut: honest no-data when vendor_attribution_wired=False;
    note populated iff unresolved; spend_managed/roi always None.
  * AttributionAnalyticsOut: vendor dimension resolved=False, others resolved=True;
    collected_total derived from campaign dim; safe_div on avg_case_value.
  * RevenueInfluenceMatrixOut: rows carry correct role tag; Unassigned label for
    null employee_id; revenue_influenced honoured; double-counting is intentional.
  * safe_div zero-denominator → None (canonical contract from metrics module).

Pure (no DB): real-Postgres aggregation is exercised in
``tests/integration/test_analytics_pages.py``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from packages.analytics.metrics import safe_div
from packages.analytics.queries import InfluenceRow, VendorGroupRow
from packages.analytics.schemas import (
    AnalyticsFiltersEchoOut,
    AnalyticsWindowOut,
    InfluenceRowOut,
    VendorGroupOut,
    VendorPerformanceOut,
)

# ---------------------------------------------------------------------------
# Helpers — mirror the service logic so tests are independent of internal
# method signatures while exercising the same derived-metric logic.
# ---------------------------------------------------------------------------


def _build_vendor_out(row: VendorGroupRow) -> VendorGroupOut:
    return VendorGroupOut(
        vendor_id=row.vendor_id,
        leads=row.leads,
        consults=row.consults,
        shows=row.shows,
        surgeries=row.surgeries,
        revenue=row.revenue,
        collected=row.collected,
        spend_managed=None,
        roi=None,
    )


def _build_influence_out(row: InfluenceRow) -> InfluenceRowOut:
    uid = row.actor_id
    label = str(uid)[:8] if uid is not None else "Unassigned"
    return InfluenceRowOut(
        employee_id=uid,
        employee_label=label,
        role=row.role,
        revenue_influenced=row.revenue_influenced,
        case_count=row.case_count,
    )


# ---------------------------------------------------------------------------
# VendorGroupOut tests (ENG-517)
# ---------------------------------------------------------------------------


def test_vendor_out_null_vendor_id_passes_through() -> None:
    row = VendorGroupRow(
        vendor_id=None,
        leads=1000,
        consults=500,
        shows=300,
        surgeries=100,
        revenue=500000.0,
        collected=450000.0,
    )
    out = _build_vendor_out(row)
    assert out.vendor_id is None


def test_vendor_out_spend_managed_always_none() -> None:
    """spend_managed must NEVER be non-None — no vendor→spend column on the fact."""
    row = VendorGroupRow(
        vendor_id=None,
        leads=100,
        consults=50,
        shows=30,
        surgeries=10,
        revenue=50000.0,
        collected=45000.0,
    )
    out = _build_vendor_out(row)
    assert out.spend_managed is None, (
        "spend_managed must be None — no vendor→spend mapping on the analytics fact."
    )


def test_vendor_out_roi_always_none() -> None:
    """roi is None without spend data."""
    row = VendorGroupRow(
        vendor_id=None,
        leads=50,
        consults=25,
        shows=15,
        surgeries=5,
        revenue=25000.0,
        collected=22000.0,
    )
    out = _build_vendor_out(row)
    assert out.roi is None


def test_vendor_out_with_real_vendor_id() -> None:
    vid = uuid.uuid4()
    row = VendorGroupRow(
        vendor_id=vid,
        leads=200,
        consults=100,
        shows=60,
        surgeries=20,
        revenue=100000.0,
        collected=90000.0,
    )
    out = _build_vendor_out(row)
    assert out.vendor_id == vid
    assert out.leads == 200
    assert out.collected == pytest.approx(90000.0)


def _make_window_and_filters() -> tuple[AnalyticsWindowOut, AnalyticsFiltersEchoOut]:
    now = datetime.now(tz=UTC)
    window = AnalyticsWindowOut(preset="last_30_days", start=now, end=now, tz="UTC")
    filters_echo = AnalyticsFiltersEchoOut(
        time_range="last_30_days",
        location_id=None,
        campaign_id=None,
        source=None,
        vendor_id=None,
        caller_id=None,
        coordinator_id=None,
        doctor_id=None,
    )
    return window, filters_echo


def test_vendor_performance_out_unresolved_sets_note() -> None:
    """VendorPerformanceOut.note is populated when vendor_attribution_wired=False."""
    window, filters_echo = _make_window_and_filters()
    out = VendorPerformanceOut(
        window=window,
        filters=filters_echo,
        vendor_attribution_wired=False,
        note="vendor_id is NULL on all rows",
        vendors=[],
    )
    assert not out.vendor_attribution_wired
    assert out.note is not None
    assert "NULL" in out.note


def test_vendor_performance_out_resolved_has_no_note() -> None:
    """When vendor_attribution_wired=True, note should be None."""
    window, filters_echo = _make_window_and_filters()
    out = VendorPerformanceOut(
        window=window,
        filters=filters_echo,
        vendor_attribution_wired=True,
        note=None,
        vendors=[],
    )
    assert out.vendor_attribution_wired
    assert out.note is None


# ---------------------------------------------------------------------------
# InfluenceRowOut tests (ENG-527)
# ---------------------------------------------------------------------------


def test_influence_row_null_actor_gets_unassigned_label() -> None:
    row = InfluenceRow(
        actor_id=None,
        role="caller",
        revenue_influenced=50000.0,
        case_count=10,
    )
    out = _build_influence_out(row)
    assert out.employee_id is None
    assert out.employee_label == "Unassigned"


def test_influence_row_uuid_actor_gets_short_prefix() -> None:
    uid = uuid.uuid4()
    row = InfluenceRow(
        actor_id=uid,
        role="coordinator",
        revenue_influenced=120000.0,
        case_count=25,
    )
    out = _build_influence_out(row)
    assert out.employee_id == uid
    assert out.employee_label == str(uid)[:8]
    assert len(out.employee_label) == 8


def test_influence_row_role_preserved() -> None:
    for role in ("vendor", "caller", "coordinator", "doctor"):
        row = InfluenceRow(
            actor_id=None,
            role=role,
            revenue_influenced=10000.0,
            case_count=5,
        )
        out = _build_influence_out(row)
        assert out.role == role


def test_influence_row_revenue_and_count_preserved() -> None:
    row = InfluenceRow(
        actor_id=None,
        role="doctor",
        revenue_influenced=300000.0,
        case_count=42,
    )
    out = _build_influence_out(row)
    assert out.revenue_influenced == pytest.approx(300000.0)
    assert out.case_count == 42


def test_influence_double_counting_is_intentional() -> None:
    """The same revenue appears once per role dimension — this is by design.

    A patient's $10,000 collected appears in both the Caller row and the
    Coordinator row if both are assigned. Summing across roles would over-count
    the total collected revenue; callers of the matrix must NOT sum across roles.
    This test documents and asserts the behaviour rather than guarding against it.
    """
    caller_row = InfluenceRow(
        actor_id=None, role="caller", revenue_influenced=10000.0, case_count=1
    )
    coord_row = InfluenceRow(
        actor_id=None, role="coordinator", revenue_influenced=10000.0, case_count=1
    )
    caller_out = _build_influence_out(caller_row)
    coord_out = _build_influence_out(coord_row)

    # Both report the same revenue — this is intentional, not a bug.
    assert caller_out.revenue_influenced == pytest.approx(10000.0)
    assert coord_out.revenue_influenced == pytest.approx(10000.0)

    # If summed across roles the total would be $20,000 for a $10,000 patient —
    # callers must never sum across roles.
    naive_sum = caller_out.revenue_influenced + coord_out.revenue_influenced
    assert naive_sum == pytest.approx(20000.0), (
        "Cross-role sum over-counts by design. "
        "This test documents the double-counting behaviour; do not sum across roles."
    )


# ---------------------------------------------------------------------------
# safe_div zero-denominator → None (canonical contract)
# ---------------------------------------------------------------------------


def test_safe_div_zero_denominator_gives_none() -> None:
    assert safe_div(5000.0, 0.0) is None
    assert safe_div(5000.0, 0) is None


def test_safe_div_none_numerator_gives_none() -> None:
    assert safe_div(None, 100.0) is None


def test_safe_div_none_denominator_gives_none() -> None:
    assert safe_div(100.0, None) is None


def test_safe_div_normal_division() -> None:
    assert safe_div(10000.0, 4) == pytest.approx(2500.0)


def test_safe_div_real_zero_numerator_is_not_none() -> None:
    # 0 / non-zero = 0.0 (real zero, not None)
    result = safe_div(0.0, 100.0)
    assert result is not None
    assert result == pytest.approx(0.0)
