"""Unit coverage for the ENG-486 T-15m consultation reminder scan."""

from __future__ import annotations

from datetime import UTC, datetime

from apps.worker.jobs.consultation_reminders import (
    _REMINDER_HORIZON,
    _format_scheduled_when,
)
from packages.integrations.chat.events import (
    ALL_EVENT_TYPES,
    EVENT_CONSULTATION_REMINDER,
)
from packages.integrations.chat.seeds import (
    _DEFAULT_RULES,
    CONSULT_REMINDERS_CHANNEL,
    CONSULTATION_REMINDER_RICH_TEMPLATE,
)


def test_reminder_horizon_is_15_minutes() -> None:
    assert _REMINDER_HORIZON.total_seconds() == 15 * 60


def test_format_scheduled_when_is_human_readable_with_tz() -> None:
    when = datetime(2026, 6, 17, 9, 0, tzinfo=UTC)
    assert _format_scheduled_when(when) == "Jun 17, 2026 9:00 AM UTC"
    # Naive instants are treated as UTC (mirrors the scheduled-notify formatter).
    assert _format_scheduled_when(datetime(2026, 6, 17, 9, 0)).endswith("UTC")


def test_reminder_event_is_in_the_roster() -> None:
    assert EVENT_CONSULTATION_REMINDER in ALL_EVENT_TYPES


def test_default_seed_routes_reminder_to_consult_reminders_channel() -> None:
    rule = next(
        r for r in _DEFAULT_RULES if r[0] == EVENT_CONSULTATION_REMINDER
    )
    event_type, channel, conditions, _template, _description = rule
    assert channel == CONSULT_REMINDERS_CHANNEL
    # The scanner already filters confirmed + due, so the rule carries no
    # extra condition (a stray condition would silently suppress reminders).
    assert conditions == []


def test_reminder_template_text_carries_doctor_mention() -> None:
    # ENG-543: the @mention must live in the post ``text`` (message body) so
    # Mattermost actually notifies the doctor — not only in an attachment field.
    text = CONSULTATION_REMINDER_RICH_TEMPLATE["text"]
    assert isinstance(text, str)
    assert "{{doctor_mention}}" in text
