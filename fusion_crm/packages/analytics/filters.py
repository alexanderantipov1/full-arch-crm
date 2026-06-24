"""Shared analytics filter + time-range contract (ENG-507).

Every Revenue-Intelligence page consumes the SAME filter DTO and the SAME
time-range resolver, so metric windows are defined once (no drift). The filters
mirror ``market.md``'s global filter bar: date range, location, campaign,
source, vendor, caller, coordinator, doctor.

Location supports **aggregate (all locations, the default) AND per-location**:
``location_id=None`` means aggregate; a value scopes to that clinic. The
time-range resolver is timezone-aware — a per-location request resolves
"Today"/"This Month"/… in that location's timezone (``tenant.location.
timezone_override`` falling back to ``tenant.timezone``), so day boundaries are
the clinic's local midnights, not UTC.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.core.exceptions import ValidationError

# market.md preset ladder + Custom.
TimeRangePreset = Literal[
    "today",
    "yesterday",
    "last_7_days",
    "last_30_days",
    "last_90_days",
    "this_month",
    "this_quarter",
    "this_year",
    "custom",
]

_ROLLING_DAYS: dict[str, int] = {
    "last_7_days": 7,
    "last_30_days": 30,
    "last_90_days": 90,
}


@dataclass(frozen=True)
class ResolvedWindow:
    """A half-open ``[start, end)`` instant window, timezone-aware.

    ``start`` / ``end`` are tz-aware datetimes; Postgres compares them against
    ``timestamptz`` columns correctly regardless of the resolver's zone. ``tz``
    records the zone the calendar boundaries were computed in (for display).
    """

    preset: TimeRangePreset
    start: datetime
    end: datetime
    tz: str


def _zone(tz: str | None) -> ZoneInfo:
    if not tz:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(tz)
    except Exception as exc:  # unknown tz name → explicit contract error
        raise ValidationError(f"unknown timezone: {tz!r}") from exc


def _quarter_start_month(month: int) -> int:
    return ((month - 1) // 3) * 3 + 1


def resolve_time_range(
    preset: TimeRangePreset,
    *,
    now: datetime,
    tz: str | None = None,
    custom_start: datetime | None = None,
    custom_end: datetime | None = None,
) -> ResolvedWindow:
    """Resolve a preset (or Custom) to a half-open ``[start, end)`` window.

    Calendar presets are day-aligned in ``tz``: ``today`` is
    ``[local_midnight, next_local_midnight)``; ``last_N_days`` is the trailing N
    calendar days INCLUDING today; ``this_month`` / ``this_quarter`` /
    ``this_year`` span the current period. ``custom`` requires both
    ``custom_start`` and ``custom_end`` (start < end).

    ``now`` is supplied by the caller (tz-aware) so the resolver is pure and
    testable. The returned bounds are tz-aware in ``tz``.
    """
    zone = _zone(tz)
    local_now = now.astimezone(zone)
    start_of_today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_tomorrow = start_of_today + timedelta(days=1)

    if preset == "custom":
        if custom_start is None or custom_end is None:
            raise ValidationError(
                "custom time range requires both start and end"
            )
        if custom_start >= custom_end:
            raise ValidationError("custom time range start must be before end")
        return ResolvedWindow("custom", custom_start, custom_end, str(zone))

    if preset == "today":
        return ResolvedWindow(preset, start_of_today, start_of_tomorrow, str(zone))
    if preset == "yesterday":
        return ResolvedWindow(
            preset, start_of_today - timedelta(days=1), start_of_today, str(zone)
        )
    if preset in _ROLLING_DAYS:
        days = _ROLLING_DAYS[preset]
        return ResolvedWindow(
            preset,
            start_of_today - timedelta(days=days - 1),
            start_of_tomorrow,
            str(zone),
        )
    if preset == "this_month":
        start = start_of_today.replace(day=1)
        end = (
            start.replace(year=start.year + 1, month=1)
            if start.month == 12
            else start.replace(month=start.month + 1)
        )
        return ResolvedWindow(preset, start, end, str(zone))
    if preset == "this_quarter":
        q_month = _quarter_start_month(local_now.month)
        start = start_of_today.replace(month=q_month, day=1)
        end_month = q_month + 3
        end = (
            start.replace(year=start.year + 1, month=end_month - 12)
            if end_month > 12
            else start.replace(month=end_month)
        )
        return ResolvedWindow(preset, start, end, str(zone))
    if preset == "this_year":
        start = start_of_today.replace(month=1, day=1)
        end = start.replace(year=start.year + 1)
        return ResolvedWindow(preset, start, end, str(zone))

    raise ValidationError(f"unsupported time range preset: {preset!r}")


class AnalyticsFilters(BaseModel):
    """Shared global filter bar for every analytics page (ENG-507).

    ``time_range`` selects a preset; ``custom_start`` / ``custom_end`` are
    required only when ``time_range == 'custom'``. ``location_id=None`` is the
    default AGGREGATE (all locations); a value scopes to one clinic. The
    remaining dimensions are equality filters over ``fact_patient_journey``;
    ``None`` means "do not filter on this dimension".
    """

    model_config = ConfigDict(extra="forbid")

    time_range: TimeRangePreset = "last_30_days"
    custom_start: datetime | None = None
    custom_end: datetime | None = None
    location_id: UUID | None = None
    campaign_id: UUID | None = None
    source: str | None = Field(default=None, max_length=128)
    vendor_id: UUID | None = None
    caller_id: UUID | None = None
    coordinator_id: UUID | None = None
    doctor_id: UUID | None = None

    @model_validator(mode="after")
    def _check_custom(self) -> AnalyticsFilters:
        if self.time_range == "custom" and (
            self.custom_start is None or self.custom_end is None
        ):
            raise ValueError("custom time_range requires custom_start and custom_end")
        return self

    def resolve_window(
        self, *, now: datetime | None = None, tz: str | None = None
    ) -> ResolvedWindow:
        """Resolve this filter's time range to a concrete window."""
        return resolve_time_range(
            self.time_range,
            now=now or datetime.now(tz=UTC),
            tz=tz,
            custom_start=self.custom_start,
            custom_end=self.custom_end,
        )
