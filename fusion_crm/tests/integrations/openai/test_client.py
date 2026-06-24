"""Tests for OpenAI Agents SDK integration wrappers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from packages.core.exceptions import ValidationError
from packages.integrations.openai.client import (
    DEFAULT_OPENAI_HEALTH_MODEL,
    DEFAULT_OPENAI_PLANNING_MODEL,
    OpenAIAgentHealthClient,
    OpenAIAgentPlanningClient,
)
from packages.integrations.openai.schemas import (
    OpenAIAgentPlanDecisionOut,
    OpenAIAgentPlanIn,
    OpenAIToolDescriptor,
)


def test_agent_plan_input_rejects_raw_sql_prompts() -> None:
    tool = OpenAIToolDescriptor(
        id="ask_manager_analytics",
        description="Answer approved aggregate manager analytics questions.",
        data_classes=["ops"],
        input_posture="manager question only",
        output_posture="aggregate answer plan",
        policy_posture="aggregate only; no direct database access",
    )

    with pytest.raises(ValueError):
        OpenAIAgentPlanIn(
            user_prompt="select * from phi.patient",
            tools=[tool],
        )


@pytest.mark.asyncio
async def test_agent_health_client_uses_tenant_key_without_env(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeProvider:
        def __init__(self, **kwargs):
            captured["provider_kwargs"] = kwargs

    async def _fake_run(agent, input_text, **kwargs):
        captured["agent_name"] = agent.name
        captured["agent_model"] = agent.model
        captured["input"] = input_text
        captured["run_kwargs"] = kwargs
        return SimpleNamespace(
            final_output="ok",
            last_agent=SimpleNamespace(name=agent.name),
        )

    monkeypatch.setattr(
        "packages.integrations.openai.client.OpenAIProvider",
        FakeProvider,
    )
    monkeypatch.setattr(
        "packages.integrations.openai.client.Runner.run",
        _fake_run,
    )

    result = await OpenAIAgentHealthClient(
        api_key="sk-test-openai-secret",
    ).test_connection()

    assert result.ok is True
    assert result.provider_kind == "openai"
    assert result.credential_kind == "api_key"
    assert result.model == DEFAULT_OPENAI_HEALTH_MODEL
    assert result.output == "ok"
    assert captured["provider_kwargs"] == {
        "api_key": "sk-test-openai-secret",
        "use_responses": True,
    }
    assert captured["agent_name"] == "Fusion OpenAI Health Check"
    assert captured["agent_model"] == DEFAULT_OPENAI_HEALTH_MODEL
    assert captured["input"] == "Return exactly: ok"
    assert captured["run_kwargs"]["max_turns"] == 1
    assert captured["run_kwargs"]["run_config"].tracing_disabled is True
    assert captured["run_kwargs"]["run_config"].trace_include_sensitive_data is False


@pytest.mark.asyncio
async def test_agent_health_client_marks_unexpected_output_not_ok(monkeypatch) -> None:
    class FakeProvider:
        def __init__(self, **kwargs):
            pass

    async def _fake_run(agent, input_text, **kwargs):
        return SimpleNamespace(
            final_output="not ok",
            last_agent=SimpleNamespace(name=agent.name),
        )

    monkeypatch.setattr(
        "packages.integrations.openai.client.OpenAIProvider",
        FakeProvider,
    )
    monkeypatch.setattr(
        "packages.integrations.openai.client.Runner.run",
        _fake_run,
    )

    result = await OpenAIAgentHealthClient(
        api_key="sk-test-openai-secret",
    ).test_connection()

    assert result.ok is False
    assert result.output == "not ok"


@pytest.mark.asyncio
async def test_agent_planning_client_uses_safe_prompt_envelope(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeProvider:
        def __init__(self, **kwargs):
            captured["provider_kwargs"] = kwargs

    async def _fake_run(agent, input_text, **kwargs):
        captured["agent_name"] = agent.name
        captured["agent_model"] = agent.model
        captured["input"] = input_text
        captured["run_kwargs"] = kwargs
        return SimpleNamespace(
            final_output=(
                '{"outcome":"tool_plan","intent":"manager_analytics",'
                '"tool_id":"ask_manager_analytics","tool_arguments":'
                '{"question_kind":"lead_conversion"},'
                '"confidence":"high","clarification_question":null,'
                '"refusal_reason":null,'
                '"safety_notes":["Aggregate-only planning."]}'
            ),
            last_agent=SimpleNamespace(name=agent.name),
        )

    monkeypatch.setattr(
        "packages.integrations.openai.client.OpenAIProvider",
        FakeProvider,
    )
    monkeypatch.setattr(
        "packages.integrations.openai.client.Runner.run",
        _fake_run,
    )

    result = await OpenAIAgentPlanningClient(
        api_key="sk-test-openai-secret",
    ).generate_plan(
        OpenAIAgentPlanIn(
            user_prompt="How are lead conversions trending?",
            tools=[
                OpenAIToolDescriptor(
                    id="ask_manager_analytics",
                    description="Answer approved aggregate manager analytics questions.",
                    data_classes=["ops"],
                    input_posture="manager question only",
                    output_posture="aggregate answer plan",
                    policy_posture="aggregate only; no direct database access",
                )
            ],
        )
    )

    assert result.provider_kind == "openai"
    assert result.model == DEFAULT_OPENAI_PLANNING_MODEL
    assert result.last_agent == "Fusion Agent Runtime Planner"
    assert result.outcome == "tool_plan"
    assert result.tool_id == "ask_manager_analytics"
    assert result.tool_arguments == {"question_kind": "lead_conversion"}
    assert captured["provider_kwargs"] == {
        "api_key": "sk-test-openai-secret",
        "use_responses": True,
    }
    assert captured["agent_model"] == DEFAULT_OPENAI_PLANNING_MODEL
    assert "How are lead conversions trending?" in captured["input"]
    assert "sk-test-openai-secret" not in captured["input"]
    assert captured["run_kwargs"]["max_turns"] == 1
    assert captured["run_kwargs"]["run_config"].tracing_disabled is True
    assert captured["run_kwargs"]["run_config"].trace_include_sensitive_data is False


@pytest.mark.asyncio
async def test_agent_planning_client_rejects_unknown_tool(monkeypatch) -> None:
    class FakeProvider:
        def __init__(self, **kwargs):
            pass

    async def _fake_run(agent, input_text, **kwargs):
        return SimpleNamespace(
            final_output=(
                '{"outcome":"tool_plan","intent":"unknown",'
                '"tool_id":"direct_database_query","tool_arguments":{},'
                '"confidence":"high","clarification_question":null,'
                '"refusal_reason":null,"safety_notes":[]}'
            ),
            last_agent=SimpleNamespace(name=agent.name),
        )

    monkeypatch.setattr(
        "packages.integrations.openai.client.OpenAIProvider",
        FakeProvider,
    )
    monkeypatch.setattr(
        "packages.integrations.openai.client.Runner.run",
        _fake_run,
    )

    with pytest.raises(ValidationError) as exc_info:
        await OpenAIAgentPlanningClient(
            api_key="sk-test-openai-secret",
        ).generate_plan(
            OpenAIAgentPlanIn(
                user_prompt="Show me the database.",
                tools=[
                    OpenAIToolDescriptor(
                        id="ask_manager_analytics",
                        description="Answer approved aggregate manager analytics questions.",
                        data_classes=["ops"],
                        input_posture="manager question only",
                        output_posture="aggregate answer plan",
                        policy_posture="aggregate only; no direct database access",
                    )
                ],
            )
        )

    assert "unknown tool" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_agent_planning_client_accepts_typed_agent_output(monkeypatch) -> None:
    class FakeProvider:
        def __init__(self, **kwargs):
            pass

    async def _fake_run(agent, input_text, **kwargs):
        return SimpleNamespace(
            final_output=OpenAIAgentPlanDecisionOut(
                outcome="clarification_required",
                intent="manager_analytics",
                tool_id=None,
                tool_arguments=[],
                confidence="medium",
                clarification_question=(
                    "Which aggregate manager question should be planned?"
                ),
                refusal_reason=None,
                safety_notes=["No tool selected before clarification."],
            ),
            last_agent=SimpleNamespace(name=agent.name),
        )

    monkeypatch.setattr(
        "packages.integrations.openai.client.OpenAIProvider",
        FakeProvider,
    )
    monkeypatch.setattr(
        "packages.integrations.openai.client.Runner.run",
        _fake_run,
    )

    result = await OpenAIAgentPlanningClient(
        api_key="sk-test-openai-secret",
    ).generate_plan(
        OpenAIAgentPlanIn(
            user_prompt="Help me plan an approved analytics answer.",
            tools=[
                OpenAIToolDescriptor(
                    id="ask_manager_analytics",
                    description="Answer approved aggregate manager analytics questions.",
                    data_classes=["ops"],
                    input_posture="manager question only",
                    output_posture="aggregate answer plan",
                    policy_posture="aggregate only; no direct database access",
                )
            ],
        )
    )

    assert result.outcome == "clarification_required"
    assert result.tool_id is None
    assert result.clarification_question is not None
    assert result.model == DEFAULT_OPENAI_PLANNING_MODEL
