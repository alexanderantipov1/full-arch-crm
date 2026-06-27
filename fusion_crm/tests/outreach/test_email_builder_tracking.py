"""ENG-134 additions to ``packages.outreach.email_builder.build_rfc822``.

Tests:

- The ``tracking_pixel_url`` parameter injects a 1x1 ``<img>`` tag at
  the end of ``body_html`` ONLY when supplied.
- Omitting the parameter (or passing None) leaves the body untouched
  — the ENG-132 baseline.
- The ``List-Unsubscribe`` and ``List-Unsubscribe-Post`` headers are
  always present (RFC 8058 compliance).
- A tracking-pixel URL containing a double quote cannot break out of
  the attribute (HTML-escape defence).
"""

from __future__ import annotations

import email
from email import policy

from packages.outreach.email_builder import build_rfc822


def _parse(raw: bytes) -> email.message.EmailMessage:
    return email.message_from_bytes(raw, policy=policy.default)  # type: ignore[return-value]


def _html_part(raw: bytes) -> str:
    msg = _parse(raw)
    for part in msg.iter_parts():
        if part.get_content_type() == "text/html":
            return part.get_content()
    return ""


def test_tracking_pixel_injected_when_url_supplied() -> None:
    raw = build_rfc822(
        from_address="info@x.example",
        from_display_name=None,
        to="patient@example.com",
        subject="Welcome",
        body_html="<p>Hi there</p>",
        body_text="Hi there",
        list_unsubscribe_url="https://x.example/u/abc",
        list_unsubscribe_mailto="mailto:unsubscribe@x.example",
        tracking_pixel_url="https://x.example/outreach/track/open/abc.sig",
    )
    html = _html_part(raw)
    assert "<p>Hi there</p>" in html
    assert 'src="https://x.example/outreach/track/open/abc.sig"' in html
    assert 'width="1"' in html
    assert 'height="1"' in html


def test_tracking_pixel_omitted_when_url_not_supplied() -> None:
    raw = build_rfc822(
        from_address="info@x.example",
        from_display_name=None,
        to="patient@example.com",
        subject="Hi",
        body_html="<p>Body</p>",
        body_text="Body",
        list_unsubscribe_url="https://x.example/u/abc",
        list_unsubscribe_mailto="mailto:unsubscribe@x.example",
    )
    html = _html_part(raw)
    # No <img> appended.
    assert "<img" not in html.lower()


def test_tracking_pixel_default_is_none() -> None:
    """Backwards-compatible: omitting the kwarg behaves like ENG-132."""
    raw = build_rfc822(
        from_address="info@x.example",
        from_display_name=None,
        to="patient@example.com",
        subject="Hi",
        body_html="<p>Body</p>",
        body_text="Body",
        list_unsubscribe_url="https://x.example/u/abc",
        list_unsubscribe_mailto="mailto:unsubscribe@x.example",
        tracking_pixel_url=None,
    )
    html = _html_part(raw)
    assert "<img" not in html.lower()


def test_list_unsubscribe_headers_always_present_with_pixel() -> None:
    """RFC 8058 compliance is not affected by ENG-134 pixel injection."""
    raw = build_rfc822(
        from_address="info@x.example",
        from_display_name=None,
        to="patient@example.com",
        subject="Hi",
        body_html="<p>Body</p>",
        body_text="Body",
        list_unsubscribe_url="https://x.example/u/abc",
        list_unsubscribe_mailto="mailto:unsubscribe@x.example",
        tracking_pixel_url="https://x.example/outreach/track/open/abc.sig",
    )
    msg = _parse(raw)
    unsub = msg["List-Unsubscribe"]
    assert "https://x.example/u/abc" in unsub
    assert "mailto:unsubscribe@x.example" in unsub
    assert msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


def test_list_unsubscribe_headers_always_present_without_pixel() -> None:
    """Same headers are present whether or not a tracking pixel is injected."""
    raw = build_rfc822(
        from_address="info@x.example",
        from_display_name=None,
        to="patient@example.com",
        subject="Hi",
        body_html="<p>Body</p>",
        body_text="Body",
        list_unsubscribe_url="https://x.example/u/abc",
        list_unsubscribe_mailto="mailto:unsubscribe@x.example",
    )
    msg = _parse(raw)
    unsub = msg["List-Unsubscribe"]
    assert "https://x.example/u/abc" in unsub
    assert "mailto:unsubscribe@x.example" in unsub
    assert msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


def test_tracking_pixel_url_is_html_escaped() -> None:
    """A maliciously-formed URL with a quote cannot break out of the attribute."""
    raw = build_rfc822(
        from_address="info@x.example",
        from_display_name=None,
        to="patient@example.com",
        subject="Hi",
        body_html="<p>Body</p>",
        body_text="Body",
        list_unsubscribe_url="https://x.example/u/abc",
        list_unsubscribe_mailto="mailto:unsubscribe@x.example",
        # Hostile URL — should be escaped.
        tracking_pixel_url='https://x.example/track/"><script>alert(1)</script>',
    )
    html = _html_part(raw)
    # The literal script tag must NOT appear unescaped.
    assert "<script>alert(1)</script>" not in html
    # The escaped form should be present.
    assert "&lt;script&gt;" in html or "&#x27;" in html or "&quot;" in html
