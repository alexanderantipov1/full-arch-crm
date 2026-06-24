"""AnalyticsFilters DTO validation tests (ENG-507)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError as PydanticValidationError

from packages.analytics.filters import AnalyticsFilters


def test_defaults_aggregate_and_last_30() -> None:
    f = AnalyticsFilters()
    assert f.time_range == "last_30_days"
    assert f.location_id is None  # aggregate over all locations


def test_custom_requires_both_bounds() -> None:
    with pytest.raises(PydanticValidationError):
        AnalyticsFilters(time_range="custom", custom_start=datetime(2026, 1, 1, tzinfo=UTC))


def test_custom_with_bounds_ok() -> None:
    f = AnalyticsFilters(
        time_range="custom",
        custom_start=datetime(2026, 1, 1, tzinfo=UTC),
        custom_end=datetime(2026, 2, 1, tzinfo=UTC),
    )
    assert f.time_range == "custom"


def test_per_location_filter_set() -> None:
    loc = uuid.uuid4()
    f = AnalyticsFilters(location_id=loc, source="google_ads")
    assert f.location_id == loc
    assert f.source == "google_ads"


def test_extra_keys_forbidden() -> None:
    with pytest.raises(PydanticValidationError):
        AnalyticsFilters(bogus="x")  # type: ignore[call-arg]


def test_resolve_window_uses_tz() -> None:
    f = AnalyticsFilters(time_range="today")
    now = datetime(2026, 6, 18, 18, 30, tzinfo=UTC)
    w = f.resolve_window(now=now, tz="UTC")
    assert w.start == datetime(2026, 6, 18, tzinfo=UTC)
