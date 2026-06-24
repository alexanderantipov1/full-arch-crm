"""Outreach template render engine.

Per ADR-0004 decision #2, templates are Mustache strings rendered
against a typed ``PersonRenderContext``. The renderer walks every
``{{...}}`` placeholder; if the name is NOT in ``ALLOWED_MERGE_FIELDS``
the placeholder renders empty AND a warning is appended to
``RenderTrace.unknown_fields`` so the service layer can audit it.

Body formats:

- ``markdown`` — Mustache → Markdown → HTML (with raw-HTML stripping)
- ``mjml``     — Mustache → MJML envelope → HTML (best-effort; falls
  back to inline-CSS HTML when ``mjml-python`` is unavailable)
- ``html``     — REJECTED at the service layer in Stage 1; the
  renderer raises ``ValueError`` defensively if it ever sees one.

The render engine itself is dependency-free with respect to the DB —
callers pass the resolved ``PersonRenderContext`` (built by the
service from ``IdentityService`` + ``OpsService`` reads). This keeps
the renderer unit-testable and predictable.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any

import chevron
from markdown_it import MarkdownIt

from packages.core.logging import get_logger

from ._mjml_blocks import (
    DEFAULT_ENVELOPE,
    FALLBACK_HTML_ENVELOPE,
    UNSUBSCRIBE_PLACEHOLDER,
)
from .merge_fields import ALLOWED_MERGE_FIELDS, format_value, is_allowed
from .schemas import RenderedEmail, TemplateOut

log = get_logger("outreach.render")

# Try to import mjml-python lazily; absence is allowed in Stage 1 dev
# environments and the service layer gates the body_format=mjml path
# accordingly. We keep the import optional so test environments don't
# need to ship the native MJML toolchain.
try:  # pragma: no cover — import guard, exercised by environment
    import mjml as _mjml  # type: ignore[import-not-found]

    _HAS_MJML: bool = True
except Exception:  # noqa: BLE001 — broad import guard is intentional here
    _mjml = None
    _HAS_MJML = False


_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z_][\w.]*)\s*\}\}")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


# --- Render context -------------------------------------------------------


@dataclass
class PersonRenderContext:
    """Tightly-scoped substitution context for one render.

    Built by ``TemplateService.render`` from ``IdentityService`` +
    ``OpsService`` reads. The renderer is forbidden from touching
    anything outside this dataclass — every placeholder substitution
    flows through ``ALLOWED_MERGE_FIELDS``.

    Each attribute corresponds to a section of the allowlist; missing
    values render as the empty string.
    """

    patient_first_name: str | None = None
    patient_last_name: str | None = None
    patient_full_name: str | None = None
    lead_status: str | None = None
    lead_source: str | None = None
    appointment_date: date | datetime | None = None
    appointment_time: time | datetime | None = None
    appointment_location_name: str | None = None
    location_name: str | None = None
    location_address: str | None = None
    location_phone: str | None = None
    tenant_name: str | None = None

    def to_chevron_data(self) -> dict[str, Any]:
        """Project the context into the dotted-key dict chevron expects.

        Chevron does not natively understand ``{{patient.first_name}}``
        as a flat key — it expects nested dicts. We pre-build the
        nested structure here so the operator-friendly placeholder
        syntax works without changing the engine.
        """
        return {
            "patient": {
                "first_name": format_value(
                    "patient.first_name", self.patient_first_name
                ),
                "last_name": format_value(
                    "patient.last_name", self.patient_last_name
                ),
                "full_name": format_value(
                    "patient.full_name", self.patient_full_name
                ),
            },
            "lead": {
                "status": format_value("lead.status", self.lead_status),
                "source": format_value("lead.source", self.lead_source),
            },
            "appointment": {
                "date": format_value("appointment.date", self.appointment_date),
                "time": format_value("appointment.time", self.appointment_time),
                "location_name": format_value(
                    "appointment.location_name", self.appointment_location_name
                ),
            },
            "location": {
                "name": format_value("location.name", self.location_name),
                "address": format_value(
                    "location.address", self.location_address
                ),
                "phone": format_value("location.phone", self.location_phone),
            },
            "tenant": {
                "name": format_value("tenant.name", self.tenant_name),
            },
        }


# --- Trace ---------------------------------------------------------------


@dataclass
class RenderTrace:
    """Side-channel diagnostics from a render call.

    Used by ``TemplateService.render`` to write
    ``outreach.template.merge_field_unknown`` audit rows for every
    unknown placeholder, and by ``TemplateService.validate`` to
    surface the same issues in the operator UI without writing audit.
    """

    unknown_fields: list[str] = field(default_factory=list)
    empty_subject: bool = False


# --- Render entry points -------------------------------------------------


def render_template(
    template: TemplateOut,
    person: PersonRenderContext,
    *,
    unsubscribe_url_placeholder: str = "{{ unsubscribe_url }}",
) -> RenderedEmail:
    """Render ``template`` against ``person`` into a ``RenderedEmail``.

    Raises ``ValueError`` for ``body_format='html'`` (forbidden in
    Stage 1) and for unknown body formats. ``mjml`` falls back to the
    inline-CSS HTML envelope when ``mjml-python`` is not installed.

    The unsubscribe block is rendered with the placeholder URL so the
    return value is operator-previewable; the send service swaps in
    the real one-click URL once the ``send_id`` is known.
    """
    rendered, _trace = render_with_trace(
        template,
        person,
        unsubscribe_url_placeholder=unsubscribe_url_placeholder,
    )
    return rendered


def render_with_trace(
    template: TemplateOut,
    person: PersonRenderContext,
    *,
    unsubscribe_url_placeholder: str = "{{ unsubscribe_url }}",
) -> tuple[RenderedEmail, RenderTrace]:
    """Render and return both the email and the diagnostic trace."""
    if template.body_format == "html":
        # Stage 1 forbids operator-supplied raw HTML — too risky pre-PHI.
        raise ValueError(
            "body_format='html' is forbidden in Stage 1 outreach templates"
        )

    trace = RenderTrace()
    data = person.to_chevron_data()

    # Subject
    trace.unknown_fields.extend(_collect_unknown_fields(template.subject_template))
    subject = chevron.render(template.subject_template, data).strip()
    if not subject:
        trace.empty_subject = True

    # Body
    trace.unknown_fields.extend(_collect_unknown_fields(template.body_template))
    substituted_body = chevron.render(template.body_template, data)

    # Strip ``<script>``/``<style>`` and any other raw HTML tags from the
    # operator's substituted Markdown — operators cannot inject HTML in
    # Stage 1. After this the body is plain text + Markdown formatting.
    safe_substituted_body = _strip_raw_html(substituted_body)

    if template.body_format == "markdown":
        body_html = _markdown_to_html(safe_substituted_body)
    elif template.body_format == "mjml":
        body_html = _wrap_mjml_envelope(
            _markdown_to_html(safe_substituted_body),
            unsubscribe_url_placeholder=unsubscribe_url_placeholder,
        )
    else:  # pragma: no cover — guarded by the enum check above
        raise ValueError(f"unknown body_format: {template.body_format!r}")

    body_text = _html_to_plaintext(body_html)
    list_unsubscribe_header = (
        f"<{unsubscribe_url_placeholder}>"  # filled in at send time
    )

    return (
        RenderedEmail(
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            list_unsubscribe_header=list_unsubscribe_header,
        ),
        trace,
    )


# --- Internals -----------------------------------------------------------


def _collect_unknown_fields(mustache_text: str) -> list[str]:
    """Return placeholder names in ``mustache_text`` that are not allowed.

    We accept dotted names (``patient.first_name``) only; any name not
    on ``ALLOWED_MERGE_FIELDS`` is reported. Section tags (``{{#x}}``,
    ``{{/x}}``, ``{{^x}}``) are recognised by their leading sigil and
    excluded — they never substitute a value.
    """
    unknown: list[str] = []
    for match in _PLACEHOLDER_RE.finditer(mustache_text):
        name = match.group(1)
        # Section tags carry a leading sigil that the regex above strips.
        # We re-inspect the surrounding context to skip them rather than
        # parse Mustache fully.
        before = mustache_text[max(0, match.start() - 2) : match.start()]
        if "{{" in before:
            # Defensive — unlikely given the regex anchors on `{{ name }}`.
            continue
        if "{{#" in mustache_text[match.start() : match.end() + 1]:
            continue
        if not is_allowed(name):
            unknown.append(name)
    return unknown


def _strip_raw_html(text: str) -> str:
    """Strip raw HTML tags from operator content.

    Operator Markdown bodies must not contain inline HTML in Stage 1.
    This is a defence-in-depth measure on top of the Mustache
    logic-less surface — even if a merge field somehow carries HTML,
    we strip it before the Markdown renderer ever sees it.
    """
    return _HTML_TAG_RE.sub("", text)


def _markdown_to_html(markdown_text: str) -> str:
    """Render Markdown to HTML using ``markdown-it-py``.

    Configured in commonmark mode; HTML in the source is treated as
    text (not as live HTML), which compounds with ``_strip_raw_html``
    above so any operator-supplied tag is dropped twice over.
    """
    md = MarkdownIt("commonmark", {"html": False, "breaks": True, "linkify": True})
    return md.render(markdown_text).strip()


def _wrap_mjml_envelope(
    html_body: str,
    *,
    unsubscribe_url_placeholder: str,
) -> str:
    """Wrap an HTML body in the curated MJML envelope.

    Falls back to the inline-CSS HTML wrapper when ``mjml-python`` is
    not installed. The fallback path is operationally fine for Stage 1
    (the email still renders cleanly); the MJML path produces tighter
    cross-client HTML when the toolchain is present.
    """
    unsub_block = UNSUBSCRIBE_PLACEHOLDER.replace(
        "{{ unsubscribe_url }}", unsubscribe_url_placeholder
    )

    if not _HAS_MJML:
        # Inline-CSS fallback. Mustache-substitute the body + unsubscribe
        # block into the wrapper without going through chevron again
        # (the wrapper is a static template with two named slots).
        return (
            FALLBACK_HTML_ENVELOPE
            .replace("{{ body }}", html_body)
            .replace("{{ unsubscribe_block }}", unsub_block)
        )

    envelope = (
        DEFAULT_ENVELOPE
        .replace("{{ body }}", html_body)
        .replace("{{ unsubscribe_block }}", unsub_block)
    )
    try:
        # mjml-python returns a result object; guard against API drift.
        compiled = _mjml.mjml_to_html(envelope)  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001 — fall back rather than 500 the render
        log.warning("outreach.render.mjml_compile_failed")
        return (
            FALLBACK_HTML_ENVELOPE
            .replace("{{ body }}", html_body)
            .replace("{{ unsubscribe_block }}", unsub_block)
        )
    if isinstance(compiled, str):
        return compiled
    rendered = getattr(compiled, "html", None)
    return rendered if isinstance(rendered, str) else ""


def _html_to_plaintext(html_text: str) -> str:
    """Produce a minimal plain-text rendition of an HTML body.

    Used for ``multipart/alternative`` plain-text part. We strip tags
    and unescape HTML entities; this is intentionally not a full
    HTML-to-text converter — operator bodies in Stage 1 are Markdown,
    so the Markdown source survives mostly intact through tag stripping.
    """
    stripped = _HTML_TAG_RE.sub("", html_text)
    return html.unescape(stripped).strip()


# Re-export so callers can introspect the allowlist without importing
# from ``merge_fields`` directly. (e.g. operator UI surfaces this list.)
__all__ = [
    "ALLOWED_MERGE_FIELDS",
    "PersonRenderContext",
    "RenderTrace",
    "render_template",
    "render_with_trace",
]
