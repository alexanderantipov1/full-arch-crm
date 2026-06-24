"""Render-engine tests for outreach templates (ENG-133).

The renderer is dependency-free with respect to the DB, so these are
pure unit tests against ``render_template`` /
``render_with_trace`` and ``PersonRenderContext``. Service-layer
tests (tenant isolation through the service entry points) live in
``test_template_service.py``.
"""

from __future__ import annotations

from datetime import date, datetime, time
from uuid import uuid4

import pytest

from packages.outreach.merge_fields import ALLOWED_MERGE_FIELDS, format_value
from packages.outreach.render import (
    PersonRenderContext,
    render_template,
    render_with_trace,
)
from packages.outreach.schemas import TemplateOut


def _make_template(
    *,
    subject: str = "Hi {{patient.first_name}}",
    body: str = "Hello {{patient.first_name}} — your status is {{lead.status}}.",
    body_format: str = "markdown",
    category: str = "marketing",
    tracking_enabled: bool = False,
) -> TemplateOut:
    now = datetime(2026, 5, 10, 12, 0, 0)
    return TemplateOut(
        id=uuid4(),
        tenant_id=uuid4(),
        name="t",
        description=None,
        subject_template=subject,
        body_template=body,
        body_format=body_format,  # type: ignore[arg-type]
        category=category,  # type: ignore[arg-type]
        tracking_enabled=tracking_enabled,
        intent_tags=[],
        version=1,
        status="active",
        created_by_actor_id=None,
        created_at=now,
        updated_at=now,
    )


# --- Markdown + Mustache happy path --------------------------------------


def test_render_markdown_substitutes_known_fields() -> None:
    template = _make_template()
    person = PersonRenderContext(
        patient_first_name="Alice",
        patient_last_name="Smith",
        patient_full_name="Alice Smith",
        lead_status="qualified",
    )
    rendered = render_template(template, person)
    assert rendered.subject == "Hi Alice"
    assert "Alice" in rendered.body_html
    assert "qualified" in rendered.body_html
    # Markdown-rendered: Mustache substitutions land verbatim, with a
    # paragraph wrapper from markdown-it.
    assert "<p>" in rendered.body_html
    assert rendered.body_text  # plaintext alternative is non-empty
    assert rendered.list_unsubscribe_header is not None


def test_render_markdown_renders_paragraph_break() -> None:
    template = _make_template(
        body=(
            "Hello {{patient.first_name}}.\n\n"
            "Your status is **{{lead.status}}**."
        ),
    )
    person = PersonRenderContext(
        patient_first_name="Bob",
        lead_status="contacted",
    )
    rendered = render_template(template, person)
    assert "<strong>contacted</strong>" in rendered.body_html


# --- Unknown merge field -------------------------------------------------


def test_render_unknown_field_renders_empty_and_traces() -> None:
    template = _make_template(
        subject="Hi {{patient.first_name}}",
        body="SSN: {{ssn}}; status: {{lead.status}}.",
    )
    person = PersonRenderContext(
        patient_first_name="Carol",
        lead_status="qualified",
    )
    rendered, trace = render_with_trace(template, person)
    assert "Carol" in rendered.subject
    # The unknown placeholder renders to empty rather than to the
    # literal Mustache token. Static operator copy such as "SSN:"
    # remains normal body text.
    assert "{{ssn}}" not in rendered.body_html
    assert "qualified" in rendered.body_html
    assert "ssn" in trace.unknown_fields


def test_render_warns_on_subject_unknown_field() -> None:
    template = _make_template(
        subject="Hi {{shadow_name}}",
        body="Body",
    )
    person = PersonRenderContext()
    rendered, trace = render_with_trace(template, person)
    # No known substitution remains — chevron strips the unknown
    # placeholder, leaving the static prefix.
    assert rendered.subject == "Hi"
    assert "shadow_name" in trace.unknown_fields


# --- HTML body_format is rejected ----------------------------------------


def test_render_html_body_format_raises_value_error() -> None:
    template = _make_template(body_format="html")
    with pytest.raises(ValueError) as excinfo:
        render_template(template, PersonRenderContext())
    assert "body_format='html'" in str(excinfo.value)


# --- Tenant isolation at the renderer is structural ---------------------
#
# The renderer never reads the DB; tenant isolation is enforced at the
# service layer (``TemplateService.render`` looks up the template by
# ``(tenant_id, template_id)`` first). We verify that here at the
# render-input level: rendering works with whatever ``TemplateOut`` you
# hand in, but the service refuses to fetch a template from the wrong
# tenant. The matching service-level test lives in
# ``test_template_service.py``.


def test_render_does_not_inspect_tenant_id() -> None:
    """Sanity: the renderer does not pin to a particular tenant.

    Two templates with different tenant_ids but identical bodies
    produce the same rendered output — the renderer is tenant-blind.
    Tenant isolation is the service's job.
    """
    t1 = _make_template()
    t2 = _make_template()
    # Different tenant_ids on the inputs.
    assert t1.tenant_id != t2.tenant_id
    person = PersonRenderContext(patient_first_name="Dave")
    r1 = render_template(t1, person)
    r2 = render_template(t2, person)
    assert r1.subject == r2.subject == "Hi Dave"


# --- MJML body format ----------------------------------------------------


def test_render_mjml_falls_back_to_inline_html_envelope() -> None:
    """MJML body wraps in either the MJML envelope or the inline-CSS fallback."""
    template = _make_template(
        body=("Hi {{patient.first_name}}!"),
        body_format="mjml",
    )
    person = PersonRenderContext(patient_first_name="Eve")
    rendered = render_template(template, person)
    assert "Eve" in rendered.body_html
    # Either path should produce HTML containing the rendered body.
    assert "<" in rendered.body_html and ">" in rendered.body_html


# --- Merge-field formatting ---------------------------------------------


def test_format_value_date_mmddyyyy() -> None:
    formatted = format_value("appointment.date", date(2026, 6, 1))
    assert formatted == "06/01/2026"


def test_format_value_time_h_mm_am_pm() -> None:
    formatted = format_value("appointment.time", time(14, 5))
    assert formatted == "2:05 PM"


def test_format_value_unknown_returns_empty() -> None:
    assert format_value("not.allowed", "anything") == ""


def test_format_value_none_returns_empty() -> None:
    assert format_value("patient.first_name", None) == ""


def test_allowlist_contains_expected_fields() -> None:
    assert "patient.first_name" in ALLOWED_MERGE_FIELDS
    assert "appointment.date" in ALLOWED_MERGE_FIELDS
    assert "tenant.name" in ALLOWED_MERGE_FIELDS
    assert "ssn" not in ALLOWED_MERGE_FIELDS  # negative
