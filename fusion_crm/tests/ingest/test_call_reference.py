"""Tests for pure call-reference extraction."""

from __future__ import annotations

import pytest

from packages.ingest.call_reference import CallReference, detect_call_references


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://api.twilio.com/2010-04-01/Accounts/AC123/Recordings/REabc123",
            CallReference(
                url="https://api.twilio.com/2010-04-01/Accounts/AC123/Recordings/REabc123",
                provider="twilio",
                kind="recording",
                external_id="REabc123",
            ),
        ),
        (
            "https://fusion.zoom.us/j/987654321",
            CallReference(
                url="https://fusion.zoom.us/j/987654321",
                provider="zoom",
                kind="meeting",
                external_id="987654321",
            ),
        ),
        (
            "https://fusion.zoom.us/rec/share/recording-token-123",
            CallReference(
                url="https://fusion.zoom.us/rec/share/recording-token-123",
                provider="zoom",
                kind="recording",
                external_id="recording-token-123",
            ),
        ),
        (
            "https://meet.google.com/abc-defg-hij",
            CallReference(
                url="https://meet.google.com/abc-defg-hij",
                provider="google_meet",
                kind="meeting",
                external_id="abc-defg-hij",
            ),
        ),
        (
            "https://teams.microsoft.com/l/meetup-join/19%3ameeting_NjQ",
            CallReference(
                url="https://teams.microsoft.com/l/meetup-join/19%3ameeting_NjQ",
                provider="teams",
                kind="meeting",
                external_id="19:meeting_NjQ",
            ),
        ),
        (
            "https://v.ringcentral.com/join/123456789",
            CallReference(
                url="https://v.ringcentral.com/join/123456789",
                provider="ringcentral",
                kind="meeting",
                external_id="123456789",
            ),
        ),
        (
            "https://dialpad.com/app/calls/call-123",
            CallReference(
                url="https://dialpad.com/app/calls/call-123",
                provider="dialpad",
                kind="call_log",
                external_id="call-123",
            ),
        ),
        (
            "https://app.justcall.io/calls/jc-456",
            CallReference(
                url="https://app.justcall.io/calls/jc-456",
                provider="justcall",
                kind="call_log",
                external_id="jc-456",
            ),
        ),
        (
            "https://app.openphone.com/calls/op-789",
            CallReference(
                url="https://app.openphone.com/calls/op-789",
                provider="openphone",
                kind="call_log",
                external_id="op-789",
            ),
        ),
    ],
)
def test_detects_known_provider_urls(url: str, expected: CallReference) -> None:
    assert detect_call_references(f"Reference: {url}") == [expected]


def test_detects_multiple_urls_and_strips_trailing_punctuation() -> None:
    references = detect_call_references(
        "Join https://fusion.zoom.us/j/111222333, "
        "then see recording https://api.twilio.com/2010-04-01/Accounts/AC123/"
        "Recordings/RE999)."
    )

    assert [reference.provider for reference in references] == ["zoom", "twilio"]
    assert references[0].url == "https://fusion.zoom.us/j/111222333"
    assert references[1].url is not None
    assert references[1].url.endswith("/RE999")


def test_ignores_malformed_and_non_provider_free_text_urls() -> None:
    assert detect_call_references("See https://example.com/calls/abc and https://") == []


def test_returns_empty_for_no_urls() -> None:
    assert detect_call_references("No call reference here") == []
    assert detect_call_references(None) == []


def test_allowlisted_key_accepts_other_url_and_opaque_id() -> None:
    assert detect_call_references(
        None,
        allowlisted_keys={"CallObject": "https://recordings.example.test/calls/abc123"},
    ) == [
        CallReference(
            url="https://recordings.example.test/calls/abc123",
            provider="other",
            kind="call_log",
            external_id="abc123",
        )
    ]
    assert detect_call_references(
        None,
        allowlisted_keys={"CallObject": "provider-recording-abc123"},
    ) == [
        CallReference(
            url=None,
            provider="other",
            kind="call_log",
            external_id="provider-recording-abc123",
        )
    ]


def test_non_allowlisted_key_does_not_accept_other_url_or_opaque_id() -> None:
    assert (
        detect_call_references(
            None,
            allowlisted_keys={"Description": "https://recordings.example.test/calls/abc"},
        )
        == []
    )
