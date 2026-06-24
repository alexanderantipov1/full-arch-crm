"""Time-range resolver tests — presets, custom, aggregate vs per-location tz (ENG-507)."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from packages.analytics.filters import resolve_time_range
from packages.core.exceptions import ValidationError

# Mid-afternoon UTC so "today" is unambiguous in both UTC and US zones.
_NOW = datetime(2026, 6, 18, 18, 30, tzinfo=UTC)  # a Thursday


def test_today_utc() -> None:
    w = resolve_time_range("today", now=_NOW, tz="UTC")
    assert w.start == datetime(2026, 6, 18, tzinfo=UTC)
    assert w.end == datetime(2026, 6, 19, tzinfo=UTC)
    assert w.preset == "today"


def test_yesterday_utc() -> None:
    w = resolve_time_range("yesterday", now=_NOW, tz="UTC")
    assert w.start == datetime(2026, 6, 17, tzinfo=UTC)
    assert w.end == datetime(2026, 6, 18, tzinfo=UTC)


@pytest.mark.parametrize(
    ("preset", "expected_start_day"),
    [
        ("last_7_days", 12),  # 18 - 6 → inclusive of today = 7 days
        ("last_30_days", 5 - 30 + 18),  # 2026-05-20
        ("last_90_days", 18),  # checked via length below
    ],
)
def test_rolling_windows_include_today(preset: str, expected_start_day: int) -> None:
    w = resolve_time_range(preset, now=_NOW, tz="UTC")  # type: ignore[arg-type]
    # End is always tomorrow's midnight (today included).
    assert w.end == datetime(2026, 6, 19, tzinfo=UTC)
    assert (w.end - w.start).days == {"last_7_days": 7, "last_30_days": 30, "last_90_days": 90}[preset]


def test_this_month() -> None:
    w = resolve_time_range("this_month", now=_NOW, tz="UTC")
    assert w.start == datetime(2026, 6, 1, tzinfo=UTC)
    assert w.end == datetime(2026, 7, 1, tzinfo=UTC)


def test_this_quarter() -> None:
    # June is in Q2 (Apr–Jun).
    w = resolve_time_range("this_quarter", now=_NOW, tz="UTC")
    assert w.start == datetime(2026, 4, 1, tzinfo=UTC)
    assert w.end == datetime(2026, 7, 1, tzinfo=UTC)


def test_this_year() -> None:
    w = resolve_time_range("this_year", now=_NOW, tz="UTC")
    assert w.start == datetime(2026, 1, 1, tzinfo=UTC)
    assert w.end == datetime(2027, 1, 1, tzinfo=UTC)


def test_custom_requires_both_bounds() -> None:
    with pytest.raises(ValidationError):
        resolve_time_range("custom", now=_NOW, custom_start=_NOW)


def test_custom_start_before_end() -> None:
    with pytest.raises(ValidationError):
        resolve_time_range(
            "custom",
            now=_NOW,
            custom_start=datetime(2026, 6, 10, tzinfo=UTC),
            custom_end=datetime(2026, 6, 1, tzinfo=UTC),
        )


def test_custom_window_passthrough() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 2, 1, tzinfo=UTC)
    w = resolve_time_range("custom", now=_NOW, custom_start=start, custom_end=end)
    assert (w.start, w.end) == (start, end)


def test_per_location_tz_shifts_day_boundary() -> None:
    # Aggregate (UTC) vs per-location (America/Los_Angeles) differ: at 18:30 UTC
    # LA is 11:30 PDT same day, so LA midnight is 07:00 UTC, not 00:00 UTC.
    utc = resolve_time_range("today", now=_NOW, tz="UTC")
    la = resolve_time_range("today", now=_NOW, tz="America/Los_Angeles")
    assert la.tz == "America/Los_Angeles"
    assert la.start == datetime(2026, 6, 18, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    # The LA day starts 7h after the UTC day on this date (PDT = UTC-7).
    assert la.start.astimezone(UTC) == datetime(2026, 6, 18, 7, 0, tzinfo=UTC)
    assert la.start.astimezone(UTC) != utc.start


def test_unknown_tz_raises() -> None:
    with pytest.raises(ValidationError):
        resolve_time_range("today", now=_NOW, tz="Mars/Phobos")
