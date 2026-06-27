"""OpenAI Agents SDK client wrappers.

The product runtime passes tenant-scoped API keys in memory. Do not rely
on ``OPENAI_API_KEY`` here; the application source of truth is
``tenant.integration_credential``.
"""

from __future__ import annotations

import json

from agents import Agent, RunConfig, Runner
from agents.models.openai_provider import OpenAIProvider
from openai import APIConnectionError, APIError, APITimeoutError, AuthenticationError
from pydantic import ValidationError as PydanticValidationError

from packages.core.exceptions import IntegrationError, ValidationError

from .schemas import (
    OpenAIAgentPlanDecisionOut,
    OpenAIAgentPlanIn,
    OpenAIAgentPlanOut,
    OpenAIConnectionCheckOut,
    OpenAIManagerAnswerDecisionOut,
    OpenAIManagerAnswerIn,
    OpenAIManagerAnswerOut,
)

DEFAULT_OPENAI_HEALTH_MODEL = "gpt-4.1-mini"
DEFAULT_OPENAI_PLANNING_MODEL = "gpt-4.1-mini"
DEFAULT_OPENAI_ANSWER_MODEL = "gpt-4.1"
_HEALTH_AGENT_NAME = "Fusion OpenAI Health Check"
_PLANNING_AGENT_NAME = "Fusion Agent Runtime Planner"
_ANSWER_AGENT_NAME = "Fusion Manager Answer Generator"


class OpenAIInvalidCredentialError(IntegrationError):
    """The stored OpenAI API key was rejected by OpenAI."""

    code = "openai_credential_invalid"
    http_status = 409


class OpenAIConnectionFailedError(IntegrationError):
    """OpenAI could not complete the health-check request."""

    code = "openai_connection_failed"
    http_status = 502


class OpenAIAgentHealthClient:
    """Minimal Agents SDK runner for validating one tenant API key."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_OPENAI_HEALTH_MODEL,
    ) -> None:
        if not api_key.strip():
            raise ValidationError("OpenAI API key is empty")
        if not model.strip():
            raise ValidationError("OpenAI health-check model is empty")

        self._api_key = api_key
        self._model = model

    async def test_connection(self) -> OpenAIConnectionCheckOut:
        """Run a tiny agent turn and return safe status metadata."""

        agent = Agent(
            name=_HEALTH_AGENT_NAME,
            instructions=(
                "You are a connection health-check agent. "
                "Return exactly the lowercase word ok."
            ),
            model=self._model,
        )
        run_config = RunConfig(
            model_provider=OpenAIProvider(
                api_key=self._api_key,
                use_responses=True,
            ),
            tracing_disabled=True,
            trace_include_sensitive_data=False,
            workflow_name=_HEALTH_AGENT_NAME,
        )

        try:
            result = await Runner.run(
                agent,
                "Return exactly: ok",
                max_turns=1,
                run_config=run_config,
            )
        except AuthenticationError as exc:
            raise OpenAIInvalidCredentialError(
                "OpenAI API key was rejected",
                details={"provider_kind": "openai", "status_code": exc.status_code},
            ) from exc
        except (APIConnectionError, APITimeoutError) as exc:
            raise OpenAIConnectionFailedError(
                "OpenAI API is unreachable",
                details={"provider_kind": "openai"},
            ) from exc
        except APIError as exc:
            raise OpenAIConnectionFailedError(
                "OpenAI API request failed",
                details={
                    "provider_kind": "openai",
                    "status_code": getattr(exc, "status_code", None),
                },
            ) from exc

        output = str(result.final_output).strip()
        return OpenAIConnectionCheckOut(
            ok=output.lower() == "ok",
            model=self._model,
            last_agent=result.last_agent.name,
            output=output[:120] or "empty",
        )


class OpenAIAgentPlanningClient:
    """Constrained Agents SDK runner for validated Agent Runtime planning."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_OPENAI_PLANNING_MODEL,
    ) -> None:
        if not api_key.strip():
            raise ValidationError("OpenAI API key is empty")
        if not model.strip():
            raise ValidationError("OpenAI planning model is empty")

        self._api_key = api_key
        self._model = model

    async def generate_plan(self, payload: OpenAIAgentPlanIn) -> OpenAIAgentPlanOut:
        """Run one planning turn and return validated safe plan metadata."""

        agent = Agent(
            name=_PLANNING_AGENT_NAME,
            instructions=_planning_instructions(),
            model=self._model,
            output_type=OpenAIAgentPlanDecisionOut,
        )
        run_config = RunConfig(
            model_provider=OpenAIProvider(
                api_key=self._api_key,
                use_responses=True,
            ),
            tracing_disabled=True,
            trace_include_sensitive_data=False,
            workflow_name=_PLANNING_AGENT_NAME,
        )

        try:
            result = await Runner.run(
                agent,
                _planning_input(payload),
                max_turns=1,
                run_config=run_config,
            )
        except AuthenticationError as exc:
            raise OpenAIInvalidCredentialError(
                "OpenAI API key was rejected",
                details={"provider_kind": "openai", "status_code": exc.status_code},
            ) from exc
        except (APIConnectionError, APITimeoutError) as exc:
            raise OpenAIConnectionFailedError(
                "OpenAI API is unreachable",
                details={"provider_kind": "openai"},
            ) from exc
        except APIError as exc:
            raise OpenAIConnectionFailedError(
                "OpenAI API request failed",
                details={
                    "provider_kind": "openai",
                    "status_code": getattr(exc, "status_code", None),
                },
            ) from exc

        parsed = _coerce_plan_output(result.final_output)
        parsed["model"] = self._model
        parsed["last_agent"] = result.last_agent.name
        try:
            plan = OpenAIAgentPlanOut.model_validate(parsed)
        except PydanticValidationError as exc:
            raise ValidationError(
                "OpenAI planning response did not match the safe plan contract",
                details={"provider_kind": "openai", "contract": "agent_plan_v1"},
            ) from exc

        _validate_plan_against_tools(plan, payload)
        return plan


class OpenAIManagerAnswerClient:
    """Constrained Agents SDK runner for manager-facing aggregate answers."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_OPENAI_ANSWER_MODEL,
    ) -> None:
        if not api_key.strip():
            raise ValidationError("OpenAI API key is empty")
        if not model.strip():
            raise ValidationError("OpenAI answer model is empty")

        self._api_key = api_key
        self._model = model

    async def generate_answer(
        self,
        payload: OpenAIManagerAnswerIn,
    ) -> OpenAIManagerAnswerOut:
        """Run one answer turn and return validated safe answer metadata."""

        agent = Agent(
            name=_ANSWER_AGENT_NAME,
            instructions=_answer_instructions(),
            model=self._model,
            output_type=OpenAIManagerAnswerDecisionOut,
        )
        run_config = RunConfig(
            model_provider=OpenAIProvider(
                api_key=self._api_key,
                use_responses=True,
            ),
            tracing_disabled=True,
            trace_include_sensitive_data=False,
            workflow_name=_ANSWER_AGENT_NAME,
        )

        try:
            result = await Runner.run(
                agent,
                _answer_input(payload),
                max_turns=1,
                run_config=run_config,
            )
        except AuthenticationError as exc:
            raise OpenAIInvalidCredentialError(
                "OpenAI API key was rejected",
                details={"provider_kind": "openai", "status_code": exc.status_code},
            ) from exc
        except (APIConnectionError, APITimeoutError) as exc:
            raise OpenAIConnectionFailedError(
                "OpenAI API is unreachable",
                details={"provider_kind": "openai"},
            ) from exc
        except APIError as exc:
            raise OpenAIConnectionFailedError(
                "OpenAI API request failed",
                details={
                    "provider_kind": "openai",
                    "status_code": getattr(exc, "status_code", None),
                },
            ) from exc

        parsed = _coerce_answer_output(result.final_output)
        parsed["model"] = self._model
        parsed["last_agent"] = result.last_agent.name
        try:
            return OpenAIManagerAnswerOut.model_validate(parsed)
        except PydanticValidationError as exc:
            raise ValidationError(
                "OpenAI answer response did not match the safe answer contract",
                details={"provider_kind": "openai", "contract": "manager_answer_v1"},
            ) from exc


def _planning_instructions() -> str:
    return (
        "You are Fusion CRM Agent Runtime Planner. "
        "Choose only from the provided approved tools. "
        "Never invent tools, never produce SQL, never request direct database "
        "access, never include PHI, secrets, raw provider payloads, or raw rows. "
        "Return only one object with keys: outcome, intent, tool_id, "
        "tool_arguments, confidence, clarification_question, refusal_reason, "
        "safety_notes. tool_arguments must be a list of objects with keys "
        "key and value. outcome must be one of tool_plan, "
        "clarification_required, refused. confidence must be high, medium, or low. "
        "For ask_manager_analytics, use tool_arguments key question for the "
        "manager analytics question. "
        "Use null for unavailable optional fields and an empty list for "
        "tool_arguments when no tool is selected."
    )


def _planning_input(payload: OpenAIAgentPlanIn) -> str:
    tool_summaries = [
        {
            "id": tool.id,
            "description": tool.description,
            "data_classes": tool.data_classes,
            "input_posture": tool.input_posture,
            "output_posture": tool.output_posture,
            "policy_posture": tool.policy_posture,
            "requires_approval": tool.requires_approval,
        }
        for tool in payload.tools
    ]
    envelope = {
        "schema": "fusion_agent_plan_v1",
        "policy": {
            "allowed": [
                "choose one approved tool",
                "ask a clarification question",
                "refuse unsafe or unsupported requests",
            ],
            "blocked": [
                "raw SQL",
                "direct database access",
                "PHI or row-level clinical data",
                "secrets",
                "raw provider payloads",
                "write-capable actions in V1 unless approval posture is explicit",
            ],
        },
        "user_prompt": payload.user_prompt,
        "approved_tools": tool_summaries,
    }
    return json.dumps(envelope, ensure_ascii=True, sort_keys=True)


def _answer_instructions() -> str:
    return (
        "You are Fusion CRM Manager Answer Generator. "
        "Write a concise manager-facing answer only from the provided aggregate "
        "result and source refs. Never invent metrics, definitions, query ids, "
        "read models, catalog meaning, SQL, row-level rows, PHI, secrets, raw "
        "provider payloads, or unsupported recommendations. Return only one "
        "object with keys: summary, key_numbers, explanation, caveats, "
        "confidence, safety_notes. key_numbers must be a list of objects with "
        "keys label, value, unit, comparison. confidence must be high, medium, "
        "or low. Mention limitations in caveats when the aggregate result is "
        "partial, empty, filtered, or hard to compare."
    )


def _answer_input(payload: OpenAIManagerAnswerIn) -> str:
    envelope = {
        "schema": "fusion_manager_answer_v1",
        "policy": {
            "allowed": [
                "summarize approved aggregate execution only",
                "explain key numbers in plain language",
                "state caveats and source refs from the envelope",
            ],
            "blocked": [
                "raw SQL",
                "direct database access",
                "PHI or row-level rows",
                "secrets",
                "raw provider payloads",
                "unapproved metric definitions",
                "invented query ids or read models",
            ],
        },
        "manager_question": payload.manager_question,
        "source_refs": {
            "tool_id": payload.tool_id,
            "query_id": payload.query_id,
            "read_model_id": payload.read_model_id,
            "execution_run_id": payload.execution_run_id,
            "approved_catalog_version_refs": payload.approved_catalog_version_refs,
            "evidence_refs": payload.evidence_refs,
        },
        "data_classes": payload.data_classes,
        "caveats": payload.caveats,
        "aggregate_result": payload.aggregate_result,
    }
    return json.dumps(envelope, ensure_ascii=True, sort_keys=True)


def _coerce_plan_output(output: object) -> dict[str, object]:
    if isinstance(output, OpenAIAgentPlanDecisionOut):
        return _normalize_plan_output(output.model_dump())
    if isinstance(output, OpenAIAgentPlanOut):
        return output.model_dump(
            exclude={"provider_kind", "credential_kind", "model", "last_agent"}
        )
    return _normalize_plan_output(_parse_plan_output(str(output)))


def _coerce_answer_output(output: object) -> dict[str, object]:
    if isinstance(output, OpenAIManagerAnswerDecisionOut):
        return output.model_dump()
    if isinstance(output, OpenAIManagerAnswerOut):
        return output.model_dump(
            exclude={"provider_kind", "credential_kind", "model", "last_agent"}
        )
    return _parse_answer_output(str(output))


def _normalize_plan_output(parsed: dict[str, object]) -> dict[str, object]:
    raw_arguments = parsed.get("tool_arguments")
    if isinstance(raw_arguments, list):
        arguments: dict[str, object] = {}
        for item in raw_arguments:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            if isinstance(key, str):
                arguments[key] = item.get("value")
        parsed["tool_arguments"] = arguments
    return parsed


def _parse_answer_output(output: str) -> dict[str, object]:
    cleaned = output.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            "OpenAI answer response was not valid JSON",
            details={"provider_kind": "openai", "contract": "manager_answer_v1"},
        ) from exc
    if not isinstance(parsed, dict):
        raise ValidationError(
            "OpenAI answer response was not a JSON object",
            details={"provider_kind": "openai", "contract": "manager_answer_v1"},
        )
    return parsed


def _parse_plan_output(output: str) -> dict[str, object]:
    cleaned = output.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            "OpenAI planning response was not valid JSON",
            details={"provider_kind": "openai", "contract": "agent_plan_v1"},
        ) from exc
    if not isinstance(parsed, dict):
        raise ValidationError(
            "OpenAI planning response was not a JSON object",
            details={"provider_kind": "openai", "contract": "agent_plan_v1"},
        )
    return parsed


def _validate_plan_against_tools(
    plan: OpenAIAgentPlanOut,
    payload: OpenAIAgentPlanIn,
) -> None:
    allowed_tool_ids = {tool.id for tool in payload.tools}
    if plan.outcome == "tool_plan":
        if not plan.tool_id:
            raise ValidationError(
                "OpenAI planning response did not select a tool",
                details={"provider_kind": "openai", "contract": "agent_plan_v1"},
            )
        if plan.tool_id not in allowed_tool_ids:
            raise ValidationError(
                "OpenAI planning response selected an unknown tool",
                details={
                    "provider_kind": "openai",
                    "contract": "agent_plan_v1",
                    "tool_id": plan.tool_id,
                },
            )
        return
    if plan.tool_id is not None:
        raise ValidationError(
            "OpenAI planning response included a tool for a non-tool outcome",
            details={"provider_kind": "openai", "contract": "agent_plan_v1"},
        )
    if plan.outcome == "clarification_required" and not plan.clarification_question:
        raise ValidationError(
            "OpenAI planning response omitted the clarification question",
            details={"provider_kind": "openai", "contract": "agent_plan_v1"},
        )
    if plan.outcome == "refused" and not plan.refusal_reason:
        raise ValidationError(
            "OpenAI planning response omitted the refusal reason",
            details={"provider_kind": "openai", "contract": "agent_plan_v1"},
        )
