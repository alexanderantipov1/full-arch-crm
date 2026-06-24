"""Merge-field allowlist for outreach templates.

Templates may reference ONLY the keys listed below. The render engine
walks every ``{{...}}`` placeholder; unknown names render as the empty
string and produce a ``outreach.template.merge_field_unknown`` audit
warning so operators can see which placeholders are stripped.

The allowlist is intentionally small: every field listed here must be
something the operator can legally surface in marketing /
transactional copy. Nothing clinical lands here. If a future template
needs a richer field, add it here AND to the build path in
``render.PersonRenderContext.build`` — never widen at the renderer
level alone.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Final

# Logical types accepted in the allowlist. The render engine inspects
# the value's type at call time and formats accordingly.
#
# * ``str``      — substituted verbatim, escaped for HTML when applicable
# * ``"date"``   — ``date | datetime`` formatted as ``MM/DD/YYYY``
# * ``"time"``   — ``time | datetime`` formatted as ``h:mm AM/PM``
ALLOWED_MERGE_FIELDS: Final[dict[str, Any]] = {
    "patient.first_name": str,
    "patient.last_name": str,
    "patient.full_name": str,
    "lead.status": str,
    "lead.source": str,
    "appointment.date": "date",
    "appointment.time": "time",
    "appointment.location_name": str,
    "location.name": str,
    "location.address": str,
    "location.phone": str,
    "tenant.name": str,
}


def is_allowed(field_name: str) -> bool:
    """Return True if ``field_name`` (e.g. ``patient.first_name``) is allowed."""
    return field_name in ALLOWED_MERGE_FIELDS


def format_value(field_name: str, value: object) -> str:
    """Format an allowlist value as the canonical string for substitution.

    Returns the empty string when ``value`` is ``None`` or the field name
    is unknown — the caller decides whether to log a warning.
    """
    if value is None:
        return ""
    spec = ALLOWED_MERGE_FIELDS.get(field_name)
    if spec is None:
        return ""

    if spec == "date":
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            return value.strftime("%m/%d/%Y")
        return ""

    if spec == "time":
        if isinstance(value, datetime):
            value = value.time()
        if isinstance(value, time):
            # %I gives the hour zero-padded; strip the leading zero so we
            # produce ``h:mm AM/PM`` per the field documentation.
            formatted = value.strftime("%I:%M %p").lstrip("0")
            return formatted
        return ""

    # Default: stringify. We do not coerce arbitrary objects — only plain
    # strings flow through. Anything else returns empty so a misconfigured
    # context cannot smuggle an object repr into operator-visible copy.
    if isinstance(value, str):
        return value
    return ""
