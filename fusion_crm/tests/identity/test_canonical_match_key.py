"""Unit tests for ``packages.identity.canonical`` match keys.

These functions are the heart of the phone-format duplicate fix: the same US
number stored digit-only / with a leading country code / in E.164 must produce
ONE match key so the resolver/sweep collapse it to one person regardless of
which source (e.g. CareStack vs Salesforce) wrote which format.

Numbers below are synthetic, drawn from the reserved ``555-01xx`` directory
range — valid US format, never assignable to a real person.
"""

from __future__ import annotations

import pytest

from packages.identity.canonical import (
    email_match_key,
    identifier_match_key,
    phone_match_key,
)

# One synthetic number in every storage format a provider has produced; the
# digit-only vs E.164 split is exactly the class of bug that defeated
# exact-string matching.
_US_FORMS = [
    "2015550123",
    "12015550123",
    "+12015550123",
    "(201) 555-0123",
    "201-555-0123",
    "+1 201 555 0123",
]


def test_all_us_phone_forms_share_one_match_key() -> None:
    keys = {phone_match_key(f) for f in _US_FORMS}
    assert keys == {"+12015550123"}


def test_phone_match_key_is_idempotent_on_e164() -> None:
    assert phone_match_key("+12015550123") == "+12015550123"
    assert phone_match_key(phone_match_key("2015550123")) == "+12015550123"


def test_distinct_numbers_get_distinct_keys() -> None:
    assert phone_match_key("2015550123") != phone_match_key("2015550124")


@pytest.mark.parametrize("junk", ["", None, "garbage", "123", "n/a"])
def test_phone_match_key_never_raises_on_junk(junk: str | None) -> None:
    # Must be total so a whole-table backfill never aborts on one bad row.
    result = phone_match_key(junk)  # type: ignore[arg-type]
    assert isinstance(result, str)


def test_email_match_key_lowercases_and_trims() -> None:
    assert email_match_key("  Foo@Bar.COM ") == "foo@bar.com"
    assert email_match_key(None) == ""


def test_identifier_match_key_dispatches_by_kind() -> None:
    assert identifier_match_key("phone", "2015550123") == "+12015550123"
    assert identifier_match_key("email", "A@B.com") == "a@b.com"
    # Opaque external ids are compared verbatim.
    assert identifier_match_key("carestack_patient_id", "9999001") == "9999001"
    assert identifier_match_key("salesforce_contact_id", "00Qxx") == "00Qxx"


def test_identifier_match_key_never_raises() -> None:
    assert identifier_match_key("phone", None) == ""
    assert identifier_match_key("email", None) == ""
    assert identifier_match_key("other", None) == ""
