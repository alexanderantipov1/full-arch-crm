"""Condition predicate engine for notification rules (ENG-437, Block D).

A :class:`packages.integrations.models.NotificationRule` carries a JSONB
``conditions`` list. Each predicate is a dict
``{"field": str, "op": str, "value": ...}``. :func:`evaluate` resolves
each predicate against an event ``context`` dict and ANDs the results;
an empty list always matches.

``field`` is a dotted path into ``context`` (e.g. ``"lead.Phone"``
descends into ``context["lead"]["Phone"]``). A path that cannot be
resolved yields ``None`` for the operand — the same value a present-but-
null field would yield — so ``is_empty`` / ``is_present`` behave
intuitively for both.

This is a pure function with no I/O: the rule engine is unit-testable in
isolation and never touches the DB.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

# Sentinel distinct from a literal ``None`` value in the context so we can
# tell "path missing" apart from "path present but null" if we ever need
# to. Today both collapse to "empty" semantics, but keeping the
# distinction internal avoids a future refactor.
_MISSING = object()

# Operators that compare the resolved field against a single ``value``.
_BINARY_OPS = frozenset({"eq", "neq", "in", "not_in", "contains"})
# Operators that ignore ``value`` and only inspect presence/emptiness.
_UNARY_OPS = frozenset({"is_empty", "is_present"})
SUPPORTED_OPS = _BINARY_OPS | _UNARY_OPS


def _resolve(field: str, context: dict[str, Any]) -> Any:
    """Walk a dotted ``field`` path into ``context``; ``_MISSING`` if absent."""
    current: Any = context
    for part in field.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return _MISSING
    return current


def _is_empty(value: Any) -> bool:
    """True for a missing path, ``None``, or an empty string/collection."""
    if value is _MISSING or value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _evaluate_one(predicate: dict[str, Any], context: dict[str, Any]) -> bool:
    field = predicate.get("field")
    op = predicate.get("op")
    if not isinstance(field, str) or not field:
        raise ValueError(f"condition predicate missing a string 'field': {predicate!r}")
    if not isinstance(op, str) or op not in SUPPORTED_OPS:
        raise ValueError(
            f"unknown condition op {op!r}; supported: {sorted(SUPPORTED_OPS)}"
        )

    operand = _resolve(field, context)
    expected = predicate.get("value")

    if op == "is_empty":
        return _is_empty(operand)
    if op == "is_present":
        return not _is_empty(operand)

    # Binary ops treat a missing path as ``None`` so comparisons are total.
    actual = None if operand is _MISSING else operand

    if op == "eq":
        return actual == expected
    if op == "neq":
        return actual != expected
    if op == "in":
        if not isinstance(expected, Sequence) or isinstance(expected, (str, bytes)):
            raise ValueError(f"'in' value must be a list, got {type(expected).__name__}")
        return actual in expected
    if op == "not_in":
        if not isinstance(expected, Sequence) or isinstance(expected, (str, bytes)):
            raise ValueError(
                f"'not_in' value must be a list, got {type(expected).__name__}"
            )
        return actual not in expected
    if op == "contains":
        # Substring (str) or membership (collection) of ``expected`` within
        # the resolved field.
        if actual is None:
            return False
        if isinstance(actual, str):
            return str(expected) in actual
        if isinstance(actual, (list, tuple, set, dict)):
            return expected in actual
        return False

    # Unreachable: op was validated against SUPPORTED_OPS above.
    raise ValueError(f"unhandled condition op {op!r}")  # pragma: no cover


def evaluate(conditions: list[dict[str, Any]], context: dict[str, Any]) -> bool:
    """Return ``True`` iff every predicate in ``conditions`` matches.

    Empty ``conditions`` → always ``True`` (unconditional rule). List
    semantics are AND. Raises :class:`ValueError` on a malformed
    predicate or unknown operator — a misconfigured rule must fail loudly
    rather than silently never (or always) firing.
    """
    for predicate in conditions:
        if not isinstance(predicate, dict):
            raise ValueError(f"condition predicate must be a dict, got {predicate!r}")
        if not _evaluate_one(predicate, context):
            return False
    return True


__all__ = ["SUPPORTED_OPS", "evaluate"]
