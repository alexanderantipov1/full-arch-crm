"""Tests for Agent Runtime manager answer contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from packages.agent_runtime.schemas import (
    AgentRuntimeManagerAnswerEligibilityOut,
    AgentRuntimeManagerAnswerOut,
    AgentRuntimeManagerAnswerWidgetOut,
)


def test_manager_answer_contract_accepts_safe_generated_answer() -> None:
    answer = AgentRuntimeManagerAnswerOut(
        status="generated",
        summary="Lead conversion improved for the selected aggregate period.",
        key_numbers=[
            {
                "label": "Converted leads",
                "value": 42,
                "unit": "leads",
                "comparison": "Higher than the prior aggregate period.",
            }
        ],
        explanation=(
            "The answer is based on the approved lead conversion read model "
            "and aggregate query result."
        ),
        caveats=["The answer excludes row-level lead details."],
        source_refs={
            "tool_id": "ask_manager_analytics",
            "query_id": "lead_conversion_funnel.v1",
            "read_model_id": "lead_conversion",
            "execution_run_id": "run-123",
            "approved_catalog_version_refs": ["catalog:v1"],
            "evidence_refs": ["service_owned_read_model_execution"],
        },
        confidence="high",
        safety_notes=["Aggregate-only answer; no row-level rows included."],
    )

    assert answer.status == "generated"
    assert answer.source_refs is not None
    assert answer.source_refs.query_id == "lead_conversion_funnel.v1"


def test_manager_answer_contract_requires_generated_answer_fields() -> None:
    with pytest.raises(PydanticValidationError):
        AgentRuntimeManagerAnswerOut(
            status="generated",
            summary="Missing source refs should fail.",
            key_numbers=[{"label": "Converted leads", "value": 42}],
            explanation="Aggregate explanation.",
            confidence="medium",
            safety_notes=["Aggregate-only answer."],
        )


def test_manager_answer_contract_rejects_sensitive_text() -> None:
    with pytest.raises(PydanticValidationError):
        AgentRuntimeManagerAnswerOut(
            status="generated",
            summary="Use raw_sql to explain the answer.",
            key_numbers=[{"label": "Converted leads", "value": 42}],
            explanation="Aggregate explanation.",
            source_refs={
                "tool_id": "ask_manager_analytics",
                "query_id": "lead_conversion_funnel.v1",
                "read_model_id": "lead_conversion",
                "execution_run_id": "run-123",
            },
            confidence="low",
            safety_notes=["Aggregate-only answer."],
        )


def test_manager_answer_widget_contract_accepts_safe_payload() -> None:
    widget = AgentRuntimeManagerAnswerWidgetOut(
        id="consultation_status_bar_chart",
        title="Consultation Status",
        widget_type="bar_chart",
        unit="count",
        points=[
            {
                "label": "scheduled",
                "value": 2,
                "unit": "count",
                "evidence_ref": "result.result.consultation_status[0].count",
            }
        ],
        evidence_refs=["result.result.consultation_status[0].count"],
    )

    assert widget.widget_type == "bar_chart"
    assert widget.points[0].value == 2


def test_manager_answer_widget_contract_rejects_sensitive_text() -> None:
    with pytest.raises(PydanticValidationError):
        AgentRuntimeManagerAnswerWidgetOut(
            id="raw_sql_widget",
            title="Unsafe widget",
            widget_type="metric",
            points=[{"label": "Unsafe", "value": 1}],
        )


def test_manager_answer_widget_contract_rejects_empty_points() -> None:
    with pytest.raises(PydanticValidationError):
        AgentRuntimeManagerAnswerWidgetOut(
            id="empty_widget",
            title="Empty Widget",
            widget_type="bar_chart",
            points=[],
        )


def test_manager_answer_widget_contract_rejects_bool_values() -> None:
    with pytest.raises(PydanticValidationError):
        AgentRuntimeManagerAnswerWidgetOut(
            id="boolean_widget",
            title="Boolean Widget",
            widget_type="metric",
            points=[{"label": "Converted", "value": True}],
        )


def test_manager_answer_widget_contract_rejects_string_values() -> None:
    with pytest.raises(PydanticValidationError):
        AgentRuntimeManagerAnswerWidgetOut(
            id="string_widget",
            title="String Widget",
            widget_type="metric",
            points=[{"label": "Converted", "value": "42"}],
        )


def test_manager_answer_eligibility_requires_executed_aggregate_source_refs() -> None:
    eligible = AgentRuntimeManagerAnswerEligibilityOut(
        eligible=True,
        reason="Approved aggregate execution can be summarized.",
        answer_posture="generated",
        execution_status="executed",
        result_posture="safe_aggregate_tool_execution",
        tool_id="ask_manager_analytics",
        query_id="lead_conversion_funnel.v1",
        read_model_id="lead_conversion",
        data_classes=["ops", "integration metadata"],
        source_refs={
            "tool_id": "ask_manager_analytics",
            "query_id": "lead_conversion_funnel.v1",
            "read_model_id": "lead_conversion",
            "execution_run_id": "run-123",
        },
    )

    assert eligible.eligible is True

    with pytest.raises(PydanticValidationError):
        AgentRuntimeManagerAnswerEligibilityOut(
            eligible=True,
            reason="Planning-only posture should fail.",
            answer_posture="generated",
            execution_status="not_executed",
            result_posture="safe_llm_plan_metadata_only",
        )
