"""Pure call-reference extraction helpers for ingest pipelines."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, unquote, urlparse

CallProvider = Literal[
    "twilio",
    "zoom",
    "google_meet",
    "teams",
    "ringcentral",
    "dialpad",
    "justcall",
    "openphone",
    "other",
]
CallReferenceKind = Literal["recording", "meeting", "call_log", "unknown"]


@dataclass(frozen=True)
class CallReference:
    """Metadata pointer to a call or meeting resource.

    The extractor never fetches URLs, downloads audio, transcribes content, or
    calls external services. It only classifies strings already present in the
    captured provider payload.
    """

    url: str | None
    provider: CallProvider
    kind: CallReferenceKind
    external_id: str | None = None


_URL_RE = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
_OPAQUE_REFERENCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/=-]{5,}$")
_TRAILING_URL_PUNCTUATION = ".,;:!?)\\]}\"'"
_ALLOWLISTED_REFERENCE_KEYS = frozenset(
    {
        "callobject",
        "call_object",
        "callrecording",
        "call_recording",
        "recordingurl",
        "recording_url",
        "recordinglink",
        "recording_link",
        "meetingurl",
        "meeting_url",
        "meetinglink",
        "meeting_link",
        "callurl",
        "call_url",
        "callreference",
        "call_reference",
    }
)


def detect_call_references(
    text: str | None,
    *,
    allowlisted_keys: dict[str, str] | None = None,
) -> list[CallReference]:
    """Detect call or meeting references without performing any I/O.

    Free text is restricted to known call/meeting provider domains. Values
    passed through ``allowlisted_keys`` are trusted structured fields and may
    additionally yield ``provider="other"`` URLs or opaque external ids; this
    preserves Salesforce ``Task.CallObject`` behavior without accepting every
    arbitrary URL from free-text descriptions.
    """

    references: list[CallReference] = []
    seen: set[tuple[str | None, str, str, str | None]] = set()

    def add(reference: CallReference) -> None:
        key = (reference.url, reference.provider, reference.kind, reference.external_id)
        if key not in seen:
            seen.add(key)
            references.append(reference)

    for url in _extract_urls(text):
        reference = _reference_from_url(url, allow_other=False)
        if reference is not None:
            add(reference)

    for key, value in (allowlisted_keys or {}).items():
        if not _is_allowlisted_key(key):
            continue
        value = value.strip()
        if not value:
            continue

        found_url = False
        for url in _extract_urls(value):
            found_url = True
            reference = _reference_from_url(url, allow_other=True)
            if reference is not None:
                add(reference)

        if not found_url and _OPAQUE_REFERENCE_RE.fullmatch(value):
            add(
                CallReference(
                    url=None,
                    provider="other",
                    kind="call_log",
                    external_id=value,
                )
            )

    return references


def _extract_urls(text: str | None) -> list[str]:
    if text is None:
        return []
    urls: list[str] = []
    for match in _URL_RE.finditer(text):
        url = match.group(0).rstrip(_TRAILING_URL_PUNCTUATION)
        if _valid_url(url):
            urls.append(url)
    return urls


def _valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_allowlisted_key(key: str) -> bool:
    return key.strip().lower().replace("-", "_") in _ALLOWLISTED_REFERENCE_KEYS


def _reference_from_url(url: str, *, allow_other: bool) -> CallReference | None:
    parsed = urlparse(url)
    host = _host_without_port(parsed.netloc)
    provider = _provider_for_host(host)
    if provider is None:
        if not allow_other:
            return None
        provider = "other"
    return CallReference(
        url=url,
        provider=provider,
        kind=_kind_for_url(provider, parsed.path),
        external_id=_external_id_for_url(provider, parsed.path, parsed.query),
    )


def _host_without_port(netloc: str) -> str:
    host = netloc.rsplit("@", 1)[-1].split(":", 1)[0].lower()
    return host[4:] if host.startswith("www.") else host


def _provider_for_host(host: str) -> CallProvider | None:
    if _domain_matches(host, "twilio.com"):
        return "twilio"
    if _domain_matches(host, "zoom.us"):
        return "zoom"
    if host == "meet.google.com":
        return "google_meet"
    if _domain_matches(host, "teams.microsoft.com") or host == "aka.ms":
        return "teams"
    if (
        _domain_matches(host, "ringcentral.com")
        or _domain_matches(host, "ringcentral.us")
        or _domain_matches(host, "rcvideo.com")
    ):
        return "ringcentral"
    if _domain_matches(host, "dialpad.com"):
        return "dialpad"
    if _domain_matches(host, "justcall.io") or _domain_matches(host, "justcall.com"):
        return "justcall"
    if _domain_matches(host, "openphone.com"):
        return "openphone"
    return None


def _domain_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def _kind_for_url(provider: CallProvider, path: str) -> CallReferenceKind:
    lower = path.lower()
    if any(token in lower for token in ("recording", "recordings", "/rec/")):
        return "recording"
    if any(token in lower for token in ("meeting", "meetup", "/j/", "join")):
        return "meeting"
    if any(token in lower for token in ("call", "calls")):
        return "call_log"
    if provider in {"google_meet", "teams"}:
        return "meeting"
    return "unknown"


def _external_id_for_url(
    provider: CallProvider,
    path: str,
    query: str,
) -> str | None:
    path_segments = [unquote(segment) for segment in path.split("/") if segment]
    params = parse_qs(query)

    if provider == "twilio":
        return _first_matching_segment(path_segments, prefixes=("RE", "CA"))
    if provider == "zoom":
        return _segment_after(path_segments, "j") or _zoom_recording_id(path_segments)
    if provider == "google_meet":
        return path_segments[0] if path_segments else None
    if provider == "teams":
        return _first_query_value(params, "meetingId", "threadId") or (
            path_segments[-1] if path_segments else None
        )
    if provider in {"ringcentral", "dialpad", "justcall", "openphone"}:
        return (
            _first_query_value(params, "meetingId", "callId", "call_id", "recordingId")
            or _segment_after_any(
                path_segments,
                {"calls", "call", "recordings", "recording", "meetings", "meeting"},
            )
            or (path_segments[-1] if path_segments else None)
        )
    return path_segments[-1] if path_segments else None


def _first_matching_segment(
    segments: list[str],
    *,
    prefixes: tuple[str, ...],
) -> str | None:
    for segment in segments:
        if any(segment.startswith(prefix) for prefix in prefixes):
            return segment
    return None


def _segment_after(segments: list[str], marker: str) -> str | None:
    for index, segment in enumerate(segments[:-1]):
        if segment.lower() == marker:
            return segments[index + 1]
    return None


def _zoom_recording_id(segments: list[str]) -> str | None:
    if len(segments) >= 3 and segments[0].lower() == "rec":
        return segments[-1]
    return None


def _segment_after_any(segments: list[str], markers: set[str]) -> str | None:
    for index, segment in enumerate(segments[:-1]):
        if segment.lower() in markers:
            return segments[index + 1]
    return None


def _first_query_value(params: dict[str, list[str]], *keys: str) -> str | None:
    for key in keys:
        values = params.get(key)
        if values and values[0]:
            return values[0]
    return None
