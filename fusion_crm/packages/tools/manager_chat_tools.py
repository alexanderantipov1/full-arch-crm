"""Manager analytics chat tools.

V1 is deterministic: it maps manager questions to approved analytics query ids,
builds a structured query spec, enforces aggregate-only posture, and optionally
executes through ``run_analytics_query``. It does not call an LLM and does not
accept SQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

from packages.audit.service import AuditService
from packages.core.exceptions import ValidationError

from .analytics_tools import AnalyticsQueryId, analytics_query_metadata, run_analytics_query
from .base import ToolContext
from .semantic_time import (
    ResolvedTimeWindow,
    apply_question_time_window,
    coerce_datetime,
    normalized_question_text,
)


@dataclass(frozen=True, slots=True)
class _QuestionRule:
    query_id: AnalyticsQueryId
    keywords: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ManagerAnalyticsQueryMatch:
    """Deterministic approved query/read-model match for a manager question."""

    query_id: AnalyticsQueryId
    read_model_id: str
    confidence: Literal["high", "medium", "low"]
    matched_keywords: tuple[str, ...]
    reason: str


_QUESTION_RULES: tuple[_QuestionRule, ...] = (
    _QuestionRule(
        query_id="paid_leads_by_source.v1",
        keywords=(
            "paid lead",
            "paid source",
            "google",
            "facebook",
            "meta",
            "instagram",
            "ppc",
            "adwords",
            "paid search",
            "paid social",
            "платн",
            "реклам",
            "источник кампании",
            "leads pagados",
            "campana",
            "fuente",
        ),
    ),
    _QuestionRule(
        query_id="treatment_revenue_evidence.v1",
        keywords=(
            "revenue",
            "payment",
            "collected",
            "collection",
            "treatment",
            "invoice",
            "выруч",
            "оплат",
            "собра",
            "tratamiento",
            "ingreso",
            "pago",
        ),
    ),
    _QuestionRule(
        query_id="consultation_followup_worklist.v1",
        keywords=(
            "follow-up",
            "followup",
            "overdue",
            "no show",
            "no-show",
            "next action",
            "consultation follow",
            "не приш",
            "не яв",
            "вернул",
            "вернуть",
            "перезапис",
            "повторн",
            "consulta seguimiento",
            "seguimiento",
            "no vino",
            "no asist",
            "recuper",
        ),
    ),
    _QuestionRule(
        query_id="lead_conversion_funnel.v1",
        keywords=(
            "conversion",
            "funnel",
            "booked",
            "booked appointment",
            "completed consult",
            "scheduled appointment",
            "scheduled appointments",
            "scheduled consultation",
            "appointment conversion",
            "appointments scheduled",
            "converted",
            "consult rate",
            "конверс",
            "воронк",
            "запис",
            "консультац",
            "embudo",
            "cita programada",
            "citas programadas",
            "agendada",
            "agendadas",
            "consulta complet",
        ),
    ),
    _QuestionRule(
        query_id="lead_source_profile.v1",
        keywords=(
            "lead source",
            "source profile",
            "where leads",
            "which source",
            "источник лид",
            "откуда лид",
            "fuente",
            "origen",
        ),
    ),
)


async def ask_manager_analytics(
    ctx: ToolContext,
    *,
    question: str,
    params: dict[str, object] | None = None,
    execute: bool = True,
) -> dict:
    """Plan and optionally execute an approved aggregate manager question."""
    clean_question = question.strip()
    if not clean_question:
        raise ValidationError("question is required")

    planned_match = select_manager_query_match(clean_question)
    planned_query_id = planned_match.query_id if planned_match is not None else None

    if planned_query_id is None:
        audit = AuditService(ctx.session)
        await audit.record_tool_call(
            principal=ctx.principal,
            tool_name="ask_manager_analytics",
            extra={
                "planned_query_id": planned_query_id,
                "execute": execute,
                "param_keys": sorted((params or {}).keys()),
            },
        )
        return {
            "planner": {
                "status": "clarification_needed",
                "question": clean_question,
                "reason": "Question did not match an approved V1 analytics intent.",
                "clarification": (
                    "Ask about lead source, conversion funnel, paid leads, "
                    "consultation follow-up, or treatment revenue."
                ),
            },
            "query_spec": None,
            "policy_preflight": {
                "decision": "clarify",
                "reason": "No approved query id selected.",
            },
            "execution": None,
            "explanation": None,
        }

    planned_params = _apply_manager_time_window(clean_question, params or {})
    time_window = _manager_time_window_from_params(planned_params)
    audit = AuditService(ctx.session)
    await audit.record_tool_call(
        principal=ctx.principal,
        tool_name="ask_manager_analytics",
        extra={
            "planned_query_id": planned_query_id,
            "execute": execute,
            "param_keys": sorted(planned_params.keys()),
            "time_window_source": time_window.source,
            "time_window_preset": time_window.preset,
            "time_window_disclosure": time_window.disclosure,
        },
    )

    query_spec = {
        "intent": "manager_analytics",
        "query_id": planned_query_id,
        "params": planned_params,
        "output_level": "aggregate",
    }
    policy_preflight = {
        "decision": "allow",
        "reason": "Aggregate-only V1 analytics query selected from approved registry.",
        "row_level": False,
        "export": False,
        "raw_sql": False,
        "raw_payload": False,
    }

    execution = None
    explanation = None
    if execute:
        execution = await run_analytics_query(
            ctx,
            query_id=planned_query_id,
            params=planned_params,
        )
        execution = _attach_manager_time_window(execution, time_window)
        explanation = _explain_aggregate_result(execution)

    return {
        "planner": {
            "status": "planned",
            "question": clean_question,
            "query_id": planned_query_id,
            "read_model_id": planned_match.read_model_id if planned_match else None,
            "match_confidence": planned_match.confidence if planned_match else None,
            "match_reason": planned_match.reason if planned_match else None,
            "matched_keywords": list(planned_match.matched_keywords)
            if planned_match
            else [],
        },
        "query_spec": query_spec,
        "policy_preflight": policy_preflight,
        "execution": execution,
        "explanation": explanation,
    }


def select_manager_query_id(question: str) -> AnalyticsQueryId | None:
    """Select an approved query id using deterministic V1 keyword rules."""
    match = select_manager_query_match(question)
    return match.query_id if match is not None else None


def select_manager_query_match(question: str) -> ManagerAnalyticsQueryMatch | None:
    """Return deterministic approved query/read-model metadata for a question."""
    text = normalized_question_text(question)
    scores: list[tuple[int, int, _QuestionRule, tuple[str, ...]]] = []
    for index, rule in enumerate(_QUESTION_RULES):
        matched_keywords = tuple(
            keyword
            for keyword in rule.keywords
            if normalized_question_text(keyword) in text
        )
        score = len(matched_keywords)
        if score:
            scores.append((score, -index, rule, matched_keywords))
    if not scores:
        return None
    score, _, rule, matched_keywords = max(scores)
    metadata = analytics_query_metadata(rule.query_id)
    confidence: Literal["high", "medium", "low"]
    if score >= 2:
        confidence = "high"
    else:
        confidence = "medium"
    return ManagerAnalyticsQueryMatch(
        query_id=rule.query_id,
        read_model_id=str(metadata["read_model_id"]),
        confidence=confidence,
        matched_keywords=matched_keywords,
        reason=(
            "Question matched approved manager analytics query keywords: "
            + ", ".join(matched_keywords)
        ),
    )

def _explain_aggregate_result(execution: dict[str, object]) -> str:
    query_id = str(execution.get("query_id"))
    read_model_id = str(execution.get("read_model_id"))
    row_count_raw = execution.get("row_count")
    row_count = row_count_raw if isinstance(row_count_raw, int) else 0
    explanation = (
        f"Executed {query_id} for read model {read_model_id}. "
        f"The result is aggregate-only and contains {row_count} aggregate buckets. "
        "No row-level drilldown or export was produced."
    )
    time_window = execution.get("time_window")
    if isinstance(time_window, dict):
        disclosure = time_window.get("disclosure")
        if isinstance(disclosure, str) and disclosure.strip():
            explanation = f"{explanation} {disclosure.strip()}"
    return explanation


def _apply_manager_time_window(
    question: str,
    params: dict[str, object],
) -> dict[str, object]:
    return apply_question_time_window(
        params,
        question=question,
        now=_utc_now(),
        preserve_stamped=True,
    )


def _manager_time_window_from_params(params: dict[str, object]) -> ResolvedTimeWindow:
    return ResolvedTimeWindow(
        preset=str(params["time_window_preset"]),
        source=_time_window_source(params["time_window_source"]),
        created_from=coerce_datetime(params.get("created_from")),
        created_to=coerce_datetime(params.get("created_to")),
        disclosure=str(params["time_window_disclosure"]),
    )


def _time_window_source(value: object) -> Literal["explicit", "semantic", "default"]:
    if value in {"explicit", "semantic", "default"}:
        return cast(Literal["explicit", "semantic", "default"], value)
    raise ValidationError(
        "invalid manager analytics time-window source",
        details={"time_window_source": str(value)},
    )


def _attach_manager_time_window(
    execution: dict[str, object],
    time_window: ResolvedTimeWindow,
) -> dict[str, object]:
    updated = dict(execution)
    metadata = {
        "source": time_window.source,
        "preset": time_window.preset,
        "created_from": time_window.created_from.isoformat()
        if time_window.created_from is not None
        else None,
        "created_to": time_window.created_to.isoformat()
        if time_window.created_to is not None
        else None,
        "disclosure": time_window.disclosure,
    }
    updated["time_window"] = metadata
    filters = updated.get("filters")
    if isinstance(filters, dict):
        updated["filters"] = {
            **filters,
            "time_window_source": time_window.source,
            "time_window_preset": time_window.preset,
            "time_window_disclosure": time_window.disclosure,
        }
    return updated

def _utc_now() -> datetime:
    return datetime.now(tz=UTC)
