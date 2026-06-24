"""Service-layer match policy must score on canonical keys (ENG-562).

The repository surfacing a cross-format phone candidate is necessary but not
sufficient: ``_evaluate_match_policy`` / ``_evaluate_pair_for_sweep`` must also
treat a digit-only stored phone as equal to an E.164 hint, or the auto-accept is
dropped and a duplicate/ambiguous person is created. Numbers are synthetic
(reserved ``555-01xx`` range).
"""

from __future__ import annotations

from packages.identity.models import Person, PersonIdentifier
from packages.identity.schemas import MatchHintIn
from packages.identity.service import (
    _AutoAccept,
    _evaluate_match_policy,
    _evaluate_pair_for_sweep,
)


def _person_with_phone(phone: str) -> Person:
    person = Person(given_name="Alex", family_name="Tester", display_name="Alex Tester")
    person.identifiers = [PersonIdentifier(kind="phone", value=phone)]
    return person


def _hint_with_phone(phone: str) -> MatchHintIn:
    return MatchHintIn(
        source_system="salesforce",
        source_kind="lead",
        source_id="LEAD-1",
        given_name="Alex",
        family_name="Tester",
        display_name="Alex Tester",
        email_normalized=None,
        phone_normalized=phone,
    )


def test_policy_auto_accepts_across_phone_formats() -> None:
    # Candidate stored digit-only; incoming hint is E.164 — same number.
    candidate = _person_with_phone("2015550123")
    hint = _hint_with_phone("+12015550123")

    decision = _evaluate_match_policy(hint, [candidate])

    assert isinstance(decision, _AutoAccept)
    assert decision.match_rule == "phone_name"


def test_sweep_auto_accepts_across_phone_formats() -> None:
    a = _person_with_phone("2015550123")
    b = _person_with_phone("+12015550123")

    decision = _evaluate_pair_for_sweep(a, b)

    assert decision.kind == "auto_accept"
    assert decision.match_rule == "phone_name"
