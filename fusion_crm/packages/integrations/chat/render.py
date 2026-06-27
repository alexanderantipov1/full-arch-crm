"""De-identified template renderer for notifications (ENG-437, Block D).

This module is the compliance guardrail of the messenger layer. A
:class:`packages.integrations.models.NotificationRule` carries a JSONB
``template`` whose string values contain ``{{var}}`` placeholders.
:func:`render` substitutes those placeholders from an event ``context``
— but in the default ``deidentified`` mode it will ONLY emit variables
that are on an explicit allowlist of opaque identifiers and non-PII
labels/codes.

Why an allowlist and not a denylist: a denylist fails open (a new PII
field nobody blocked leaks into a chat workspace). An allowlist fails
closed — an un-listed variable renders as the literal ``[redacted]`` and
a structured warning is logged (the warning carries only the variable
name, never the value). So a name / phone / DOB sitting in ``context``
can never reach a corporate chat channel through a deidentified template.

``phi_mode="full"`` substitutes any context var verbatim (the allowlist
is bypassed). ENG-460 turned this ON by default: the messenger is an
AUTHORIZED PHI surface (only staff with PHI access read the Mattermost
team), so notification cards carry the patient's real name / phone /
provider to be useful to staff. The call site
(:meth:`NotificationEventService.emit`) selects the mode from
``Settings.messenger_phi_full`` (default True); flipping the flag off
restores the de-identified allowlist behaviour. SECURITY: with full mode
on, PHI lands in the Mattermost store, so the Mattermost server must be
treated as a PHI system (access control / TLS / backup / retention).
"""

from __future__ import annotations

import re
from typing import Any

from packages.core.logging import get_logger

log = get_logger("integrations.notification.render")

# Opaque identifiers + the event type. Always safe — these are UUIDs /
# URLs / machine codes, never human-readable PII.
_CORE_ALLOWED: frozenset[str] = frozenset(
    {
        "person_uid",  # opaque global UUID
        "deep_link",  # internal staff URL keyed by person_uid
        "event_type",  # machine event code, e.g. "lead.created"
    }
)

# Non-PII labels / codes. These are enums, statuses, sources, and roles —
# categorical values, NOT free text and NOT identifying. Extend this set
# deliberately; anything that could carry a name, phone, email, DOB, or
# clinical text MUST NOT be added.
_SAFE_FIELD_ALLOWED: frozenset[str] = frozenset(
    {
        "stage",  # opportunity stage label
        "source",  # lead source label
        "lead_status",  # lead status enum
        "owner_role",  # role of the owning actor (e.g. "agent", "tc")
        "owner_id",  # opaque actor/owner UUID (not a name)
        "provider",  # provider code, e.g. "salesforce"
        "object",  # provider object name, e.g. "Lead"
        "sync_status",  # sync run status, e.g. "failed"
        # ENG-457 consultation card — all categorical / machine values, no
        # patient name and no clinical free-text.
        "status",  # consultation status enum, e.g. "scheduled"
        "consultation_kind",  # consultation kind enum, e.g. "initial"
        "scheduled_at",  # consultation scheduled instant (ISO-8601 timestamp)
        # ENG-465 consultation card — categorical / non-identifying values.
        # The readable scheduled time and visit duration carry no patient
        # identity, so they are safe even in de-identified mode. The doctor /
        # clinic / owner / phone are NOT listed here — they are names/PII and
        # render [redacted] (then prune) when the PHI flag is off.
        "scheduled_when",  # human-readable scheduled time, e.g. "Jun 20, 2026 3:00 PM UTC"
        "duration",  # visit duration label, e.g. "60 min"
    }
)

# The full deidentified allowlist.
DEIDENTIFIED_ALLOWLIST: frozenset[str] = _CORE_ALLOWED | _SAFE_FIELD_ALLOWED

REDACTED = "[redacted]"

_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _stringify(value: Any) -> str:
    """Render a single resolved value to text (booleans/ints/UUIDs ok)."""
    return str(value)


def _substitute_text(
    text: str,
    context: dict[str, Any],
    *,
    phi_mode: str,
    event_type: str | None,
) -> str:
    def _replace(match: re.Match[str]) -> str:
        var = match.group(1)
        if phi_mode == "deidentified" and var not in DEIDENTIFIED_ALLOWLIST:
            # Fail closed: never emit the value, log the variable name only.
            log.warning(
                "notification.render.redacted_variable",
                variable=var,
                event_type=event_type,
                phi_mode=phi_mode,
            )
            return REDACTED
        if var not in context or context[var] is None:
            # Allowlisted but absent from context → also redacted (no leak,
            # and no raw "{{var}}" left dangling in the message).
            return REDACTED
        return _stringify(context[var])

    return _PLACEHOLDER.sub(_replace, text)


def _is_empty_field_value(value: Any) -> bool:
    """True when a rendered attachment-field value carries no real content.

    A Mattermost attachment ``field`` whose ``value`` rendered to an empty
    string or to the literal :data:`REDACTED` (an allowlisted-but-absent or
    blocked variable) is noise — the title with no value reads as a dangling
    label (e.g. ``Owner (TC): [redacted]``). ENG-465 drops such fields so the
    card stays clean when an optional value (doctor / clinic / owner / phone)
    is missing.
    """
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    return stripped == "" or stripped == REDACTED


def _prune_attachment_fields(node: Any) -> Any:
    """Recursively drop attachment ``fields`` entries with an empty value.

    Walks the rendered tree and, for any dict carrying a ``fields`` list
    (the Mattermost attachment shape), removes field entries whose ``value``
    is empty / :data:`REDACTED`. Other nodes pass through untouched. Operates
    on the already-rendered structure so it sees substituted values.
    """
    if isinstance(node, dict):
        pruned: dict[str, Any] = {}
        for key, value in node.items():
            if key == "fields" and isinstance(value, list):
                pruned[key] = [
                    field
                    for field in value
                    if not (
                        isinstance(field, dict)
                        and _is_empty_field_value(field.get("value"))
                    )
                ]
            else:
                pruned[key] = _prune_attachment_fields(value)
        return pruned
    if isinstance(node, list):
        return [_prune_attachment_fields(item) for item in node]
    return node


def render(
    template: dict[str, Any],
    context: dict[str, Any],
    *,
    phi_mode: str = "deidentified",
) -> dict[str, Any]:
    """Render a notification ``template`` against an event ``context``.

    String leaves anywhere in the template (top-level values and strings
    nested in lists/dicts, e.g. Mattermost attachment blocks) have their
    ``{{var}}`` placeholders substituted. In ``deidentified`` mode
    (default) only :data:`DEIDENTIFIED_ALLOWLIST` variables render their
    value; everything else becomes :data:`REDACTED`. ``phi_mode="full"``
    substitutes any context var (reserved; unused today).

    Non-string leaves (ints, bools, None) are passed through untouched —
    they carry no placeholders. The returned dict is a deep copy; the
    input template is never mutated.

    ENG-465: after substitution, Mattermost attachment ``fields`` whose
    rendered ``value`` is empty or :data:`REDACTED` are pruned so an absent
    optional value (doctor / clinic / owner / phone) does not leave a
    dangling label on the card. Top-level ``text`` and other strings are
    untouched — they keep their fallback rendering.

    Raises:
        ValueError: if ``phi_mode`` is not ``"deidentified"`` or
            ``"full"``.
    """
    if phi_mode not in ("deidentified", "full"):
        raise ValueError(
            f"unknown phi_mode {phi_mode!r}; expected 'deidentified' or 'full'"
        )

    event_type = context.get("event_type")
    if not isinstance(event_type, str):
        event_type = None

    def _walk(node: Any) -> Any:
        if isinstance(node, str):
            return _substitute_text(
                node, context, phi_mode=phi_mode, event_type=event_type
            )
        if isinstance(node, dict):
            return {k: _walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [_walk(v) for v in node]
        return node

    rendered = _walk(template)
    rendered = _prune_attachment_fields(rendered)
    # ``_walk`` over a dict always returns a dict.
    return rendered  # type: ignore[no-any-return]


__all__ = [
    "DEIDENTIFIED_ALLOWLIST",
    "REDACTED",
    "render",
]
