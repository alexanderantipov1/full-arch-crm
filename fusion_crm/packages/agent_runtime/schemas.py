"""DTOs for the Fusion CRM agent runtime."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class AgentRuntimeConnectionCheckOut(BaseModel):
    """Safe metadata returned by provider connection checks."""

    model_config = ConfigDict(frozen=True)

    ok: bool
    runtime: Literal["agent_runtime"] = "agent_runtime"
    provider_kind: Literal["openai"] = "openai"
    credential_kind: Literal["api_key"] = "api_key"
    model: str = Field(..., min_length=1)
    last_agent: str = Field(..., min_length=1)
    output: str = Field(..., min_length=1, max_length=120)


AgentRuntimeToolStatus = Literal["available", "planned", "deferred"]
AgentRuntimeToolExecutionPosture = Literal[
    "executable",
    "planning_only",
    "approval_required",
    "blocked",
]


class AgentRuntimeToolProjectionOut(BaseModel):
    """Safe metadata describing one agent-callable or planned tool."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    owner_package: str = Field(..., min_length=1)
    status: AgentRuntimeToolStatus
    callable: bool
    execution_posture: AgentRuntimeToolExecutionPosture = "planning_only"
    data_classes: list[str]
    input_posture: str = Field(..., min_length=1)
    output_posture: str = Field(..., min_length=1)
    policy_posture: str = Field(..., min_length=1)
    limits: list[str] = Field(default_factory=list)
    downstream_surfaces: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    notes: list[str] = Field(default_factory=list)


class AgentRuntimeToolsProjectionOut(BaseModel):
    """Safe tools registry projection returned to the workbench."""

    model_config = ConfigDict(frozen=True)

    runtime: Literal["agent_runtime"] = "agent_runtime"
    source: Literal["packages.tools.registry"] = "packages.tools.registry"
    tools: list[AgentRuntimeToolProjectionOut]


class AgentRuntimeLlmPlanIn(BaseModel):
    """Internal LLM planning request for Agent Runtime pilot runs."""

    model_config = ConfigDict(frozen=True)

    user_prompt: str = Field(..., min_length=1, max_length=2000)

    @field_validator("user_prompt", mode="after")
    @classmethod
    def _validate_safe_prompt(cls, value: str) -> str:
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
                raise ValueError(
                    "Unsafe prompt detail is not allowed for LLM planning."
                )
        return value


AgentRuntimeLlmPlanOutcome = Literal[
    "tool_plan",
    "clarification_required",
    "refused",
]
AgentRuntimeLlmPlanConfidence = Literal["high", "medium", "low"]
AgentRuntimeLlmPlanPolicyResult = Literal[
    "allowed",
    "denied",
    "blocked",
    "approval_required",
]

AgentRuntimeLlmExecutionStatus = Literal[
    "not_applicable",
    "not_executed",
    "executed",
    "clarification_required",
    "denied",
    "no_match",
    "failed",
]


class AgentRuntimeLlmExecutionOut(BaseModel):
    """Safe aggregate execution result attached to an LLM-planned run."""

    model_config = ConfigDict(frozen=True)

    status: AgentRuntimeLlmExecutionStatus
    tool_id: str = Field(..., min_length=1, max_length=160)
    query_id: str | None = Field(default=None, max_length=160)
    read_model_id: str | None = Field(default=None, max_length=160)
    match_status: Literal["matched", "clarification_required", "no_match"] = "no_match"
    match_confidence: Literal["high", "medium", "low"] | None = None
    match_reason: str | None = Field(default=None, max_length=400)
    matched_keywords: list[str] = Field(default_factory=list)
    output_type: Literal["aggregate", "none"] = "none"
    data_classes: list[str] = Field(default_factory=list)
    row_count: int | None = Field(default=None, ge=0)
    explanation: str | None = Field(default=None, max_length=500)
    policy_reason: str = Field(..., min_length=1, max_length=400)
    result: dict[str, object] | None = None

    @field_validator(
        "tool_id",
        "query_id",
        "read_model_id",
        "match_reason",
        "explanation",
        "policy_reason",
        mode="after",
    )
    @classmethod
    def _validate_safe_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value)

    @field_validator("data_classes", mode="after")
    @classmethod
    def _validate_safe_data_classes(cls, value: list[str]) -> list[str]:
        return [_safe_text(item) for item in value]

    @field_validator("matched_keywords", mode="after")
    @classmethod
    def _validate_safe_matched_keywords(cls, value: list[str]) -> list[str]:
        return [_safe_text(item) for item in value]


class AgentRuntimeLlmPlanOut(BaseModel):
    """Safe LLM planning response returned by Agent Runtime."""

    model_config = ConfigDict(frozen=True)

    runtime: Literal["agent_runtime"] = "agent_runtime"
    provider_kind: Literal["openai"] = "openai"
    credential_kind: Literal["api_key"] = "api_key"
    run_id: str
    model: str = Field(..., min_length=1, max_length=120)
    last_agent: str = Field(..., min_length=1, max_length=160)
    outcome: AgentRuntimeLlmPlanOutcome
    intent: str = Field(..., min_length=1, max_length=160)
    tool_id: str | None = Field(default=None, max_length=160)
    tool_arguments: dict[str, object] = Field(default_factory=dict)
    confidence: AgentRuntimeLlmPlanConfidence
    clarification_question: str | None = Field(default=None, max_length=400)
    refusal_reason: str | None = Field(default=None, max_length=400)
    safety_notes: list[str] = Field(default_factory=list)
    policy_result: AgentRuntimeLlmPlanPolicyResult
    policy_reason: str = Field(..., min_length=1, max_length=400)
    approval_required: bool = False
    execution_status: AgentRuntimeLlmExecutionStatus = "not_executed"
    execution: AgentRuntimeLlmExecutionOut | None = None
    answer_eligibility: AgentRuntimeManagerAnswerEligibilityOut | None = None
    manager_answer: AgentRuntimeManagerAnswerOut | None = None
    result_posture: Literal[
        "safe_llm_plan_metadata_only",
        "safe_aggregate_tool_execution",
    ] = "safe_llm_plan_metadata_only"

    @field_validator(
        "last_agent",
        "intent",
        "tool_id",
        "clarification_question",
        "refusal_reason",
        "policy_reason",
        mode="after",
    )
    @classmethod
    def _validate_safe_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value)

    @field_validator("safety_notes", mode="after")
    @classmethod
    def _validate_safe_notes(cls, value: list[str]) -> list[str]:
        return [_safe_text(item) for item in value]


AgentRuntimeManagerAnswerStatus = Literal[
    "generated",
    "generated_with_caveat",
    "not_generated",
    "validation_failed",
    "blocked",
]

AgentRuntimeDataQualityMetricStatus = Literal["ok", "caveat", "blocked", "unknown"]


class AgentRuntimeDataQualityMetricOut(BaseModel):
    """One safe aggregate read-model data-quality metric."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., min_length=1, max_length=160)
    label: str = Field(..., min_length=1, max_length=160)
    value: int | float | str
    unit: str | None = Field(default=None, max_length=80)
    numerator: int | float | None = None
    denominator: int | float | None = None
    status: AgentRuntimeDataQualityMetricStatus = "unknown"
    evidence_ref: str | None = Field(default=None, max_length=160)

    @field_validator("id", "label", "unit", "evidence_ref", mode="after")
    @classmethod
    def _validate_safe_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value)

    @field_validator("value", mode="after")
    @classmethod
    def _validate_safe_value(cls, value: int | float | str) -> int | float | str:
        if isinstance(value, str):
            return _safe_text(value)
        return value


class AgentRuntimeManagerAnswerKeyNumberOut(BaseModel):
    """One safe aggregate value included in a manager-facing answer."""

    model_config = ConfigDict(frozen=True)

    label: str = Field(..., min_length=1, max_length=120)
    value: int | float | str
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
    def _validate_safe_value(cls, value: int | float | str) -> int | float | str:
        if isinstance(value, str):
            return _safe_text(value)
        return value


AgentRuntimeManagerAnswerWidgetType = Literal["metric", "bar_chart"]


class AgentRuntimeManagerAnswerWidgetPointOut(BaseModel):
    """One safe aggregate point for a manager-answer widget."""

    model_config = ConfigDict(frozen=True)

    label: str = Field(..., min_length=1, max_length=120)
    value: int | float
    unit: str | None = Field(default=None, max_length=80)
    evidence_ref: str | None = Field(default=None, max_length=160)

    @field_validator("label", "unit", "evidence_ref", mode="after")
    @classmethod
    def _validate_safe_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value)

    @field_validator("value", mode="before")
    @classmethod
    def _validate_numeric_value(cls, value: object) -> object:
        if isinstance(value, bool) or isinstance(value, str):
            raise ValueError("Widget point values must be numeric aggregates.")
        return value


class AgentRuntimeManagerAnswerWidgetOut(BaseModel):
    """Safe deterministic presentation payload for a manager answer."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., min_length=1, max_length=160)
    title: str = Field(..., min_length=1, max_length=160)
    widget_type: AgentRuntimeManagerAnswerWidgetType
    unit: str | None = Field(default=None, max_length=80)
    points: list[AgentRuntimeManagerAnswerWidgetPointOut] = Field(
        default_factory=list,
        max_length=12,
    )
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("id", "title", "unit", mode="after")
    @classmethod
    def _validate_safe_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value)

    @field_validator("evidence_refs", mode="after")
    @classmethod
    def _validate_safe_refs(cls, value: list[str]) -> list[str]:
        return [_safe_text(item) for item in value]

    @model_validator(mode="after")
    def _validate_points(self) -> AgentRuntimeManagerAnswerWidgetOut:
        if not self.points:
            raise ValueError("Manager answer widgets require points.")
        return self


class AgentRuntimeManagerAnswerSourceRefsOut(BaseModel):
    """Safe refs that ground a generated manager-facing answer."""

    model_config = ConfigDict(frozen=True)

    tool_id: str = Field(..., min_length=1, max_length=160)
    query_id: str = Field(..., min_length=1, max_length=160)
    read_model_id: str = Field(..., min_length=1, max_length=160)
    execution_run_id: str = Field(..., min_length=1, max_length=160)
    approved_catalog_version_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator(
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
        "approved_catalog_version_refs",
        "evidence_refs",
        mode="after",
    )
    @classmethod
    def _validate_safe_lists(cls, value: list[str]) -> list[str]:
        return [_safe_text(item) for item in value]


class AgentRuntimeManagerAnswerOut(BaseModel):
    """Safe manager-facing answer generated from approved aggregate execution."""

    model_config = ConfigDict(frozen=True)

    status: AgentRuntimeManagerAnswerStatus
    model: str | None = Field(default=None, max_length=120)
    last_agent: str | None = Field(default=None, max_length=160)
    summary: str | None = Field(default=None, max_length=600)
    key_numbers: list[AgentRuntimeManagerAnswerKeyNumberOut] = Field(
        default_factory=list
    )
    explanation: str | None = Field(default=None, max_length=1600)
    caveats: list[str] = Field(default_factory=list)
    source_refs: AgentRuntimeManagerAnswerSourceRefsOut | None = None
    widgets: list[AgentRuntimeManagerAnswerWidgetOut] = Field(
        default_factory=list,
        max_length=8,
    )
    confidence: AgentRuntimeLlmPlanConfidence | None = None
    safety_notes: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)

    @field_validator("model", "last_agent", "summary", "explanation", mode="after")
    @classmethod
    def _validate_safe_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value)

    @field_validator(
        "caveats",
        "safety_notes",
        "validation_errors",
        mode="after",
    )
    @classmethod
    def _validate_safe_lists(cls, value: list[str]) -> list[str]:
        return [_safe_text(item) for item in value]

    @model_validator(mode="after")
    def _validate_generated_answer_contract(self) -> AgentRuntimeManagerAnswerOut:
        if self.status in {"generated", "generated_with_caveat"}:
            if not self.summary:
                raise ValueError("Generated manager answers require a summary.")
            if not self.key_numbers:
                raise ValueError("Generated manager answers require key numbers.")
            if not self.explanation:
                raise ValueError("Generated manager answers require an explanation.")
            if self.source_refs is None:
                raise ValueError("Generated manager answers require source refs.")
            if self.confidence is None:
                raise ValueError("Generated manager answers require confidence.")
            if not self.safety_notes:
                raise ValueError("Generated manager answers require safety notes.")
        elif self.status in {"validation_failed", "blocked"} and not (
            self.validation_errors or self.caveats
        ):
            raise ValueError(
                "Blocked or validation-failed manager answers require a safe reason."
            )
        return self


class AgentRuntimeManagerAnswerEligibilityOut(BaseModel):
    """Safe eligibility decision before manager answer generation."""

    model_config = ConfigDict(frozen=True)

    eligible: bool
    reason: str = Field(..., min_length=1, max_length=400)
    answer_posture: Literal["generated", "generated_with_caveat", "blocked"]
    execution_status: AgentRuntimeLlmExecutionStatus
    result_posture: Literal[
        "safe_llm_plan_metadata_only",
        "safe_aggregate_tool_execution",
    ]
    tool_id: str | None = Field(default=None, max_length=160)
    query_id: str | None = Field(default=None, max_length=160)
    read_model_id: str | None = Field(default=None, max_length=160)
    data_classes: list[str] = Field(default_factory=list)
    source_refs: AgentRuntimeManagerAnswerSourceRefsOut | None = None
    data_quality_evidence_refs: list[str] = Field(default_factory=list)
    data_quality_metrics: list[AgentRuntimeDataQualityMetricOut] = Field(
        default_factory=list
    )
    caveats: list[str] = Field(default_factory=list)

    @field_validator(
        "reason",
        "tool_id",
        "query_id",
        "read_model_id",
        mode="after",
    )
    @classmethod
    def _validate_safe_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value)

    @field_validator("data_classes", "data_quality_evidence_refs", "caveats", mode="after")
    @classmethod
    def _validate_safe_data_classes(cls, value: list[str]) -> list[str]:
        return [_safe_text(item) for item in value]

    @model_validator(mode="after")
    def _validate_eligibility_refs(self) -> AgentRuntimeManagerAnswerEligibilityOut:
        if self.eligible:
            if self.answer_posture == "blocked":
                raise ValueError("Eligible answers require a generated answer posture.")
            if self.execution_status != "executed":
                raise ValueError("Eligible answers require executed aggregate status.")
            if self.result_posture != "safe_aggregate_tool_execution":
                raise ValueError(
                    "Eligible answers require safe aggregate tool execution posture."
                )
            if self.source_refs is None:
                raise ValueError("Eligible answers require source refs.")
        return self


AgentRuntimeRunStatus = Literal[
    "success",
    "failure",
    "blocked",
    "approval_required",
    "denied",
]

AgentRuntimeDataLevel = Literal[
    "none",
    "metadata_only",
    "aggregate_only",
    "row_level",
]

AgentRuntimePolicyDecisionResult = Literal[
    "allowed",
    "denied",
    "blocked",
    "approval_required",
]

AgentRuntimeFinalOutcome = Literal[
    "completed",
    "failed",
    "blocked",
    "denied",
    "approval_required",
]

AgentRuntimeCatalogConsumptionStatus = Literal[
    "approved_version_refs",
    "missing_catalog_version",
    "not_applicable",
]


class AgentRuntimeToolCallSummaryOut(BaseModel):
    """Safe summary of a tool call inside an agent run."""

    model_config = ConfigDict(frozen=True)

    tool_id: str = Field(..., min_length=1)
    status: AgentRuntimeRunStatus
    data_classes: list[str] = Field(default_factory=list)
    output_posture: str = Field(..., min_length=1)
    approval_request_id: str | None = Field(default=None, max_length=120)


class AgentRuntimePolicyDecisionOut(BaseModel):
    """Safe policy decision summary for an agent run."""

    model_config = ConfigDict(frozen=True)

    gate_id: str = Field(..., min_length=1, max_length=120)
    result: AgentRuntimePolicyDecisionResult
    reason: str = Field(..., min_length=1, max_length=400)
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("gate_id", "reason", mode="after")
    @classmethod
    def _validate_safe_text(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("evidence_refs", mode="after")
    @classmethod
    def _validate_safe_refs(cls, value: list[str]) -> list[str]:
        return [_safe_text(item) for item in value]


class AgentRuntimeAnswerWidgetAuditSummaryOut(BaseModel):
    """Audit-safe metadata for manager answer widgets."""

    model_config = ConfigDict(frozen=True)

    count: int = Field(default=0, ge=0, le=8)
    types: list[AgentRuntimeManagerAnswerWidgetType] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("evidence_refs", mode="after")
    @classmethod
    def _validate_safe_refs(cls, value: list[str]) -> list[str]:
        return [_safe_text(item) for item in value]


class AgentRuntimeAnswerAuditSummaryOut(BaseModel):
    """Safe manager answer metadata attached to run history."""

    model_config = ConfigDict(frozen=True)

    status: AgentRuntimeManagerAnswerStatus
    eligible: bool = False
    reason: str = Field(..., min_length=1, max_length=400)
    answer_posture: Literal["generated", "generated_with_caveat", "blocked"] | None = None
    model: str | None = Field(default=None, max_length=120)
    confidence: AgentRuntimeLlmPlanConfidence | None = None
    source_refs: AgentRuntimeManagerAnswerSourceRefsOut | None = None
    caveats: list[str] = Field(default_factory=list)
    data_quality_evidence_refs: list[str] = Field(default_factory=list)
    data_quality_metrics: list[AgentRuntimeDataQualityMetricOut] = Field(
        default_factory=list
    )
    widget_summary: AgentRuntimeAnswerWidgetAuditSummaryOut = Field(
        default_factory=AgentRuntimeAnswerWidgetAuditSummaryOut
    )
    safety_notes: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)

    @field_validator("reason", "model", mode="after")
    @classmethod
    def _validate_safe_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value)

    @field_validator(
        "caveats",
        "data_quality_evidence_refs",
        "safety_notes",
        "validation_errors",
        mode="after",
    )
    @classmethod
    def _validate_safe_lists(cls, value: list[str]) -> list[str]:
        return [_safe_text(item) for item in value]


class AgentRuntimeAuditSummaryOut(BaseModel):
    """Safe audit posture attached to an agent run summary."""

    model_config = ConfigDict(frozen=True)

    data_classes: list[str] = Field(default_factory=list)
    data_level: AgentRuntimeDataLevel = "metadata_only"
    row_level: bool = False
    phi: bool = False
    billing: bool = False
    export: bool = False
    masked: bool = True
    policy_result: str = Field(..., min_length=1)
    policy_gate: str = Field(default="runtime_preflight", min_length=1, max_length=120)
    policy_reason: str | None = Field(default=None, max_length=400)
    approval_required: bool = False
    final_outcome: AgentRuntimeFinalOutcome = "completed"
    policy_decisions: list[AgentRuntimePolicyDecisionOut] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    compliance_notes: list[str] = Field(default_factory=list)
    linked_approval_request_ids: list[str] = Field(default_factory=list)
    query_registry_refs: list[str] = Field(default_factory=list)
    read_model_refs: list[str] = Field(default_factory=list)
    approved_catalog_version_refs: list[str] = Field(default_factory=list)
    catalog_consumption_status: AgentRuntimeCatalogConsumptionStatus = (
        "not_applicable"
    )
    answer: AgentRuntimeAnswerAuditSummaryOut | None = None

    @field_validator(
        "policy_result",
        "policy_gate",
        "policy_reason",
        mode="after",
    )
    @classmethod
    def _validate_safe_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value)

    @field_validator(
        "data_classes",
        "evidence_refs",
        "compliance_notes",
        "linked_approval_request_ids",
        "query_registry_refs",
        "read_model_refs",
        "approved_catalog_version_refs",
        mode="after",
    )
    @classmethod
    def _validate_safe_lists(cls, value: list[str]) -> list[str]:
        return [_safe_text(item) for item in value]


class AgentRuntimeRunSummaryOut(BaseModel):
    """Safe history row for one agent runtime execution."""

    model_config = ConfigDict(frozen=True)

    id: str
    agent_name: str = Field(..., min_length=1)
    provider_kind: str = Field(..., min_length=1)
    model: str | None = None
    run_kind: str = Field(..., min_length=1)
    status: AgentRuntimeRunStatus
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    triggered_by: str | None = None
    tool_calls: list[AgentRuntimeToolCallSummaryOut] = Field(default_factory=list)
    result_posture: str = Field(..., min_length=1)
    audit_summary: AgentRuntimeAuditSummaryOut
    error_code: str | None = None
    error_message: str | None = None


class AgentRuntimeRunHistoryFiltersOut(BaseModel):
    """Safe filters applied to Agent Runtime run history."""

    model_config = ConfigDict(frozen=True)

    limit: int = Field(default=25, ge=1, le=100)
    status: AgentRuntimeRunStatus | None = None
    tool_id: str | None = Field(default=None, max_length=160)
    policy_result: str | None = Field(default=None, max_length=80)
    final_outcome: AgentRuntimeFinalOutcome | None = None
    triggered_by: str | None = Field(default=None, max_length=320)
    started_after: datetime | None = None
    started_before: datetime | None = None

    @field_validator("tool_id", "policy_result", "triggered_by", mode="after")
    @classmethod
    def _validate_safe_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value)


class AgentRuntimeRunHistoryOut(BaseModel):
    """Safe recent Agent Runtime run history."""

    model_config = ConfigDict(frozen=True)

    runtime: Literal["agent_runtime"] = "agent_runtime"
    filters: AgentRuntimeRunHistoryFiltersOut = Field(
        default_factory=AgentRuntimeRunHistoryFiltersOut
    )
    runs: list[AgentRuntimeRunSummaryOut]


AgentRuntimeApprovalStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "needs_edit",
    "unresolved",
]

AgentRuntimeApprovalWorkflowState = Literal[
    "pending_review",
    "approved_no_auto_execution",
    "rejected",
    "needs_edit",
    "unresolved",
    "expired",
    "executed_after_approval",
]

AgentRuntimeApprovalTargetKind = Literal[
    "semantic_catalog_mapping_proposal",
    "semantic_catalog_impact_preview",
    "large_analysis_run",
    "export_request",
    "write_tool_execution",
]

AgentRuntimeApprovalDecision = Literal[
    "approve",
    "reject",
    "request_edit",
    "mark_unresolved",
]


class AgentRuntimeApprovalRequestCreateIn(BaseModel):
    """Safe request to create a human approval boundary."""

    model_config = ConfigDict(frozen=True)

    source_run_id: str | None = None
    agent_name: str = Field(..., min_length=1, max_length=160)
    tool_id: str | None = Field(default=None, max_length=160)
    target_kind: AgentRuntimeApprovalTargetKind
    target_ref: str | None = Field(default=None, max_length=160)
    title: str = Field(..., min_length=1, max_length=200)
    reason: str = Field(..., min_length=1, max_length=2000)
    evidence_summary: str = Field(..., min_length=1, max_length=2000)
    requested_action: str = Field(..., min_length=1, max_length=200)
    data_classes: list[str] = Field(default_factory=list)
    affected_surfaces: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    approval_posture: str = Field(
        default="human_review_required_no_auto_mutation",
        min_length=1,
        max_length=120,
    )


class AgentRuntimeApprovalDecisionIn(BaseModel):
    """Human decision for one pending approval request."""

    model_config = ConfigDict(frozen=True)

    decision: AgentRuntimeApprovalDecision
    decision_summary: str = Field(..., min_length=1, max_length=2000)
    edit_summary: str | None = Field(default=None, max_length=2000)


class AgentRuntimeApprovalRequestOut(BaseModel):
    """Safe approval request summary returned to the workbench."""

    model_config = ConfigDict(frozen=True)

    id: str
    source_run_id: str | None = None
    agent_name: str = Field(..., min_length=1)
    tool_id: str | None = None
    target_kind: AgentRuntimeApprovalTargetKind
    target_ref: str | None = None
    title: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    evidence_summary: str = Field(..., min_length=1)
    requested_action: str = Field(..., min_length=1)
    status: AgentRuntimeApprovalStatus
    requested_at: datetime
    requested_by: str | None = None
    decided_at: datetime | None = None
    decided_by: str | None = None
    workflow_state: AgentRuntimeApprovalWorkflowState = "pending_review"
    data_classes: list[str] = Field(default_factory=list)
    affected_surfaces: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    approval_posture: str = Field(..., min_length=1)
    decision_summary: str | None = None
    edit_summary: str | None = None


class AgentRuntimeApprovalRequestsOut(BaseModel):
    """Safe recent human approval requests."""

    model_config = ConfigDict(frozen=True)

    runtime: Literal["agent_runtime"] = "agent_runtime"
    approvals: list[AgentRuntimeApprovalRequestOut]


AgentRuntimeLinkageImpactConfidence = Literal["known", "likely", "unknown"]
AgentRuntimeLinkageStepStatus = Literal[
    "ready",
    "in_review",
    "blocked",
    "planned",
    "deferred",
]


class AgentRuntimeLinkageImpactSurfaceOut(BaseModel):
    """Safe surface impacted by a review-only agent output."""

    model_config = ConfigDict(frozen=True)

    surface: str = Field(..., min_length=1, max_length=120)
    confidence: AgentRuntimeLinkageImpactConfidence
    reason: str = Field(..., min_length=1, max_length=400)

    @field_validator("surface", "reason", mode="after")
    @classmethod
    def _validate_safe_text(cls, value: str) -> str:
        return _safe_text(value)


class AgentRuntimeLinkageStepOut(BaseModel):
    """One step in the agent-to-approved-catalog path."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., min_length=1, max_length=120)
    title: str = Field(..., min_length=1, max_length=160)
    status: AgentRuntimeLinkageStepStatus
    owner: str = Field(..., min_length=1, max_length=160)
    contract: str = Field(..., min_length=1, max_length=400)

    @field_validator("id", "title", "owner", "contract", mode="after")
    @classmethod
    def _validate_safe_text(cls, value: str) -> str:
        return _safe_text(value)


class AgentRuntimeDiaCatalogLinkageOut(BaseModel):
    """Safe linkage projection from DIA output to catalog review."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., min_length=1, max_length=120)
    title: str = Field(..., min_length=1, max_length=200)
    source_agent: str = Field(..., min_length=1, max_length=160)
    output_kind: Literal["mapping_proposal", "gap_brief"]
    runtime_run_id: str | None = None
    approval_request_id: str | None = None
    catalog_proposal_ref: str | None = Field(default=None, max_length=160)
    approved_catalog_version_ref: str | None = Field(default=None, max_length=160)
    review_posture: str = Field(..., min_length=1, max_length=160)
    downstream_consumption: Literal["approved_version_only"]
    data_classes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    query_registry_refs: list[str] = Field(default_factory=list)
    read_model_refs: list[str] = Field(default_factory=list)
    approved_catalog_version_refs: list[str] = Field(default_factory=list)
    impact_surfaces: list[AgentRuntimeLinkageImpactSurfaceOut]
    path: list[AgentRuntimeLinkageStepOut]
    notes: list[str] = Field(default_factory=list)

    @field_validator(
        "id",
        "title",
        "source_agent",
        "runtime_run_id",
        "approval_request_id",
        "catalog_proposal_ref",
        "approved_catalog_version_ref",
        "review_posture",
        mode="after",
    )
    @classmethod
    def _validate_safe_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value)

    @field_validator(
        "data_classes",
        "evidence_refs",
        "query_registry_refs",
        "read_model_refs",
        "approved_catalog_version_refs",
        "notes",
        mode="after",
    )
    @classmethod
    def _validate_safe_lists(cls, value: list[str]) -> list[str]:
        return [_safe_text(item) for item in value]


class AgentRuntimeDiaCatalogLinkagesOut(BaseModel):
    """Safe DIA and Semantic Catalog linkage projection."""

    model_config = ConfigDict(frozen=True)

    runtime: Literal["agent_runtime"] = "agent_runtime"
    source: Literal["agent_runtime_projection"] = "agent_runtime_projection"
    linkages: list[AgentRuntimeDiaCatalogLinkageOut]


def _safe_text(value: str) -> str:
    lowered = value.lower()
    for marker in _SENSITIVE_TEXT_MARKERS:
        if marker in lowered:
            raise ValueError("Unsafe detail is not allowed in agent runtime summaries.")
    return value
