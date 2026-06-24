"""Unit tests for the incremental sync-window helpers (ENG)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from packages.ingest.sync_window import (
    DEFAULT_WATERMARK_OVERLAP,
    parse_watermark,
    resume_modified_since,
)


def test_parse_watermark_truncates_overlong_fraction_and_assumes_utc() -> None:
    # CareStack emits 7 fractional digits and no timezone.
    parsed = parse_watermark("2026-06-02T23:52:17.7406657")
    assert parsed == datetime(2026, 6, 2, 23, 52, 17, 740665, tzinfo=UTC)


def test_parse_watermark_accepts_trailing_z() -> None:
    parsed = parse_watermark("2026-05-26T10:00:00Z")
    assert parsed == datetime(2026, 5, 26, 10, 0, 0, tzinfo=UTC)


def test_parse_watermark_preserves_explicit_offset_as_utc() -> None:
    parsed = parse_watermark("2026-05-26T12:00:00+02:00")
    assert parsed == datetime(2026, 5, 26, 10, 0, 0, tzinfo=UTC)


def test_parse_watermark_returns_none_for_empty_or_garbage() -> None:
    assert parse_watermark(None) is None
    assert parse_watermark("") is None
    assert parse_watermark("   ") is None
    assert parse_watermark("not-a-date") is None


def test_resume_uses_default_when_no_watermark() -> None:
    default_since = datetime(2026, 5, 1, tzinfo=UTC)
    assert resume_modified_since(None, default_since=default_since) == default_since
    assert (
        resume_modified_since("garbage", default_since=default_since) == default_since
    )


def test_resume_subtracts_overlap_from_watermark() -> None:
    default_since = datetime(2026, 5, 1, tzinfo=UTC)
    out = resume_modified_since(
        "2026-06-02T23:52:17Z", default_since=default_since
    )
    assert out == datetime(2026, 6, 2, 23, 52, 17, tzinfo=UTC) - DEFAULT_WATERMARK_OVERLAP


def test_resume_honours_custom_overlap() -> None:
    default_since = datetime(2026, 5, 1, tzinfo=UTC)
    out = resume_modified_since(
        "2026-06-02T12:00:00Z",
        default_since=default_since,
        overlap=timedelta(hours=1),
    )
    assert out == datetime(2026, 6, 2, 11, 0, 0, tzinfo=UTC)
