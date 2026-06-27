"""Pure identifier canonicalisation — no DB, no service/repository deps.

This module is imported by BOTH ``packages.identity.service`` (write path,
normalisation) and ``packages.identity.repository`` (read path, match-key
comparison). It must stay dependency-free of those modules to avoid an import
cycle: it depends only on stdlib, ``phonenumbers`` and ``packages.core``.

Two distinct concepts live here:

* **Normalisation** (``normalise_phone`` / ``normalise_email``) — the canonical
  value we STORE in ``identity.person_identifier.value``. Phones become E.164
  for valid numbers (ENG-463); emails become lower-cased. These may RAISE
  ``ValidationError`` so ingest surfaces bad input.

* **Match keys** (``phone_match_key`` / ``email_match_key`` /
  ``identifier_match_key``) — the canonical form we COMPARE on. Same canonical
  output as normalisation, but TOTAL (never raises) so a backfill over the whole
  table and the write-path population can run row-by-row without aborting on one
  malformed legacy value. The match key is what makes a phone stored as
  ``2015550123`` match an incoming ``+12015550123`` (ENG-562, the phone-format
  duplicate fix): both map to ``+12015550123``.
"""

from __future__ import annotations

import re

import phonenumbers

from packages.core.exceptions import ValidationError

_PHONE_DIGITS = re.compile(r"\D+")


def normalise_phone(phone: str, *, region: str = "US") -> str:
    """Canonicalize a phone number to E.164 (e.g. ``+19258125438``).

    Uses libphonenumber (``phonenumbers``) so identity/actor match keys
    always align for the same number AND the stored value is directly
    Twilio-dialable (ENG-463). ``region`` is the assumed country for
    numbers without an explicit ``+`` country code (default US).

    Only genuinely **valid** numbers become E.164 — fictional 555-area,
    all-zeros, and too-short inputs are NOT promoted to a confident
    ``+1…`` (they would be undialable by Twilio and a misleading match
    key). Unparseable / not-valid input falls back to a digit-strip
    (>= 7 digits) so ingestion never hard-fails; that path is
    intentionally NOT E.164 and dial-time must re-validate.
    """
    raw = (phone or "").strip()
    # Common IDD '00' prefix → '+' so e.g. '0044 7911 123456' parses as
    # international rather than a malformed US number.
    candidate = "+" + raw[2:] if raw.startswith("00") else raw
    try:
        parsed = phonenumbers.parse(candidate, region)
    except phonenumbers.NumberParseException:
        parsed = None
    if parsed is not None and phonenumbers.is_valid_number(parsed):
        return phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.E164
        )
    digits = _PHONE_DIGITS.sub("", raw)
    if len(digits) < 7:
        raise ValidationError("phone must contain at least 7 digits")
    return digits


def normalise_email(email: str) -> str:
    email = email.strip().lower()
    if "@" not in email or len(email) > 320:
        raise ValidationError("invalid email")
    return email


def phone_match_key(value: str | None) -> str:
    """Return the canonical match key for a phone value. Never raises.

    Mirrors :func:`normalise_phone` (so a valid number → its E.164 form, the
    same key regardless of whether the stored value was ``2015550123``,
    ``12015550123`` or ``+12015550123``) but degrades gracefully on input that
    ``normalise_phone`` would reject (< 7 digits): it returns the bare digit
    strip instead of raising, so a whole-table backfill never aborts on one
    junk row. Empty / digit-less input yields ``""``.
    """
    try:
        return normalise_phone(value or "")
    except ValidationError:
        return _PHONE_DIGITS.sub("", value or "")


def email_match_key(value: str | None) -> str:
    """Return the canonical match key for an email value. Never raises."""
    return (value or "").strip().lower()


def identifier_match_key(kind: str, value: str | None) -> str:
    """Return the canonical match key for an identifier of ``kind``.

    ``phone`` → E.164-style key; ``email`` → lower-cased; every other kind
    (``carestack_patient_id``, ``salesforce_contact_id``, …) is already an
    opaque external id and is compared verbatim. Total — never raises.
    """
    if kind == "phone":
        return phone_match_key(value)
    if kind == "email":
        return email_match_key(value)
    return value or ""
