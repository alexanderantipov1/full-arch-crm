"""Unit tests for the condition predicate engine (ENG-437, Block D).

Pure functions — no DB, no fixtures. Covers every operator, dotted-path
resolution, AND semantics, the empty-list (always-match) case, and the
unknown-op ValueError.
"""

from __future__ import annotations

import pytest

from packages.integrations.chat.conditions import SUPPORTED_OPS, evaluate

# --- empty list always matches ------------------------------------------


def test_empty_conditions_always_match() -> None:
    assert evaluate([], {}) is True
    assert evaluate([], {"anything": 1}) is True


# --- is_empty / is_present ----------------------------------------------


@pytest.mark.parametrize(
    "value,expected_empty",
    [
        (None, True),
        ("", True),
        ("   ", True),
        ([], True),
        ({}, True),
        ("x", False),
        (["a"], False),
        (0, False),  # zero is present, not empty
        (False, False),  # False is present, not empty
    ],
)
def test_is_empty_and_is_present(value: object, expected_empty: bool) -> None:
    ctx = {"f": value}
    assert evaluate([{"field": "f", "op": "is_empty"}], ctx) is expected_empty
    assert evaluate([{"field": "f", "op": "is_present"}], ctx) is (not expected_empty)


def test_missing_path_is_empty() -> None:
    assert evaluate([{"field": "nope", "op": "is_empty"}], {}) is True
    assert evaluate([{"field": "a.b.c", "op": "is_present"}], {"a": {}}) is False


# --- eq / neq ------------------------------------------------------------


def test_eq_neq() -> None:
    ctx = {"status": "new"}
    assert evaluate([{"field": "status", "op": "eq", "value": "new"}], ctx) is True
    assert evaluate([{"field": "status", "op": "eq", "value": "lost"}], ctx) is False
    assert evaluate([{"field": "status", "op": "neq", "value": "lost"}], ctx) is True
    assert evaluate([{"field": "status", "op": "neq", "value": "new"}], ctx) is False


# --- in / not_in ---------------------------------------------------------


def test_in_not_in() -> None:
    ctx = {"stage": "qualified"}
    assert (
        evaluate(
            [{"field": "stage", "op": "in", "value": ["new", "qualified"]}], ctx
        )
        is True
    )
    assert (
        evaluate([{"field": "stage", "op": "in", "value": ["lost"]}], ctx) is False
    )
    assert (
        evaluate([{"field": "stage", "op": "not_in", "value": ["lost"]}], ctx) is True
    )


def test_in_requires_list_value() -> None:
    with pytest.raises(ValueError, match="'in' value must be a list"):
        evaluate([{"field": "s", "op": "in", "value": "notalist"}], {"s": "x"})


# --- contains ------------------------------------------------------------


def test_contains_substring() -> None:
    ctx = {"label": "implant consult"}
    assert evaluate([{"field": "label", "op": "contains", "value": "implant"}], ctx)
    assert not evaluate([{"field": "label", "op": "contains", "value": "crown"}], ctx)


def test_contains_collection_membership() -> None:
    ctx = {"tags": ["a", "b"]}
    assert evaluate([{"field": "tags", "op": "contains", "value": "a"}], ctx)
    assert not evaluate([{"field": "tags", "op": "contains", "value": "z"}], ctx)


# --- dotted paths --------------------------------------------------------


def test_dotted_path_resolution() -> None:
    ctx = {"lead": {"Phone": "", "Status": "new"}}
    assert evaluate([{"field": "lead.Phone", "op": "is_empty"}], ctx) is True
    assert evaluate([{"field": "lead.Status", "op": "eq", "value": "new"}], ctx) is True


# --- AND semantics -------------------------------------------------------


def test_and_semantics_all_must_match() -> None:
    ctx = {"lead": {"Phone": "", "Status": "new"}}
    both = [
        {"field": "lead.Phone", "op": "is_empty"},
        {"field": "lead.Status", "op": "eq", "value": "new"},
    ]
    assert evaluate(both, ctx) is True
    one_fails = [
        {"field": "lead.Phone", "op": "is_empty"},
        {"field": "lead.Status", "op": "eq", "value": "lost"},
    ]
    assert evaluate(one_fails, ctx) is False


# --- error handling ------------------------------------------------------


def test_unknown_op_raises() -> None:
    with pytest.raises(ValueError, match="unknown condition op"):
        evaluate([{"field": "f", "op": "startswith", "value": "x"}], {"f": "xyz"})


def test_missing_field_raises() -> None:
    with pytest.raises(ValueError, match="missing a string 'field'"):
        evaluate([{"op": "is_empty"}], {})


def test_non_dict_predicate_raises() -> None:
    with pytest.raises(ValueError, match="must be a dict"):
        evaluate(["not-a-dict"], {})  # type: ignore[list-item]


def test_supported_ops_roster() -> None:
    assert SUPPORTED_OPS == {
        "is_empty",
        "is_present",
        "eq",
        "neq",
        "in",
        "not_in",
        "contains",
    }
