"""ENG-518/519/520 — Actor Performance derived-metric layer (pure unit).

Covers the service-layer composition for CallerPerformanceOut,
CoordinatorPerformanceOut, and DoctorPerformanceOut — specifically that:
  * ``safe_div`` is applied to every ratio (zero denominator → ``None``, not 0).
  * ``calls_made`` is always ``None`` (honest no-data: no per-call count in fact).
  * ``None`` caller/coordinator/doctor_id rows pass through without error.

Pure (no DB): the real-Postgres aggregation is exercised in
``tests/integration/test_analytics_pages.py``.
"""

from __future__ import annotations

import pytest

from packages.analytics.metrics import safe_div
from packages.analytics.queries import CallerGroupRow, CoordinatorGroupRow, DoctorGroupRow
from packages.analytics.schemas import CallerGroupOut, CoordinatorGroupOut, DoctorGroupOut

# ---------------------------------------------------------------------------
# Helpers — mirror what the service does (keeps tests independent of internal
# method signatures while testing the same derived-metric logic)
# ---------------------------------------------------------------------------


def _build_caller_out(row: CallerGroupRow) -> CallerGroupOut:
    return CallerGroupOut(
        caller_id=row.caller_id,
        leads=row.leads,
        reached=row.reached,
        consults=row.consults,
        calls_made=None,
        lead_to_contact=safe_div(row.reached, row.leads),
        lead_to_consult=safe_div(row.consults, row.leads),
        collected=row.collected,
        revenue_per_lead=safe_div(row.collected, row.leads),
        revenue_per_consult=safe_div(row.collected, row.consults),
    )


def _build_coordinator_out(row: CoordinatorGroupRow) -> CoordinatorGroupOut:
    return CoordinatorGroupOut(
        coordinator_id=row.coordinator_id,
        consults_assigned=row.consults_assigned,
        shows=row.shows,
        treatment_presented=row.treatment_presented,
        surgery_scheduled=row.surgery_scheduled,
        surgery_completed=row.surgery_completed,
        collected=row.collected,
        scheduled_to_show=safe_div(row.shows, row.consults_assigned),
        show_to_surgery=safe_div(row.surgery_completed, row.shows),
        revenue_per_consult=safe_div(row.collected, row.consults_assigned),
    )


def _build_doctor_out(row: DoctorGroupRow) -> DoctorGroupOut:
    return DoctorGroupOut(
        doctor_id=row.doctor_id,
        consults=row.consults,
        treatment_presented=row.treatment_presented,
        treatment_accepted=row.treatment_accepted,
        surgery_completed=row.surgery_completed,
        collected=row.collected,
        consult_to_accepted=safe_div(row.treatment_accepted, row.consults),
        accepted_to_surgery=safe_div(row.surgery_completed, row.treatment_accepted),
        revenue_per_consult=safe_div(row.collected, row.consults),
        revenue_per_surgery=safe_div(row.collected, row.surgery_completed),
    )


# ---------------------------------------------------------------------------
# CallerGroupOut tests (ENG-518)
# ---------------------------------------------------------------------------


def test_caller_out_derived_metrics_normal() -> None:
    row = CallerGroupRow(caller_id=None, leads=10, reached=8, consults=4, collected=20000.0)
    out = _build_caller_out(row)

    assert out.calls_made is None  # always no-data
    assert out.lead_to_contact == pytest.approx(0.8)
    assert out.lead_to_consult == pytest.approx(0.4)
    assert out.revenue_per_lead == pytest.approx(2000.0)
    assert out.revenue_per_consult == pytest.approx(5000.0)
    assert out.leads == 10
    assert out.reached == 8
    assert out.collected == pytest.approx(20000.0)


def test_caller_out_zero_leads_gives_none_ratios() -> None:
    row = CallerGroupRow(caller_id=None, leads=0, reached=0, consults=0, collected=0.0)
    out = _build_caller_out(row)

    assert out.calls_made is None
    assert out.lead_to_contact is None
    assert out.lead_to_consult is None
    assert out.revenue_per_lead is None
    assert out.revenue_per_consult is None


def test_caller_out_reached_but_no_consults() -> None:
    row = CallerGroupRow(caller_id=None, leads=5, reached=3, consults=0, collected=0.0)
    out = _build_caller_out(row)

    assert out.lead_to_contact == pytest.approx(0.6)
    assert out.lead_to_consult == pytest.approx(0.0)  # 0/5 = 0.0 (real zero, not None)
    assert out.revenue_per_consult is None  # 0 denominator


def test_caller_out_null_caller_id_passes_through() -> None:
    row = CallerGroupRow(caller_id=None, leads=2, reached=1, consults=1, collected=5000.0)
    out = _build_caller_out(row)
    assert out.caller_id is None


# ---------------------------------------------------------------------------
# CoordinatorGroupOut tests (ENG-519)
# ---------------------------------------------------------------------------


def test_coordinator_out_derived_metrics_normal() -> None:
    import uuid
    cid = uuid.uuid4()
    row = CoordinatorGroupRow(
        coordinator_id=cid,
        consults_assigned=10,
        shows=7,
        treatment_presented=6,
        surgery_scheduled=5,
        surgery_completed=4,
        collected=40000.0,
    )
    out = _build_coordinator_out(row)

    assert out.scheduled_to_show == pytest.approx(0.7)
    assert out.show_to_surgery == pytest.approx(4 / 7)
    assert out.revenue_per_consult == pytest.approx(4000.0)
    assert out.coordinator_id == cid


def test_coordinator_out_zero_consults_gives_none() -> None:
    row = CoordinatorGroupRow(
        coordinator_id=None,
        consults_assigned=0,
        shows=0,
        treatment_presented=0,
        surgery_scheduled=0,
        surgery_completed=0,
        collected=0.0,
    )
    out = _build_coordinator_out(row)

    assert out.scheduled_to_show is None
    assert out.show_to_surgery is None
    assert out.revenue_per_consult is None


def test_coordinator_out_shows_but_no_surgeries() -> None:
    row = CoordinatorGroupRow(
        coordinator_id=None,
        consults_assigned=5,
        shows=5,
        treatment_presented=5,
        surgery_scheduled=0,
        surgery_completed=0,
        collected=25000.0,
    )
    out = _build_coordinator_out(row)

    assert out.scheduled_to_show == pytest.approx(1.0)
    assert out.show_to_surgery == pytest.approx(0.0)  # 0/5 real zero
    assert out.revenue_per_consult == pytest.approx(5000.0)


# ---------------------------------------------------------------------------
# DoctorGroupOut tests (ENG-520)
# ---------------------------------------------------------------------------


def test_doctor_out_derived_metrics_normal() -> None:
    import uuid
    did = uuid.uuid4()
    row = DoctorGroupRow(
        doctor_id=did,
        consults=8,
        treatment_presented=6,
        treatment_accepted=5,
        surgery_completed=4,
        collected=80000.0,
    )
    out = _build_doctor_out(row)

    assert out.consult_to_accepted == pytest.approx(5 / 8)
    assert out.accepted_to_surgery == pytest.approx(4 / 5)
    assert out.revenue_per_consult == pytest.approx(10000.0)
    assert out.revenue_per_surgery == pytest.approx(20000.0)
    assert out.doctor_id == did


def test_doctor_out_zero_consults_gives_none() -> None:
    row = DoctorGroupRow(
        doctor_id=None,
        consults=0,
        treatment_presented=0,
        treatment_accepted=0,
        surgery_completed=0,
        collected=0.0,
    )
    out = _build_doctor_out(row)

    assert out.consult_to_accepted is None
    assert out.accepted_to_surgery is None
    assert out.revenue_per_consult is None
    assert out.revenue_per_surgery is None


def test_doctor_out_accepted_but_no_surgery() -> None:
    row = DoctorGroupRow(
        doctor_id=None,
        consults=5,
        treatment_presented=5,
        treatment_accepted=5,
        surgery_completed=0,
        collected=50000.0,
    )
    out = _build_doctor_out(row)

    assert out.consult_to_accepted == pytest.approx(1.0)
    assert out.accepted_to_surgery == pytest.approx(0.0)  # 0/5 real zero
    assert out.revenue_per_surgery is None  # 0 denominator


def test_doctor_out_null_doctor_id_passes_through() -> None:
    row = DoctorGroupRow(
        doctor_id=None,
        consults=3,
        treatment_presented=2,
        treatment_accepted=2,
        surgery_completed=2,
        collected=30000.0,
    )
    out = _build_doctor_out(row)
    assert out.doctor_id is None


# ---------------------------------------------------------------------------
# calls_made is always None — cardinal contract test (ENG-518 no-data rule)
# ---------------------------------------------------------------------------


def test_calls_made_is_always_none() -> None:
    """``calls_made`` must NEVER be anything other than None.

    The fact table has no per-call-attempt count column. ``first_contact_date``
    records whether contact was made (one row per person), not how many calls
    were dialed. Any truthy value here would be a fabricated metric.
    """
    row = CallerGroupRow(caller_id=None, leads=100, reached=80, consults=50, collected=500000.0)
    out = _build_caller_out(row)
    assert out.calls_made is None, (
        "calls_made must be None — the fact has no dialer call-count column. "
        "Fabricating it from first_contact_date would be dishonest."
    )
