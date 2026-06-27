"""Unit tests for Cost Intelligence helpers and Bottleneck Detection rules (ENG-522/524).

Tests are DB-free: they exercise the pure rule functions and the ``safe_div``
helper directly with hand-built row objects. The bottleneck rule functions and
cost metric helpers are module-level functions in ``metrics_service.py``; we
import them directly so each rule can be tested in isolation.

Pattern mirrors ``tests/analytics/test_metrics.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from packages.analytics.metrics import safe_div
from packages.analytics.metrics_service import (
    _MIN_CALLER_LEADS,
    _MIN_CAMPAIGN_LEADS,
    _MIN_COORDINATOR_CONSULTS,
    _MIN_DOCTOR_CONSULTS,
    _caller_booking_rule,
    _campaign_show_rate_rule,
    _coordinator_surgery_rule,
    _doctor_acceptance_rule,
    _is_bottleneck,
    _median,
    _relative_severity,
)

# ---------------------------------------------------------------------------
# Lightweight stub row types (mirror the query dataclasses without DB)
# ---------------------------------------------------------------------------


@dataclass
class _CampaignRow:
    group_id: UUID | None
    group_label: str | None
    shows: int
    leads: int


@dataclass
class _CoordinatorRow:
    coordinator_id: UUID | None
    consults_assigned: int
    shows: int
    surgery_completed: int


@dataclass
class _DoctorRow:
    doctor_id: UUID | None
    consults: int
    treatment_accepted: int


@dataclass
class _CallerRow:
    caller_id: UUID | None
    leads: int
    consults: int


# ---------------------------------------------------------------------------
# _median helper
# ---------------------------------------------------------------------------


def test_median_empty() -> None:
    assert _median([]) is None


def test_median_single() -> None:
    assert _median([0.5]) == 0.5


def test_median_even() -> None:
    assert _median([0.2, 0.4]) == pytest.approx(0.3)


def test_median_odd() -> None:
    assert _median([0.1, 0.3, 0.5]) == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# _relative_severity helper — severity by relative shortfall s=(median-rate)/median
# Bands: s >= 0.75 high, s >= 0.55 medium, else low.
# ---------------------------------------------------------------------------


def test_relative_severity_high_zero_rate() -> None:
    # 0% against any positive median → s = 1.0 → high (base-rate-agnostic).
    assert _relative_severity(0.0588, 0.0) == "high"  # low-base cohort
    assert _relative_severity(0.80, 0.0) == "high"  # high-base cohort


def test_relative_severity_high_band() -> None:
    # s = (0.10 - 0.02)/0.10 = 0.80 >= 0.75 → high
    assert _relative_severity(0.10, 0.02) == "high"


def test_relative_severity_medium_band() -> None:
    # s = (0.10 - 0.04)/0.10 = 0.60 in [0.55, 0.75) → medium
    assert _relative_severity(0.10, 0.04) == "medium"


def test_relative_severity_low_band() -> None:
    # s = (0.10 - 0.055)/0.10 = 0.45 < 0.55 → low
    assert _relative_severity(0.10, 0.055) == "low"


def test_relative_severity_base_rate_agnostic() -> None:
    # Same relative shortfall (s=0.75) gives the same severity at any base rate.
    # high-base: median 0.80, rate 0.20 → s = 0.75 → high
    assert _relative_severity(0.80, 0.20) == "high"
    # low-base: median 0.0588, rate 0.0147 → s = 0.75 → high
    assert _relative_severity(0.0588, 0.0147) == "high"


# ---------------------------------------------------------------------------
# _is_bottleneck flag predicate — relative ≥40% below median + ≥2pp floor.
# ---------------------------------------------------------------------------


def test_is_bottleneck_none_median() -> None:
    # No median to compare against → never flag (no divide-by-zero).
    assert _is_bottleneck(None, 0.0) is False


def test_is_bottleneck_zero_median() -> None:
    # Median 0 → never flag (nothing to compare).
    assert _is_bottleneck(0.0, 0.0) is False


def test_is_bottleneck_low_base_zero_rate_flagged() -> None:
    # THE BUG: low-base median 0.0588, entity at 0.0.
    # relative: 0.0 <= 0.0588 * 0.6 = 0.0353 → True
    # absolute: 0.0588 - 0.0 = 0.0588 >= 0.02 → True → flagged.
    assert _is_bottleneck(0.0588, 0.0) is True


def test_is_bottleneck_relative_drop_boundary() -> None:
    # Exactly at the 40% relative drop: rate = median * 0.6.
    # 0.0588 * 0.6 = 0.03528 → rate <= 0.03528 flags; just above does not.
    assert _is_bottleneck(0.0588, 0.0588 * 0.6) is True
    assert _is_bottleneck(0.0588, 0.0588 * 0.6 + 0.0001) is False


def test_is_bottleneck_absolute_floor_blocks_high_base() -> None:
    # High base: median 0.80, rate 0.79 → 50%? No: relative drop is tiny
    # (0.79 > 0.80*0.6=0.48 → relative test fails) so not flagged. But test the
    # floor path: a 41% relative drop that is < 2pp absolute should NOT flag.
    # Construct: median 0.04, rate 0.0235 → relative 0.0235 <= 0.024 True,
    # absolute 0.04 - 0.0235 = 0.0165 < 0.02 → blocked by floor.
    assert _is_bottleneck(0.04, 0.0235) is False


def test_is_bottleneck_above_relative_not_flagged() -> None:
    # Entity only slightly below median (well within 40%) → not flagged.
    assert _is_bottleneck(0.50, 0.45) is False


# ---------------------------------------------------------------------------
# Campaign show-rate rule
# ---------------------------------------------------------------------------


def test_campaign_rule_empty_no_findings() -> None:
    """No campaigns → no findings."""
    findings = _campaign_show_rate_rule(
        [], cohort_leads=100, cohort_collected=50_000.0
    )
    assert findings == []


def test_campaign_rule_below_min_sample_skipped() -> None:
    """Campaigns with fewer than _MIN_CAMPAIGN_LEADS leads are skipped."""
    row = _CampaignRow(
        group_id=uuid4(), group_label="Small", shows=0, leads=_MIN_CAMPAIGN_LEADS - 1
    )
    findings = _campaign_show_rate_rule(
        [row], cohort_leads=100, cohort_collected=50_000.0  # type: ignore[arg-type]
    )
    assert findings == []


def test_campaign_rule_unassigned_skipped() -> None:
    """Unassigned bucket (group_id=None) is never flagged."""
    row = _CampaignRow(
        group_id=None, group_label=None, shows=0, leads=_MIN_CAMPAIGN_LEADS + 5
    )
    findings = _campaign_show_rate_rule(
        [row], cohort_leads=100, cohort_collected=50_000.0  # type: ignore[arg-type]
    )
    assert findings == []


def test_campaign_rule_all_equal_no_findings() -> None:
    """When all campaigns have the same show rate, deviation is 0 → no findings."""
    cid = uuid4()
    rows = [
        _CampaignRow(group_id=cid, group_label="A", shows=5, leads=10),
        _CampaignRow(group_id=uuid4(), group_label="B", shows=5, leads=10),
    ]
    findings = _campaign_show_rate_rule(
        rows, cohort_leads=20, cohort_collected=10_000.0  # type: ignore[arg-type]
    )
    assert findings == []


def test_campaign_rule_flags_low_show() -> None:
    """Campaign with show rate 0.10 vs median 0.60 → deviation 0.50 >> threshold."""
    good_id = uuid4()
    bad_id = uuid4()
    rows = [
        _CampaignRow(group_id=good_id, group_label="Good", shows=6, leads=10),  # 0.6
        _CampaignRow(group_id=bad_id, group_label="Bad", shows=1, leads=10),  # 0.1
    ]
    # median([0.6, 0.1]) = 0.35; deviation for bad = 0.35 - 0.10 = 0.25 > 0.15
    findings = _campaign_show_rate_rule(
        rows, cohort_leads=20, cohort_collected=10_000.0  # type: ignore[arg-type]
    )
    assert len(findings) == 1
    assert findings[0].entity.id == bad_id
    assert findings[0].category == "campaign_low_show"
    assert findings[0].severity in ("low", "medium", "high")


def test_campaign_rule_revenue_loss_computed() -> None:
    """estimated_revenue_loss is not None when cohort has leads + collected."""
    good_id = uuid4()
    bad_id = uuid4()
    rows = [
        _CampaignRow(group_id=good_id, group_label="Good", shows=8, leads=10),  # 0.8
        _CampaignRow(group_id=bad_id, group_label="Bad", shows=1, leads=10),  # 0.1
    ]
    # median([0.8, 0.1]) = 0.45; deviation for bad = 0.45-0.10 = 0.35 > 0.15
    findings = _campaign_show_rate_rule(
        rows, cohort_leads=20, cohort_collected=20_000.0  # type: ignore[arg-type]
    )
    assert len(findings) == 1
    assert findings[0].estimated_revenue_loss is not None
    assert findings[0].estimated_revenue_loss > 0


def test_campaign_rule_zero_cohort_leads_no_loss() -> None:
    """When cohort_leads=0 the revenue-loss estimate is None (safe_div guard)."""
    bad_id = uuid4()
    good_id = uuid4()
    rows = [
        _CampaignRow(group_id=good_id, group_label="Good", shows=8, leads=10),
        _CampaignRow(group_id=bad_id, group_label="Bad", shows=1, leads=10),
    ]
    findings = _campaign_show_rate_rule(
        rows, cohort_leads=0, cohort_collected=0.0  # type: ignore[arg-type]
    )
    for f in findings:
        assert f.estimated_revenue_loss is None


# ---------------------------------------------------------------------------
# Coordinator show→surgery rule
# ---------------------------------------------------------------------------


def test_coordinator_rule_empty_no_findings() -> None:
    findings = _coordinator_surgery_rule(
        [], cohort_surgeries=10, cohort_collected=5000.0
    )
    assert findings == []


def test_coordinator_rule_below_min_consults_skipped() -> None:
    row = _CoordinatorRow(
        coordinator_id=uuid4(),
        consults_assigned=_MIN_COORDINATOR_CONSULTS - 1,
        shows=0,
        surgery_completed=0,
    )
    findings = _coordinator_surgery_rule(
        [row], cohort_surgeries=10, cohort_collected=5000.0  # type: ignore[arg-type]
    )
    assert findings == []


def test_coordinator_rule_unassigned_skipped() -> None:
    row = _CoordinatorRow(
        coordinator_id=None,
        consults_assigned=_MIN_COORDINATOR_CONSULTS + 2,
        shows=5,
        surgery_completed=0,
    )
    findings = _coordinator_surgery_rule(
        [row], cohort_surgeries=10, cohort_collected=5000.0  # type: ignore[arg-type]
    )
    assert findings == []


def test_coordinator_rule_flags_low_conversion() -> None:
    """Coordinator with show→surgery 0% vs median 50% → flagged."""
    cid1, cid2 = uuid4(), uuid4()
    rows = [
        _CoordinatorRow(
            coordinator_id=cid1, consults_assigned=10, shows=10, surgery_completed=5
        ),  # 0.5
        _CoordinatorRow(
            coordinator_id=cid2, consults_assigned=10, shows=10, surgery_completed=0
        ),  # 0.0
    ]
    # median([0.5, 0.0]) = 0.25; cid2 rate 0.0: relative 0.0 <= 0.25*0.6=0.15
    # and absolute 0.25 >= 0.02 → flagged.
    findings = _coordinator_surgery_rule(
        rows, cohort_surgeries=5, cohort_collected=5000.0  # type: ignore[arg-type]
    )
    assert any(f.entity.id == cid2 for f in findings)
    assert findings[0].category == "coordinator_low_surgery_conversion"


def test_coordinator_rule_high_severity() -> None:
    """Relative shortfall s ≥ 0.75 → high severity."""
    cid1, cid2 = uuid4(), uuid4()
    rows = [
        _CoordinatorRow(
            coordinator_id=cid1, consults_assigned=10, shows=10, surgery_completed=9
        ),  # 0.9
        _CoordinatorRow(
            coordinator_id=cid2, consults_assigned=10, shows=10, surgery_completed=1
        ),  # 0.1
    ]
    # median([0.9, 0.1]) = 0.5; cid2 s = (0.5 - 0.1)/0.5 = 0.8 >= 0.75 → high
    findings = _coordinator_surgery_rule(
        rows, cohort_surgeries=10, cohort_collected=10_000.0  # type: ignore[arg-type]
    )
    flagged = [f for f in findings if f.entity.id == cid2]
    assert len(flagged) == 1
    assert flagged[0].severity == "high"


# ---------------------------------------------------------------------------
# Doctor acceptance rule
# ---------------------------------------------------------------------------


def test_doctor_rule_below_min_consults_skipped() -> None:
    row = _DoctorRow(
        doctor_id=uuid4(),
        consults=_MIN_DOCTOR_CONSULTS - 1,
        treatment_accepted=0,
    )
    findings = _doctor_acceptance_rule(
        [row], cohort_accepted=5, cohort_collected=5000.0  # type: ignore[arg-type]
    )
    assert findings == []


def test_doctor_rule_flags_low_acceptance() -> None:
    """Doctor with 0% acceptance vs median 40% → flagged."""
    did1, did2 = uuid4(), uuid4()
    rows = [
        _DoctorRow(doctor_id=did1, consults=10, treatment_accepted=4),  # 0.4
        _DoctorRow(doctor_id=did2, consults=10, treatment_accepted=0),  # 0.0
    ]
    # median([0.4, 0.0]) = 0.20; did2 rate 0.0: relative 0.0 <= 0.20*0.6=0.12
    # and absolute 0.20 >= 0.02 → flagged.
    findings = _doctor_acceptance_rule(
        rows, cohort_accepted=4, cohort_collected=4_000.0  # type: ignore[arg-type]
    )
    assert any(f.entity.id == did2 for f in findings)
    assert findings[0].category == "doctor_low_acceptance"


def test_doctor_rule_all_zero_acceptance_no_median() -> None:
    """All doctors at 0% → median 0 → no comparison baseline → no findings."""
    rows = [
        _DoctorRow(doctor_id=uuid4(), consults=10, treatment_accepted=0),
        _DoctorRow(doctor_id=uuid4(), consults=10, treatment_accepted=0),
    ]
    findings = _doctor_acceptance_rule(
        rows, cohort_accepted=0, cohort_collected=0.0  # type: ignore[arg-type]
    )
    assert findings == []


# ---------------------------------------------------------------------------
# Caller booking rule
# ---------------------------------------------------------------------------


def test_caller_rule_below_min_leads_skipped() -> None:
    row = _CallerRow(
        caller_id=uuid4(), leads=_MIN_CALLER_LEADS - 1, consults=0
    )
    findings = _caller_booking_rule(
        [row], cohort_consults=5, cohort_collected=5000.0  # type: ignore[arg-type]
    )
    assert findings == []


def test_caller_rule_unassigned_skipped() -> None:
    row = _CallerRow(caller_id=None, leads=20, consults=0)
    findings = _caller_booking_rule(
        [row], cohort_consults=0, cohort_collected=0.0  # type: ignore[arg-type]
    )
    assert findings == []


def test_caller_rule_flags_low_booking() -> None:
    """Caller with 0% booking vs median 40% → flagged."""
    cid1, cid2 = uuid4(), uuid4()
    rows = [
        _CallerRow(caller_id=cid1, leads=10, consults=4),  # 0.4
        _CallerRow(caller_id=cid2, leads=10, consults=0),  # 0.0
    ]
    # median([0.4, 0.0]) = 0.20; cid2 rate 0.0: relative 0.0 <= 0.20*0.6=0.12
    # and absolute 0.20 >= 0.02 → flagged.
    findings = _caller_booking_rule(
        rows, cohort_consults=4, cohort_collected=4_000.0  # type: ignore[arg-type]
    )
    assert any(f.entity.id == cid2 for f in findings)
    assert findings[0].category == "caller_low_booking"


def test_caller_rule_revenue_loss_none_when_no_consults() -> None:
    """When cohort_consults=0, revenue-per-consult is None → loss is None."""
    cid1, cid2 = uuid4(), uuid4()
    rows = [
        _CallerRow(caller_id=cid1, leads=10, consults=4),
        _CallerRow(caller_id=cid2, leads=10, consults=0),
    ]
    findings = _caller_booking_rule(
        rows, cohort_consults=0, cohort_collected=4_000.0  # type: ignore[arg-type]
    )
    for f in findings:
        assert f.estimated_revenue_loss is None


# ---------------------------------------------------------------------------
# Relative-shortfall severity boundary tests (s = (median - rate)/median)
# Bands: high s ≥ 0.75, medium s ≥ 0.55, else low.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("median_rate", "rate", "expected_sev"),
    [
        # s computed = (median - rate)/median.
        (0.10, 0.10, "low"),     # s = 0.00 → low
        (0.10, 0.06, "low"),     # s = 0.40 → low (< 0.55)
        (0.10, 0.045, "medium"),  # s = 0.55 → medium (boundary)
        (0.10, 0.04, "medium"),  # s = 0.60 → medium
        (0.10, 0.025, "high"),   # s = 0.75 → high (boundary)
        (0.10, 0.0, "high"),     # s = 1.00 → high
        # Base-rate-agnostic: identical s at a low base rate gives same severity.
        (0.0588, 0.0, "high"),       # s = 1.00 → high (the production caller)
        (0.0588, 0.0147, "high"),    # s = 0.75 → high
    ],
)
def test_relative_severity_boundaries(
    median_rate: float, rate: float, expected_sev: str
) -> None:
    assert _relative_severity(median_rate, rate) == expected_sev


def test_low_base_rate_cohort_produces_finding_regression() -> None:
    """REGRESSION (ENG-524): a low-base-rate caller cohort MUST produce findings.

    This is the exact production bug: caller lead→consult median ≈ 0.0588. Under
    the old ABSOLUTE 15-pp model, ``median - 0.15 = -0.091 < 0`` so NO caller
    could ever be flagged — even one booking 0.0% on 21 leads. The relative
    model flags it.

    Cohort:
      - caller A: 5 consults / 50 leads = 0.10 (typical-ish)
      - caller B: 4 consults / 60 leads ≈ 0.0667
      - caller C: 0 consults / 21 leads = 0.0 (clear bottleneck)
      - caller D: 1 consult / 68 leads ≈ 0.0147 (clear bottleneck)
    median([0.10, 0.0667, 0.0, 0.0147]) = (0.0147 + 0.0667)/2 ≈ 0.0407.
    Caller C (0.0): s = 1.00 → flagged high.
    Caller D (0.0147): relative 0.0147 <= 0.0407*0.6 = 0.0244 → True;
                       absolute 0.0407 - 0.0147 = 0.026 >= 0.02 → True → flagged.
    """
    a, b, c, d = uuid4(), uuid4(), uuid4(), uuid4()
    rows = [
        _CallerRow(caller_id=a, leads=50, consults=5),  # 0.10
        _CallerRow(caller_id=b, leads=60, consults=4),  # 0.0667
        _CallerRow(caller_id=c, leads=21, consults=0),  # 0.0  — the bug case
        _CallerRow(caller_id=d, leads=68, consults=1),  # 0.0147
    ]
    findings = _caller_booking_rule(
        rows, cohort_consults=10, cohort_collected=100_000.0  # type: ignore[arg-type]
    )
    flagged_ids = {f.entity.id for f in findings}
    # The 0.0% caller on 21 leads MUST be flagged (the exact production bug).
    assert c in flagged_ids
    # The 1.47% caller is also a real bottleneck on this cohort.
    assert d in flagged_ids
    # And it must be high severity for the 0% caller.
    c_finding = next(f for f in findings if f.entity.id == c)
    assert c_finding.severity == "high"


def test_low_base_rate_cohort_with_absolute_15pp_would_miss() -> None:
    """Sanity: confirm the OLD absolute-15pp gate would have flagged nothing.

    Demonstrates the bug is genuinely fixed: at this low base rate, ``median -
    0.15`` is negative, so an absolute-pp model flags nobody, while the relative
    model (current code) flags the 0% caller.
    """
    median = 0.0588
    # Old broken gate: flag iff (median - rate) >= 0.15 → impossible here.
    assert (median - 0.0) < 0.15  # even a 0% rate fails the old absolute gate
    # New gate flags it:
    assert _is_bottleneck(median, 0.0) is True


# ---------------------------------------------------------------------------
# safe_div integration with cost metrics
# ---------------------------------------------------------------------------


def test_safe_div_zero_denom_none() -> None:
    assert safe_div(1000.0, 0) is None


def test_safe_div_none_numerator_none() -> None:
    assert safe_div(None, 10) is None


def test_safe_div_normal() -> None:
    assert safe_div(1000.0, 10) == pytest.approx(100.0)


def test_cost_per_revenue_dollar_formula() -> None:
    """spend / collected: basic cost-per-dollar-collected calculation."""
    spend = 5_000.0
    collected = 50_000.0
    result = safe_div(spend, collected)
    assert result == pytest.approx(0.10)  # $0.10 marketing cost per $1 collected


def test_cost_per_lead_zero_leads() -> None:
    """Zero leads → None, not a division error."""
    assert safe_div(10_000.0, 0) is None


def test_no_spend_propagates_none() -> None:
    """When spend is None, safe_div(None, anything) = None."""
    assert safe_div(None, 100) is None
    assert safe_div(None, 0) is None
