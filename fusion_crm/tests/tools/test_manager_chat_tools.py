"""Tests for deterministic manager analytics chat planning."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from packages.core.exceptions import ValidationError
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.tools import manager_chat_tools
from packages.tools.base import ToolContext
from packages.tools.manager_chat_tools import (
    ask_manager_analytics,
    select_manager_query_id,
    select_manager_query_match,
)


def test_selects_paid_leads_query() -> None:
    assert (
        select_manager_query_id("How many paid leads came from Google this month?")
        == "paid_leads_by_source.v1"
    )


def test_selects_revenue_query() -> None:
    assert (
        select_manager_query_id("Show treatment revenue and collected payments.")
        == "treatment_revenue_evidence.v1"
    )


def test_selects_followup_query() -> None:
    assert (
        select_manager_query_id("Which consultations need overdue follow-up?")
        == "consultation_followup_worklist.v1"
    )


def test_selects_conversion_query() -> None:
    assert (
        select_manager_query_id("What is the conversion funnel from leads to booked consults?")
        == "lead_conversion_funnel.v1"
    )


def test_returns_query_read_model_match_metadata() -> None:
    match = select_manager_query_match(
        "What is the conversion funnel from leads to booked consults?"
    )

    assert match is not None
    assert match.query_id == "lead_conversion_funnel.v1"
    assert match.read_model_id == "lead_conversion"
    assert match.confidence == "high"
    assert "conversion" in match.matched_keywords
    assert "approved manager analytics query" in match.reason


def test_selects_conversion_for_appointment_booking_language() -> None:
    match = select_manager_query_match(
        "How many scheduled appointments came from paid leads this month?"
    )

    assert match is not None
    assert match.query_id == "lead_conversion_funnel.v1"
    assert match.read_model_id == "lead_conversion"
    assert match.confidence == "high"
    assert set(match.matched_keywords) >= {
        "scheduled appointment",
        "scheduled appointments",
    }


def test_selects_conversion_for_spanish_cita_language() -> None:
    match = select_manager_query_match(
        "Resume la conversion de citas programadas por fuente este mes"
    )

    assert match is not None
    assert match.query_id == "lead_conversion_funnel.v1"
    assert match.read_model_id == "lead_conversion"
    assert match.confidence == "high"
    assert set(match.matched_keywords) >= {
        "conversion",
        "citas programadas",
    }


def test_unknown_question_needs_clarification() -> None:
    assert select_manager_query_id("Tell me something interesting.") is None
    assert select_manager_query_match("Tell me something interesting.") is None


@pytest.mark.asyncio
async def test_ask_manager_analytics_defaults_direct_tool_to_last_30_days(
    monkeypatch,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    captured: dict[str, object] = {}
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)

    async def fake_run_analytics_query(ctx, *, query_id, params=None):
        captured["ctx"] = ctx
        captured["query_id"] = query_id
        captured["params"] = params
        return {
            "query_id": query_id,
            "read_model_id": "lead_conversion",
            "filters": {
                "created_from": params["created_from"],
                "created_to": params["created_to"],
            },
            "row_count": 1,
            "result": {"lead_status": [{"key": "new", "count": 2}]},
        }

    class FakeAuditService:
        def __init__(self, session):
            captured["audit_session"] = session

        async def record_tool_call(self, **kwargs):
            captured["audit_call"] = kwargs

    monkeypatch.setattr(manager_chat_tools, "_utc_now", lambda: now)
    monkeypatch.setattr(manager_chat_tools, "run_analytics_query", fake_run_analytics_query)
    monkeypatch.setattr(manager_chat_tools, "AuditService", FakeAuditService)

    principal = Principal(
        id=uuid.uuid4(),
        email="manager@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    result = await ask_manager_analytics(
        ToolContext(principal=principal, session=MagicMock()),
        question="Show lead conversion performance.",
    )

    params = captured["params"]
    assert isinstance(params, dict)
    assert params["created_from"] == "2026-05-16T12:00:00+00:00"
    assert params["created_to"] == "2026-06-15T12:00:00+00:00"
    assert params["time_window_source"] == "default"
    assert params["time_window_preset"] == "last_30_days"
    assert params["time_window_disclosure"] == (
        "No time period was specified, so this uses the last 30 days."
    )
    assert result["query_spec"]["params"] == params
    assert result["execution"]["time_window"] == {
        "source": "default",
        "preset": "last_30_days",
        "created_from": "2026-05-16T12:00:00+00:00",
        "created_to": "2026-06-15T12:00:00+00:00",
        "disclosure": "No time period was specified, so this uses the last 30 days.",
    }
    assert (
        result["execution"]["filters"]["time_window_disclosure"]
        == "No time period was specified, so this uses the last 30 days."
    )
    assert "No time period was specified" in result["explanation"]
    audit_extra = captured["audit_call"]["extra"]
    assert audit_extra["time_window_source"] == "default"
    assert audit_extra["time_window_preset"] == "last_30_days"
    assert "last 30 days" in audit_extra["time_window_disclosure"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "preset", "created_from", "created_to"),
    [
        (
            "Show lead conversion last week.",
            "last_week",
            "2026-06-08T00:00:00+00:00",
            "2026-06-15T00:00:00+00:00",
        ),
        (
            "Show lead conversion today.",
            "today",
            "2026-06-15T00:00:00+00:00",
            "2026-06-15T12:00:00+00:00",
        ),
        (
            "Покажи конверсию за неделю",
            "last_7_days",
            "2026-06-08T12:00:00+00:00",
            "2026-06-15T12:00:00+00:00",
        ),
        (
            "Покажи конверсию за этот квартал",
            "this_quarter",
            "2026-04-01T00:00:00+00:00",
            "2026-06-15T12:00:00+00:00",
        ),
        (
            "Resume el embudo este mes",
            "this_month",
            "2026-06-01T00:00:00+00:00",
            "2026-06-15T12:00:00+00:00",
        ),
        (
            "Show lead conversion for the last 30 days.",
            "last_30_days",
            "2026-05-16T12:00:00+00:00",
            "2026-06-15T12:00:00+00:00",
        ),
    ],
)
async def test_ask_manager_analytics_derives_direct_tool_time_windows(
    monkeypatch,
    question: str,
    preset: str,
    created_from: str,
    created_to: str,
) -> None:
    captured: dict[str, object] = {}
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)

    class FakeAuditService:
        def __init__(self, session):
            pass

        async def record_tool_call(self, **kwargs):
            captured["audit_call"] = kwargs

    monkeypatch.setattr(manager_chat_tools, "_utc_now", lambda: now)
    monkeypatch.setattr(manager_chat_tools, "AuditService", FakeAuditService)

    principal = Principal(
        id=uuid.uuid4(),
        email="manager@example.com",
        tenant_id=TenantId(uuid.uuid4()),
        roles=frozenset({Role.ADMIN}),
    )
    result = await ask_manager_analytics(
        ToolContext(principal=principal, session=MagicMock()),
        question=question,
        execute=False,
    )

    params = result["query_spec"]["params"]
    assert params["created_from"] == created_from
    assert params["created_to"] == created_to
    assert params["time_window_source"] == "semantic"
    assert params["time_window_preset"] == preset
    assert params["time_window_disclosure"] == (
        f"Applied semantic time window: {preset}."
    )
    audit_extra = captured["audit_call"]["extra"]
    assert audit_extra["time_window_source"] == "semantic"
    assert audit_extra["time_window_preset"] == preset


@pytest.mark.asyncio
async def test_ask_manager_analytics_preserves_runtime_stamped_time_window(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeAuditService:
        def __init__(self, session):
            pass

        async def record_tool_call(self, **kwargs):
            captured["audit_call"] = kwargs

    monkeypatch.setattr(manager_chat_tools, "AuditService", FakeAuditService)

    principal = Principal(
        id=uuid.uuid4(),
        email="manager@example.com",
        tenant_id=TenantId(uuid.uuid4()),
        roles=frozenset({Role.ADMIN}),
    )
    stamped_params = {
        "created_from": "2026-06-08T00:00:00+00:00",
        "created_to": "2026-06-15T12:00:00+00:00",
        "time_window_source": "semantic",
        "time_window_preset": "this_week",
        "time_window_disclosure": "Applied semantic time window: this_week.",
    }
    result = await ask_manager_analytics(
        ToolContext(principal=principal, session=MagicMock()),
        question="Show lead conversion performance this week.",
        params=stamped_params,
        execute=False,
    )

    params = result["query_spec"]["params"]
    assert params == stamped_params
    audit_extra = captured["audit_call"]["extra"]
    assert audit_extra["time_window_source"] == "semantic"
    assert audit_extra["time_window_preset"] == "this_week"
    assert audit_extra["time_window_disclosure"] == (
        "Applied semantic time window: this_week."
    )


@pytest.mark.asyncio
async def test_ask_manager_analytics_rejects_unsupported_direct_time_expression(
    monkeypatch,
) -> None:
    class FakeAuditService:
        def __init__(self, session):
            pass

        async def record_tool_call(self, **kwargs):
            raise AssertionError("unsupported time expressions must not be audited")

    monkeypatch.setattr(manager_chat_tools, "AuditService", FakeAuditService)

    principal = Principal(
        id=uuid.uuid4(),
        email="manager@example.com",
        tenant_id=TenantId(uuid.uuid4()),
        roles=frozenset({Role.ADMIN}),
    )

    with pytest.raises(ValidationError, match="Time expression is not supported"):
        await ask_manager_analytics(
            ToolContext(principal=principal, session=MagicMock()),
            question="Show lead conversion since the office opened.",
            execute=False,
        )
