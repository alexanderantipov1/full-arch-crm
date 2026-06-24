"""Unit tests for the implant case_type taxonomy + resolver (ENG-539, B1.5).

Pure (no DB): exercises the CDT → case_type mapping and the per-person
precedence resolver, including the unclassified / non-implant outcomes and the
documented precedence ordering
(all_on_x > overdenture > implant_bridge > multiple_implants > single_implant).
"""

from __future__ import annotations

import pytest

from packages.analytics.case_type import (
    ALL_CASE_TYPES,
    MANUAL_ONLY_CASE_TYPES,
    classify_cdt,
    resolve_case_type,
)

# --- per-CDT mapping --------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("D6010", "placement"),
        # ENG-539 operator decision 2026-06-20: all surgical-placement variants
        # count as placements (aligned with the ENG-511 implant-surgery set).
        ("D6012", "placement"),
        ("D6013", "placement"),
        ("D6040", "placement"),
        ("D6050", "placement"),
        ("D6010.A", "all_on_x"),
        ("D6114", "all_on_x"),
        ("D6115", "all_on_x"),
        ("D6118", "all_on_x"),
        ("D6053", "overdenture"),
        ("D6054", "overdenture"),
        ("D6065", "implant_bridge"),
        ("D6066", "implant_bridge"),
        ("D6068", "implant_bridge"),
        ("D6075", "implant_bridge"),
        ("D6011", "implant_other"),
        ("D6011NC", "implant_other"),
        ("D6058", "implant_other"),
        # non-implant / unknown CDT → not classified.
        ("D0120", None),
        ("", None),
    ],
)
def test_classify_cdt(code: str, expected: str | None) -> None:
    assert classify_cdt(code) == expected


def test_classify_cdt_normalises_case_and_whitespace() -> None:
    assert classify_cdt(" d6010 ") == "placement"
    assert classify_cdt("d6010.a") == "all_on_x"


# --- per-person resolution + precedence -------------------------------------


def test_single_implant_exactly_one_placement() -> None:
    res = resolve_case_type(["D6010"])
    assert res.case_type == "single_implant"
    assert res.has_implant is True


def test_multiple_implants_two_or_more_placements() -> None:
    res = resolve_case_type(["D6010", "D6010"])
    assert res.case_type == "multiple_implants"
    assert res.has_implant is True


def test_placement_variants_count_as_placement() -> None:
    # Operator decision 2026-06-20: mini/interim/eposteal/transosteal placements
    # count like D6010, so a single one → single_implant and two → multiple.
    assert resolve_case_type(["D6040"]).case_type == "single_implant"
    assert resolve_case_type(["D6010", "D6013"]).case_type == "multiple_implants"
    assert resolve_case_type(["D6012", "D6050"]).case_type == "multiple_implants"


def test_second_stage_is_not_a_placement() -> None:
    # D6011 / D6011NC (uncovery) are NOT new placements → unclassified (review).
    res = resolve_case_type(["D6011", "D6011NC"])
    assert res.case_type is None
    assert res.has_implant is True


def test_all_on_x_from_custom_code() -> None:
    assert resolve_case_type(["D6010.A"]).case_type == "all_on_x"


def test_all_on_x_from_full_arch_denture() -> None:
    assert resolve_case_type(["D6114"]).case_type == "all_on_x"


def test_overdenture() -> None:
    assert resolve_case_type(["D6053"]).case_type == "overdenture"


def test_implant_bridge() -> None:
    assert resolve_case_type(["D6065"]).case_type == "implant_bridge"


def test_precedence_all_on_x_beats_single_overdenture_bridge_multiple() -> None:
    # A footprint touching every signal must resolve to all_on_x (highest).
    codes = ["D6010", "D6010", "D6053", "D6065", "D6114"]
    assert resolve_case_type(codes).case_type == "all_on_x"


def test_precedence_overdenture_beats_bridge_and_placement() -> None:
    assert resolve_case_type(["D6010", "D6053", "D6065"]).case_type == "overdenture"


def test_precedence_bridge_beats_placement() -> None:
    assert resolve_case_type(["D6010", "D6065"]).case_type == "implant_bridge"


def test_precedence_multiple_beats_single() -> None:
    # Two placements + nothing higher → multiple_implants (not single).
    assert resolve_case_type(["D6010", "D6010"]).case_type == "multiple_implants"


def test_unclassified_when_only_non_determinative_implant_codes() -> None:
    # Abutment / second-stage only: implant-present but no clean case → review.
    res = resolve_case_type(["D6058", "D6011"])
    assert res.case_type is None
    assert res.has_implant is True


def test_not_an_implant_patient() -> None:
    res = resolve_case_type(["D0120", "D2740"])
    assert res.case_type is None
    assert res.has_implant is False


def test_empty_input() -> None:
    res = resolve_case_type([])
    assert res.case_type is None
    assert res.has_implant is False


# --- allowed-value sets -----------------------------------------------------


def test_auto_values_are_subset_of_all_case_types() -> None:
    auto = {
        "single_implant",
        "multiple_implants",
        "all_on_x",
        "overdenture",
        "implant_bridge",
    }
    assert auto <= ALL_CASE_TYPES
    assert MANUAL_ONLY_CASE_TYPES <= ALL_CASE_TYPES
    # Manual-only labels are never auto-derivable.
    assert auto.isdisjoint(MANUAL_ONLY_CASE_TYPES)


def test_resolver_never_emits_manual_only_value() -> None:
    # No CDT combination can yield a manual-only label.
    for codes in (["D6010.A"], ["D6114", "D6115"], ["D6010", "D6053"]):
        assert resolve_case_type(codes).case_type not in MANUAL_ONLY_CASE_TYPES
