"""Unit tests for the de-identified template renderer (ENG-437, Block D).

The renderer is the compliance guardrail: in ``deidentified`` mode it
must NEVER emit a context value that is not on the allowlist. These tests
prove that names / phones / DOB / clinical text in the context can never
leak into a rendered chat message — they are replaced by ``[redacted]``.
"""

from __future__ import annotations

import uuid

import pytest

from packages.integrations.chat.event_service import build_deep_link
from packages.integrations.chat.render import REDACTED, render

# --- allowlisted variables render their value ---------------------------


def test_renders_core_allowlisted_vars() -> None:
    uid = uuid.uuid4()
    out = render(
        {"text": "New lead {{person_uid}} ({{event_type}}) — {{deep_link}}"},
        {
            "person_uid": str(uid),
            "event_type": "lead.created",
            "deep_link": f"https://app/persons/{uid}",
        },
    )
    assert str(uid) in out["text"]
    assert "lead.created" in out["text"]
    assert f"https://app/persons/{uid}" in out["text"]
    assert REDACTED not in out["text"]


def test_renders_safe_field_labels() -> None:
    out = render(
        {"text": "stage={{stage}} source={{source}} role={{owner_role}}"},
        {"stage": "qualified", "source": "web", "owner_role": "agent"},
    )
    assert out["text"] == "stage=qualified source=web role=agent"


# --- the core guardrail: PII in context never leaks ---------------------


def test_name_in_context_is_redacted() -> None:
    out = render(
        {"text": "Lead {{first_name}} {{last_name}} — {{person_uid}}"},
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "person_uid": "abc",
        },
    )
    assert "Jane" not in out["text"]
    assert "Doe" not in out["text"]
    assert out["text"] == f"Lead {REDACTED} {REDACTED} — abc"


def test_phone_in_context_never_emitted() -> None:
    out = render(
        {"text": "Call {{phone}} about lead {{person_uid}}"},
        {"phone": "+1-555-867-5309", "person_uid": "abc"},
    )
    assert "555" not in out["text"]
    assert "867" not in out["text"]
    assert out["text"] == f"Call {REDACTED} about lead abc"


def test_pii_redacted_in_nested_blocks() -> None:
    template = {
        "text": "header",
        "blocks": [
            {"type": "section", "text": "Patient {{first_name}} dob {{dob}}"},
        ],
    }
    out = render(
        template,
        {"first_name": "Jane", "dob": "1990-01-01", "person_uid": "abc"},
    )
    assert "Jane" not in str(out)
    assert "1990" not in str(out)
    assert out["blocks"][0]["text"] == f"Patient {REDACTED} dob {REDACTED}"


def test_template_is_not_mutated() -> None:
    template = {"text": "{{first_name}}"}
    render(template, {"first_name": "Jane"})
    assert template == {"text": "{{first_name}}"}


def test_allowlisted_but_absent_renders_redacted() -> None:
    out = render({"text": "stage={{stage}}"}, {})
    assert out["text"] == f"stage={REDACTED}"


def test_non_string_leaves_pass_through() -> None:
    out = render(
        {"text": "{{stage}}", "count": 3, "flag": True, "nothing": None},
        {"stage": "new"},
    )
    assert out["count"] == 3
    assert out["flag"] is True
    assert out["nothing"] is None


# --- full mode (ENG-460: messenger is an authorized PHI surface) --------


def test_full_mode_renders_any_var() -> None:
    out = render(
        {"text": "{{first_name}}"},
        {"first_name": "Jane"},
        phi_mode="full",
    )
    assert out["text"] == "Jane"


def test_full_mode_substitutes_name_and_phone() -> None:
    """ENG-460: full mode emits the real name + phone (NOT [redacted])."""
    out = render(
        {"text": "Lead {{name}} — {{phone}}"},
        {"name": "Angel Bryant", "phone": "19254918047"},
        phi_mode="full",
    )
    assert out["text"] == "Lead Angel Bryant — 19254918047"
    assert REDACTED not in out["text"]


def test_full_mode_substitutes_name_phone_in_attachment_blocks() -> None:
    """ENG-460: full mode flows into nested Mattermost attachment cards."""
    template = {
        "text": "🆕 New lead: {{name}}",
        "blocks": [
            {
                "title": "🆕 New lead",
                "text": "**{{name}}**",
                "fields": [
                    {"title": "Phone", "value": "{{phone}}", "short": True},
                    {"title": "Source", "value": "{{source}}", "short": True},
                ],
            }
        ],
    }
    out = render(
        template,
        {"name": "Angel Bryant", "phone": "19254918047", "source": "Facebook"},
        phi_mode="full",
    )
    block = out["blocks"][0]
    assert block["text"] == "**Angel Bryant**"
    assert block["fields"][0]["value"] == "19254918047"
    assert block["fields"][1]["value"] == "Facebook"
    assert REDACTED not in str(out)


def test_deidentified_still_redacts_name_and_phone() -> None:
    """ENG-460 must not weaken the de-identified fallback mode."""
    out = render(
        {"text": "Lead {{name}} — {{phone}}"},
        {"name": "Angel Bryant", "phone": "19254918047"},
        phi_mode="deidentified",
    )
    assert "Angel" not in out["text"]
    assert "9254918047" not in out["text"]
    assert out["text"] == f"Lead {REDACTED} — {REDACTED}"


def test_unknown_phi_mode_raises() -> None:
    with pytest.raises(ValueError, match="unknown phi_mode"):
        render({"text": "x"}, {}, phi_mode="bogus")


# --- ENG-465: empty attachment fields are pruned ------------------------


def test_empty_attachment_fields_are_pruned() -> None:
    """An attachment field whose value renders empty / [redacted] is dropped
    so the card carries no dangling label (e.g. ``Owner (TC): [redacted]``)."""
    template = {
        "text": "Consultation for {{name}}",
        "blocks": [
            {
                "title": "📅 Consultation scheduled",
                "text": "**{{name}}**",
                "fields": [
                    {"title": "Doctor", "value": "{{doctor}}", "short": True},
                    {"title": "Owner (TC)", "value": "{{owner}}", "short": True},
                    {"title": "Status", "value": "{{status}}", "short": True},
                ],
            }
        ],
    }
    out = render(
        template,
        {"name": "Ghausuddin Nezami", "doctor": "Olga Antipova", "status": "scheduled"},
        phi_mode="full",
    )
    fields = out["blocks"][0]["fields"]
    titles = [f["title"] for f in fields]
    # Owner had no value → pruned. Doctor + Status kept.
    assert titles == ["Doctor", "Status"]
    assert REDACTED not in str(out)


def test_blank_string_field_value_is_pruned() -> None:
    """A field that renders to an empty string (not just [redacted]) is also
    dropped — covers the case where the context value is an empty string."""
    template = {
        "blocks": [
            {
                "fields": [
                    {"title": "Phone", "value": "{{phone}}", "short": True},
                    {"title": "Doctor", "value": "{{doctor}}", "short": True},
                ]
            }
        ]
    }
    out = render(
        template, {"phone": "", "doctor": "Olga Antipova"}, phi_mode="full"
    )
    fields = out["blocks"][0]["fields"]
    assert [f["title"] for f in fields] == ["Doctor"]


def test_prune_keeps_text_fallback_untouched() -> None:
    """Pruning operates only on attachment ``fields`` — the top-level ``text``
    keeps its substituted rendering as a fallback (an absent var stays
    [redacted] there, never silently dropped)."""
    out = render(
        {"text": "Doctor: {{doctor}}", "blocks": []},
        {},
        phi_mode="full",
    )
    # ``text`` keeps the [redacted] substitution; only attachment fields prune.
    assert out["text"] == "Doctor: [redacted]"


# --- deep link builder ---------------------------------------------------


def test_build_deep_link_uses_web_app_base_url() -> None:
    uid = uuid.uuid4()
    link = build_deep_link(uid)
    assert link.endswith(f"/persons/{uid}")
    assert "//" in link  # has a scheme + host
