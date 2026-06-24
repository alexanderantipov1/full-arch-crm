"""Tests for the Fusion CRM agent runtime service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError as PydanticValidationError

from packages.agent_runtime import service as agent_runtime_service
from packages.agent_runtime.models import AgentRuntimeApprovalRequest, AgentRuntimeRun
from packages.agent_runtime.schemas import (
    AgentRuntimeApprovalDecisionIn,
    AgentRuntimeApprovalRequestCreateIn,
    AgentRuntimeLlmExecutionOut,
    AgentRuntimeLlmPlanIn,
    AgentRuntimeLlmPlanOut,
)
from packages.agent_runtime.service import AgentRuntimeService
from packages.core.exceptions import ValidationError
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.integrations.openai.schemas import (
    OpenAIAgentPlanOut,
    OpenAIConnectionCheckOut,
    OpenAIManagerAnswerOut,
)
from packages.tools.base import ToolSpec
from packages.tools.manager_chat_tools import select_manager_query_match


def _manager_answer_aggregate_execution(
    result: dict[str, object],
    *,
    time_window: dict[str, object] | None = None,
) -> Any:
    tool_result: dict[str, object] = {"result": result}
    if time_window is not None:
        tool_result["time_window"] = time_window
    return agent_runtime_service._LlmToolExecution(  # noqa: SLF001
        status="executed",
        run_status="completed",
        final_outcome="tool_executed",
        result_posture="safe_aggregate_tool_execution",
        policy_reason="Aggregate-only V1 analytics query selected.",
        output=AgentRuntimeLlmExecutionOut(
            status="executed",
            tool_id="ask_manager_analytics",
            query_id="lead_conversion_funnel.v1",
            read_model_id="lead_conversion",
            match_status="matched",
            match_confidence="high",
            match_reason="Aggregate-only V1 analytics query selected.",
            output_type="aggregate",
            data_classes=["ops", "integration_metadata"],
            row_count=1,
            explanation="Executed approved aggregate analytics query.",
            policy_reason="Aggregate-only V1 analytics query selected.",
            result=tool_result,
        ),
    )


def test_safe_tool_question_accepts_manager_question_alias() -> None:
    question = agent_runtime_service._safe_tool_question(  # noqa: SLF001
        {"manager_question": "Lead conversion performance this week"},
    )

    assert question == "Lead conversion performance this week"


def test_safe_tool_params_derives_this_week_window_from_question() -> None:
    params = agent_runtime_service._safe_tool_params(  # noqa: SLF001
        {},
        question="What is lead conversion performance this week?",
        now=datetime(2026, 6, 9, 15, 30, tzinfo=UTC),
    )

    assert params == {
        "created_from": "2026-06-08T00:00:00+00:00",
        "created_to": "2026-06-09T15:30:00+00:00",
        "time_window_disclosure": "Applied semantic time window: this_week.",
        "time_window_preset": "this_week",
        "time_window_source": "semantic",
    }


def test_safe_tool_params_keeps_explicit_time_window() -> None:
    params = agent_runtime_service._safe_tool_params(  # noqa: SLF001
        {
            "params": {
                "created_from": "2026-06-01T00:00:00+00:00",
                "created_to": "2026-06-02T00:00:00+00:00",
            }
        },
        question="What is lead conversion performance this week?",
        now=datetime(2026, 6, 9, 15, 30, tzinfo=UTC),
    )

    assert params == {
        "created_from": "2026-06-01T00:00:00+00:00",
        "created_to": "2026-06-02T00:00:00+00:00",
        "time_window_disclosure": (
            "Applied explicit time window from structured tool parameters."
        ),
        "time_window_preset": "explicit",
        "time_window_source": "explicit",
    }


def test_safe_tool_params_derives_russian_this_month_window() -> None:
    params = agent_runtime_service._safe_tool_params(  # noqa: SLF001
        {},
        question="Сколько пациентов вернули за этот месяц?",
        now=datetime(2026, 6, 9, 15, 30, tzinfo=UTC),
    )

    assert params == {
        "created_from": "2026-06-01T00:00:00+00:00",
        "created_to": "2026-06-09T15:30:00+00:00",
        "time_window_disclosure": "Applied semantic time window: this_month.",
        "time_window_preset": "this_month",
        "time_window_source": "semantic",
    }


def test_safe_tool_params_derives_spanish_last_7_days_window() -> None:
    params = agent_runtime_service._safe_tool_params(  # noqa: SLF001
        {},
        question="Cuantos leads llegaron los últimos 7 días?",
        now=datetime(2026, 6, 9, 15, 30, tzinfo=UTC),
    )

    assert params == {
        "created_from": "2026-06-02T15:30:00+00:00",
        "created_to": "2026-06-09T15:30:00+00:00",
        "time_window_disclosure": "Applied semantic time window: last_7_days.",
        "time_window_preset": "last_7_days",
        "time_window_source": "semantic",
    }


@pytest.mark.parametrize(
    ("question", "preset", "created_from", "created_to"),
    [
        (
            "How many leads came in yesterday?",
            "yesterday",
            "2026-06-08T00:00:00+00:00",
            "2026-06-09T00:00:00+00:00",
        ),
        (
            "Сколько консультаций было в прошлом месяце?",
            "last_month",
            "2026-05-01T00:00:00+00:00",
            "2026-06-01T00:00:00+00:00",
        ),
        (
            "Resume la conversion por fuente este trimestre",
            "this_quarter",
            "2026-04-01T00:00:00+00:00",
            "2026-06-09T15:30:00+00:00",
        ),
        (
            "Show treatment revenue last quarter.",
            "last_quarter",
            "2026-01-01T00:00:00+00:00",
            "2026-04-01T00:00:00+00:00",
        ),
        (
            "Сколько лидов пришло за этот год?",
            "this_year",
            "2026-01-01T00:00:00+00:00",
            "2026-06-09T15:30:00+00:00",
        ),
        (
            "Cuantos pagos fueron el año pasado?",
            "last_year",
            "2025-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
        ),
        (
            "Show lead conversion for the last 30 days.",
            "last_30_days",
            "2026-05-10T15:30:00+00:00",
            "2026-06-09T15:30:00+00:00",
        ),
    ],
)
def test_safe_tool_params_derives_multilingual_calendar_windows(
    question: str,
    preset: str,
    created_from: str,
    created_to: str,
) -> None:
    params = agent_runtime_service._safe_tool_params(  # noqa: SLF001
        {},
        question=question,
        now=datetime(2026, 6, 9, 15, 30, tzinfo=UTC),
    )

    assert params == {
        "created_from": created_from,
        "created_to": created_to,
        "time_window_disclosure": f"Applied semantic time window: {preset}.",
        "time_window_preset": preset,
        "time_window_source": "semantic",
    }


def test_safe_tool_params_defaults_to_last_30_days_when_time_missing() -> None:
    params = agent_runtime_service._safe_tool_params(  # noqa: SLF001
        {},
        question="Show lead conversion performance.",
        now=datetime(2026, 6, 9, 15, 30, tzinfo=UTC),
    )

    assert params == {
        "created_from": "2026-05-10T15:30:00+00:00",
        "created_to": "2026-06-09T15:30:00+00:00",
        "time_window_disclosure": (
            "No time period was specified, so this uses the last 30 days."
        ),
        "time_window_preset": "last_30_days",
        "time_window_source": "default",
    }


def test_safe_tool_params_blocks_unsupported_time_expression() -> None:
    with pytest.raises(ValidationError, match="Time expression is not supported"):
        agent_runtime_service._safe_tool_params(  # noqa: SLF001
            {},
            question="Show lead conversion since the office opened.",
            now=datetime(2026, 6, 9, 15, 30, tzinfo=UTC),
        )


def test_manager_query_match_understands_russian_no_show_recovery() -> None:
    match = select_manager_query_match(
        "Сколько пациентов мы вернули на консультацию после того, "
        "как они не пришли за этот месяц?",
    )

    assert match is not None
    assert match.query_id == "consultation_followup_worklist.v1"
    assert match.read_model_id == "consultation_followup"
    assert set(match.matched_keywords) >= {"не приш", "вернул"}


def test_manager_query_match_understands_spanish_paid_source() -> None:
    match = select_manager_query_match(
        "Resume la conversion de leads pagados por fuente este mes",
    )

    assert match is not None
    assert match.query_id == "paid_leads_by_source.v1"
    assert set(match.matched_keywords) >= {"leads pagados", "fuente"}


def test_deterministic_manager_analytics_fallback_replaces_llm_clarification() -> None:
    plan = OpenAIAgentPlanOut(
        model="gpt-4.1-mini",
        last_agent="Fusion Agent Runtime Planner",
        outcome="clarification_required",
        intent="understand manager question",
        tool_id=None,
        tool_arguments={},
        confidence="high",
        clarification_question="Which metric should be used?",
        safety_notes=["LLM asked for clarification."],
    )

    updated = agent_runtime_service._apply_deterministic_manager_analytics_fallback(  # noqa: SLF001
        plan,
        user_prompt=(
            "Сколько пациентов мы вернули на консультацию после того, "
            "как они не пришли за этот месяц?"
        ),
    )

    assert updated.outcome == "tool_plan"
    assert updated.tool_id == "ask_manager_analytics"
    assert updated.tool_arguments == {
        "question": (
            "Сколько пациентов мы вернули на консультацию после того, "
            "как они не пришли за этот месяц?"
        )
    }
    assert updated.clarification_question is None
    assert any(
        "Deterministic approved manager analytics matcher" in note
        for note in updated.safety_notes
    )


@pytest.mark.asyncio
async def test_agent_runtime_openai_check_projects_provider_result(monkeypatch) -> None:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="admin@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    captured: dict[str, object] = {}

    class FakeOpenAIIntegrationService:
        def __init__(self, session):
            captured["session"] = session

        async def test_connection(self, tenant_id_arg):
            captured["tenant_id"] = tenant_id_arg
            return OpenAIConnectionCheckOut(
                ok=True,
                model="gpt-4.1-mini",
                last_agent="Fusion OpenAI Health Check",
                output="ok",
            )

    monkeypatch.setattr(
        "packages.agent_runtime.service.OpenAIIntegrationService",
        FakeOpenAIIntegrationService,
    )

    class FakeRunRepository:
        def __init__(self, session):
            captured["run_repo_session"] = session

        async def add(self, run):
            captured["run"] = run
            return run

    session = MagicMock()
    service = AgentRuntimeService(session)
    service._run_repo = cast(Any, FakeRunRepository(session))  # noqa: SLF001
    result = await service.test_openai_connection(principal)

    assert result.ok is True
    assert result.runtime == "agent_runtime"
    assert result.provider_kind == "openai"
    assert result.credential_kind == "api_key"
    assert result.model == "gpt-4.1-mini"
    assert result.last_agent == "Fusion OpenAI Health Check"
    assert result.output == "ok"
    assert captured["session"] == session
    assert captured["tenant_id"] == tenant_id
    run = captured["run"]
    assert isinstance(run, AgentRuntimeRun)
    assert run.tenant_id == tenant_id
    assert run.trigger_actor_id == principal.id
    assert run.trigger_actor_email == "admin@example.com"
    assert run.agent_name == "Fusion OpenAI Health Check"
    assert run.provider_kind == "openai"
    assert run.model == "gpt-4.1-mini"
    assert run.run_kind == "provider_health_check"
    assert run.status == "success"
    assert run.result_posture == "safe_metadata_only"
    assert run.audit_summary["phi"] is False
    assert "sk-" not in str(run.audit_summary)


@pytest.mark.asyncio
async def test_agent_runtime_openai_check_records_failure_for_not_ok_result(
    monkeypatch,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="admin@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    captured: dict[str, object] = {}

    class FakeOpenAIIntegrationService:
        def __init__(self, session):
            captured["session"] = session

        async def test_connection(self, tenant_id_arg):
            captured["tenant_id"] = tenant_id_arg
            return OpenAIConnectionCheckOut(
                ok=False,
                model="gpt-4.1-mini",
                last_agent="Fusion OpenAI Health Check",
                output="not ok",
            )

    monkeypatch.setattr(
        "packages.agent_runtime.service.OpenAIIntegrationService",
        FakeOpenAIIntegrationService,
    )

    class FakeRunRepository:
        async def add(self, run):
            captured["run"] = run
            return run

    session = MagicMock()
    session.flush = AsyncMock()
    service = AgentRuntimeService(session)
    service._run_repo = cast(Any, FakeRunRepository())  # noqa: SLF001
    result = await service.test_openai_connection(principal)

    assert result.ok is False
    run = captured["run"]
    assert isinstance(run, AgentRuntimeRun)
    assert run.status == "failure"
    assert run.error_code is None
    assert run.error_message is None
    assert run.audit_summary["final_outcome"] == "failed"
    assert run.audit_summary["policy_result"] == "blocked"
    policy_decisions = cast(
        list[dict[str, object]],
        run.audit_summary["policy_decisions"],
    )
    assert policy_decisions[1]["result"] == "blocked"
    assert "not ok" not in str(run.audit_summary)
    assert "sk-" not in str(run.audit_summary)


@pytest.mark.asyncio
async def test_agent_runtime_openai_check_records_failure_for_platform_error(
    monkeypatch,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="admin@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    captured: dict[str, object] = {}

    class FakeOpenAIIntegrationService:
        def __init__(self, session):
            captured["session"] = session

        async def test_connection(self, tenant_id_arg):
            captured["tenant_id"] = tenant_id_arg
            raise ValidationError(
                "OpenAI credential payload is missing api_key",
                details={"provider_kind": "openai"},
            )

    monkeypatch.setattr(
        "packages.agent_runtime.service.OpenAIIntegrationService",
        FakeOpenAIIntegrationService,
    )

    class FakeRunRepository:
        async def add(self, run):
            captured["run"] = run
            return run

    session = MagicMock()
    session.flush = AsyncMock()
    service = AgentRuntimeService(session)
    service._run_repo = cast(Any, FakeRunRepository())  # noqa: SLF001

    with pytest.raises(ValidationError):
        await service.test_openai_connection(principal)

    run = captured["run"]
    assert isinstance(run, AgentRuntimeRun)
    assert run.status == "failure"
    assert run.error_code == "validation_error"
    assert run.error_message == "OpenAI credential payload is missing api_key"
    assert run.audit_summary["final_outcome"] == "failed"
    assert run.audit_summary["policy_result"] == "blocked"
    assert "sk-" not in str(run.audit_summary)


@pytest.mark.asyncio
async def test_agent_runtime_llm_plan_records_safe_success(monkeypatch) -> None:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="manager@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    captured: dict[str, object] = {}

    class FakeOpenAIIntegrationService:
        def __init__(self, session):
            captured["session"] = session

        async def generate_agent_plan(self, tenant_id_arg, payload):
            captured["tenant_id"] = tenant_id_arg
            captured["payload"] = payload
            return OpenAIAgentPlanOut(
                model="gpt-4.1-mini",
                last_agent="Fusion Agent Runtime Planner",
                outcome="tool_plan",
                intent="manager_analytics",
                tool_id="ask_manager_analytics",
                tool_arguments={"question": "lead conversion performance this week"},
                confidence="high",
                safety_notes=["Aggregate-only planning."],
            )

        async def generate_manager_answer(self, tenant_id_arg, payload):
            captured["answer_tenant_id"] = tenant_id_arg
            captured["answer_payload"] = payload
            return OpenAIManagerAnswerOut(
                model="gpt-4.1",
                last_agent="Fusion Manager Answer Generator",
                summary="Lead conversion has scheduled consultations in the aggregate.",
                key_numbers=[
                    {
                        "label": "Scheduled consultations",
                        "value": 2,
                        "unit": "consultations",
                        "comparison": "From the selected aggregate result.",
                    }
                ],
                explanation=(
                    "The answer summarizes the approved aggregate read-model "
                    "execution only."
                ),
                caveats=["No row-level rows are included."],
                confidence="high",
                safety_notes=["Aggregate-only answer."],
            )

    monkeypatch.setattr(
        "packages.agent_runtime.service.OpenAIIntegrationService",
        FakeOpenAIIntegrationService,
    )

    async def fake_ask_manager_analytics(ctx, *, question, params=None, execute=True):
        captured["tool_tenant_id"] = ctx.tenant_id
        captured["tool_question"] = question
        captured["tool_params"] = params
        captured["tool_execute"] = execute
        return {
            "planner": {
                "status": "planned",
                "question": question,
                "query_id": "lead_conversion_funnel.v1",
            },
            "query_spec": {
                "intent": "manager_analytics",
                "query_id": "lead_conversion_funnel.v1",
                "params": params or {},
                "output_level": "aggregate",
            },
            "policy_preflight": {
                "decision": "allow",
                "reason": "Aggregate-only V1 analytics query selected.",
            },
            "execution": {
                "query_id": "lead_conversion_funnel.v1",
                "read_model_id": "lead_conversion",
                "output_type": "aggregate",
                "aggregation_level": "aggregate",
                "data_classes": ["ops", "integration_metadata"],
                "definition_versions": {"lead_source": "v1"},
                "filters": {"limit": 10},
                "row_count": 2,
                "warnings": [],
                "drilldown_available": False,
                "export_available": True,
                "result": {
                    "lead_status": [{"key": "new", "count": 4}],
                    "consultation_status": [{"key": "scheduled", "count": 2}],
                },
            },
            "explanation": (
                "Executed lead_conversion_funnel.v1 for read model lead_conversion. "
                "The result is aggregate-only."
            ),
        }

    monkeypatch.setitem(
        agent_runtime_service.ALL_TOOLS,
        "ask_manager_analytics",
        ToolSpec(
            name="ask_manager_analytics",
            description="Fake aggregate manager analytics tool.",
            fn=fake_ask_manager_analytics,
            touches=frozenset({"ops", "interaction"}),
        ),
    )

    class FakeRunRepository:
        async def add(self, run):
            run.id = uuid.uuid4()
            captured["run"] = run
            return run

    session = MagicMock()
    session.flush = AsyncMock()
    service = AgentRuntimeService(session)
    service._run_repo = cast(Any, FakeRunRepository())  # noqa: SLF001
    result = await service.generate_llm_plan(
        principal,
        AgentRuntimeLlmPlanIn(
            user_prompt="How are lead conversions trending?",
        ),
    )

    assert result.runtime == "agent_runtime"
    assert result.provider_kind == "openai"
    assert result.outcome == "tool_plan"
    assert result.tool_id == "ask_manager_analytics"
    assert result.tool_arguments == {"question": "lead conversion performance this week"}
    assert result.execution_status == "executed"
    assert result.result_posture == "safe_aggregate_tool_execution"
    assert result.execution is not None
    assert result.execution.query_id == "lead_conversion_funnel.v1"
    assert result.execution.read_model_id == "lead_conversion"
    assert result.execution.match_status == "matched"
    assert result.execution.match_confidence == "medium"
    assert result.execution.match_reason is not None
    assert result.execution.matched_keywords == ["conversion"]
    assert result.execution.row_count == 2
    assert result.answer_eligibility is not None
    assert result.answer_eligibility.eligible is True
    assert result.answer_eligibility.query_id == "lead_conversion_funnel.v1"
    assert result.manager_answer is not None
    assert result.manager_answer.status == "generated"
    assert result.manager_answer.model == "gpt-4.1"
    assert result.manager_answer.last_agent == "Fusion Manager Answer Generator"
    assert result.manager_answer.summary is not None
    assert "Applied semantic time window: this_week." in result.manager_answer.caveats
    assert result.manager_answer.source_refs is not None
    assert result.manager_answer.source_refs.query_id == "lead_conversion_funnel.v1"
    assert result.manager_answer.source_refs.read_model_id == "lead_conversion"
    assert result.manager_answer.source_refs.execution_run_id == result.run_id
    assert [widget.widget_type for widget in result.manager_answer.widgets] == [
        "metric",
        "bar_chart",
        "bar_chart",
    ]
    metric_widget = result.manager_answer.widgets[0]
    assert metric_widget.id == "key_number_1"
    assert metric_widget.points[0].label == "Scheduled consultations"
    assert metric_widget.points[0].value == 2
    lead_status_widget = result.manager_answer.widgets[1]
    assert lead_status_widget.id == "lead_status_bar_chart"
    assert lead_status_widget.title == "Lead Status"
    assert lead_status_widget.points[0].label == "new"
    assert lead_status_widget.points[0].value == 4
    assert isinstance(lead_status_widget.points[0].value, int)
    assert lead_status_widget.points[0].evidence_ref == (
        "result.result.lead_status[0].count"
    )
    consultation_widget = result.manager_answer.widgets[2]
    assert consultation_widget.id == "consultation_status_bar_chart"
    assert consultation_widget.points[0].label == "scheduled"
    assert consultation_widget.points[0].value == 2
    assert consultation_widget.points[0].evidence_ref == (
        "result.result.consultation_status[0].count"
    )
    assert captured["tenant_id"] == tenant_id
    assert captured["answer_tenant_id"] == tenant_id
    assert captured["tool_tenant_id"] == tenant_id
    assert captured["tool_question"] == "lead conversion performance this week"
    assert captured["tool_execute"] is True
    tool_params = cast(dict[str, object], captured["tool_params"])
    assert tool_params["time_window_preset"] == "this_week"
    assert tool_params["time_window_source"] == "semantic"
    answer_payload = cast(Any, captured["answer_payload"])
    assert answer_payload.manager_question == "lead conversion performance this week"
    assert answer_payload.tool_id == "ask_manager_analytics"
    assert answer_payload.query_id == "lead_conversion_funnel.v1"
    assert answer_payload.read_model_id == "lead_conversion"
    assert answer_payload.execution_run_id == result.run_id
    assert answer_payload.aggregate_result["query_id"] == "lead_conversion_funnel.v1"
    assert answer_payload.aggregate_result["read_model_id"] == "lead_conversion"
    assert answer_payload.aggregate_result["row_count"] == 2
    assert answer_payload.aggregate_result["time_window"]["preset"] == "this_week"
    assert answer_payload.aggregate_result["filters"]["time_window_preset"] == (
        "this_week"
    )
    assert answer_payload.aggregate_result["result"] == {
        "lead_status": [{"key": "new", "count": 4}],
        "consultation_status": [{"key": "scheduled", "count": 2}],
    }
    assert "raw_sql" not in str(answer_payload)
    assert "raw_provider_payload" not in str(answer_payload)
    plan_payload = cast(Any, captured["payload"])
    assert "ask_manager_analytics" in {tool.id for tool in plan_payload.tools}
    run = captured["run"]
    assert isinstance(run, AgentRuntimeRun)
    assert run.tenant_id == tenant_id
    assert run.trigger_actor_email == "manager@example.com"
    assert run.agent_name == "Fusion Agent Runtime Planner"
    assert run.provider_kind == "openai"
    assert run.model == "gpt-4.1-mini"
    assert run.run_kind == "llm_planning_with_tool_execution"
    assert run.status == "success"
    assert run.result_posture == "safe_aggregate_tool_execution"
    assert run.tool_calls[0]["tool_id"] == "ask_manager_analytics"
    assert run.tool_calls[0]["output_posture"] == "aggregate analytics result"
    assert run.tool_calls[0]["query_id"] == "lead_conversion_funnel.v1"
    assert run.tool_calls[0]["read_model_id"] == "lead_conversion"
    assert run.audit_summary["policy_gate"] == "llm_plan_and_tool_execution"
    assert run.audit_summary["data_level"] == "aggregate_only"
    assert run.audit_summary["query_registry_refs"] == [
        "lead_conversion_funnel.v1"
    ]
    assert run.audit_summary["read_model_refs"] == ["lead_conversion"]
    assert run.audit_summary["approved_catalog_version_refs"] == [
        "consultation_completed:v1",
        "consultation_scheduled:v1",
        "lead_source:v1",
    ]
    assert run.audit_summary["catalog_consumption_status"] == "approved_version_refs"
    answer_audit = cast(dict[str, object], run.audit_summary["answer"])
    answer_source_refs = cast(dict[str, object], answer_audit["source_refs"])
    evidence_refs = cast(list[str], run.audit_summary["evidence_refs"])
    assert answer_audit["status"] == "generated"
    assert answer_audit["eligible"] is True
    assert answer_audit["model"] == "gpt-4.1"
    assert answer_audit["confidence"] == "high"
    assert answer_audit["widget_summary"] == {
        "count": 3,
        "types": ["metric", "bar_chart"],
        "evidence_refs": [
            "manager_answer.key_numbers[0]",
            "result.result.lead_status[0].count",
            "result.result.consultation_status[0].count",
        ],
    }
    assert answer_source_refs["query_id"] == (
        "lead_conversion_funnel.v1"
    )
    assert answer_source_refs["read_model_id"] == (
        "lead_conversion"
    )
    assert answer_source_refs["execution_run_id"] == (
        result.run_id
    )
    assert "manager_answer_contract" in evidence_refs
    assert "manager_answer_llm_generation" in evidence_refs
    assert "manager_answer_widgets" in evidence_refs
    assert "Lead conversion has scheduled consultations" not in str(
        run.audit_summary
    )
    assert "Scheduled consultations" not in str(run.audit_summary)
    assert run.audit_summary["phi"] is False
    assert "How are lead conversions trending?" not in str(run.audit_summary)
    assert "sk-" not in str(run.audit_summary)
    assert "raw_provider_payload" not in str(run.audit_summary)


def test_manager_answer_metric_widgets_skip_non_numeric_key_numbers() -> None:
    answer = OpenAIManagerAnswerOut(
        model="gpt-4.1",
        last_agent="Fusion Manager Answer Generator",
        summary="Lead conversion has aggregate context.",
        key_numbers=[
            {
                "label": "Qualitative status",
                "value": "steady",
                "unit": "status",
            }
        ],
        explanation="The answer summarizes aggregate read-model output only.",
        confidence="medium",
        safety_notes=["Aggregate-only answer."],
    )

    widgets = agent_runtime_service._manager_answer_metric_widgets(  # noqa: SLF001
        answer,
    )

    assert widgets == []


@pytest.mark.asyncio
async def test_agent_runtime_generates_with_caveat_for_aggregate_quality_evidence(
    monkeypatch,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="manager@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    captured: dict[str, object] = {}

    class FakeOpenAIIntegrationService:
        def __init__(self, session):
            captured["session"] = session

        async def generate_agent_plan(self, tenant_id_arg, payload):
            captured["tenant_id"] = tenant_id_arg
            return OpenAIAgentPlanOut(
                model="gpt-4.1-mini",
                last_agent="Fusion Agent Runtime Planner",
                outcome="tool_plan",
                intent="manager_analytics",
                tool_id="ask_manager_analytics",
                tool_arguments={
                    "question": "paid leads by source this week"
                },
                confidence="high",
            )

        async def generate_manager_answer(self, tenant_id_arg, payload):
            captured["answer_tenant_id"] = tenant_id_arg
            captured["answer_payload"] = payload
            return OpenAIManagerAnswerOut(
                model="gpt-4.1",
                last_agent="Fusion Manager Answer Generator",
                summary="Paid leads are summarized by source with data-quality caveats.",
                key_numbers=[
                    {
                        "label": "Paid leads",
                        "value": 12,
                        "unit": "leads",
                    }
                ],
                explanation="The answer uses aggregate read-model output only.",
                caveats=["Use attribution caveats."],
                confidence="medium",
                safety_notes=["Aggregate-only answer."],
            )

    monkeypatch.setattr(
        "packages.agent_runtime.service.OpenAIIntegrationService",
        FakeOpenAIIntegrationService,
    )

    async def fake_ask_manager_analytics(ctx, *, question, params=None, execute=True):
        return {
            "planner": {
                "status": "planned",
                "question": question,
                "query_id": "paid_leads_by_source.v1",
            },
            "query_spec": {
                "intent": "manager_analytics",
                "query_id": "paid_leads_by_source.v1",
                "params": params or {},
                "output_level": "aggregate",
            },
            "policy_preflight": {
                "decision": "allow",
                "reason": "Aggregate-only V1 analytics query selected.",
            },
            "execution": {
                "query_id": "paid_leads_by_source.v1",
                "read_model_id": "paid_leads",
                "output_type": "aggregate",
                "aggregation_level": "aggregate",
                "data_classes": ["ops", "integration_metadata"],
                "definition_versions": {"lead_source": "v1"},
                "filters": {"limit": 10},
                "row_count": 1,
                "warnings": [
                    "Some lead source values are unmapped and require catalog review."
                ],
                "data_quality_evidence_refs": [
                    "lead.lead_source",
                    "lead.campaign",
                ],
                "data_quality_evidence": {
                    "refs": ["lead.lead_source", "lead.campaign"],
                    "metrics": [
                        {
                            "id": "source_attribution_coverage",
                            "label": "Source attribution coverage",
                            "value": 0.8,
                            "unit": "ratio",
                            "numerator": 8,
                            "denominator": 10,
                            "status": "caveat",
                            "evidence_ref": "lead.lead_source",
                        }
                    ],
                    "caveats": [
                        "2 lead aggregate rows lack approved source attribution."
                    ],
                    "blockers": [],
                },
                "drilldown_available": False,
                "export_available": True,
                "result": {
                    "sources": [{"key": "paid_social/facebook", "count": 12}],
                },
            },
            "explanation": "Executed approved aggregate analytics query.",
        }

    monkeypatch.setitem(
        agent_runtime_service.ALL_TOOLS,
        "ask_manager_analytics",
        ToolSpec(
            name="ask_manager_analytics",
            description="Fake aggregate manager analytics tool.",
            fn=fake_ask_manager_analytics,
            touches=frozenset({"ops", "interaction"}),
        ),
    )

    class FakeRunRepository:
        async def add(self, run):
            run.id = uuid.uuid4()
            captured["run"] = run
            return run

    session = MagicMock()
    session.flush = AsyncMock()
    service = AgentRuntimeService(session)
    service._run_repo = cast(Any, FakeRunRepository())  # noqa: SLF001
    result = await service.generate_llm_plan(
        principal,
        AgentRuntimeLlmPlanIn(user_prompt="Show paid leads by source."),
    )

    assert result.answer_eligibility is not None
    assert result.answer_eligibility.eligible is True
    assert result.answer_eligibility.answer_posture == "generated_with_caveat"
    assert result.answer_eligibility.data_quality_evidence_refs == [
        "lead.lead_source",
        "lead.campaign",
        "aggregate_read_model_data_quality_metrics",
        "aggregate_execution_warnings",
    ]
    assert len(result.answer_eligibility.data_quality_metrics) == 1
    assert result.answer_eligibility.data_quality_metrics[0].id == (
        "source_attribution_coverage"
    )
    assert result.answer_eligibility.data_quality_metrics[0].status == "caveat"
    assert result.manager_answer is not None
    assert result.manager_answer.status == "generated_with_caveat"
    assert "Some lead source values are unmapped" in " ".join(
        result.manager_answer.caveats
    )
    answer_payload = cast(Any, captured["answer_payload"])
    assert "Some lead source values are unmapped" in " ".join(
        answer_payload.caveats
    )
    assert answer_payload.aggregate_result["time_window"]["preset"] == "this_week"

    run = captured["run"]
    assert isinstance(run, AgentRuntimeRun)
    answer_audit = cast(dict[str, object], run.audit_summary["answer"])
    assert answer_audit["status"] == "generated_with_caveat"
    assert answer_audit["answer_posture"] == "generated_with_caveat"
    assert answer_audit["data_quality_evidence_refs"] == [
        "lead.lead_source",
        "lead.campaign",
        "aggregate_read_model_data_quality_metrics",
        "aggregate_execution_warnings",
    ]
    answer_metrics = cast(list[dict[str, object]], answer_audit["data_quality_metrics"])
    assert answer_metrics[0]["id"] == "source_attribution_coverage"
    evidence_refs = cast(list[str], run.audit_summary["evidence_refs"])
    assert "manager_answer_data_quality_caveats" in evidence_refs
    policy_decisions = cast(
        list[dict[str, object]],
        run.audit_summary["policy_decisions"],
    )
    quality_gate = next(
        item
        for item in policy_decisions
        if item["gate_id"] == "aggregate_read_model_data_quality"
    )
    assert quality_gate["result"] == "allowed"


@pytest.mark.asyncio
async def test_agent_runtime_blocks_answer_for_quality_metric_blocker(
    monkeypatch,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="manager@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    captured: dict[str, object] = {"answer_called": False}

    class FakeOpenAIIntegrationService:
        def __init__(self, session):
            captured["session"] = session

        async def generate_agent_plan(self, tenant_id_arg, payload):
            captured["tenant_id"] = tenant_id_arg
            return OpenAIAgentPlanOut(
                model="gpt-4.1-mini",
                last_agent="Fusion Agent Runtime Planner",
                outcome="tool_plan",
                intent="manager_analytics",
                tool_id="ask_manager_analytics",
                tool_arguments={"question": "paid leads by source this week"},
                confidence="high",
            )

        async def generate_manager_answer(self, tenant_id_arg, payload):
            captured["answer_called"] = True
            raise AssertionError("Data-quality blockers must not generate answers")

    monkeypatch.setattr(
        "packages.agent_runtime.service.OpenAIIntegrationService",
        FakeOpenAIIntegrationService,
    )

    async def fake_ask_manager_analytics(ctx, *, question, params=None, execute=True):
        return {
            "planner": {
                "status": "planned",
                "question": question,
                "query_id": "paid_leads_by_source.v1",
            },
            "query_spec": {
                "intent": "manager_analytics",
                "query_id": "paid_leads_by_source.v1",
                "params": params or {},
                "output_level": "aggregate",
            },
            "policy_preflight": {
                "decision": "allow",
                "reason": "Aggregate-only V1 analytics query selected.",
            },
            "execution": {
                "query_id": "paid_leads_by_source.v1",
                "read_model_id": "paid_leads",
                "output_type": "aggregate",
                "aggregation_level": "aggregate",
                "data_classes": ["ops", "integration_metadata"],
                "definition_versions": {"paid_lead": "v1", "lead_source": "v1"},
                "filters": {"limit": 10},
                "row_count": 1,
                "warnings": [],
                "data_quality_evidence": {
                    "refs": ["lead.person_uid"],
                    "metrics": [
                        {
                            "id": "identity_linkage_coverage",
                            "label": "Identity linkage coverage",
                            "value": 0.5,
                            "unit": "ratio",
                            "numerator": 5,
                            "denominator": 10,
                            "status": "blocked",
                            "evidence_ref": "lead.person_uid",
                        }
                    ],
                    "caveats": [],
                    "blockers": [
                        "Lead read-model identity linkage coverage is incomplete; manager answer generation is blocked."
                    ],
                },
                "drilldown_available": False,
                "export_available": True,
                "result": {
                    "sources": [{"key": "paid_social/facebook", "count": 12}],
                },
            },
            "explanation": "Executed approved aggregate analytics query.",
        }

    monkeypatch.setitem(
        agent_runtime_service.ALL_TOOLS,
        "ask_manager_analytics",
        ToolSpec(
            name="ask_manager_analytics",
            description="Fake aggregate manager analytics tool.",
            fn=fake_ask_manager_analytics,
            touches=frozenset({"ops", "interaction"}),
        ),
    )

    class FakeRunRepository:
        async def add(self, run):
            run.id = uuid.uuid4()
            captured["run"] = run
            return run

    session = MagicMock()
    session.flush = AsyncMock()
    service = AgentRuntimeService(session)
    service._run_repo = cast(Any, FakeRunRepository())  # noqa: SLF001
    result = await service.generate_llm_plan(
        principal,
        AgentRuntimeLlmPlanIn(user_prompt="Show paid leads by source."),
    )

    assert result.execution_status == "executed"
    assert result.answer_eligibility is not None
    assert result.answer_eligibility.eligible is False
    assert result.answer_eligibility.answer_posture == "blocked"
    assert result.answer_eligibility.data_quality_metrics[0].status == "blocked"
    assert "identity linkage coverage is incomplete" in (
        result.answer_eligibility.reason
    )
    assert result.manager_answer is not None
    assert result.manager_answer.status == "not_generated"
    assert captured["answer_called"] is False
    run = captured["run"]
    assert isinstance(run, AgentRuntimeRun)
    answer_audit = cast(dict[str, object], run.audit_summary["answer"])
    assert answer_audit["eligible"] is False
    assert answer_audit["answer_posture"] == "blocked"
    answer_metrics = cast(list[dict[str, object]], answer_audit["data_quality_metrics"])
    assert answer_metrics[0]["status"] == "blocked"
    policy_decisions = cast(
        list[dict[str, object]],
        run.audit_summary["policy_decisions"],
    )
    quality_gate = next(
        item
        for item in policy_decisions
        if item["gate_id"] == "aggregate_read_model_data_quality"
    )
    assert quality_gate["result"] == "blocked"


def test_manager_answer_correctness_metrics_detect_appointment_threshold() -> None:
    execution = _manager_answer_aggregate_execution(
        {
            "appointment_status": [{"key": "scheduled", "count": 50_000}],
        }
    )

    metrics = agent_runtime_service._manager_answer_correctness_metrics(  # noqa: SLF001
        execution,
    )

    assert len(metrics) == 1
    metric = metrics[0]
    assert metric.id == "suspicious_consultation_aggregate_count"
    assert metric.status == "blocked"
    assert metric.value == 50_000
    assert metric.denominator == 50_000
    assert metric.evidence_ref == "result.result.appointment_status[0].count"


def test_manager_answer_correctness_metrics_keep_multiple_refs_ordered() -> None:
    execution = _manager_answer_aggregate_execution(
        {
            "consultation_status": [
                {"key": "scheduled", "count": 91_000},
                {"key": "completed", "count": 92_000},
            ],
            "appointment_status": [{"key": "booked", "count": 50_000}],
        },
        time_window={
            "source": "semantic",
            "preset": "this_month",
            "created_from": "2026-06-01T00:00:00+00:00",
            "created_to": "2026-06-15T12:00:00+00:00",
            "disclosure": "Applied semantic time window: this_month.",
        },
    )

    metrics = agent_runtime_service._manager_answer_correctness_metrics(  # noqa: SLF001
        execution,
    )

    assert [metric.evidence_ref for metric in metrics] == [
        "result.result.consultation_status[0].count",
        "result.result.consultation_status[1].count",
        "result.result.appointment_status[0].count",
    ]
    refs = agent_runtime_service._manager_answer_correctness_evidence_refs(  # noqa: SLF001
        [*metrics, metrics[0]],
    )
    assert refs == [
        "aggregate_correctness_guardrails",
        "result.result.consultation_status[0].count",
        "result.result.consultation_status[1].count",
        "result.result.appointment_status[0].count",
    ]
    blockers = agent_runtime_service._manager_answer_correctness_blockers(  # noqa: SLF001
        execution,
    )
    assert len(blockers) == 3
    assert "appointment_status[0].count`=50000" in blockers[2]


def test_manager_answer_correctness_metrics_ignore_below_threshold_counts() -> None:
    execution = _manager_answer_aggregate_execution(
        {
            "consultation_status": [{"key": "scheduled", "count": 49_999}],
            "appointment_status": [{"key": "booked", "count": 49_999}],
        }
    )

    metrics = agent_runtime_service._manager_answer_correctness_metrics(  # noqa: SLF001
        execution,
    )

    assert metrics == []


@pytest.mark.asyncio
async def test_agent_runtime_blocks_suspicious_consultation_totals_before_answer(
    monkeypatch,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="manager@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    captured: dict[str, object] = {"answer_called": False}

    class FakeOpenAIIntegrationService:
        def __init__(self, session):
            captured["session"] = session

        async def generate_agent_plan(self, tenant_id_arg, payload):
            captured["tenant_id"] = tenant_id_arg
            return OpenAIAgentPlanOut(
                model="gpt-4.1-mini",
                last_agent="Fusion Agent Runtime Planner",
                outcome="tool_plan",
                intent="manager_analytics",
                tool_id="ask_manager_analytics",
                tool_arguments={
                    "question": "lead conversion performance this month"
                },
                confidence="high",
            )

        async def generate_manager_answer(self, tenant_id_arg, payload):
            captured["answer_called"] = True
            raise AssertionError("Suspicious aggregates must not generate answers")

    monkeypatch.setattr(
        "packages.agent_runtime.service.OpenAIIntegrationService",
        FakeOpenAIIntegrationService,
    )

    async def fake_ask_manager_analytics(ctx, *, question, params=None, execute=True):
        return {
            "planner": {
                "status": "planned",
                "question": question,
                "query_id": "lead_conversion_funnel.v1",
            },
            "query_spec": {
                "intent": "manager_analytics",
                "query_id": "lead_conversion_funnel.v1",
                "params": params or {},
                "output_level": "aggregate",
            },
            "policy_preflight": {
                "decision": "allow",
                "reason": "Aggregate-only V1 analytics query selected.",
            },
            "execution": {
                "query_id": "lead_conversion_funnel.v1",
                "read_model_id": "lead_conversion",
                "output_type": "aggregate",
                "aggregation_level": "aggregate",
                "data_classes": ["ops", "integration_metadata"],
                "definition_versions": {"lead_source": "v1"},
                "filters": {"limit": 10},
                "row_count": 2,
                "warnings": [],
                "drilldown_available": False,
                "export_available": True,
                "result": {
                    "lead_status": [{"key": "new", "count": 4}],
                    "consultation_status": [
                        {"key": "scheduled", "count": 91_000}
                    ],
                },
            },
            "explanation": "Executed approved aggregate analytics query.",
        }

    monkeypatch.setitem(
        agent_runtime_service.ALL_TOOLS,
        "ask_manager_analytics",
        ToolSpec(
            name="ask_manager_analytics",
            description="Fake aggregate manager analytics tool.",
            fn=fake_ask_manager_analytics,
            touches=frozenset({"ops", "interaction"}),
        ),
    )

    class FakeRunRepository:
        async def add(self, run):
            run.id = uuid.uuid4()
            captured["run"] = run
            return run

    session = MagicMock()
    session.flush = AsyncMock()
    service = AgentRuntimeService(session)
    service._run_repo = cast(Any, FakeRunRepository())  # noqa: SLF001
    result = await service.generate_llm_plan(
        principal,
        AgentRuntimeLlmPlanIn(user_prompt="How are lead conversions this month?"),
    )

    assert result.execution_status == "executed"
    assert result.answer_eligibility is not None
    assert result.answer_eligibility.eligible is False
    assert "consultation aggregate" in result.answer_eligibility.reason
    assert result.answer_eligibility.data_quality_evidence_refs == [
        "aggregate_correctness_guardrails",
        "result.result.consultation_status[0].count",
    ]
    assert len(result.answer_eligibility.data_quality_metrics) == 1
    correctness_metric = result.answer_eligibility.data_quality_metrics[0]
    assert correctness_metric.id == "suspicious_consultation_aggregate_count"
    assert correctness_metric.status == "blocked"
    assert correctness_metric.value == 91_000
    assert correctness_metric.denominator == 50_000
    assert correctness_metric.evidence_ref == (
        "result.result.consultation_status[0].count"
    )
    assert result.manager_answer is not None
    assert result.manager_answer.status == "not_generated"
    assert captured["answer_called"] is False
    run = captured["run"]
    assert isinstance(run, AgentRuntimeRun)
    answer_audit = cast(dict[str, object], run.audit_summary["answer"])
    assert answer_audit["eligible"] is False
    assert "consultation aggregate" in str(answer_audit["reason"])
    assert answer_audit["data_quality_evidence_refs"] == [
        "aggregate_correctness_guardrails",
        "result.result.consultation_status[0].count",
    ]
    answer_metrics = cast(list[dict[str, object]], answer_audit["data_quality_metrics"])
    assert answer_metrics == [
        {
            "id": "suspicious_consultation_aggregate_count",
            "label": "Suspicious consultation aggregate count",
            "value": 91_000.0,
            "unit": "count",
            "numerator": None,
            "denominator": 50_000.0,
            "status": "blocked",
            "evidence_ref": "result.result.consultation_status[0].count",
        }
    ]
    evidence_refs = cast(list[str], run.audit_summary["evidence_refs"])
    assert "aggregate_correctness_guardrails" in evidence_refs


@pytest.mark.asyncio
async def test_agent_runtime_llm_plan_executes_direct_analytics_query_tool(
    monkeypatch,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="manager@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    captured: dict[str, object] = {}

    class FakeOpenAIIntegrationService:
        def __init__(self, session):
            captured["session"] = session

        async def generate_agent_plan(self, tenant_id_arg, payload):
            captured["tenant_id"] = tenant_id_arg
            return OpenAIAgentPlanOut(
                model="gpt-4.1-mini",
                last_agent="Fusion Agent Runtime Planner",
                outcome="tool_plan",
                intent="manager_analytics_query",
                tool_id="run_analytics_query",
                tool_arguments={
                    "query_id": "paid_leads",
                    "params": {"source_provider": "google"},
                },
                confidence="high",
                safety_notes=["Aggregate-only query id selected."],
            )

    monkeypatch.setattr(
        "packages.agent_runtime.service.OpenAIIntegrationService",
        FakeOpenAIIntegrationService,
    )

    async def fake_run_analytics_query(ctx, *, query_id, params=None):
        captured["tool_tenant_id"] = ctx.tenant_id
        captured["query_id"] = query_id
        captured["params"] = params
        return {
            "query_id": "paid_leads_by_source.v1",
            "read_model_id": "paid_leads",
            "output_type": "aggregate",
            "aggregation_level": "aggregate",
            "data_classes": ["ops", "integration_metadata"],
            "definition_versions": {"paid_lead": "v1", "lead_source": "v1"},
            "filters": {"source_provider": "google"},
            "row_count": 1,
            "warnings": [],
            "drilldown_available": False,
            "export_available": True,
            "result": {"sources": [{"source": "google", "count": 7}]},
        }

    monkeypatch.setitem(
        agent_runtime_service.ALL_TOOLS,
        "run_analytics_query",
        ToolSpec(
            name="run_analytics_query",
            description="Fake approved analytics query tool.",
            fn=fake_run_analytics_query,
            touches=frozenset({"ops", "interaction"}),
        ),
    )

    class FakeRunRepository:
        async def add(self, run):
            run.id = uuid.uuid4()
            captured["run"] = run
            return run

    session = MagicMock()
    session.flush = AsyncMock()
    service = AgentRuntimeService(session)
    service._run_repo = cast(Any, FakeRunRepository())  # noqa: SLF001
    result = await service.generate_llm_plan(
        principal,
        AgentRuntimeLlmPlanIn(user_prompt="Run paid leads by source."),
    )

    assert result.tool_id == "run_analytics_query"
    assert result.execution_status == "executed"
    assert result.execution is not None
    assert result.execution.query_id == "paid_leads_by_source.v1"
    assert result.execution.read_model_id == "paid_leads"
    assert result.execution.match_status == "matched"
    assert result.execution.match_confidence == "high"
    assert result.execution.matched_keywords == [
        "paid_leads_by_source.v1",
        "paid_leads",
    ]
    assert captured["query_id"] == "paid_leads_by_source.v1"
    params = cast(dict[str, object], captured["params"])
    assert params["source_provider"] == "google"
    assert params["time_window_preset"] == "last_30_days"
    assert params["time_window_source"] == "default"
    run = captured["run"]
    assert isinstance(run, AgentRuntimeRun)
    assert run.run_kind == "llm_planning_with_tool_execution"
    assert run.status == "success"
    assert run.tool_calls[0]["tool_id"] == "run_analytics_query"
    assert run.tool_calls[0]["query_id"] == "paid_leads_by_source.v1"
    assert run.tool_calls[0]["read_model_id"] == "paid_leads"
    assert run.audit_summary["policy_gate"] == "llm_plan_and_tool_execution"
    policy_decisions = cast(list[dict[str, object]], run.audit_summary["policy_decisions"])
    assert "approved_query_read_model_match" in {
        item["gate_id"] for item in policy_decisions
    }


@pytest.mark.asyncio
async def test_agent_runtime_llm_plan_leaves_planning_only_tool_unexecuted(
    monkeypatch,
) -> None:
    result, run = await _run_llm_plan_with_fake_plan(
        monkeypatch,
        OpenAIAgentPlanOut(
            model="gpt-4.1-mini",
            last_agent="Fusion Agent Runtime Planner",
            outcome="tool_plan",
            intent="data_intelligence_discovery",
            tool_id="data_intelligence_discover",
            tool_arguments={"dataset": "salesforce_leads"},
            confidence="medium",
        ),
    )

    assert result.policy_result == "allowed"
    assert result.execution_status == "not_executed"
    assert result.execution is None
    assert run.status == "success"
    assert run.run_kind == "llm_planning"
    assert run.tool_calls[0]["status"] == "success"
    assert "no approved Agent Runtime execution adapter" in str(
        run.audit_summary["policy_reason"]
    )


@pytest.mark.asyncio
async def test_agent_runtime_llm_plan_stops_unmatched_question_before_tool_execution(
    monkeypatch,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="manager@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    captured: dict[str, object] = {"tool_called": False}

    class FakeOpenAIIntegrationService:
        def __init__(self, session):
            captured["session"] = session

        async def generate_agent_plan(self, tenant_id_arg, payload):
            captured["tenant_id"] = tenant_id_arg
            return OpenAIAgentPlanOut(
                model="gpt-4.1-mini",
                last_agent="Fusion Agent Runtime Planner",
                outcome="tool_plan",
                intent="manager_analytics",
                tool_id="ask_manager_analytics",
                tool_arguments={"question": "show overall performance"},
                confidence="medium",
            )

    monkeypatch.setattr(
        "packages.agent_runtime.service.OpenAIIntegrationService",
        FakeOpenAIIntegrationService,
    )

    async def fake_ask_manager_analytics(ctx, *, question, params=None, execute=True):
        captured["tool_called"] = True
        raise AssertionError("unmatched questions must stop before tool execution")

    monkeypatch.setitem(
        agent_runtime_service.ALL_TOOLS,
        "ask_manager_analytics",
        ToolSpec(
            name="ask_manager_analytics",
            description="Fake aggregate manager analytics tool.",
            fn=fake_ask_manager_analytics,
            touches=frozenset({"ops", "interaction"}),
        ),
    )

    class FakeRunRepository:
        async def add(self, run):
            run.id = uuid.uuid4()
            captured["run"] = run
            return run

    session = MagicMock()
    session.flush = AsyncMock()
    service = AgentRuntimeService(session)
    service._run_repo = cast(Any, FakeRunRepository())  # noqa: SLF001
    result = await service.generate_llm_plan(
        principal,
        AgentRuntimeLlmPlanIn(user_prompt="Show performance."),
    )

    assert captured["tool_called"] is False
    assert result.execution_status == "no_match"
    assert result.execution is not None
    assert result.execution.match_status == "no_match"
    assert result.execution.query_id is None
    assert result.execution.read_model_id is None
    run = captured["run"]
    assert isinstance(run, AgentRuntimeRun)
    assert run.status == "blocked"
    assert run.tool_calls[0]["status"] == "blocked"
    assert run.audit_summary["policy_gate"] == "llm_plan_contract"


@pytest.mark.asyncio
async def test_agent_runtime_llm_plan_fails_when_tool_execution_drifts_from_match(
    monkeypatch,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="manager@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    captured: dict[str, object] = {}

    class FakeOpenAIIntegrationService:
        def __init__(self, session):
            captured["session"] = session

        async def generate_agent_plan(self, tenant_id_arg, payload):
            captured["tenant_id"] = tenant_id_arg
            return OpenAIAgentPlanOut(
                model="gpt-4.1-mini",
                last_agent="Fusion Agent Runtime Planner",
                outcome="tool_plan",
                intent="manager_analytics",
                tool_id="ask_manager_analytics",
                tool_arguments={"question": "paid leads from Google this month"},
                confidence="high",
            )

    monkeypatch.setattr(
        "packages.agent_runtime.service.OpenAIIntegrationService",
        FakeOpenAIIntegrationService,
    )

    async def fake_ask_manager_analytics(ctx, *, question, params=None, execute=True):
        return {
            "planner": {
                "status": "planned",
                "question": question,
                "query_id": "lead_conversion_funnel.v1",
            },
            "query_spec": {
                "intent": "manager_analytics",
                "query_id": "lead_conversion_funnel.v1",
                "params": params or {},
                "output_level": "aggregate",
            },
            "policy_preflight": {"decision": "allow", "reason": "Allowed."},
            "execution": {
                "query_id": "lead_conversion_funnel.v1",
                "read_model_id": "lead_conversion",
                "output_type": "aggregate",
                "aggregation_level": "aggregate",
                "data_classes": ["ops", "integration_metadata"],
                "definition_versions": {"lead_source": "v1"},
                "filters": {"limit": 10},
                "row_count": 1,
                "warnings": [],
                "drilldown_available": False,
                "export_available": True,
                "result": {"lead_status": [{"key": "new", "count": 4}]},
            },
            "explanation": "Executed approved aggregate analytics query.",
        }

    monkeypatch.setitem(
        agent_runtime_service.ALL_TOOLS,
        "ask_manager_analytics",
        ToolSpec(
            name="ask_manager_analytics",
            description="Fake aggregate manager analytics tool.",
            fn=fake_ask_manager_analytics,
            touches=frozenset({"ops", "interaction"}),
        ),
    )

    class FakeRunRepository:
        async def add(self, run):
            run.id = uuid.uuid4()
            captured["run"] = run
            return run

    session = MagicMock()
    session.flush = AsyncMock()
    service = AgentRuntimeService(session)
    service._run_repo = cast(Any, FakeRunRepository())  # noqa: SLF001
    result = await service.generate_llm_plan(
        principal,
        AgentRuntimeLlmPlanIn(user_prompt="Paid lead performance."),
    )

    assert result.execution_status == "failed"
    assert result.execution is not None
    assert result.execution.match_status == "matched"
    assert result.execution.query_id == "paid_leads_by_source.v1"
    assert result.execution.read_model_id == "paid_leads"
    assert result.execution.result is None
    run = captured["run"]
    assert isinstance(run, AgentRuntimeRun)
    assert run.status == "failure"
    assert run.error_code == "analytics_query_match_drift"
    assert run.tool_calls[0]["query_id"] == "paid_leads_by_source.v1"
    answer_audit = cast(dict[str, object], run.audit_summary["answer"])
    assert answer_audit["status"] == "not_generated"
    assert answer_audit["eligible"] is False
    assert answer_audit["reason"] == (
        "Manager answer generation requires executed aggregate output."
    )


@pytest.mark.asyncio
async def test_agent_runtime_llm_plan_blocks_execution_without_safe_question(
    monkeypatch,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="manager@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    captured: dict[str, object] = {}

    class FakeOpenAIIntegrationService:
        def __init__(self, session):
            captured["session"] = session

        async def generate_agent_plan(self, tenant_id_arg, payload):
            captured["tenant_id"] = tenant_id_arg
            return OpenAIAgentPlanOut(
                model="gpt-4.1-mini",
                last_agent="Fusion Agent Runtime Planner",
                outcome="tool_plan",
                intent="manager_analytics",
                tool_id="ask_manager_analytics",
                tool_arguments={"question_kind": "lead_conversion"},
                confidence="high",
            )

    monkeypatch.setattr(
        "packages.agent_runtime.service.OpenAIIntegrationService",
        FakeOpenAIIntegrationService,
    )

    class FakeRunRepository:
        async def add(self, run):
            run.id = uuid.uuid4()
            captured["run"] = run
            return run

    session = MagicMock()
    session.flush = AsyncMock()
    service = AgentRuntimeService(session)
    service._run_repo = cast(Any, FakeRunRepository())  # noqa: SLF001
    result = await service.generate_llm_plan(
        principal,
        AgentRuntimeLlmPlanIn(
            user_prompt="Which aggregate manager analytics tool should answer conversion?",
        ),
    )

    assert result.policy_result == "allowed"
    assert result.execution_status == "no_match"
    assert result.execution is not None
    assert result.execution.status == "no_match"
    assert result.execution.result is None
    run = captured["run"]
    assert isinstance(run, AgentRuntimeRun)
    assert run.status == "blocked"
    assert run.result_posture == "safe_llm_plan_metadata_only"
    assert run.audit_summary["policy_gate"] == "llm_plan_contract"
    assert run.audit_summary["data_level"] == "metadata_only"
    assert "raw_sql" not in str(run.audit_summary)


@pytest.mark.asyncio
async def test_agent_runtime_llm_plan_records_safe_failure(monkeypatch) -> None:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="manager@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    captured: dict[str, object] = {}

    class FakeOpenAIIntegrationService:
        def __init__(self, session):
            captured["session"] = session

        async def generate_agent_plan(self, tenant_id_arg, payload):
            captured["tenant_id"] = tenant_id_arg
            raise ValidationError(
                "OpenAI planning response did not match the safe plan contract",
                details={"provider_kind": "openai"},
            )

    monkeypatch.setattr(
        "packages.agent_runtime.service.OpenAIIntegrationService",
        FakeOpenAIIntegrationService,
    )

    class FakeRunRepository:
        async def add(self, run):
            run.id = uuid.uuid4()
            captured["run"] = run
            return run

    service = AgentRuntimeService(MagicMock())
    service._run_repo = cast(Any, FakeRunRepository())  # noqa: SLF001

    with pytest.raises(ValidationError):
        await service.generate_llm_plan(
            principal,
            AgentRuntimeLlmPlanIn(user_prompt="Plan a safe aggregate answer."),
        )

    run = captured["run"]
    assert isinstance(run, AgentRuntimeRun)
    assert run.status == "failure"
    assert run.error_code == "validation_error"
    assert run.result_posture == "safe_llm_plan_metadata_only"
    assert run.audit_summary["policy_result"] == "blocked"
    assert run.audit_summary["final_outcome"] == "failed"
    assert "Plan a safe aggregate answer." not in str(run.audit_summary)
    assert "sk-" not in str(run.audit_summary)


@pytest.mark.asyncio
async def test_agent_runtime_llm_plan_denies_phi_tool(monkeypatch) -> None:
    result, run = await _run_llm_plan_with_fake_plan(
        monkeypatch,
        OpenAIAgentPlanOut(
            model="gpt-4.1-mini",
            last_agent="Fusion Agent Runtime Planner",
            outcome="tool_plan",
            intent="clinical_snapshot",
            tool_id="get_phi_person_snapshot",
            tool_arguments={"person_uid": "00000000-0000-0000-0000-000000000000"},
            confidence="medium",
        ),
    )

    assert result.policy_result == "denied"
    assert result.approval_required is False
    assert "PHI-bearing tools" in result.policy_reason
    assert run.status == "denied"
    assert run.audit_summary["policy_result"] == "denied"
    assert run.audit_summary["final_outcome"] == "denied"
    assert run.audit_summary["phi"] is True
    assert run.tool_calls[0]["status"] == "denied"


@pytest.mark.asyncio
async def test_agent_runtime_llm_plan_requires_approval_for_export_tool(
    monkeypatch,
) -> None:
    approvals: list[AgentRuntimeApprovalRequest] = []
    result, run = await _run_llm_plan_with_fake_plan(
        monkeypatch,
        OpenAIAgentPlanOut(
            model="gpt-4.1-mini",
            last_agent="Fusion Agent Runtime Planner",
            outcome="tool_plan",
            intent="export_report",
            tool_id="export_analytics_csv",
            tool_arguments={"query_id": "lead_conversion"},
            confidence="medium",
        ),
        approval_sink=approvals,
    )

    assert result.policy_result == "approval_required"
    assert result.approval_required is True
    assert "requires human approval" in result.policy_reason
    assert run.status == "approval_required"
    assert run.audit_summary["approval_required"] is True
    assert run.audit_summary["final_outcome"] == "approval_required"
    assert run.audit_summary["export"] is True
    assert run.tool_calls[0]["status"] == "approval_required"
    assert len(approvals) == 1
    approval = approvals[0]
    assert approval.source_run_id == run.id
    assert approval.status == "pending"
    assert approval.target_kind == "export_request"
    assert approval.target_ref == "lead_conversion"
    assert approval.tool_id == "export_analytics_csv"
    assert approval.approval_posture == "human_review_required_no_auto_execution"
    linked_approval_ids = cast(
        list[str],
        run.audit_summary["linked_approval_request_ids"],
    )
    assert str(approval.id) in linked_approval_ids
    assert run.tool_calls[0]["approval_request_id"] == str(approval.id)


@pytest.mark.asyncio
async def test_agent_runtime_llm_plan_blocks_non_aggregate_tool(monkeypatch) -> None:
    result, run = await _run_llm_plan_with_fake_plan(
        monkeypatch,
        OpenAIAgentPlanOut(
            model="gpt-4.1-mini",
            last_agent="Fusion Agent Runtime Planner",
            outcome="tool_plan",
            intent="resolve_person",
            tool_id="resolve_person",
            tool_arguments={"email": "example@example.com"},
            confidence="medium",
        ),
    )

    assert result.policy_result == "blocked"
    assert result.approval_required is False
    assert "aggregate-only" in result.policy_reason
    assert run.status == "blocked"
    assert run.audit_summary["policy_result"] == "blocked"
    assert run.audit_summary["final_outcome"] == "blocked"
    assert run.tool_calls[0]["status"] == "blocked"


@pytest.mark.asyncio
async def test_agent_runtime_llm_plan_blocks_clarification(monkeypatch) -> None:
    result, run = await _run_llm_plan_with_fake_plan(
        monkeypatch,
        OpenAIAgentPlanOut(
            model="gpt-4.1-mini",
            last_agent="Fusion Agent Runtime Planner",
            outcome="clarification_required",
            intent="ambiguous_analytics",
            confidence="low",
            clarification_question="Which time period should be used?",
        ),
    )

    assert result.policy_result == "blocked"
    assert result.tool_id is None
    assert result.clarification_question == "Which time period should be used?"
    assert run.status == "blocked"
    assert run.tool_calls == []
    assert run.audit_summary["final_outcome"] == "blocked"


@pytest.mark.parametrize(
    (
        "sample_prompt",
        "provider_plan",
        "expected_policy_result",
        "expected_run_status",
        "expected_final_outcome",
        "expected_approval_required",
    ),
    [
        (
            "Which aggregate manager analytics tool should answer lead conversion performance?",
            OpenAIAgentPlanOut(
                model="gpt-4.1-mini",
                last_agent="Fusion Agent Runtime Planner",
                outcome="tool_plan",
                intent="manager_analytics_aggregate_question",
                tool_id="ask_manager_analytics",
                tool_arguments={"question": "lead conversion performance"},
                confidence="high",
                safety_notes=["Aggregate-only planning."],
            ),
            "allowed",
            "success",
            "completed",
            False,
        ),
        (
            "I am not sure which analytics question I need for marketing performance.",
            OpenAIAgentPlanOut(
                model="gpt-4.1-mini",
                last_agent="Fusion Agent Runtime Planner",
                outcome="clarification_required",
                intent="ambiguous_manager_analytics_question",
                confidence="low",
                clarification_question="Which approved manager question should be used?",
            ),
            "blocked",
            "blocked",
            "blocked",
            False,
        ),
        (
            "Can the agent run an unrestricted database query?",
            OpenAIAgentPlanOut(
                model="gpt-4.1-mini",
                last_agent="Fusion Agent Runtime Planner",
                outcome="refused",
                intent="raw_database_access_attempt",
                confidence="high",
                refusal_reason="Direct database access is not allowed.",
                safety_notes=["No tool selected."],
            ),
            "denied",
            "denied",
            "denied",
            False,
        ),
        (
            "Show a row-level clinical patient snapshot.",
            OpenAIAgentPlanOut(
                model="gpt-4.1-mini",
                last_agent="Fusion Agent Runtime Planner",
                outcome="tool_plan",
                intent="clinical_snapshot",
                tool_id="get_phi_person_snapshot",
                tool_arguments={"person_uid": "00000000-0000-0000-0000-000000000000"},
                confidence="medium",
            ),
            "denied",
            "denied",
            "denied",
            False,
        ),
        (
            "Prepare an analytics CSV export for lead conversion.",
            OpenAIAgentPlanOut(
                model="gpt-4.1-mini",
                last_agent="Fusion Agent Runtime Planner",
                outcome="tool_plan",
                intent="export_report",
                tool_id="export_analytics_csv",
                tool_arguments={"query_id": "lead_conversion"},
                confidence="medium",
            ),
            "approval_required",
            "approval_required",
            "approval_required",
            True,
        ),
        (
            "Create a Semantic Catalog mapping proposal for campaign source values.",
            OpenAIAgentPlanOut(
                model="gpt-4.1-mini",
                last_agent="Fusion Agent Runtime Planner",
                outcome="tool_plan",
                intent="semantic_mapping_review",
                tool_id="data_intelligence_semantic_mapping_proposal",
                tool_arguments={"field": "campaign_source"},
                confidence="medium",
            ),
            "approval_required",
            "approval_required",
            "approval_required",
            True,
        ),
    ],
)
@pytest.mark.asyncio
async def test_agent_runtime_llm_eval_pack_records_safe_policy_outcomes(
    monkeypatch,
    sample_prompt: str,
    provider_plan: OpenAIAgentPlanOut,
    expected_policy_result: str,
    expected_run_status: str,
    expected_final_outcome: str,
    expected_approval_required: bool,
) -> None:
    result, run = await _run_llm_plan_with_fake_plan(
        monkeypatch,
        provider_plan,
        user_prompt=sample_prompt,
    )

    assert result.policy_result == expected_policy_result
    assert result.approval_required is expected_approval_required
    assert run.status == expected_run_status
    assert run.audit_summary["policy_result"] == expected_policy_result
    assert run.audit_summary["final_outcome"] == expected_final_outcome
    assert run.audit_summary["approval_required"] is expected_approval_required
    expected_policy_gate = (
        "llm_plan_and_tool_execution"
        if result.execution_status == "executed"
        else "llm_plan_contract"
    )
    expected_data_level = (
        "aggregate_only"
        if result.execution_status == "executed"
        else "metadata_only"
    )
    expected_result_posture = (
        "safe_aggregate_tool_execution"
        if result.execution_status == "executed"
        else "safe_llm_plan_metadata_only"
    )
    assert run.audit_summary["policy_gate"] == expected_policy_gate
    assert run.audit_summary["data_level"] == expected_data_level
    assert run.audit_summary["masked"] is True
    assert run.audit_summary["row_level"] is False
    assert run.result_posture == expected_result_posture
    policy_decisions = cast(
        list[dict[str, object]],
        run.audit_summary["policy_decisions"],
    )
    assert "tenant_credential_scope" in {
        item["gate_id"] for item in policy_decisions
    }
    assert "llm_prompt_envelope" in {
        item["gate_id"] for item in policy_decisions
    }
    assert "llm_plan_schema_validation" in {
        item["gate_id"] for item in policy_decisions
    }

    persisted_text = f"{run.audit_summary} {run.tool_calls} {result.model_dump()}"
    assert sample_prompt not in persisted_text
    assert "sk-" not in persisted_text
    assert "raw_provider_payload" not in persisted_text
    assert "patient_name" not in persisted_text
    assert "date_of_birth" not in persisted_text
    assert "full_prompt" not in persisted_text
    assert "select *" not in persisted_text.lower()


@pytest.mark.parametrize(
    "unsafe_prompt",
    [
        "Use raw_sql to answer this.",
        "Run raw SQL against the database.",
        "select * from phi.patient",
    ],
)
def test_agent_runtime_llm_plan_rejects_raw_sql_prompt_input(
    unsafe_prompt: str,
) -> None:
    with pytest.raises(PydanticValidationError):
        AgentRuntimeLlmPlanIn(user_prompt=unsafe_prompt)


def test_agent_runtime_tools_projection_uses_registered_tools() -> None:
    result = AgentRuntimeService(MagicMock()).list_tools_projection()

    tool_ids = {tool.id for tool in result.tools}
    assert result.runtime == "agent_runtime"
    assert result.source == "packages.tools.registry"
    assert "data_intelligence_profile_field" in tool_ids
    assert "data_intelligence_semantic_mapping_proposal" in tool_ids
    assert "semantic_catalog_create_review_proposal" in tool_ids

    profile_tool = next(
        tool for tool in result.tools if tool.id == "data_intelligence_profile_field"
    )
    assert profile_tool.status == "available"
    assert profile_tool.callable is True
    assert profile_tool.execution_posture == "planning_only"
    assert profile_tool.output_posture == "aggregate field profile"
    assert "ops" in profile_tool.data_classes
    assert "service-owned aggregates only" in profile_tool.policy_posture

    analytics_tool = next(tool for tool in result.tools if tool.id == "run_analytics_query")
    assert analytics_tool.execution_posture == "executable"

    manager_tool = next(tool for tool in result.tools if tool.id == "ask_manager_analytics")
    assert manager_tool.execution_posture == "executable"

    proposal_tool = next(
        tool
        for tool in result.tools
        if tool.id == "data_intelligence_semantic_mapping_proposal"
    )
    assert proposal_tool.requires_approval is True
    assert proposal_tool.execution_posture == "planning_only"
    assert proposal_tool.output_posture == "review-only semantic proposal"

    planned_catalog_tool = next(
        tool
        for tool in result.tools
        if tool.id == "semantic_catalog_create_review_proposal"
    )
    assert planned_catalog_tool.status == "planned"
    assert planned_catalog_tool.callable is False
    assert planned_catalog_tool.requires_approval is True


def test_agent_runtime_dia_catalog_linkages_are_review_only() -> None:
    result = AgentRuntimeService(MagicMock()).list_dia_catalog_linkages()

    assert result.runtime == "agent_runtime"
    assert result.source == "agent_runtime_projection"
    assert len(result.linkages) >= 2

    mapping = next(
        item
        for item in result.linkages
        if item.id == "dia-lead-source-mapping-to-catalog-review"
    )
    assert mapping.output_kind == "mapping_proposal"
    assert mapping.review_posture == "review_only_no_auto_approval"
    assert mapping.downstream_consumption == "approved_version_only"
    assert mapping.approval_request_id == "approval-semantic-catalog-1"
    assert mapping.approved_catalog_version_ref is None
    assert mapping.query_registry_refs == [
        "paid_leads_by_source.v1",
        "lead_source_profile.v1",
    ]
    assert mapping.read_model_refs == ["paid_leads", "lead_source_profile"]
    assert mapping.approved_catalog_version_refs == [
        "paid_lead:v1",
        "lead_source:v1",
    ]
    assert {surface.confidence for surface in mapping.impact_surfaces} == {
        "known",
        "likely",
        "unknown",
    }
    assert [step.id for step in mapping.path] == [
        "agent_run",
        "review_only_output",
        "human_approval",
        "catalog_review",
        "approved_version",
    ]
    assert "sk-" not in mapping.model_dump_json()
    assert "raw_provider_payload" not in mapping.model_dump_json()


@pytest.mark.asyncio
async def test_agent_runtime_run_history_projects_safe_rows() -> None:
    tenant_id = TenantId(uuid.uuid4())
    now = datetime(2026, 6, 5, 16, 0, tzinfo=UTC)
    run = AgentRuntimeRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        trigger_actor_id=uuid.uuid4(),
        trigger_actor_email="admin@example.com",
        agent_name="Fusion OpenAI Health Check",
        provider_kind="openai",
        model="gpt-4.1-mini",
        run_kind="provider_health_check",
        status="success",
        started_at=now,
        completed_at=now,
        duration_ms=12,
        tool_calls=[],
        result_posture="safe_metadata_only",
        audit_summary={
            "data_classes": ["integration_metadata"],
            "data_level": "metadata_only",
            "row_level": False,
            "phi": False,
            "billing": False,
            "export": False,
            "masked": True,
            "policy_result": "allowed",
            "policy_gate": "provider_credential_health_check",
            "policy_reason": "Tenant OpenAI credential check uses metadata only.",
            "approval_required": False,
            "final_outcome": "completed",
            "policy_decisions": [
                {
                    "gate_id": "tenant_credential_scope",
                    "result": "allowed",
                    "reason": "Credential resolved server-side for current tenant.",
                    "evidence_refs": ["tenant_credential_status"],
                }
            ],
            "evidence_refs": ["provider_health_check"],
            "compliance_notes": ["No sensitive details stored."],
            "linked_approval_request_ids": [],
        },
    )

    class FakeRunRepository:
        async def list_recent(
            self,
            tenant_id_arg,
            *,
            limit,
            status=None,
            triggered_by=None,
            started_after=None,
            started_before=None,
        ):
            assert tenant_id_arg == tenant_id
            assert limit == 10
            assert status is None
            assert triggered_by is None
            assert started_after is None
            assert started_before is None
            return [run]

    service = AgentRuntimeService(MagicMock())
    service._run_repo = cast(Any, FakeRunRepository())  # noqa: SLF001
    result = await service.list_run_history(tenant_id, limit=10)

    assert result.runtime == "agent_runtime"
    assert len(result.runs) == 1
    summary = result.runs[0]
    assert summary.agent_name == "Fusion OpenAI Health Check"
    assert summary.status == "success"
    assert summary.triggered_by == "admin@example.com"
    assert summary.audit_summary.phi is False
    assert summary.audit_summary.policy_result == "allowed"
    assert summary.audit_summary.data_level == "metadata_only"
    assert summary.audit_summary.policy_gate == "provider_credential_health_check"
    assert summary.audit_summary.final_outcome == "completed"
    assert summary.audit_summary.policy_decisions[0].gate_id == "tenant_credential_scope"
    assert summary.audit_summary.evidence_refs == ["provider_health_check"]
    assert summary.audit_summary.answer is None


@pytest.mark.asyncio
async def test_agent_runtime_run_history_filters_safe_metadata() -> None:
    tenant_id = TenantId(uuid.uuid4())
    now = datetime(2026, 6, 5, 16, 0, tzinfo=UTC)
    matched_run = AgentRuntimeRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        trigger_actor_id=uuid.uuid4(),
        trigger_actor_email="admin@example.com",
        agent_name="Fusion Agent Runtime Planner",
        provider_kind="openai",
        model="gpt-4.1-mini",
        run_kind="llm_planning_with_tool_execution",
        status="success",
        started_at=now,
        completed_at=now,
        duration_ms=40,
        tool_calls=[
            {
                "tool_id": "run_analytics_query",
                "status": "success",
                "data_classes": ["ops"],
                "output_posture": "aggregate analytics result",
            }
        ],
        result_posture="safe_aggregate_tool_execution",
        audit_summary={
            "data_classes": ["ops"],
            "data_level": "aggregate_only",
            "row_level": False,
            "phi": False,
            "billing": False,
            "export": False,
            "masked": True,
            "policy_result": "allowed",
            "policy_gate": "llm_plan_and_tool_execution",
            "policy_reason": "Approved aggregate tool executed.",
            "approval_required": False,
            "final_outcome": "completed",
            "policy_decisions": [],
            "evidence_refs": ["approved_query_read_model_match"],
            "compliance_notes": [
                "Run history stores manager answer metadata only; answer body and "
                "provider payload are not persisted."
            ],
            "linked_approval_request_ids": [],
            "query_registry_refs": ["paid_leads_by_source.v1"],
            "read_model_refs": ["paid_leads"],
            "approved_catalog_version_refs": ["lead_source:v1"],
            "catalog_consumption_status": "approved_version_refs",
            "answer": {
                "status": "generated",
                "eligible": True,
                "reason": "Approved aggregate execution can be summarized for managers.",
                "model": "gpt-4.1",
                "confidence": "high",
                "source_refs": {
                    "tool_id": "run_analytics_query",
                    "query_id": "paid_leads_by_source.v1",
                    "read_model_id": "paid_leads",
                    "execution_run_id": "run-answer-1",
                    "approved_catalog_version_refs": ["lead_source:v1"],
                    "evidence_refs": ["service_owned_read_model_execution"],
                },
                "caveats": ["No row-level rows are included."],
                "safety_notes": ["Aggregate-only answer."],
                "validation_errors": [],
            },
        },
    )
    denied_run = AgentRuntimeRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        trigger_actor_id=uuid.uuid4(),
        trigger_actor_email="admin@example.com",
        agent_name="Export Planner",
        provider_kind="openai",
        model="gpt-4.1-mini",
        run_kind="export_request_preflight",
        status="denied",
        started_at=now,
        completed_at=now,
        duration_ms=20,
        tool_calls=[
            {
                "tool_id": "export_analytics_csv",
                "status": "denied",
                "data_classes": ["ops"],
                "output_posture": "no export generated",
            }
        ],
        result_posture="denied_no_export",
        audit_summary={
            "data_classes": ["ops"],
            "data_level": "row_level",
            "row_level": True,
            "phi": False,
            "billing": False,
            "export": True,
            "masked": True,
            "policy_result": "denied",
            "policy_gate": "row_level_export_policy",
            "policy_reason": "Row-level export denied.",
            "approval_required": False,
            "final_outcome": "denied",
            "policy_decisions": [],
            "evidence_refs": ["export_preflight"],
            "compliance_notes": [],
            "linked_approval_request_ids": [],
        },
    )
    captured: dict[str, object] = {}

    class FakeRunRepository:
        async def list_recent(
            self,
            tenant_id_arg,
            *,
            limit,
            status=None,
            triggered_by=None,
            started_after=None,
            started_before=None,
        ):
            captured["tenant_id"] = tenant_id_arg
            captured["limit"] = limit
            captured["status"] = status
            captured["triggered_by"] = triggered_by
            captured["started_after"] = started_after
            captured["started_before"] = started_before
            return [matched_run, denied_run]

    service = AgentRuntimeService(MagicMock())
    service._run_repo = cast(Any, FakeRunRepository())  # noqa: SLF001
    result = await service.list_run_history(
        tenant_id,
        limit=5,
        status="success",
        tool_id="run_analytics_query",
        policy_result="allowed",
        final_outcome="completed",
        triggered_by="admin@example.com",
        started_after=now,
        started_before=now,
    )

    assert result.filters.status == "success"
    assert result.filters.tool_id == "run_analytics_query"
    assert result.filters.policy_result == "allowed"
    assert result.filters.final_outcome == "completed"
    assert result.filters.triggered_by == "admin@example.com"
    assert [run.id for run in result.runs] == [str(matched_run.id)]
    answer = result.runs[0].audit_summary.answer
    assert answer is not None
    assert answer.status == "generated"
    assert answer.model == "gpt-4.1"
    assert answer.source_refs is not None
    assert answer.source_refs.query_id == "paid_leads_by_source.v1"
    history_text = str(result.model_dump(mode="json"))
    assert "manager answer summary" not in history_text
    assert "raw_provider_payload" not in history_text
    assert "sk-" not in history_text
    assert captured == {
        "tenant_id": tenant_id,
        "limit": 25,
        "status": "success",
        "triggered_by": "admin@example.com",
        "started_after": now,
        "started_before": now,
    }


@pytest.mark.asyncio
async def test_agent_runtime_rejects_unsafe_audit_summary_text() -> None:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="admin@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    service = AgentRuntimeService(MagicMock())

    with pytest.raises(PydanticValidationError):
        await service._record_run(  # noqa: SLF001
            principal=principal,
            agent_name="Unsafe Agent",
            provider_kind="openai",
            model="gpt-4.1-mini",
            run_kind="unsafe",
            status="denied",
            started_at=datetime(2026, 6, 5, 16, 0, tzinfo=UTC),
            completed_at=datetime(2026, 6, 5, 16, 0, tzinfo=UTC),
            tool_calls=[],
            result_posture="denied",
            audit_summary={
                "data_classes": ["ops"],
                "data_level": "aggregate_only",
                "row_level": False,
                "phi": False,
                "billing": False,
                "export": False,
                "masked": True,
                "policy_result": "denied",
                "policy_gate": "runtime_preflight",
                "policy_reason": "Unsafe raw_provider_payload detail.",
                "approval_required": False,
                "final_outcome": "denied",
            },
        )


@pytest.mark.asyncio
async def test_agent_runtime_creates_safe_approval_request() -> None:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="admin@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    captured: dict[str, object] = {}

    class FakeApprovalRepository:
        async def add(self, approval):
            approval.id = uuid.uuid4()
            approval.created_at = datetime(2026, 6, 5, 16, 15, tzinfo=UTC)
            approval.updated_at = datetime(2026, 6, 5, 16, 15, tzinfo=UTC)
            captured["approval"] = approval
            return approval

    service = AgentRuntimeService(MagicMock())
    service._approval_repo = cast(Any, FakeApprovalRepository())  # noqa: SLF001
    payload = AgentRuntimeApprovalRequestCreateIn(
        agent_name="Data Intelligence Mapping Helper",
        tool_id="data_intelligence_semantic_mapping_proposal",
        target_kind="semantic_catalog_mapping_proposal",
        target_ref="lead-source-google-ads",
        title="Review mapping candidate",
        reason="Repeated source values need human review.",
        evidence_summary="Aggregate coverage only; bounded examples remain masked.",
        requested_action="Create a Semantic Catalog review draft.",
        data_classes=["ops", "integration_metadata", "ops"],
        affected_surfaces=["semantic_catalog", "data_intelligence"],
        risk_flags=["business_meaning_change"],
    )

    result = await service.create_approval_request(principal, payload)

    approval = captured["approval"]
    assert isinstance(approval, AgentRuntimeApprovalRequest)
    assert approval.tenant_id == tenant_id
    assert approval.requested_by_actor_id == principal.id
    assert approval.requested_by_actor_email == "admin@example.com"
    assert approval.status == "pending"
    assert approval.target_kind == "semantic_catalog_mapping_proposal"
    assert approval.data_classes == ["integration_metadata", "ops"]
    assert approval.approval_posture == "human_review_required_no_auto_mutation"
    assert result.status == "pending"
    assert result.requested_by == "admin@example.com"
    assert "sk-" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_agent_runtime_rejects_unsafe_approval_detail() -> None:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="admin@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    payload = AgentRuntimeApprovalRequestCreateIn(
        agent_name="Unsafe Helper",
        target_kind="large_analysis_run",
        title="Unsafe detail",
        reason="Contains raw_provider_payload and must not persist.",
        evidence_summary="Aggregate only.",
        requested_action="Review",
    )

    with pytest.raises(ValidationError):
        await AgentRuntimeService(MagicMock()).create_approval_request(
            principal,
            payload,
        )


@pytest.mark.asyncio
async def test_agent_runtime_decides_pending_approval_request() -> None:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="reviewer@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    approval_id = uuid.uuid4()
    approval = AgentRuntimeApprovalRequest(
        id=approval_id,
        tenant_id=tenant_id,
        requested_by_actor_id=uuid.uuid4(),
        requested_by_actor_email="admin@example.com",
        agent_name="Data Intelligence Mapping Helper",
        tool_id="data_intelligence_semantic_mapping_proposal",
        target_kind="semantic_catalog_mapping_proposal",
        target_ref="lead-source-google-ads",
        title="Review mapping candidate",
        reason="Repeated source values need human review.",
        evidence_summary="Aggregate coverage only.",
        requested_action="Create Semantic Catalog review draft.",
        status="pending",
        requested_at=datetime(2026, 6, 5, 16, 0, tzinfo=UTC),
        data_classes=["ops"],
        affected_surfaces=["semantic_catalog"],
        risk_flags=["business_meaning_change"],
        approval_posture="human_review_required_no_auto_mutation",
    )

    captured: dict[str, object] = {}

    class FakeApprovalRepository:
        async def get_for_tenant(self, tenant_id_arg, approval_id_arg):
            assert tenant_id_arg == tenant_id
            assert approval_id_arg == approval_id
            return approval

    class FakeRunRepository:
        async def add(self, run):
            run.id = uuid.uuid4()
            captured["run"] = run
            return run

    session = MagicMock()
    session.flush = AsyncMock()
    service = AgentRuntimeService(session)
    service._approval_repo = cast(Any, FakeApprovalRepository())  # noqa: SLF001
    service._run_repo = cast(Any, FakeRunRepository())  # noqa: SLF001

    result = await service.decide_approval_request(
        principal,
        approval_id,
        AgentRuntimeApprovalDecisionIn(
            decision="request_edit",
            decision_summary="Needs clearer affected surfaces.",
            edit_summary="Add catalog/read-model impact notes.",
        ),
    )

    assert result.status == "needs_edit"
    assert result.decided_by == "reviewer@example.com"
    assert result.workflow_state == "needs_edit"
    assert result.decision_summary == "Needs clearer affected surfaces."
    assert result.edit_summary == "Add catalog/read-model impact notes."
    assert approval.decided_by_actor_id == principal.id
    session.flush.assert_awaited_once()
    decision_run = captured["run"]
    assert isinstance(decision_run, AgentRuntimeRun)
    assert decision_run.run_kind == "approval_decision"
    assert decision_run.status == "blocked"
    assert decision_run.audit_summary["policy_gate"] == "human_approval_decision"
    assert decision_run.audit_summary["linked_approval_request_ids"] == [
        str(approval_id)
    ]
    assert decision_run.tool_calls[0]["approval_request_id"] == str(approval_id)


async def _run_llm_plan_with_fake_plan(
    monkeypatch: pytest.MonkeyPatch,
    plan: OpenAIAgentPlanOut,
    *,
    user_prompt: str = "Plan a safe aggregate answer.",
    approval_sink: list[AgentRuntimeApprovalRequest] | None = None,
) -> tuple[AgentRuntimeLlmPlanOut, AgentRuntimeRun]:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="manager@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    captured: dict[str, object] = {}

    class FakeOpenAIIntegrationService:
        def __init__(self, session):
            captured["session"] = session

        async def generate_agent_plan(self, tenant_id_arg, payload):
            captured["tenant_id"] = tenant_id_arg
            return plan

    monkeypatch.setattr(
        "packages.agent_runtime.service.OpenAIIntegrationService",
        FakeOpenAIIntegrationService,
    )

    async def fake_ask_manager_analytics(ctx, *, question, params=None, execute=True):
        return {
            "planner": {
                "status": "planned",
                "question": question,
                "query_id": "lead_conversion_funnel.v1",
            },
            "query_spec": {
                "intent": "manager_analytics",
                "query_id": "lead_conversion_funnel.v1",
                "params": params or {},
                "output_level": "aggregate",
            },
            "policy_preflight": {
                "decision": "allow",
                "reason": "Aggregate-only V1 analytics query selected.",
            },
            "execution": {
                "query_id": "lead_conversion_funnel.v1",
                "read_model_id": "lead_conversion",
                "output_type": "aggregate",
                "aggregation_level": "aggregate",
                "data_classes": ["ops", "integration_metadata"],
                "definition_versions": {"lead_source": "v1"},
                "filters": {"limit": 10},
                "row_count": 1,
                "warnings": [],
                "drilldown_available": False,
                "export_available": True,
                "result": {
                    "lead_status": [{"key": "new", "count": 4}],
                },
            },
            "explanation": "Executed approved aggregate analytics query.",
        }

    monkeypatch.setitem(
        agent_runtime_service.ALL_TOOLS,
        "ask_manager_analytics",
        ToolSpec(
            name="ask_manager_analytics",
            description="Fake aggregate manager analytics tool.",
            fn=fake_ask_manager_analytics,
            touches=frozenset({"ops", "interaction"}),
        ),
    )

    class FakeRunRepository:
        async def add(self, run):
            run.id = uuid.uuid4()
            captured["run"] = run
            return run

    class FakeApprovalRepository:
        async def add(self, approval):
            captured["approval"] = approval
            if approval_sink is not None:
                approval_sink.append(approval)
            return approval

    session = MagicMock()
    session.flush = AsyncMock()
    service = AgentRuntimeService(session)
    service._run_repo = cast(Any, FakeRunRepository())  # noqa: SLF001
    service._approval_repo = cast(Any, FakeApprovalRepository())  # noqa: SLF001
    result = await service.generate_llm_plan(
        principal,
        AgentRuntimeLlmPlanIn(user_prompt=user_prompt),
    )

    run = captured["run"]
    assert isinstance(run, AgentRuntimeRun)
    return result, run
