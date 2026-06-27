"""DTOs for OpenAI integration calls."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SENSITIVE_TEXT_MARKERS = (
    "sk-",
    "raw_provider_payload",
    "raw payload",
    "raw_sql",
    "raw sql",
    "select *",
    "patient_name",
    "date_of_birth",
    "full_prompt",
)


class OpenAIConnectionCheckOut(BaseModel):
    """Safe metadata returned by the OpenAI connection health check."""

    model_config = ConfigDict(frozen=True)

    ok: bool
    provider_kind: Literal["openai"] = "openai"
    credential_kind: Literal["api_key"] = "api_key"
    model: str = Field(..., min_length=1)
    last_agent: str = Field(..., min_length=1)
    output: str = Field(..., min_length=1, max_length=120)


class OpenAIToolDescriptor(BaseModel):
    """Safe tool metadata projected into an LLM planning prompt."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., min_length=1, max_length=160)
    description: str = Field(..., min_length=1, max_length=600)
    data_classes: list[str] = Field(default_factory=list)
    input_posture: str = Field(..., min_length=1, max_length=240)
    output_posture: str = Field(..., min_length=1, max_length=240)
    policy_posture: str = Field(..., min_length=1, max_length=400)
    requires_approval: bool = False

    @field_validator(
        "id",
        "description",
        "input_posture",
        "output_posture",
        "policy_posture",
        mode="after",
    )
    @classmethod
    def _validate_safe_text(cls, value: str) -> str:
        return _safe_descriptor_text(value)

    @field_validator("data_classes", mode="after")
    @classmethod
    def _validate_safe_list(cls, value: list[str]) -> list[str]:
        return [_safe_descriptor_text(item) for item in value]


class OpenAIAgentPlanIn(BaseModel):
    """Safe LLM planning request assembled by Agent Runtime."""

    model_config = ConfigDict(frozen=True)

    user_prompt: str = Field(..., min_length=1, max_length=2000)
    tools: list[OpenAIToolDescriptor] = Field(..., min_length=1, max_length=40)

    @field_validator("user_prompt", mode="after")
    @classmethod
    def _validate_prompt_input(cls, value: str) -> str:
        return _safe_prompt_input(value)


OpenAIAgentPlanConfidence = Literal["high", "medium", "low"]
OpenAIAgentPlanOutcome = Literal[
    "tool_plan",
    "clarification_required",
    "refused",
]
OpenAIAgentPlanArgumentValue = str | int | float | bool | None


class OpenAIAgentPlanArgumentOut(BaseModel):
    """Strict key/value argument shape used for model structured output."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(..., min_length=1, max_length=120)
    value: OpenAIAgentPlanArgumentValue = None

    @field_validator("key", mode="after")
    @classmethod
    def _validate_safe_key(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("value", mode="after")
    @classmethod
    def _validate_safe_value(
        cls,
        value: OpenAIAgentPlanArgumentValue,
    ) -> OpenAIAgentPlanArgumentValue:
        if isinstance(value, str):
            return _safe_text(value)
        return value


class OpenAIAgentPlanDecisionOut(BaseModel):
    """Validated, safe LLM planning decision produced by the model."""

    model_config = ConfigDict(frozen=True)

    outcome: OpenAIAgentPlanOutcome
    intent: str = Field(..., min_length=1, max_length=160)
    tool_id: str | None = Field(default=None, max_length=160)
    tool_arguments: list[OpenAIAgentPlanArgumentOut] = Field(
        default_factory=list,
        max_length=20,
    )
    confidence: OpenAIAgentPlanConfidence
    clarification_question: str | None = Field(default=None, max_length=400)
    refusal_reason: str | None = Field(default=None, max_length=400)
    safety_notes: list[str] = Field(default_factory=list, max_length=8)

    @field_validator(
        "intent",
        "tool_id",
        "clarification_question",
        "refusal_reason",
        mode="after",
    )
    @classmethod
    def _validate_safe_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value)

    @field_validator("tool_arguments", mode="after")
    @classmethod
    def _validate_safe_arguments(
        cls,
        value: list[OpenAIAgentPlanArgumentOut],
    ) -> list[OpenAIAgentPlanArgumentOut]:
        return value

    @field_validator("safety_notes", mode="after")
    @classmethod
    def _validate_safe_notes(cls, value: list[str]) -> list[str]:
        return [_safe_text(item) for item in value]


class OpenAIAgentPlanOut(BaseModel):
    """Validated, safe LLM plan metadata returned to Agent Runtime."""

    model_config = ConfigDict(frozen=True)

    provider_kind: Literal["openai"] = "openai"
    credential_kind: Literal["api_key"] = "api_key"
    model: str = Field(..., min_length=1, max_length=120)
    last_agent: str = Field(..., min_length=1, max_length=160)
    outcome: OpenAIAgentPlanOutcome
    intent: str = Field(..., min_length=1, max_length=160)
    tool_id: str | None = Field(default=None, max_length=160)
    tool_arguments: dict[str, object] = Field(default_factory=dict)
    confidence: OpenAIAgentPlanConfidence
    clarification_question: str | None = Field(default=None, max_length=400)
    refusal_reason: str | None = Field(default=None, max_length=400)
    safety_notes: list[str] = Field(default_factory=list, max_length=8)

    @field_validator(
        "last_agent",
        "intent",
        "tool_id",
        "clarification_question",
        "refusal_reason",
        mode="after",
    )
    @classmethod
    def _validate_safe_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value)

    @field_validator("tool_arguments", mode="after")
    @classmethod
    def _validate_safe_arguments(cls, value: dict[str, object]) -> dict[str, object]:
        _validate_json_safe(value)
        return value

    @field_validator("safety_notes", mode="after")
    @classmethod
    def _validate_safe_notes(cls, value: list[str]) -> list[str]:
        return [_safe_text(item) for item in value]


OpenAIManagerAnswerConfidence = Literal["high", "medium", "low"]
OpenAIManagerAnswerValue = str | int | float


class OpenAIManagerAnswerKeyNumberOut(BaseModel):
    """One aggregate number produced by the manager answer model."""

    model_config = ConfigDict(frozen=True)

    label: str = Field(..., min_length=1, max_length=120)
    value: OpenAIManagerAnswerValue
    unit: str | None = Field(default=None, max_length=80)
    comparison: str | None = Field(default=None, max_length=240)

    @field_validator("label", "unit", "comparison", mode="after")
    @classmethod
    def _validate_safe_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value)

    @field_validator("value", mode="after")
    @classmethod
    def _validate_safe_value(
        cls,
        value: OpenAIManagerAnswerValue,
    ) -> OpenAIManagerAnswerValue:
        if isinstance(value, str):
            return _safe_text(value)
        return value


class OpenAIManagerAnswerIn(BaseModel):
    """Safe answer-generation request assembled by Agent Runtime."""

    model_config = ConfigDict(frozen=True)

    manager_question: str = Field(..., min_length=1, max_length=500)
    tool_id: str = Field(..., min_length=1, max_length=160)
    query_id: str = Field(..., min_length=1, max_length=160)
    read_model_id: str = Field(..., min_length=1, max_length=160)
    execution_run_id: str = Field(..., min_length=1, max_length=160)
    aggregate_result: dict[str, object]
    data_classes: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list, max_length=12)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    approved_catalog_version_refs: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    @field_validator(
        "manager_question",
        "tool_id",
        "query_id",
        "read_model_id",
        "execution_run_id",
        mode="after",
    )
    @classmethod
    def _validate_safe_text(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator(
        "data_classes",
        "caveats",
        "evidence_refs",
        "approved_catalog_version_refs",
        mode="after",
    )
    @classmethod
    def _validate_safe_lists(cls, value: list[str]) -> list[str]:
        return [_safe_text(item) for item in value]

    @field_validator("aggregate_result", mode="after")
    @classmethod
    def _validate_safe_result(cls, value: dict[str, object]) -> dict[str, object]:
        _validate_json_safe(value)
        return value


class OpenAIManagerAnswerDecisionOut(BaseModel):
    """Validated manager-facing answer content produced by the model."""

    model_config = ConfigDict(frozen=True)

    summary: str = Field(..., min_length=1, max_length=600)
    key_numbers: list[OpenAIManagerAnswerKeyNumberOut] = Field(
        ...,
        min_length=1,
        max_length=12,
    )
    explanation: str = Field(..., min_length=1, max_length=1600)
    caveats: list[str] = Field(default_factory=list, max_length=12)
    confidence: OpenAIManagerAnswerConfidence
    safety_notes: list[str] = Field(..., min_length=1, max_length=8)

    @field_validator("summary", "explanation", mode="after")
    @classmethod
    def _validate_safe_text(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("caveats", "safety_notes", mode="after")
    @classmethod
    def _validate_safe_lists(cls, value: list[str]) -> list[str]:
        return [_safe_text(item) for item in value]


class OpenAIManagerAnswerOut(BaseModel):
    """Validated, safe manager-facing answer returned to Agent Runtime."""

    model_config = ConfigDict(frozen=True)

    provider_kind: Literal["openai"] = "openai"
    credential_kind: Literal["api_key"] = "api_key"
    model: str = Field(..., min_length=1, max_length=120)
    last_agent: str = Field(..., min_length=1, max_length=160)
    summary: str = Field(..., min_length=1, max_length=600)
    key_numbers: list[OpenAIManagerAnswerKeyNumberOut] = Field(
        ...,
        min_length=1,
        max_length=12,
    )
    explanation: str = Field(..., min_length=1, max_length=1600)
    caveats: list[str] = Field(default_factory=list, max_length=12)
    confidence: OpenAIManagerAnswerConfidence
    safety_notes: list[str] = Field(..., min_length=1, max_length=8)

    @field_validator("last_agent", "summary", "explanation", mode="after")
    @classmethod
    def _validate_safe_text(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("caveats", "safety_notes", mode="after")
    @classmethod
    def _validate_safe_lists(cls, value: list[str]) -> list[str]:
        return [_safe_text(item) for item in value]


def _safe_prompt_input(value: str) -> str:
    lowered = value.lower()
    blocked_markers = (
        "sk-",
        "raw_provider_payload",
        "raw payload",
        "raw_sql",
        "raw sql",
        "select *",
        "patient_name",
        "date_of_birth",
        "full_prompt",
    )
    for marker in blocked_markers:
        if marker in lowered:
            raise ValueError("Unsafe prompt detail is not allowed for LLM planning.")
    return value


def _safe_text(value: str) -> str:
    lowered = value.lower()
    for marker in _SENSITIVE_TEXT_MARKERS:
        if marker in lowered:
            raise ValueError("Unsafe detail is not allowed in OpenAI summaries.")
    return value


def _safe_descriptor_text(value: str) -> str:
    lowered = value.lower()
    for marker in ("sk-", "patient_name", "date_of_birth", "full_prompt"):
        if marker in lowered:
            raise ValueError("Unsafe detail is not allowed in OpenAI tool metadata.")
    return value


def _validate_json_safe(value: object) -> None:
    if isinstance(value, str):
        _safe_text(value)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _safe_text(str(key))
            _validate_json_safe(item)
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_safe(item)
