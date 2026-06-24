"""Shared semantic time-window helpers for governed tools and agent runtime."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from packages.core.exceptions import ValidationError

TimeWindowSource = Literal["explicit", "semantic", "default"]


@dataclass(frozen=True, slots=True)
class ResolvedTimeWindow:
    preset: str
    source: TimeWindowSource
    created_from: datetime | None
    created_to: datetime | None
    disclosure: str


SUPPORTED_TIME_PRESETS = (
    "today",
    "yesterday",
    "this_week",
    "last_week",
    "this_month",
    "last_month",
    "this_quarter",
    "last_quarter",
    "this_year",
    "last_year",
    "last_7_days",
    "last_30_days",
)

EXPLICIT_TIME_WINDOW_DISCLOSURE = (
    "Applied explicit time window from structured tool parameters."
)
DEFAULT_LAST_30_DAYS_DISCLOSURE = (
    "No time period was specified, so this uses the last 30 days."
)


def apply_question_time_window(
    params: Mapping[str, object],
    *,
    question: str | None,
    now: datetime | None = None,
    preserve_stamped: bool = False,
) -> dict[str, object]:
    """Return params stamped with canonical time-window metadata."""
    clean_params = {str(key): value for key, value in params.items()}
    if preserve_stamped:
        stamped_window = stamped_time_window_from_params(clean_params)
        if stamped_window is not None:
            return with_time_window(clean_params, stamped_window)

    if has_explicit_time_window(clean_params):
        return with_time_window(clean_params, explicit_time_window_from_params(clean_params))

    window = resolve_question_time_window(question, now=now)
    return with_time_window(clean_params, window)


def has_explicit_time_window(params: Mapping[str, object]) -> bool:
    return any(params.get(key) is not None for key in ("created_from", "from")) or any(
        params.get(key) is not None for key in ("created_to", "to")
    )


def explicit_time_window_from_params(
    params: Mapping[str, object],
) -> ResolvedTimeWindow:
    return ResolvedTimeWindow(
        preset="explicit",
        source="explicit",
        created_from=coerce_datetime(params.get("created_from") or params.get("from")),
        created_to=coerce_datetime(params.get("created_to") or params.get("to")),
        disclosure=EXPLICIT_TIME_WINDOW_DISCLOSURE,
    )


def stamped_time_window_from_params(
    params: Mapping[str, object],
) -> ResolvedTimeWindow | None:
    source = params.get("time_window_source")
    if source not in {"explicit", "semantic", "default"}:
        return None
    preset = _optional_str(params.get("time_window_preset"))
    disclosure = _optional_str(params.get("time_window_disclosure"))
    created_from = coerce_datetime(params.get("created_from") or params.get("from"))
    created_to = coerce_datetime(params.get("created_to") or params.get("to"))
    if (
        preset is None
        or disclosure is None
        or created_from is None
        or created_to is None
    ):
        return None
    return ResolvedTimeWindow(
        preset=preset,
        source=cast(TimeWindowSource, source),
        created_from=created_from,
        created_to=created_to,
        disclosure=disclosure,
    )


def resolve_question_time_window(
    question: str | None,
    *,
    now: datetime | None = None,
) -> ResolvedTimeWindow:
    current = _utc_now(now)
    text = normalized_question_text(question or "")

    if _contains_any(text, _THIS_WEEK_MARKERS):
        return _time_window(
            preset="this_week",
            source="semantic",
            start=_start_of_week(current),
            end=current,
        )
    if _contains_any(text, _LAST_WEEK_MARKERS):
        this_week_start = _start_of_week(current)
        return _time_window(
            preset="last_week",
            source="semantic",
            start=this_week_start - timedelta(days=7),
            end=this_week_start,
        )
    if _contains_any(text, _TODAY_MARKERS):
        return _time_window(
            preset="today",
            source="semantic",
            start=_start_of_day(current),
            end=current,
        )
    if _contains_any(text, _YESTERDAY_MARKERS):
        today_start = _start_of_day(current)
        return _time_window(
            preset="yesterday",
            source="semantic",
            start=today_start - timedelta(days=1),
            end=today_start,
        )
    if _contains_any(text, _THIS_MONTH_MARKERS):
        return _time_window(
            preset="this_month",
            source="semantic",
            start=_start_of_month(current),
            end=current,
        )
    if _contains_any(text, _LAST_MONTH_MARKERS):
        this_month_start = _start_of_month(current)
        return _time_window(
            preset="last_month",
            source="semantic",
            start=_add_months(this_month_start, -1),
            end=this_month_start,
        )
    if _contains_any(text, _THIS_QUARTER_MARKERS):
        return _time_window(
            preset="this_quarter",
            source="semantic",
            start=_start_of_quarter(current),
            end=current,
        )
    if _contains_any(text, _LAST_QUARTER_MARKERS):
        this_quarter_start = _start_of_quarter(current)
        return _time_window(
            preset="last_quarter",
            source="semantic",
            start=_add_months(this_quarter_start, -3),
            end=this_quarter_start,
        )
    if _contains_any(text, _THIS_YEAR_MARKERS):
        return _time_window(
            preset="this_year",
            source="semantic",
            start=_start_of_year(current),
            end=current,
        )
    if _contains_any(text, _LAST_YEAR_MARKERS):
        this_year_start = _start_of_year(current)
        return _time_window(
            preset="last_year",
            source="semantic",
            start=this_year_start.replace(year=this_year_start.year - 1),
            end=this_year_start,
        )
    if _contains_any(text, _LAST_7_DAYS_MARKERS):
        return _time_window(
            preset="last_7_days",
            source="semantic",
            start=current - timedelta(days=7),
            end=current,
        )
    if _contains_any(text, _LAST_30_DAYS_MARKERS):
        return _time_window(
            preset="last_30_days",
            source="semantic",
            start=current - timedelta(days=30),
            end=current,
        )
    if _has_unsupported_time_expression(text):
        raise ValidationError(
            "Time expression is not supported by Semantic Time Constraints V1.",
            details={"supported_presets": SUPPORTED_TIME_PRESETS},
        )
    return _time_window(
        preset="last_30_days",
        source="default",
        start=current - timedelta(days=30),
        end=current,
    )


def with_time_window(
    params: Mapping[str, object],
    time_window: ResolvedTimeWindow,
) -> dict[str, object]:
    canonical_params = {
        str(key): value
        for key, value in params.items()
        if str(key) not in {"from", "to"}
    }
    return {
        **canonical_params,
        "created_from": time_window.created_from.isoformat()
        if time_window.created_from is not None
        else None,
        "created_to": time_window.created_to.isoformat()
        if time_window.created_to is not None
        else None,
        "time_window_source": time_window.source,
        "time_window_preset": time_window.preset,
        "time_window_disclosure": time_window.disclosure,
    }


def coerce_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValidationError(
                "invalid manager analytics datetime parameter",
                details={"value": text},
            ) from exc
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    raise ValidationError(
        "invalid manager analytics datetime parameter",
        details={"value": str(value)},
    )


def normalized_question_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _time_window(
    *,
    preset: str,
    source: Literal["semantic", "default"],
    start: datetime,
    end: datetime,
) -> ResolvedTimeWindow:
    disclosure = (
        DEFAULT_LAST_30_DAYS_DISCLOSURE
        if source == "default"
        else f"Applied semantic time window: {preset}."
    )
    return ResolvedTimeWindow(
        preset=preset,
        source=source,
        created_from=start,
        created_to=end,
        disclosure=disclosure,
    )


def _start_of_day(value: datetime) -> datetime:
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_week(value: datetime) -> datetime:
    start = _start_of_day(value)
    return start - timedelta(days=start.weekday())


def _start_of_month(value: datetime) -> datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _start_of_quarter(value: datetime) -> datetime:
    quarter_month = ((value.month - 1) // 3) * 3 + 1
    return value.replace(
        month=quarter_month,
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _start_of_year(value: datetime) -> datetime:
    return value.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return value.replace(year=year, month=month)


def _utc_now(now: datetime | None) -> datetime:
    current = now or datetime.now(tz=UTC)
    if current.tzinfo is None:
        return current.replace(tzinfo=UTC)
    return current.astimezone(UTC)


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _has_unsupported_time_expression(text: str) -> bool:
    return _contains_any(text, _UNSUPPORTED_TIME_MARKERS)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


_TODAY_MARKERS = ("today", "сегодня", "hoy")

_YESTERDAY_MARKERS = ("yesterday", "вчера", "ayer")

_THIS_WEEK_MARKERS = (
    "this week",
    "week to date",
    "wtd",
    "за эту неделю",
    "на этой неделе",
    "за текущую неделю",
    "esta semana",
)

_LAST_WEEK_MARKERS = (
    "last week",
    "previous week",
    "за прошлую неделю",
    "на прошлой неделе",
    "la semana pasada",
    "semana pasada",
)

_THIS_MONTH_MARKERS = (
    "this month",
    "month to date",
    "mtd",
    "за этот месяц",
    "в этом месяце",
    "за текущий месяц",
    "este mes",
)

_LAST_MONTH_MARKERS = (
    "last month",
    "previous month",
    "за прошлый месяц",
    "в прошлом месяце",
    "mes pasado",
    "el mes pasado",
)

_THIS_QUARTER_MARKERS = (
    "this quarter",
    "quarter to date",
    "qtd",
    "за этот квартал",
    "в этом квартале",
    "за текущий квартал",
    "este trimestre",
)

_LAST_QUARTER_MARKERS = (
    "last quarter",
    "previous quarter",
    "за прошлый квартал",
    "в прошлом квартале",
    "trimestre pasado",
    "el trimestre pasado",
)

_THIS_YEAR_MARKERS = (
    "this year",
    "year to date",
    "ytd",
    "за этот год",
    "в этом году",
    "за текущий год",
    "este ano",
)

_LAST_YEAR_MARKERS = (
    "last year",
    "previous year",
    "за прошлый год",
    "в прошлом году",
    "ano pasado",
    "el ano pasado",
)

_LAST_7_DAYS_MARKERS = (
    "last 7 days",
    "past 7 days",
    "previous 7 days",
    "за неделю",
    "за последнюю неделю",
    "за последние 7 дней",
    "ultima semana",
    "la ultima semana",
    "ultimos 7 dias",
    "los ultimos 7 dias",
)

_LAST_30_DAYS_MARKERS = (
    "last 30 days",
    "past 30 days",
    "previous 30 days",
    "за месяц",
    "за последний месяц",
    "за последние 30 дней",
    "ultimo mes",
    "el ultimo mes",
    "ultimos 30 dias",
    "los ultimos 30 dias",
)

_UNSUPPORTED_TIME_MARKERS = (
    "since ",
    "between ",
    "за период",
    "desde ",
    "entre ",
)
