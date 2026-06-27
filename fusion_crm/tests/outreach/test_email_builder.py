"""Tests for ``packages.outreach.email_builder.build_rfc822``.

Covers (ENG-132 spec):

- multipart/alternative structure (HTML + plaintext).
- ``List-Unsubscribe`` + ``List-Unsubscribe-Post: One-Click`` headers.
- UTF-8 subject + display-name encoding roundtrip.
- Optional ``In-Reply-To`` / ``References`` threading headers.
"""

from __future__ import annotations

import email
from email import policy

import pytest

from packages.outreach.email_builder import build_rfc822


def _parse(raw: bytes) -> email.message.EmailMessage:
    return email.message_from_bytes(raw, policy=policy.default)  # type: ignore[return-value]


def test_build_rfc822_has_multipart_alternative_with_html_and_text() -> None:
    raw = build_rfc822(
        from_address="info@galleriaoms.com",
        from_display_name="Galleria Dental",
        to="patient@example.com",
        subject="Welcome",
        body_html="<p>Welcome, Frank!</p>",
        body_text="Welcome, Frank!",
        list_unsubscribe_url="https://app.example.com/u/abc",
        list_unsubscribe_mailto="mailto:unsubscribe@galleriaoms.com",
    )
    msg = _parse(raw)
    assert msg.get_content_type() == "multipart/alternative"
    parts = list(msg.iter_parts())
    # plain first (RFC 2046 — clients pick the LAST acceptable part)
    assert parts[0].get_content_type() == "text/plain"
    assert parts[-1].get_content_type() == "text/html"
    assert "Welcome, Frank!" in parts[0].get_content()
    assert "<p>Welcome, Frank!</p>" in parts[-1].get_content()


def test_build_rfc822_has_one_click_unsubscribe_headers() -> None:
    raw = build_rfc822(
        from_address="info@galleriaoms.com",
        from_display_name=None,
        to="x@y.example",
        subject="hi",
        body_html="<p>hi</p>",
        body_text="hi",
        list_unsubscribe_url="https://app.example.com/u/abc",
        list_unsubscribe_mailto="mailto:unsubscribe@galleriaoms.com?subject=unsub",
    )
    msg = _parse(raw)
    unsub = msg["List-Unsubscribe"]
    assert "https://app.example.com/u/abc" in unsub
    assert "mailto:unsubscribe@galleriaoms.com" in unsub
    assert msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


def test_build_rfc822_utf8_subject_roundtrip() -> None:
    subject = "Здравствуйте, Frank — your appointment"
    raw = build_rfc822(
        from_address="info@galleriaoms.com",
        from_display_name=None,
        to="x@y.example",
        subject=subject,
        body_html="<p>hi</p>",
        body_text="hi",
        list_unsubscribe_url="https://app.example.com/u/abc",
        list_unsubscribe_mailto="mailto:unsubscribe@galleriaoms.com",
    )
    msg = _parse(raw)
    assert msg["Subject"] == subject


def test_build_rfc822_threading_headers_present_when_in_reply_to_set() -> None:
    raw = build_rfc822(
        from_address="info@x.example",
        from_display_name=None,
        to="x@y.example",
        subject="re: prior",
        body_html="<p>thanks</p>",
        body_text="thanks",
        list_unsubscribe_url="https://app.example.com/u/abc",
        list_unsubscribe_mailto="mailto:unsubscribe@x.example",
        in_reply_to="<parent@x.example>",
    )
    msg = _parse(raw)
    assert msg["In-Reply-To"] == "<parent@x.example>"
    assert msg["References"] == "<parent@x.example>"


def test_build_rfc822_rejects_missing_addresses() -> None:
    with pytest.raises(ValueError):
        build_rfc822(
            from_address="",
            from_display_name=None,
            to="x@y.example",
            subject="hi",
            body_html="<p>hi</p>",
            body_text="hi",
            list_unsubscribe_url="https://x.example/u/abc",
            list_unsubscribe_mailto="mailto:unsubscribe@x.example",
        )
    with pytest.raises(ValueError):
        build_rfc822(
            from_address="info@x.example",
            from_display_name=None,
            to="",
            subject="hi",
            body_html="<p>hi</p>",
            body_text="hi",
            list_unsubscribe_url="https://x.example/u/abc",
            list_unsubscribe_mailto="mailto:unsubscribe@x.example",
        )


def test_build_rfc822_rejects_missing_unsubscribe_pair() -> None:
    with pytest.raises(ValueError):
        build_rfc822(
            from_address="info@x.example",
            from_display_name=None,
            to="x@y.example",
            subject="hi",
            body_html="<p>hi</p>",
            body_text="hi",
            list_unsubscribe_url="",
            list_unsubscribe_mailto="mailto:unsubscribe@x.example",
        )


def test_build_rfc822_has_message_id() -> None:
    raw = build_rfc822(
        from_address="info@x.example",
        from_display_name=None,
        to="x@y.example",
        subject="hi",
        body_html="<p>hi</p>",
        body_text="hi",
        list_unsubscribe_url="https://x.example/u/abc",
        list_unsubscribe_mailto="mailto:unsubscribe@x.example",
    )
    msg = _parse(raw)
    mid = msg["Message-ID"]
    assert mid is not None
    # Message-ID is wrapped in angle brackets and ends with our domain.
    assert mid.endswith("@x.example>")


def test_build_rfc822_extra_headers_are_added_but_protected() -> None:
    raw = build_rfc822(
        from_address="info@x.example",
        from_display_name=None,
        to="x@y.example",
        subject="hi",
        body_html="<p>hi</p>",
        body_text="hi",
        list_unsubscribe_url="https://x.example/u/abc",
        list_unsubscribe_mailto="mailto:unsubscribe@x.example",
        extra_headers={
            "X-Outreach-Campaign-Id": "abc-123",
            # Attempts to override our own header are ignored.
            "Subject": "MALICIOUS",
            "List-Unsubscribe": "MALICIOUS",
        },
    )
    msg = _parse(raw)
    assert msg["X-Outreach-Campaign-Id"] == "abc-123"
    assert msg["Subject"] == "hi"
    assert "https://x.example/u/abc" in msg["List-Unsubscribe"]
