"""Tests for tenant-scoped OpenAI integration service."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId
from packages.integrations.openai.schemas import (
    OpenAIAgentPlanIn,
    OpenAIAgentPlanOut,
    OpenAIToolDescriptor,
)
from packages.integrations.openai.service import OpenAIIntegrationService


@pytest.mark.asyncio
async def test_generate_agent_plan_reads_tenant_key(monkeypatch) -> None:
    tenant_id = TenantId(uuid.uuid4())
    captured: dict[str, Any] = {}

    class FakeCredentialService:
        def __init__(self, session):
            captured["credential_session"] = session

        async def read_for(self, tenant_id_arg, provider, kind):
            captured["read_for"] = (tenant_id_arg, provider, kind)
            return {"api_key": "sk-test-openai-secret"}

    class FakePlanningClient:
        def __init__(self, *, api_key):
            captured["api_key"] = api_key

        async def generate_plan(self, payload):
            captured["payload"] = payload
            return OpenAIAgentPlanOut(
                model="gpt-4.1-mini",
                last_agent="Fusion Agent Runtime Planner",
                outcome="tool_plan",
                intent="manager_analytics",
                tool_id="ask_manager_analytics",
                tool_arguments={},
                confidence="medium",
            )

    monkeypatch.setattr(
        "packages.integrations.openai.service.IntegrationCredentialService",
        FakeCredentialService,
    )
    monkeypatch.setattr(
        "packages.integrations.openai.service.OpenAIAgentPlanningClient",
        FakePlanningClient,
    )

    payload = _planning_payload()
    result = await OpenAIIntegrationService(MagicMock()).generate_agent_plan(
        tenant_id,
        payload,
    )

    assert result.outcome == "tool_plan"
    assert captured["read_for"] == (tenant_id, "openai", "api_key")
    assert captured["api_key"] == "sk-test-openai-secret"
    assert captured["payload"] == payload


@pytest.mark.asyncio
async def test_generate_agent_plan_rejects_missing_api_key(monkeypatch) -> None:
    tenant_id = TenantId(uuid.uuid4())

    class FakeCredentialService:
        def __init__(self, session):
            pass

        async def read_for(self, tenant_id_arg, provider, kind):
            return {}

    monkeypatch.setattr(
        "packages.integrations.openai.service.IntegrationCredentialService",
        FakeCredentialService,
    )

    with pytest.raises(ValidationError) as exc_info:
        await OpenAIIntegrationService(MagicMock()).generate_agent_plan(
            tenant_id,
            _planning_payload(),
        )

    assert exc_info.value.code == "validation_error"
    assert "api_key" in exc_info.value.message


def _planning_payload() -> OpenAIAgentPlanIn:
    return OpenAIAgentPlanIn(
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
