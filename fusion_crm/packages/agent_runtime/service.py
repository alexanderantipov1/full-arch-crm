"""Application-owned agent runtime service."""

from __future__ import annotations

import unicodedata
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import NotFoundError, PlatformError, ValidationError
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.integrations.openai.schemas import (
    OpenAIAgentPlanIn,
    OpenAIAgentPlanOut,
    OpenAIManagerAnswerIn,
    OpenAIManagerAnswerOut,
    OpenAIToolDescriptor,
)
from packages.integrations.openai.service import OpenAIIntegrationService
from packages.tools.analytics_tools import (
    AnalyticsQueryId,
    analytics_query_metadata,
    canonical_analytics_query_literal,
)
from packages.tools.base import ToolContext, ToolSpec
from packages.tools.manager_chat_tools import (
    ManagerAnalyticsQueryMatch,
    select_manager_query_match,
)
from packages.tools.registry import ALL_TOOLS
from packages.tools.semantic_time import apply_question_time_window

from .models import AgentRuntimeApprovalRequest, AgentRuntimeRun
from .repository import (
    AgentRuntimeApprovalRequestRepository,
    AgentRuntimeRunRepository,
)
from .schemas import (
    AgentRuntimeApprovalDecisionIn,
    AgentRuntimeApprovalRequestCreateIn,
    AgentRuntimeApprovalRequestOut,
    AgentRuntimeApprovalRequestsOut,
    AgentRuntimeApprovalStatus,
    AgentRuntimeApprovalTargetKind,
    AgentRuntimeAuditSummaryOut,
    AgentRuntimeConnectionCheckOut,
    AgentRuntimeDataQualityMetricOut,
    AgentRuntimeDiaCatalogLinkageOut,
    AgentRuntimeDiaCatalogLinkagesOut,
    AgentRuntimeFinalOutcome,
    AgentRuntimeLinkageImpactSurfaceOut,
    AgentRuntimeLinkageStepOut,
    AgentRuntimeLlmExecutionOut,
    AgentRuntimeLlmPlanIn,
    AgentRuntimeLlmPlanOut,
    AgentRuntimeManagerAnswerEligibilityOut,
    AgentRuntimeManagerAnswerOut,
    AgentRuntimeManagerAnswerSourceRefsOut,
    AgentRuntimeManagerAnswerWidgetOut,
    AgentRuntimeManagerAnswerWidgetPointOut,
    AgentRuntimeRunHistoryFiltersOut,
    AgentRuntimeRunHistoryOut,
    AgentRuntimeRunStatus,
    AgentRuntimeRunSummaryOut,
    AgentRuntimeToolExecutionPosture,
    AgentRuntimeToolProjectionOut,
    AgentRuntimeToolsProjectionOut,
)

_SENSITIVE_APPROVAL_MARKERS = (
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

_SAFE_LLM_PLANNING_TOOL_IDS = frozenset(
    {
        "ask_manager_analytics",
        "run_analytics_query",
        "data_intelligence_discover",
        "data_intelligence_preflight",
        "data_intelligence_profile_field",
        "data_intelligence_evidence_coverage",
        "data_intelligence_person_journey_proposals",
        "data_intelligence_gap_brief",
    }
)

_LLM_TOOL_EXECUTION_REGISTRY: dict[str, str] = {
    "ask_manager_analytics": "manager_analytics_question",
    "run_analytics_query": "analytics_query",
}

_DETERMINISTIC_MANAGER_ANALYTICS_FALLBACK_NOTE = (
    "Deterministic approved manager analytics matcher selected "
    "ask_manager_analytics after LLM clarification."
)


@dataclass(frozen=True, slots=True)
class _LlmPlanPolicy:
    result: str
    run_status: str
    final_outcome: str
    reason: str
    approval_required: bool = False


@dataclass(frozen=True, slots=True)
class _ApprovedQueryReadModelMatch:
    query_id: str
    read_model_id: str
    confidence: Literal["high", "medium", "low"]
    matched_keywords: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class _LlmToolExecution:
    status: str
    run_status: str
    final_outcome: str
    result_posture: str
    policy_reason: str
    output: AgentRuntimeLlmExecutionOut | None = None
    error_code: str | None = None
    error_message: str | None = None
    query_match: _ApprovedQueryReadModelMatch | None = None


_TOOL_METADATA: dict[str, dict[str, object]] = {
    "resolve_person": {
        "owner_package": "packages.tools.person_tools",
        "input_posture": "phone or email identifier only",
        "output_posture": "identity metadata",
        "policy_posture": "tenant-scoped identity lookup",
        "execution_posture": "planning_only",
        "downstream_surfaces": ["agent_runtime", "future_manager_chat"],
    },
    "get_ops_person_snapshot": {
        "owner_package": "packages.tools.ops_tools",
        "input_posture": "person_uid only",
        "output_posture": "ops snapshot",
        "policy_posture": "PHI-free service snapshot",
        "execution_posture": "planning_only",
        "downstream_surfaces": ["future_manager_chat", "future_workflows"],
    },
    "create_followup_task": {
        "owner_package": "packages.tools.ops_tools",
        "input_posture": "structured follow-up request",
        "output_posture": "state mutation",
        "policy_posture": "ops write path; approval required in Agent Runtime V1",
        "execution_posture": "approval_required",
        "downstream_surfaces": ["future_workflows"],
        "requires_approval": True,
        "notes": ["Write-capable tools stay approval-gated for V1."],
    },
    "get_phi_person_snapshot": {
        "owner_package": "packages.tools.phi_tools",
        "input_posture": "person_uid only",
        "output_posture": "PHI-gated snapshot",
        "policy_posture": "requires PHI-read principal and append-only audit",
        "execution_posture": "blocked",
        "downstream_surfaces": ["future_clinical_agent"],
        "requires_approval": True,
        "notes": ["PHI output is not available to Agent Runtime workbench V1."],
    },
    "run_analytics_query": {
        "owner_package": "packages.tools.analytics_tools",
        "input_posture": "approved query_id and structured params only",
        "output_posture": "aggregate analytics result",
        "policy_posture": "no raw SQL or free-form database access",
        "execution_posture": "executable",
        "downstream_surfaces": ["manager_dashboard", "manager_chat", "reports"],
    },
    "ask_manager_analytics": {
        "owner_package": "packages.tools.manager_chat_tools",
        "input_posture": "manager question and approved deterministic planner inputs",
        "output_posture": "aggregate answer plan/result",
        "policy_posture": "deterministic V1 planner; no raw SQL",
        "execution_posture": "executable",
        "downstream_surfaces": ["manager_chat"],
    },
    "export_analytics_csv": {
        "owner_package": "packages.tools.export_tools",
        "input_posture": "approved aggregate export request",
        "output_posture": "aggregate CSV export",
        "policy_posture": "no XLSX, scheduled, row-level, PHI, or raw payload exports",
        "execution_posture": "approval_required",
        "downstream_surfaces": ["reports"],
        "requires_approval": True,
    },
    "save_analytics_report_definition": {
        "owner_package": "packages.tools.export_tools",
        "input_posture": "approved saved-report definition",
        "output_posture": "saved aggregate report definition",
        "policy_posture": "no scheduled delivery in V1",
        "execution_posture": "approval_required",
        "downstream_surfaces": ["reports"],
        "requires_approval": True,
    },
    "data_intelligence_discover": {
        "owner_package": "packages.tools.data_intelligence_tools",
        "input_posture": "discovery request only",
        "output_posture": "policy and dataset metadata",
        "policy_posture": "no database read",
        "downstream_surfaces": ["data_intelligence", "semantic_catalog"],
    },
    "data_intelligence_preflight": {
        "owner_package": "packages.tools.data_intelligence_tools",
        "input_posture": "proposed DIA action and fields",
        "output_posture": "allow, deny, or clarification posture",
        "policy_posture": "denies raw payloads, PHI, exports, writes, and uncapped samples",
        "downstream_surfaces": ["data_intelligence", "agent_runtime"],
    },
    "data_intelligence_profile_field": {
        "owner_package": "packages.tools.data_intelligence_tools",
        "input_posture": "allowlisted dataset and field",
        "output_posture": "aggregate field profile",
        "policy_posture": "service-owned aggregates only",
        "limits": ["allowlisted fields", "aggregate output"],
        "downstream_surfaces": ["data_intelligence", "semantic_catalog"],
    },
    "data_intelligence_linkage_coverage": {
        "owner_package": "packages.tools.data_intelligence_tools",
        "input_posture": "allowlisted linkage dataset",
        "output_posture": "coverage metrics with bounded masked examples",
        "policy_posture": "masked sample posture",
        "limits": ["bounded examples", "masked identifiers"],
        "downstream_surfaces": ["data_intelligence", "semantic_catalog"],
    },
    "data_intelligence_evidence_coverage": {
        "owner_package": "packages.tools.data_intelligence_tools",
        "input_posture": "approved evidence dataset and dimensions",
        "output_posture": "aggregate evidence coverage",
        "policy_posture": "aggregate only",
        "downstream_surfaces": ["data_intelligence", "semantic_catalog"],
    },
    "data_intelligence_bounded_sample": {
        "owner_package": "packages.tools.data_intelligence_tools",
        "input_posture": "approved dataset and capped sample request",
        "output_posture": "bounded masked sample",
        "policy_posture": "no uncapped samples",
        "limits": ["25 default rows", "100 hard cap", "masked values"],
        "downstream_surfaces": ["data_intelligence"],
    },
    "data_intelligence_semantic_mapping_proposal": {
        "owner_package": "packages.tools.data_intelligence_tools",
        "input_posture": "approved source/campaign mapping evidence",
        "output_posture": "review-only semantic proposal",
        "policy_posture": "no catalog mutation",
        "downstream_surfaces": ["data_intelligence", "semantic_catalog"],
        "requires_approval": True,
    },
    "data_intelligence_person_journey_proposals": {
        "owner_package": "packages.tools.data_intelligence_tools",
        "input_posture": "person journey registry status/kind filters",
        "output_posture": "review-only registry proposal drafts",
        "policy_posture": "no catalog mutation; blocked/internal/deferred fail closed",
        "downstream_surfaces": ["data_intelligence", "semantic_catalog"],
        "requires_approval": True,
    },
    "data_intelligence_gap_brief": {
        "owner_package": "packages.tools.data_intelligence_tools",
        "input_posture": "approved coverage and mapping observations",
        "output_posture": "non-sensitive gap brief",
        "policy_posture": "planning summary only",
        "downstream_surfaces": ["data_intelligence", "linear"],
    },
}

_PLANNED_TOOLS = [
    AgentRuntimeToolProjectionOut(
        id="semantic_catalog_create_review_proposal",
        title="Semantic Catalog Create Review Proposal",
        description=(
            "Create a human-reviewable semantic catalog proposal from an agent or "
            "Data Intelligence observation."
        ),
        owner_package="packages.insight",
        status="planned",
        callable=False,
        data_classes=["ops", "identity", "billing", "integration_metadata"],
        input_posture="review-only proposal payload",
        output_posture="catalog proposal metadata",
        policy_posture="human review required; no automatic approval",
        downstream_surfaces=["semantic_catalog", "agent_runtime"],
        requires_approval=True,
        notes=["Tracked by ENG-349."],
    ),
    AgentRuntimeToolProjectionOut(
        id="semantic_catalog_impact_preview",
        title="Semantic Catalog Impact Preview",
        description=(
            "Preview known, likely, and unknown downstream impact before a "
            "semantic catalog proposal is approved."
        ),
        owner_package="packages.insight",
        status="planned",
        callable=False,
        data_classes=["ops", "identity", "billing", "integration_metadata"],
        input_posture="proposal id or proposed semantic patch",
        output_posture="impact summary",
        policy_posture="approval helper only",
        downstream_surfaces=["semantic_catalog", "manager_dashboard", "manager_chat"],
        requires_approval=False,
        notes=["Tracked by ENG-349 and Semantic Catalog follow-ups."],
    ),
    AgentRuntimeToolProjectionOut(
        id="semantic_catalog_approved_version_lookup",
        title="Semantic Catalog Approved Version Lookup",
        description=(
            "Read approved catalog versions for downstream tools without using "
            "draft documentation as business truth."
        ),
        owner_package="packages.insight",
        status="planned",
        callable=False,
        data_classes=["ops", "identity", "billing", "integration_metadata"],
        input_posture="approved term/version query",
        output_posture="approved catalog metadata",
        policy_posture="approved-version-only consumption path",
        downstream_surfaces=["agent_runtime", "manager_chat", "read_models", "reports"],
        requires_approval=False,
        notes=["Tracked by ENG-349."],
    ),
]

_DIA_CATALOG_LINKAGES = [
    AgentRuntimeDiaCatalogLinkageOut(
        id="dia-lead-source-mapping-to-catalog-review",
        title="DIA lead source mapping candidate to Semantic Catalog review",
        source_agent="Data Intelligence Mapping Helper",
        output_kind="mapping_proposal",
        runtime_run_id="run-semantic-proposal-planned",
        approval_request_id="approval-semantic-catalog-1",
        catalog_proposal_ref="lead-source-google-ads",
        approved_catalog_version_ref=None,
        review_posture="review_only_no_auto_approval",
        downstream_consumption="approved_version_only",
        data_classes=["ops", "integration_metadata"],
        evidence_refs=["mapping_coverage_summary", "bounded_masked_examples"],
        query_registry_refs=["paid_leads_by_source.v1", "lead_source_profile.v1"],
        read_model_refs=["paid_leads", "lead_source_profile"],
        approved_catalog_version_refs=["paid_lead:v1", "lead_source:v1"],
        impact_surfaces=[
            AgentRuntimeLinkageImpactSurfaceOut(
                surface="semantic_catalog",
                confidence="known",
                reason="Human review proposal is the only path into catalog meaning.",
            ),
            AgentRuntimeLinkageImpactSurfaceOut(
                surface="manager_dashboard",
                confidence="likely",
                reason="Approved source mapping can change grouped marketing metrics.",
            ),
            AgentRuntimeLinkageImpactSurfaceOut(
                surface="manager_chat",
                confidence="likely",
                reason="Chat answers must use approved catalog definitions only.",
            ),
            AgentRuntimeLinkageImpactSurfaceOut(
                surface="reports",
                confidence="unknown",
                reason="Saved report dependencies need registry impact metadata.",
            ),
        ],
        path=[
            AgentRuntimeLinkageStepOut(
                id="agent_run",
                title="Agent run",
                status="ready",
                owner="packages.agent_runtime",
                contract="Safe run summary with metadata-only posture.",
            ),
            AgentRuntimeLinkageStepOut(
                id="review_only_output",
                title="Review-only DIA output",
                status="ready",
                owner="packages.tools.data_intelligence_tools",
                contract="Mapping proposal evidence stays aggregate or masked.",
            ),
            AgentRuntimeLinkageStepOut(
                id="human_approval",
                title="Human approval request",
                status="in_review",
                owner="packages.agent_runtime",
                contract="Human decision gates downstream review handoff.",
            ),
            AgentRuntimeLinkageStepOut(
                id="catalog_review",
                title="Semantic Catalog review",
                status="planned",
                owner="packages.insight",
                contract="Proposal becomes catalog truth only after catalog approval.",
            ),
            AgentRuntimeLinkageStepOut(
                id="approved_version",
                title="Approved catalog version",
                status="planned",
                owner="packages.insight",
                contract="Downstream consumers read approved versions only.",
            ),
        ],
        notes=[
            "Agent suggestions are never approved catalog truth by themselves.",
            "ENG-350 should verify this path in production-facing workbench docs.",
        ],
    ),
    AgentRuntimeDiaCatalogLinkageOut(
        id="dia-gap-brief-to-catalog-planning",
        title="DIA gap brief to Semantic Catalog planning",
        source_agent="Data Intelligence Gap Brief Helper",
        output_kind="gap_brief",
        runtime_run_id=None,
        approval_request_id=None,
        catalog_proposal_ref=None,
        approved_catalog_version_ref=None,
        review_posture="planning_only_no_catalog_mutation",
        downstream_consumption="approved_version_only",
        data_classes=["ops", "identity", "integration_metadata"],
        evidence_refs=["coverage_gap_summary"],
        query_registry_refs=[],
        read_model_refs=[],
        approved_catalog_version_refs=[],
        impact_surfaces=[
            AgentRuntimeLinkageImpactSurfaceOut(
                surface="semantic_catalog",
                confidence="likely",
                reason="Gap briefs can create future human-review proposals.",
            ),
            AgentRuntimeLinkageImpactSurfaceOut(
                surface="data_intelligence",
                confidence="known",
                reason="Gap brief remains local planning evidence.",
            ),
            AgentRuntimeLinkageImpactSurfaceOut(
                surface="linear",
                confidence="likely",
                reason="Gap briefs can become follow-up implementation tasks.",
            ),
        ],
        path=[
            AgentRuntimeLinkageStepOut(
                id="agent_run",
                title="Agent run",
                status="planned",
                owner="packages.agent_runtime",
                contract="Future DIA runner records safe run summary.",
            ),
            AgentRuntimeLinkageStepOut(
                id="gap_brief",
                title="Gap brief",
                status="ready",
                owner="packages.tools.data_intelligence_tools",
                contract="Planning summary only; no catalog mutation.",
            ),
            AgentRuntimeLinkageStepOut(
                id="proposal_candidate",
                title="Proposal candidate",
                status="planned",
                owner="packages.insight",
                contract="Human must decide whether a catalog proposal is needed.",
            ),
            AgentRuntimeLinkageStepOut(
                id="approved_version",
                title="Approved catalog version",
                status="blocked",
                owner="packages.insight",
                contract="Blocked until a reviewed proposal is approved.",
            ),
        ],
        notes=[
            "Gap briefs explain missing meaning; they are not business meaning.",
        ],
    ),
]


class AgentRuntimeService:
    """Entry point for Fusion-owned agent runtime operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._run_repo = AgentRuntimeRunRepository(session)
        self._approval_repo = AgentRuntimeApprovalRequestRepository(session)

    async def test_openai_connection(
        self,
        principal: Principal,
    ) -> AgentRuntimeConnectionCheckOut:
        """Run a minimal OpenAI Agents SDK check for this tenant."""

        tenant_id = principal.require_tenant()
        started_at = datetime.now(UTC)
        try:
            result = await OpenAIIntegrationService(self._session).test_connection(
                tenant_id
            )
        except PlatformError as exc:
            completed_at = datetime.now(UTC)
            await self._record_run(
                principal=principal,
                agent_name="Fusion OpenAI Health Check",
                provider_kind="openai",
                model=None,
                run_kind="provider_health_check",
                status="failure",
                started_at=started_at,
                completed_at=completed_at,
                tool_calls=[],
                result_posture="safe_metadata_only",
                audit_summary=_openai_health_audit_summary(
                    policy_result="blocked",
                    final_outcome="failed",
                    provider_decision_result="blocked",
                    provider_decision_reason=(
                        "Provider health check failed before safe success metadata "
                        "was returned."
                    ),
                ),
                error_code=exc.code,
                error_message=exc.message,
            )
            raise
        except Exception:
            completed_at = datetime.now(UTC)
            await self._record_run(
                principal=principal,
                agent_name="Fusion OpenAI Health Check",
                provider_kind="openai",
                model=None,
                run_kind="provider_health_check",
                status="failure",
                started_at=started_at,
                completed_at=completed_at,
                tool_calls=[],
                result_posture="safe_metadata_only",
                audit_summary=_openai_health_audit_summary(
                    policy_result="blocked",
                    final_outcome="failed",
                    provider_decision_result="blocked",
                    provider_decision_reason=(
                        "Provider health check failed with an unexpected runtime "
                        "error."
                    ),
                ),
                error_code="unexpected_error",
                error_message="OpenAI provider health check failed.",
            )
            raise
        completed_at = datetime.now(UTC)
        status = "success" if result.ok else "failure"
        final_outcome = "completed" if result.ok else "failed"
        provider_decision_result = "allowed" if result.ok else "blocked"
        provider_decision_reason = (
            "Response includes safe provider metadata only."
            if result.ok
            else "Health check returned unexpected safe output."
        )
        await self._record_run(
            principal=principal,
            agent_name=result.last_agent,
            provider_kind="openai",
            model=result.model,
            run_kind="provider_health_check",
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            tool_calls=[],
            result_posture="safe_metadata_only",
            audit_summary=_openai_health_audit_summary(
                policy_result="allowed" if result.ok else "blocked",
                final_outcome=final_outcome,
                provider_decision_result=provider_decision_result,
                provider_decision_reason=provider_decision_reason,
            ),
        )
        return AgentRuntimeConnectionCheckOut(
            ok=result.ok,
            model=result.model,
            last_agent=result.last_agent,
            output=result.output,
        )

    def list_tools_projection(self) -> AgentRuntimeToolsProjectionOut:
        """Return safe, read-only metadata for agent-callable tools."""

        tools = [
            self._project_registered_tool(tool)
            for tool in sorted(ALL_TOOLS.values(), key=lambda item: item.name)
        ]
        return AgentRuntimeToolsProjectionOut(tools=[*tools, *_PLANNED_TOOLS])

    def list_dia_catalog_linkages(self) -> AgentRuntimeDiaCatalogLinkagesOut:
        """Return safe DIA-to-catalog review linkage projections."""

        return AgentRuntimeDiaCatalogLinkagesOut(linkages=_DIA_CATALOG_LINKAGES)

    async def generate_llm_plan(
        self,
        principal: Principal,
        payload: AgentRuntimeLlmPlanIn,
    ) -> AgentRuntimeLlmPlanOut:
        """Run the first constrained OpenAI planning turn for Agent Runtime."""

        tenant_id = principal.require_tenant()
        started_at = datetime.now(UTC)
        plan_payload = OpenAIAgentPlanIn(
            user_prompt=payload.user_prompt,
            tools=self._openai_planning_tool_descriptors(),
        )
        try:
            plan = await OpenAIIntegrationService(self._session).generate_agent_plan(
                tenant_id,
                plan_payload,
            )
            plan = _apply_deterministic_manager_analytics_fallback(
                plan,
                user_prompt=payload.user_prompt,
            )
        except PlatformError as exc:
            completed_at = datetime.now(UTC)
            run = await self._record_run(
                principal=principal,
                agent_name="Fusion Agent Runtime Planner",
                provider_kind="openai",
                model=None,
                run_kind="llm_planning",
                status="failure",
                started_at=started_at,
                completed_at=completed_at,
                tool_calls=[],
                result_posture="safe_llm_plan_metadata_only",
                audit_summary=_llm_planning_audit_summary(
                    data_classes=["integration_metadata"],
                    policy_result="blocked",
                    final_outcome="failed",
                    planner_decision_result="blocked",
                    planner_decision_reason=(
                        "LLM planning failed before a validated safe plan was "
                        "returned."
                    ),
                ),
                error_code=exc.code,
                error_message=exc.message,
            )
            _ = run
            raise
        except Exception:
            completed_at = datetime.now(UTC)
            await self._record_run(
                principal=principal,
                agent_name="Fusion Agent Runtime Planner",
                provider_kind="openai",
                model=None,
                run_kind="llm_planning",
                status="failure",
                started_at=started_at,
                completed_at=completed_at,
                tool_calls=[],
                result_posture="safe_llm_plan_metadata_only",
                audit_summary=_llm_planning_audit_summary(
                    data_classes=["integration_metadata"],
                    policy_result="blocked",
                    final_outcome="failed",
                    planner_decision_result="blocked",
                    planner_decision_reason=(
                        "LLM planning failed with an unexpected runtime error."
                    ),
                ),
                error_code="unexpected_error",
                error_message="OpenAI LLM planning failed.",
            )
            raise

        policy = _evaluate_llm_plan_policy(plan)
        execution = await self._execute_approved_llm_plan(principal, plan, policy)
        completed_at = datetime.now(UTC)
        tool_calls = _plan_tool_calls(plan, policy)
        tool_calls = _apply_execution_to_tool_calls(tool_calls, execution)
        data_classes = _tool_call_data_classes(tool_calls)
        run = await self._record_run(
            principal=principal,
            agent_name=plan.last_agent,
            provider_kind="openai",
            model=plan.model,
            run_kind=(
                "llm_planning_with_tool_execution"
                if execution.status == "executed"
                else "llm_planning"
            ),
            status=execution.run_status,
            started_at=started_at,
            completed_at=completed_at,
            tool_calls=tool_calls,
            result_posture=execution.result_posture,
            audit_summary=_llm_planning_audit_summary(
                data_classes=data_classes,
                policy_result=execution.run_status
                if execution.status == "failed"
                else policy.result,
                final_outcome=execution.final_outcome,
                planner_decision_result=policy.result,
                planner_decision_reason=policy.reason,
                approval_required=policy.approval_required,
                export=plan.tool_id == "export_analytics_csv",
                evidence_refs=_execution_evidence_refs(execution),
                execution=execution,
            ),
            error_code=execution.error_code,
            error_message=execution.error_message,
        )
        approval_request = await self._create_policy_pause_approval_request(
            principal=principal,
            run=run,
            plan=plan,
            policy=policy,
            tool_calls=tool_calls,
        )
        _ = approval_request
        answer_eligibility = _manager_answer_eligibility_from_execution(
            run=run,
            execution=execution,
        )
        manager_answer = await self._generate_manager_answer(
            principal=principal,
            plan=plan,
            execution=execution,
            eligibility=answer_eligibility,
        )
        run.audit_summary = _audit_summary_with_manager_answer(
            run.audit_summary,
            eligibility=answer_eligibility,
            manager_answer=manager_answer,
        )
        await self._session.flush()
        return AgentRuntimeLlmPlanOut(
            run_id=str(run.id),
            model=plan.model,
            last_agent=plan.last_agent,
            outcome=plan.outcome,
            intent=plan.intent,
            tool_id=plan.tool_id,
            tool_arguments=plan.tool_arguments,
            confidence=plan.confidence,
            clarification_question=plan.clarification_question,
            refusal_reason=plan.refusal_reason,
            safety_notes=plan.safety_notes,
            policy_result=policy.result,
            policy_reason=policy.reason,
            approval_required=policy.approval_required,
            execution_status=execution.status,  # type: ignore[arg-type]
            execution=execution.output,
            answer_eligibility=answer_eligibility,
            manager_answer=manager_answer,
            result_posture=execution.result_posture,  # type: ignore[arg-type]
        )

    async def list_run_history(
        self,
        tenant_id: TenantId,
        *,
        limit: int = 25,
        status: AgentRuntimeRunStatus | None = None,
        tool_id: str | None = None,
        policy_result: str | None = None,
        final_outcome: AgentRuntimeFinalOutcome | None = None,
        triggered_by: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
    ) -> AgentRuntimeRunHistoryOut:
        """Return safe recent runtime run summaries for a tenant."""

        filters = AgentRuntimeRunHistoryFiltersOut(
            limit=limit,
            status=status,
            tool_id=tool_id,
            policy_result=policy_result,
            final_outcome=final_outcome,
            triggered_by=triggered_by,
            started_after=started_after,
            started_before=started_before,
        )
        json_filtered = any(
            value is not None
            for value in (
                filters.tool_id,
                filters.policy_result,
                filters.final_outcome,
            )
        )
        rows = await self._run_repo.list_recent(
            tenant_id,
            limit=min(250, max(filters.limit, filters.limit * 5))
            if json_filtered
            else filters.limit,
            status=filters.status,
            triggered_by=filters.triggered_by,
            started_after=filters.started_after,
            started_before=filters.started_before,
        )
        summaries = [
            self._project_run_summary(row)
            for row in rows
            if _run_matches_history_filters(row, filters)
        ][: filters.limit]
        return AgentRuntimeRunHistoryOut(
            filters=filters,
            runs=summaries,
        )

    async def create_approval_request(
        self,
        principal: Principal,
        payload: AgentRuntimeApprovalRequestCreateIn,
    ) -> AgentRuntimeApprovalRequestOut:
        """Create a safe human approval request for an agent proposal."""

        self._validate_approval_payload(payload)
        now = datetime.now(UTC)
        approval = await self._approval_repo.add(
            AgentRuntimeApprovalRequest(
                tenant_id=principal.require_tenant(),
                source_run_id=_parse_optional_uuid(payload.source_run_id),
                requested_by_actor_id=principal.id,
                requested_by_actor_email=principal.email,
                agent_name=payload.agent_name,
                tool_id=payload.tool_id,
                target_kind=payload.target_kind,
                target_ref=payload.target_ref,
                title=payload.title,
                reason=payload.reason,
                evidence_summary=payload.evidence_summary,
                requested_action=payload.requested_action,
                status="pending",
                requested_at=now,
                data_classes=sorted(set(payload.data_classes)),
                affected_surfaces=sorted(set(payload.affected_surfaces)),
                risk_flags=sorted(set(payload.risk_flags)),
                approval_posture=payload.approval_posture,
            )
        )
        return self._project_approval_request(approval)

    async def list_approval_requests(
        self,
        tenant_id: TenantId,
        *,
        status: AgentRuntimeApprovalStatus | None = None,
        limit: int = 25,
    ) -> AgentRuntimeApprovalRequestsOut:
        """Return safe approval requests for the workbench."""

        rows = await self._approval_repo.list_recent(
            tenant_id,
            status=status,
            limit=limit,
        )
        return AgentRuntimeApprovalRequestsOut(
            approvals=[self._project_approval_request(row) for row in rows],
        )

    async def decide_approval_request(
        self,
        principal: Principal,
        approval_id: uuid.UUID,
        payload: AgentRuntimeApprovalDecisionIn,
    ) -> AgentRuntimeApprovalRequestOut:
        """Record a human decision without mutating the target system."""

        _validate_safe_values(
            [
                payload.decision_summary,
                payload.edit_summary,
            ]
        )
        approval = await self._approval_repo.get_for_tenant(
            principal.require_tenant(),
            approval_id,
        )
        if approval is None:
            raise NotFoundError(
                "Agent runtime approval request was not found.",
                details={"approval_id": str(approval_id)},
            )
        if approval.status != "pending":
            raise ValidationError(
                "Only pending approval requests can be decided.",
                details={"approval_id": str(approval_id), "status": approval.status},
            )

        approval.status = _decision_to_status(payload.decision)
        approval.decided_at = datetime.now(UTC)
        approval.decided_by_actor_id = principal.id
        approval.decided_by_actor_email = principal.email
        approval.decision_summary = payload.decision_summary
        approval.edit_summary = payload.edit_summary
        await self._session.flush()
        await self._record_approval_decision_run(principal, approval)
        return self._project_approval_request(approval)

    async def _create_policy_pause_approval_request(
        self,
        *,
        principal: Principal,
        run: AgentRuntimeRun,
        plan: OpenAIAgentPlanOut,
        policy: _LlmPlanPolicy,
        tool_calls: list[dict[str, object]],
    ) -> AgentRuntimeApprovalRequestOut | None:
        if (
            not policy.approval_required
            or plan.outcome != "tool_plan"
            or plan.tool_id is None
        ):
            return None

        payload = _approval_request_payload_from_plan(run, plan, policy, tool_calls)
        approval = await self._approval_repo.add(
            AgentRuntimeApprovalRequest(
                id=uuid.uuid4(),
                tenant_id=principal.require_tenant(),
                source_run_id=run.id,
                requested_by_actor_id=principal.id,
                requested_by_actor_email=principal.email,
                agent_name=payload.agent_name,
                tool_id=payload.tool_id,
                target_kind=payload.target_kind,
                target_ref=payload.target_ref,
                title=payload.title,
                reason=payload.reason,
                evidence_summary=payload.evidence_summary,
                requested_action=payload.requested_action,
                status="pending",
                requested_at=datetime.now(UTC),
                data_classes=sorted(set(payload.data_classes)),
                affected_surfaces=sorted(set(payload.affected_surfaces)),
                risk_flags=sorted(set(payload.risk_flags)),
                approval_posture=payload.approval_posture,
            )
        )
        approval_id = str(approval.id)
        run.audit_summary = _audit_summary_with_linked_approval(
            run.audit_summary,
            approval_id,
        )
        run.tool_calls = _tool_calls_with_approval_request(tool_calls, approval_id)
        await self._session.flush()
        return self._project_approval_request(approval)

    async def _record_approval_decision_run(
        self,
        principal: Principal,
        approval: AgentRuntimeApprovalRequest,
    ) -> AgentRuntimeRun:
        now = datetime.now(UTC)
        status = _approval_decision_run_status(approval.status)
        return await self._record_run(
            principal=principal,
            agent_name="Fusion Agent Runtime Approval Review",
            provider_kind="internal",
            model=None,
            run_kind="approval_decision",
            status=status,
            started_at=now,
            completed_at=now,
            tool_calls=[
                {
                    "tool_id": approval.tool_id or "approval_request",
                    "status": status,
                    "data_classes": list(approval.data_classes),
                    "output_posture": "safe approval decision metadata",
                    "approval_request_id": str(approval.id),
                }
            ],
            result_posture="safe_approval_decision_metadata",
            audit_summary=_approval_decision_audit_summary(approval),
        )

    async def _record_run(
        self,
        *,
        principal: Principal,
        agent_name: str,
        provider_kind: str,
        model: str | None,
        run_kind: str,
        status: str,
        started_at: datetime,
        completed_at: datetime | None,
        tool_calls: list[dict[str, object]],
        result_posture: str,
        audit_summary: dict[str, object],
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> AgentRuntimeRun:
        duration_ms: int | None = None
        if completed_at is not None:
            duration_ms = max(
                0,
                int((completed_at - started_at).total_seconds() * 1000),
            )
        return await self._run_repo.add(
            AgentRuntimeRun(
                tenant_id=principal.require_tenant(),
                trigger_actor_id=principal.id,
                trigger_actor_email=principal.email,
                agent_name=agent_name,
                provider_kind=provider_kind,
                model=model,
                run_kind=run_kind,
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                tool_calls=tool_calls,
                result_posture=result_posture,
                audit_summary=AgentRuntimeAuditSummaryOut.model_validate(
                    audit_summary
                ).model_dump(mode="json"),
                error_code=error_code,
                error_message=_safe_error_message(error_message),
            )
        )

    @staticmethod
    def _project_registered_tool(tool: ToolSpec) -> AgentRuntimeToolProjectionOut:
        meta = _TOOL_METADATA.get(tool.name, {})
        return AgentRuntimeToolProjectionOut(
            id=tool.name,
            title=tool.name.replace("_", " ").title(),
            description=tool.description,
            owner_package=str(meta.get("owner_package", "packages.tools")),
            status="available",
            callable=True,
            execution_posture=_tool_execution_posture(
                meta.get("execution_posture", "planning_only")
            ),
            data_classes=sorted(tool.touches),
            input_posture=str(meta.get("input_posture", "structured tool input only")),
            output_posture=str(meta.get("output_posture", "tool response metadata")),
            policy_posture=str(meta.get("policy_posture", "registered tool policy")),
            limits=_string_list(meta.get("limits", [])),
            downstream_surfaces=_string_list(
                meta.get("downstream_surfaces", ["agent_runtime"])
            ),
            requires_approval=bool(meta.get("requires_approval", False)),
            notes=_string_list(meta.get("notes", [])),
        )

    def _openai_planning_tool_descriptors(self) -> list[OpenAIToolDescriptor]:
        """Return safe tool metadata for the LLM planning prompt."""

        descriptors: list[OpenAIToolDescriptor] = []
        for tool in sorted(ALL_TOOLS.values(), key=lambda item: item.name):
            projection = self._project_registered_tool(tool)
            descriptors.append(
                OpenAIToolDescriptor(
                    id=projection.id,
                    description=projection.description,
                    data_classes=projection.data_classes,
                    input_posture=projection.input_posture,
                    output_posture=projection.output_posture,
                    policy_posture=projection.policy_posture,
                    requires_approval=projection.requires_approval,
                )
            )
        return descriptors

    async def _generate_manager_answer(
        self,
        *,
        principal: Principal,
        plan: OpenAIAgentPlanOut,
        execution: _LlmToolExecution,
        eligibility: AgentRuntimeManagerAnswerEligibilityOut,
    ) -> AgentRuntimeManagerAnswerOut:
        """Generate a safe manager answer after approved aggregate execution."""

        if not eligibility.eligible:
            return AgentRuntimeManagerAnswerOut(
                status="not_generated",
                caveats=[eligibility.reason],
                validation_errors=[],
            )
        if execution.output is None or execution.output.result is None:
            return AgentRuntimeManagerAnswerOut(
                status="blocked",
                caveats=["Answer generation requires an aggregate execution result."],
            )
        if eligibility.source_refs is None:
            return AgentRuntimeManagerAnswerOut(
                status="blocked",
                caveats=["Answer generation requires source refs."],
            )

        try:
            answer = await OpenAIIntegrationService(
                self._session
            ).generate_manager_answer(
                principal.require_tenant(),
                OpenAIManagerAnswerIn(
                    manager_question=_manager_answer_question(plan),
                    tool_id=eligibility.source_refs.tool_id,
                    query_id=eligibility.source_refs.query_id,
                    read_model_id=eligibility.source_refs.read_model_id,
                    execution_run_id=eligibility.source_refs.execution_run_id,
                    aggregate_result=execution.output.result,
                    data_classes=eligibility.data_classes,
                    caveats=_manager_answer_caveats(execution, eligibility=eligibility),
                    evidence_refs=eligibility.source_refs.evidence_refs,
                    approved_catalog_version_refs=(
                        eligibility.source_refs.approved_catalog_version_refs
                    ),
                ),
            )
        except PlatformError as exc:
            return AgentRuntimeManagerAnswerOut(
                status="validation_failed",
                caveats=["Manager answer generation failed safely."],
                validation_errors=[exc.message],
            )
        except Exception:
            return AgentRuntimeManagerAnswerOut(
                status="validation_failed",
                caveats=["Manager answer generation failed safely."],
                validation_errors=["Unexpected manager answer generation failure."],
            )

        return AgentRuntimeManagerAnswerOut(
            status=eligibility.answer_posture,
            model=answer.model,
            last_agent=answer.last_agent,
            summary=answer.summary,
            key_numbers=[
                item.model_dump(mode="json") for item in answer.key_numbers
            ],
            explanation=answer.explanation,
            caveats=_merge_manager_answer_caveats(
                answer.caveats,
                execution,
                eligibility=eligibility,
            ),
            source_refs=eligibility.source_refs,
            widgets=_manager_answer_widgets(answer, execution),
            confidence=answer.confidence,
            safety_notes=answer.safety_notes,
        )

    async def _execute_approved_llm_plan(
        self,
        principal: Principal,
        plan: OpenAIAgentPlanOut,
        policy: _LlmPlanPolicy,
    ) -> _LlmToolExecution:
        """Execute approved tool plans through registry-owned adapters."""

        if policy.result != "allowed" or plan.outcome != "tool_plan":
            return _LlmToolExecution(
                status="not_applicable",
                run_status=policy.run_status,
                final_outcome=policy.final_outcome,
                result_posture="safe_llm_plan_metadata_only",
                policy_reason=policy.reason,
            )
        execution_adapter = _LLM_TOOL_EXECUTION_REGISTRY.get(plan.tool_id or "")
        if execution_adapter is None:
            return _LlmToolExecution(
                status="not_executed",
                run_status=policy.run_status,
                final_outcome=policy.final_outcome,
                result_posture="safe_llm_plan_metadata_only",
                policy_reason=(
                    "Selected tool is allowed for planning but has no approved "
                    "Agent Runtime execution adapter."
                ),
            )
        if execution_adapter == "analytics_query":
            return await self._execute_analytics_query_llm_plan(principal, plan)
        return await self._execute_manager_analytics_llm_plan(principal, plan)

    async def _execute_manager_analytics_llm_plan(
        self,
        principal: Principal,
        plan: OpenAIAgentPlanOut,
    ) -> _LlmToolExecution:
        """Execute approved manager analytics question plans."""

        question = _safe_tool_question(plan.tool_arguments)
        if question is None:
            output = AgentRuntimeLlmExecutionOut(
                status="no_match",
                tool_id=plan.tool_id or "ask_manager_analytics",
                match_status="no_match",
                output_type="none",
                policy_reason=(
                    "Planner did not provide a safe manager analytics question "
                    "argument for approved execution."
                ),
            )
            return _LlmToolExecution(
                status="no_match",
                run_status="blocked",
                final_outcome="blocked",
                result_posture="safe_llm_plan_metadata_only",
                policy_reason=output.policy_reason,
                output=output,
            )

        manager_query_match = select_manager_query_match(question)
        if manager_query_match is None:
            output = AgentRuntimeLlmExecutionOut(
                status="no_match",
                tool_id=plan.tool_id or "ask_manager_analytics",
                match_status="no_match",
                output_type="none",
                policy_reason=(
                    "Manager analytics question did not match an approved "
                    "query/read-model contract."
                ),
            )
            return _LlmToolExecution(
                status="no_match",
                run_status="blocked",
                final_outcome="blocked",
                result_posture="safe_llm_plan_metadata_only",
                policy_reason=output.policy_reason,
                output=output,
            )
        query_match = _query_match_from_manager_match(manager_query_match)

        try:
            params = _safe_tool_params(plan.tool_arguments, question=question)
        except PlatformError as exc:
            output = AgentRuntimeLlmExecutionOut(
                status="clarification_required",
                tool_id=plan.tool_id or "ask_manager_analytics",
                query_id=query_match.query_id,
                read_model_id=query_match.read_model_id,
                match_status="clarification_required",
                match_confidence=query_match.confidence,
                match_reason=query_match.reason,
                matched_keywords=list(query_match.matched_keywords),
                output_type="none",
                policy_reason=exc.message,
            )
            return _LlmToolExecution(
                status="clarification_required",
                run_status="blocked",
                final_outcome="blocked",
                result_posture="safe_llm_plan_metadata_only",
                policy_reason=exc.message,
                output=output,
                error_code=exc.code,
                error_message=exc.message,
                query_match=query_match,
            )
        try:
            raw_result = await ALL_TOOLS["ask_manager_analytics"].fn(
                ToolContext(principal=principal, session=self._session),
                question=question,
                params=params,
                execute=True,
            )
        except PlatformError as exc:
            output = AgentRuntimeLlmExecutionOut(
                status="failed",
                tool_id=plan.tool_id or "ask_manager_analytics",
                query_id=query_match.query_id,
                read_model_id=query_match.read_model_id,
                match_status="matched",
                match_confidence=query_match.confidence,
                match_reason=query_match.reason,
                matched_keywords=list(query_match.matched_keywords),
                output_type="none",
                policy_reason=exc.message,
            )
            return _LlmToolExecution(
                status="failed",
                run_status="failure",
                final_outcome="failed",
                result_posture="safe_llm_plan_metadata_only",
                policy_reason=exc.message,
                output=output,
                error_code=exc.code,
                error_message=exc.message,
                query_match=query_match,
            )

        if not isinstance(raw_result, dict):
            output = AgentRuntimeLlmExecutionOut(
                status="failed",
                tool_id=plan.tool_id or "ask_manager_analytics",
                query_id=query_match.query_id,
                read_model_id=query_match.read_model_id,
                match_status="matched",
                match_confidence=query_match.confidence,
                match_reason=query_match.reason,
                matched_keywords=list(query_match.matched_keywords),
                output_type="none",
                policy_reason="Approved tool returned an invalid execution envelope.",
            )
            return _LlmToolExecution(
                status="failed",
                run_status="failure",
                final_outcome="failed",
                result_posture="safe_llm_plan_metadata_only",
                policy_reason=output.policy_reason,
                output=output,
                error_code="invalid_tool_envelope",
                error_message=output.policy_reason,
                query_match=query_match,
            )

        execution = raw_result.get("execution")
        if not isinstance(execution, dict):
            planner = raw_result.get("planner")
            if isinstance(planner, dict):
                reason = str(
                    planner.get("reason")
                    or "Approved manager analytics tool requested clarification."
                )
            else:
                reason = "Approved manager analytics tool did not match a query."
            output = AgentRuntimeLlmExecutionOut(
                status="clarification_required",
                tool_id=plan.tool_id or "ask_manager_analytics",
                query_id=query_match.query_id,
                read_model_id=query_match.read_model_id,
                match_status="clarification_required",
                match_confidence=query_match.confidence,
                match_reason=query_match.reason,
                matched_keywords=list(query_match.matched_keywords),
                output_type="none",
                explanation=_optional_str(raw_result.get("explanation")),
                policy_reason=reason,
            )
            return _LlmToolExecution(
                status="clarification_required",
                run_status="blocked",
                final_outcome="blocked",
                result_posture="safe_llm_plan_metadata_only",
                policy_reason=reason,
                output=output,
                query_match=query_match,
            )

        execution = _attach_time_window_to_execution(execution, params)

        executed_query_id = _optional_str(execution.get("query_id"))
        executed_read_model_id = _optional_str(execution.get("read_model_id"))
        if (
            executed_query_id != query_match.query_id
            or executed_read_model_id != query_match.read_model_id
        ):
            reason = (
                "Approved tool execution did not match the deterministic "
                "query/read-model selection."
            )
            output = AgentRuntimeLlmExecutionOut(
                status="failed",
                tool_id=plan.tool_id or "ask_manager_analytics",
                query_id=query_match.query_id,
                read_model_id=query_match.read_model_id,
                match_status="matched",
                match_confidence=query_match.confidence,
                match_reason=query_match.reason,
                matched_keywords=list(query_match.matched_keywords),
                output_type="none",
                policy_reason=reason,
            )
            return _LlmToolExecution(
                status="failed",
                run_status="failure",
                final_outcome="failed",
                result_posture="safe_llm_plan_metadata_only",
                policy_reason=reason,
                output=output,
                error_code="analytics_query_match_drift",
                error_message=reason,
                query_match=query_match,
            )

        output = AgentRuntimeLlmExecutionOut(
            status="executed",
            tool_id=plan.tool_id or "ask_manager_analytics",
            query_id=query_match.query_id,
            read_model_id=query_match.read_model_id,
            match_status="matched",
            match_confidence=query_match.confidence,
            match_reason=query_match.reason,
            matched_keywords=list(query_match.matched_keywords),
            output_type="aggregate",
            data_classes=_string_list(execution.get("data_classes", [])),
            row_count=_optional_int(execution.get("row_count")),
            explanation=_optional_str(raw_result.get("explanation")),
            policy_reason=(
                "Approved aggregate analytics tool executed through service-owned "
                "read-model code."
            ),
            result=execution,
        )
        return _LlmToolExecution(
            status="executed",
            run_status="success",
            final_outcome="completed",
            result_posture="safe_aggregate_tool_execution",
            policy_reason=output.policy_reason,
            output=output,
            query_match=query_match,
        )

    async def _execute_analytics_query_llm_plan(
        self,
        principal: Principal,
        plan: OpenAIAgentPlanOut,
    ) -> _LlmToolExecution:
        """Execute direct approved analytics query plans."""

        try:
            query_id = _safe_tool_query_id(plan.tool_arguments)
        except PlatformError as exc:
            output = AgentRuntimeLlmExecutionOut(
                status="no_match",
                tool_id=plan.tool_id or "run_analytics_query",
                match_status="no_match",
                output_type="none",
                policy_reason=exc.message,
            )
            return _LlmToolExecution(
                status="no_match",
                run_status="blocked",
                final_outcome="blocked",
                result_posture="safe_llm_plan_metadata_only",
                policy_reason=exc.message,
                output=output,
            )

        query_match = _query_match_from_query_id(query_id)
        try:
            params = _safe_tool_params(
                plan.tool_arguments,
                question=_safe_tool_question(plan.tool_arguments) or plan.intent,
            )
        except PlatformError as exc:
            output = AgentRuntimeLlmExecutionOut(
                status="clarification_required",
                tool_id=plan.tool_id or "run_analytics_query",
                query_id=query_match.query_id,
                read_model_id=query_match.read_model_id,
                match_status="clarification_required",
                match_confidence="high",
                match_reason=query_match.reason,
                matched_keywords=list(query_match.matched_keywords),
                output_type="none",
                policy_reason=exc.message,
            )
            return _LlmToolExecution(
                status="clarification_required",
                run_status="blocked",
                final_outcome="blocked",
                result_posture="safe_llm_plan_metadata_only",
                policy_reason=exc.message,
                output=output,
                error_code=exc.code,
                error_message=exc.message,
                query_match=query_match,
            )
        try:
            execution = await ALL_TOOLS["run_analytics_query"].fn(
                ToolContext(principal=principal, session=self._session),
                query_id=query_id,
                params=params,
            )
        except PlatformError as exc:
            output = AgentRuntimeLlmExecutionOut(
                status="failed",
                tool_id=plan.tool_id or "run_analytics_query",
                query_id=query_match.query_id,
                read_model_id=query_match.read_model_id,
                match_status="matched",
                match_confidence="high",
                match_reason=query_match.reason,
                matched_keywords=list(query_match.matched_keywords),
                output_type="none",
                policy_reason=exc.message,
            )
            return _LlmToolExecution(
                status="failed",
                run_status="failure",
                final_outcome="failed",
                result_posture="safe_llm_plan_metadata_only",
                policy_reason=exc.message,
                output=output,
                error_code=exc.code,
                error_message=exc.message,
                query_match=query_match,
            )

        if not isinstance(execution, dict):
            reason = "Approved analytics query tool returned an invalid envelope."
            output = AgentRuntimeLlmExecutionOut(
                status="failed",
                tool_id=plan.tool_id or "run_analytics_query",
                query_id=query_match.query_id,
                read_model_id=query_match.read_model_id,
                match_status="matched",
                match_confidence="high",
                match_reason=query_match.reason,
                matched_keywords=list(query_match.matched_keywords),
                output_type="none",
                policy_reason=reason,
            )
            return _LlmToolExecution(
                status="failed",
                run_status="failure",
                final_outcome="failed",
                result_posture="safe_llm_plan_metadata_only",
                policy_reason=reason,
                output=output,
                error_code="invalid_tool_envelope",
                error_message=reason,
                query_match=query_match,
            )

        execution = _attach_time_window_to_execution(execution, params)

        output = _execution_output_from_analytics_execution(
            tool_id=plan.tool_id or "run_analytics_query",
            query_match=query_match,
            execution=execution,
            explanation=(
                f"Executed {query_match.query_id} for read model "
                f"{query_match.read_model_id}. The result is aggregate-only."
            ),
            policy_reason=(
                "Approved analytics query executed through service-owned "
                "read-model code."
            ),
        )
        if output.status == "failed":
            return _LlmToolExecution(
                status="failed",
                run_status="failure",
                final_outcome="failed",
                result_posture="safe_llm_plan_metadata_only",
                policy_reason=output.policy_reason,
                output=output,
                error_code="analytics_query_match_drift",
                error_message=output.policy_reason,
                query_match=query_match,
            )
        return _LlmToolExecution(
            status="executed",
            run_status="success",
            final_outcome="completed",
            result_posture="safe_aggregate_tool_execution",
            policy_reason=output.policy_reason,
            output=output,
            query_match=query_match,
        )

    @staticmethod
    def _project_run_summary(row: AgentRuntimeRun) -> AgentRuntimeRunSummaryOut:
        return AgentRuntimeRunSummaryOut(
            id=str(row.id),
            agent_name=row.agent_name,
            provider_kind=row.provider_kind,
            model=row.model,
            run_kind=row.run_kind,
            status=row.status,  # type: ignore[arg-type]
            started_at=row.started_at,
            completed_at=row.completed_at,
            duration_ms=row.duration_ms,
            triggered_by=row.trigger_actor_email,
            tool_calls=row.tool_calls,  # type: ignore[arg-type]
            result_posture=row.result_posture,
            audit_summary=AgentRuntimeAuditSummaryOut.model_validate(
                row.audit_summary
            ),
            error_code=row.error_code,
            error_message=row.error_message,
        )

    @staticmethod
    def _project_approval_request(
        row: AgentRuntimeApprovalRequest,
    ) -> AgentRuntimeApprovalRequestOut:
        return AgentRuntimeApprovalRequestOut(
            id=str(row.id),
            source_run_id=str(row.source_run_id) if row.source_run_id else None,
            agent_name=row.agent_name,
            tool_id=row.tool_id,
            target_kind=row.target_kind,  # type: ignore[arg-type]
            target_ref=row.target_ref,
            title=row.title,
            reason=row.reason,
            evidence_summary=row.evidence_summary,
            requested_action=row.requested_action,
            status=row.status,  # type: ignore[arg-type]
            requested_at=row.requested_at,
            requested_by=row.requested_by_actor_email,
            decided_at=row.decided_at,
            decided_by=row.decided_by_actor_email,
            workflow_state=_approval_workflow_state(row.status),
            data_classes=list(row.data_classes),
            affected_surfaces=list(row.affected_surfaces),
            risk_flags=list(row.risk_flags),
            approval_posture=row.approval_posture,
            decision_summary=row.decision_summary,
            edit_summary=row.edit_summary,
        )

    @staticmethod
    def _validate_approval_payload(
        payload: AgentRuntimeApprovalRequestCreateIn,
    ) -> None:
        _validate_safe_values(
            [
                payload.source_run_id,
                payload.agent_name,
                payload.tool_id,
                payload.target_ref,
                payload.title,
                payload.reason,
                payload.evidence_summary,
                payload.requested_action,
                payload.approval_posture,
                *payload.data_classes,
                *payload.affected_surfaces,
                *payload.risk_flags,
            ]
        )


def _string_list(value: object) -> list[str]:
    if isinstance(value, (list, tuple, set, frozenset)):
        return [str(item) for item in value]
    return []


def _tool_execution_posture(value: object) -> AgentRuntimeToolExecutionPosture:
    if value in {"executable", "planning_only", "approval_required", "blocked"}:
        return cast(AgentRuntimeToolExecutionPosture, value)
    return "planning_only"


def _approval_request_payload_from_plan(
    run: AgentRuntimeRun,
    plan: OpenAIAgentPlanOut,
    policy: _LlmPlanPolicy,
    tool_calls: list[dict[str, object]],
) -> AgentRuntimeApprovalRequestCreateIn:
    tool_id = plan.tool_id or "unknown_tool"
    meta = _TOOL_METADATA.get(tool_id, {})
    data_classes = _tool_call_data_classes(tool_calls)
    target_kind = _approval_target_kind_for_tool(tool_id)
    target_ref = _approval_target_ref_from_plan(plan)
    raw_downstream_surfaces = meta.get("downstream_surfaces", [])
    downstream_surfaces = (
        raw_downstream_surfaces
        if isinstance(raw_downstream_surfaces, list | tuple | set | frozenset)
        else []
    )
    affected_surfaces = sorted(
        {
            "agent_runtime",
            *[
                str(surface)
                for surface in downstream_surfaces
                if isinstance(surface, str)
            ],
        }
    )
    risk_flags = _approval_risk_flags(
        tool_id=tool_id,
        target_kind=target_kind,
        data_classes=data_classes,
    )
    return AgentRuntimeApprovalRequestCreateIn(
        source_run_id=str(run.id),
        agent_name=plan.last_agent,
        tool_id=tool_id,
        target_kind=target_kind,
        target_ref=target_ref,
        title=f"Approval required for {tool_id}",
        reason=policy.reason,
        evidence_summary=(
            "The LLM selected an approval-required tool. Agent Runtime paused "
            "before execution and stored only safe policy metadata."
        ),
        requested_action=(
            "Review the request and approve, reject, request edit, or mark "
            "unresolved. Approval does not bypass tool policy."
        ),
        data_classes=data_classes,
        affected_surfaces=affected_surfaces,
        risk_flags=risk_flags,
        approval_posture="human_review_required_no_auto_execution",
    )


def _approval_target_kind_for_tool(tool_id: str) -> AgentRuntimeApprovalTargetKind:
    if tool_id in {"export_analytics_csv", "save_analytics_report_definition"}:
        return "export_request"
    if tool_id == "data_intelligence_semantic_mapping_proposal":
        return "semantic_catalog_mapping_proposal"
    if tool_id == "semantic_catalog_create_review_proposal":
        return "semantic_catalog_impact_preview"
    if tool_id == "create_followup_task":
        return "write_tool_execution"
    return "large_analysis_run"


def _approval_target_ref_from_plan(plan: OpenAIAgentPlanOut) -> str | None:
    for key in ("target_ref", "query_id", "report_id", "mapping_id"):
        value = plan.tool_arguments.get(key)
        if isinstance(value, str) and value.strip():
            cleaned = value.strip()[:160]
            _validate_safe_values([cleaned])
            return cleaned
    return plan.tool_id


def _approval_risk_flags(
    *,
    tool_id: str,
    target_kind: AgentRuntimeApprovalTargetKind,
    data_classes: list[str],
) -> list[str]:
    flags = {"human_approval_required"}
    if target_kind == "export_request":
        flags.add("export_requested")
    if target_kind == "write_tool_execution":
        flags.add("write_capable_tool")
    if target_kind.startswith("semantic_catalog"):
        flags.add("business_meaning_change")
    if "billing" in data_classes:
        flags.add("billing_sensitive")
    if "phi" in data_classes:
        flags.add("phi_blocked")
    if tool_id not in _SAFE_LLM_PLANNING_TOOL_IDS:
        flags.add("not_auto_executable")
    return sorted(flags)


def _audit_summary_with_linked_approval(
    audit_summary: dict[str, object],
    approval_id: str,
) -> dict[str, object]:
    updated = dict(audit_summary)
    current = updated.get("linked_approval_request_ids", [])
    linked_ids = (
        [item for item in current if isinstance(item, str)]
        if isinstance(current, list)
        else []
    )
    if approval_id not in linked_ids:
        linked_ids.append(approval_id)
    updated["linked_approval_request_ids"] = linked_ids
    decisions = updated.get("policy_decisions", [])
    policy_decisions = (
        [item for item in decisions if isinstance(item, dict)]
        if isinstance(decisions, list)
        else []
    )
    policy_decisions.append(
        {
            "gate_id": "human_approval_request",
            "result": "approval_required",
            "reason": "Agent Runtime created a pending human approval request.",
            "evidence_refs": [approval_id],
        }
    )
    updated["policy_decisions"] = policy_decisions
    current_evidence_refs = updated.get("evidence_refs", [])
    evidence_refs = [
        item for item in current_evidence_refs if isinstance(item, str)
    ] if isinstance(current_evidence_refs, list) else []
    if "human_approval_request" not in evidence_refs:
        evidence_refs.append("human_approval_request")
    updated["evidence_refs"] = evidence_refs
    return AgentRuntimeAuditSummaryOut.model_validate(updated).model_dump()


def _audit_summary_with_manager_answer(
    audit_summary: dict[str, object],
    *,
    eligibility: AgentRuntimeManagerAnswerEligibilityOut,
    manager_answer: AgentRuntimeManagerAnswerOut,
) -> dict[str, object]:
    updated = dict(audit_summary)
    answer_evidence_refs = ["manager_answer_contract"]
    if manager_answer.status in {"generated", "generated_with_caveat"}:
        answer_evidence_refs.extend(
            [
                "manager_answer_llm_generation",
                "manager_answer_source_refs",
            ]
        )
        if manager_answer.widgets:
            answer_evidence_refs.append("manager_answer_widgets")
    if eligibility.answer_posture == "generated_with_caveat":
        answer_evidence_refs.append("manager_answer_data_quality_caveats")
    answer_source_refs = (
        manager_answer.source_refs
        if manager_answer.source_refs is not None
        else eligibility.source_refs
    )
    updated["answer"] = {
        "status": manager_answer.status,
        "eligible": eligibility.eligible,
        "reason": eligibility.reason,
        "answer_posture": eligibility.answer_posture,
        "model": manager_answer.model,
        "confidence": manager_answer.confidence,
        "source_refs": (
            answer_source_refs.model_dump(mode="json")
            if answer_source_refs is not None
            else None
        ),
        "caveats": manager_answer.caveats,
        "data_quality_evidence_refs": eligibility.data_quality_evidence_refs,
        "data_quality_metrics": [
            metric.model_dump(mode="json")
            for metric in eligibility.data_quality_metrics
        ],
        "widget_summary": _manager_answer_widget_audit_summary(manager_answer),
        "safety_notes": manager_answer.safety_notes,
        "validation_errors": manager_answer.validation_errors,
    }
    current_evidence_refs = updated.get("evidence_refs", [])
    evidence_refs = (
        [item for item in current_evidence_refs if isinstance(item, str)]
        if isinstance(current_evidence_refs, list)
        else []
    )
    for ref in answer_evidence_refs:
        if ref not in evidence_refs:
            evidence_refs.append(ref)
    updated["evidence_refs"] = evidence_refs

    current_notes = updated.get("compliance_notes", [])
    compliance_notes = (
        [item for item in current_notes if isinstance(item, str)]
        if isinstance(current_notes, list)
        else []
    )
    answer_note = (
        "Run history stores manager answer metadata only; answer body and "
        "provider payload are not persisted."
    )
    if answer_note not in compliance_notes:
        compliance_notes.append(answer_note)
    updated["compliance_notes"] = compliance_notes
    return AgentRuntimeAuditSummaryOut.model_validate(updated).model_dump(mode="json")


def _tool_calls_with_approval_request(
    tool_calls: list[dict[str, object]],
    approval_id: str,
) -> list[dict[str, object]]:
    return [
        {
            **call,
            "approval_request_id": approval_id,
        }
        for call in tool_calls
    ]


def _run_matches_history_filters(
    row: AgentRuntimeRun,
    filters: AgentRuntimeRunHistoryFiltersOut,
) -> bool:
    if filters.tool_id is not None:
        tool_calls = row.tool_calls if isinstance(row.tool_calls, list) else []
        if not any(
            isinstance(call, dict) and call.get("tool_id") == filters.tool_id
            for call in tool_calls
        ):
            return False
    if filters.policy_result is not None:
        if row.audit_summary.get("policy_result") != filters.policy_result:
            return False
    if filters.final_outcome is not None:
        if row.audit_summary.get("final_outcome") != filters.final_outcome:
            return False
    return True


def _safe_error_message(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.replace("\n", " ").strip()
    return cleaned[:240]


def _parse_optional_uuid(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ValidationError(
            "source_run_id must be a valid UUID.",
            details={"field": "source_run_id"},
        ) from exc


def _decision_to_status(decision: str) -> AgentRuntimeApprovalStatus:
    if decision == "approve":
        return "approved"
    if decision == "reject":
        return "rejected"
    if decision == "request_edit":
        return "needs_edit"
    if decision == "mark_unresolved":
        return "unresolved"
    raise ValidationError(
        "Unsupported approval decision.",
        details={"decision": decision},
    )


def _approval_workflow_state(status: str) -> str:
    if status == "approved":
        return "approved_no_auto_execution"
    if status == "rejected":
        return "rejected"
    if status == "needs_edit":
        return "needs_edit"
    if status == "unresolved":
        return "unresolved"
    return "pending_review"


def _approval_decision_run_status(status: str) -> str:
    if status == "approved":
        return "success"
    if status == "rejected":
        return "denied"
    return "blocked"


def _approval_decision_audit_summary(
    approval: AgentRuntimeApprovalRequest,
) -> dict[str, object]:
    status = str(approval.status)
    decision_result = "allowed" if status == "approved" else (
        "denied" if status == "rejected" else "blocked"
    )
    final_outcome = "completed" if status == "approved" else (
        "denied" if status == "rejected" else "blocked"
    )
    return AgentRuntimeAuditSummaryOut(
        data_classes=list(approval.data_classes),
        data_level="metadata_only",
        row_level=False,
        phi="phi" in approval.data_classes,
        billing="billing" in approval.data_classes,
        export=approval.target_kind == "export_request",
        masked=True,
        policy_result=decision_result,
        policy_gate="human_approval_decision",
        policy_reason=approval.decision_summary
        or "Human reviewer recorded an approval decision.",
        approval_required=False,
        final_outcome=final_outcome,  # type: ignore[arg-type]
        policy_decisions=[
            {
                "gate_id": "human_approval_decision",
                "result": decision_result,
                "reason": approval.decision_summary
                or "Human reviewer recorded a decision.",
                "evidence_refs": [str(approval.id)],
            }
        ],
        evidence_refs=[str(approval.id), "human_approval_decision"],
        compliance_notes=[
            "Approval decision stored safe metadata only.",
            "Approval does not grant restricted clinical data, direct DB access, or policy bypass.",
        ],
        linked_approval_request_ids=[str(approval.id)],
    ).model_dump()


def _openai_health_audit_summary(
    *,
    policy_result: str,
    final_outcome: str,
    provider_decision_result: str,
    provider_decision_reason: str,
) -> dict[str, object]:
    return {
        "data_classes": ["integration_metadata"],
        "data_level": "metadata_only",
        "row_level": False,
        "phi": False,
        "billing": False,
        "export": False,
        "masked": True,
        "policy_result": policy_result,
        "policy_gate": "provider_credential_health_check",
        "policy_reason": "Tenant OpenAI credential check uses metadata only.",
        "approval_required": False,
        "final_outcome": final_outcome,
        "policy_decisions": [
            {
                "gate_id": "tenant_credential_scope",
                "result": "allowed",
                "reason": "Credential resolved server-side for current tenant.",
                "evidence_refs": ["tenant_credential_status"],
            },
            {
                "gate_id": "sensitive_output_filter",
                "result": provider_decision_result,
                "reason": provider_decision_reason,
                "evidence_refs": ["safe_metadata_contract"],
            },
        ],
        "evidence_refs": ["provider_health_check"],
        "compliance_notes": [
            "No secret or sensitive runtime payload stored.",
        ],
        "linked_approval_request_ids": [],
    }


def _plan_tool_calls(
    plan: OpenAIAgentPlanOut,
    policy: _LlmPlanPolicy,
) -> list[dict[str, object]]:
    if plan.outcome != "tool_plan" or plan.tool_id is None:
        return []
    data_classes = sorted(ALL_TOOLS[plan.tool_id].touches) if plan.tool_id in ALL_TOOLS else []
    meta = _TOOL_METADATA.get(plan.tool_id, {})
    return [
        {
            "tool_id": plan.tool_id,
            "status": policy.run_status,
            "data_classes": data_classes,
            "output_posture": str(meta.get("output_posture", "safe tool plan only")),
        }
    ]


def _tool_call_data_classes(tool_calls: list[dict[str, object]]) -> list[str]:
    data_classes = {"integration_metadata"}
    for call in tool_calls:
        raw_data_classes = call.get("data_classes", [])
        if not isinstance(raw_data_classes, list):
            continue
        for data_class in raw_data_classes:
            if isinstance(data_class, str):
                data_classes.add(data_class)
    return sorted(data_classes)


def _apply_execution_to_tool_calls(
    tool_calls: list[dict[str, object]],
    execution: _LlmToolExecution,
) -> list[dict[str, object]]:
    if not tool_calls:
        return tool_calls
    updated: list[dict[str, object]] = []
    for call in tool_calls:
        next_call = dict(call)
        if execution.status == "executed":
            next_call["status"] = "success"
            next_call["output_posture"] = "aggregate analytics result"
        elif execution.status in {"no_match", "clarification_required"}:
            next_call["status"] = "blocked"
        elif execution.status == "failed":
            next_call["status"] = "failure"
        if execution.query_match is not None:
            next_call["query_id"] = execution.query_match.query_id
            next_call["read_model_id"] = execution.query_match.read_model_id
            next_call["match_confidence"] = execution.query_match.confidence
        if execution.output is not None and execution.output.data_classes:
            next_call["data_classes"] = list(execution.output.data_classes)
        updated.append(next_call)
    return updated


def _safe_tool_question(tool_arguments: dict[str, object]) -> str | None:
    raw_question = tool_arguments.get("question")
    if raw_question is None:
        raw_question = tool_arguments.get("analytics_question")
    if raw_question is None:
        raw_question = tool_arguments.get("manager_question")
    if not isinstance(raw_question, str):
        return None
    question = raw_question.strip()
    if not question:
        return None
    _validate_safe_values([question])
    return question[:500]


def _safe_tool_query_id(tool_arguments: dict[str, object]) -> AnalyticsQueryId:
    raw_query_id = tool_arguments.get("query_id")
    if not isinstance(raw_query_id, str):
        raise ValidationError(
            "Planner did not provide a safe approved analytics query_id.",
            details={"field": "query_id"},
        )
    query_id = raw_query_id.strip()
    if not query_id:
        raise ValidationError(
            "Planner did not provide a safe approved analytics query_id.",
            details={"field": "query_id"},
        )
    _validate_safe_values([query_id])
    return canonical_analytics_query_literal(query_id)


def _query_match_from_manager_match(
    match: ManagerAnalyticsQueryMatch,
) -> _ApprovedQueryReadModelMatch:
    return _ApprovedQueryReadModelMatch(
        query_id=match.query_id,
        read_model_id=match.read_model_id,
        confidence=match.confidence,
        matched_keywords=tuple(match.matched_keywords),
        reason=match.reason,
    )


def _query_match_from_query_id(query_id: AnalyticsQueryId) -> _ApprovedQueryReadModelMatch:
    canonical_query_id = str(query_id)
    metadata = analytics_query_metadata(canonical_query_id)
    read_model_id = str(metadata["read_model_id"])
    return _ApprovedQueryReadModelMatch(
        query_id=canonical_query_id,
        read_model_id=read_model_id,
        confidence="high",
        matched_keywords=(canonical_query_id, read_model_id),
        reason=(
            "Planner selected an approved analytics query/read-model contract: "
            f"{canonical_query_id} -> {read_model_id}."
        ),
    )


def _execution_output_from_analytics_execution(
    *,
    tool_id: str,
    query_match: _ApprovedQueryReadModelMatch,
    execution: dict[str, object],
    explanation: str | None,
    policy_reason: str,
) -> AgentRuntimeLlmExecutionOut:
    executed_query_id = _optional_str(execution.get("query_id"))
    executed_read_model_id = _optional_str(execution.get("read_model_id"))
    if (
        executed_query_id != query_match.query_id
        or executed_read_model_id != query_match.read_model_id
    ):
        return AgentRuntimeLlmExecutionOut(
            status="failed",
            tool_id=tool_id,
            query_id=query_match.query_id,
            read_model_id=query_match.read_model_id,
            match_status="matched",
            match_confidence=query_match.confidence,
            match_reason=query_match.reason,
            matched_keywords=list(query_match.matched_keywords),
            output_type="none",
            policy_reason=(
                "Approved tool execution did not match the deterministic "
                "query/read-model selection."
            ),
        )
    return AgentRuntimeLlmExecutionOut(
        status="executed",
        tool_id=tool_id,
        query_id=query_match.query_id,
        read_model_id=query_match.read_model_id,
        match_status="matched",
        match_confidence=query_match.confidence,
        match_reason=query_match.reason,
        matched_keywords=list(query_match.matched_keywords),
        output_type="aggregate",
        data_classes=_string_list(execution.get("data_classes", [])),
        row_count=_optional_int(execution.get("row_count")),
        explanation=_optional_str(explanation),
        policy_reason=policy_reason,
        result=execution,
    )


def _safe_tool_params(
    tool_arguments: dict[str, object],
    *,
    question: str | None = None,
    now: datetime | None = None,
) -> dict[str, object] | None:
    raw_params = tool_arguments.get("params")
    if isinstance(raw_params, dict):
        safe_params = _safe_params_dict(
            {str(key): value for key, value in raw_params.items()}
        )
        return _apply_question_time_window(safe_params, question=question, now=now)

    params: dict[str, object] = {}
    allowed_keys = {
        "created_from",
        "created_to",
        "from",
        "to",
        "source_provider",
        "lead_source",
        "location_id",
        "limit",
    }
    for key in allowed_keys:
        value = tool_arguments.get(key)
        if value is not None:
            params[key] = value
    safe_params = _safe_params_dict(params) if params else {}
    safe_params = _apply_question_time_window(safe_params, question=question, now=now)
    return safe_params if safe_params else None


def _apply_question_time_window(
    params: dict[str, object],
    *,
    question: str | None,
    now: datetime | None = None,
) -> dict[str, object]:
    return apply_question_time_window(params, question=question, now=now)


_MANAGER_ANSWER_SUSPICIOUS_CONSULTATION_COUNT = 50_000


def _safe_params_dict(params: Mapping[str, object]) -> dict[str, object]:
    safe: dict[str, object] = {}
    for key, value in params.items():
        text_key = str(key)
        if text_key in {"raw_sql", "sql", "query", "raw_provider_payload"}:
            raise ValidationError(
                "Unsafe tool parameter is not allowed for execution.",
                details={"param": text_key},
            )
        if isinstance(value, str):
            _validate_safe_values([value])
            safe[text_key] = value[:500]
        elif value is None or isinstance(value, (bool, int, float)):
            safe[text_key] = value
        else:
            safe[text_key] = str(value)[:500]
    return safe


def _attach_time_window_to_execution(
    execution: dict[str, object],
    params: dict[str, object] | None,
) -> dict[str, object]:
    time_window = _time_window_metadata_from_params(params)
    if time_window is None:
        return execution

    updated = dict(execution)
    filters = updated.get("filters")
    if isinstance(filters, dict):
        updated["filters"] = {
            **filters,
            "time_window_source": time_window["source"],
            "time_window_preset": time_window["preset"],
            "time_window_disclosure": time_window.get("disclosure"),
        }
    updated["time_window"] = time_window
    return updated


def _time_window_metadata_from_params(
    params: dict[str, object] | None,
) -> dict[str, object] | None:
    if not params:
        return None
    source = _optional_str(params.get("time_window_source"))
    preset = _optional_str(params.get("time_window_preset"))
    created_from = _optional_str(params.get("created_from") or params.get("from"))
    created_to = _optional_str(params.get("created_to") or params.get("to"))
    if source is None or preset is None:
        return None
    return {
        "source": source,
        "preset": preset,
        "created_from": created_from,
        "created_to": created_to,
        "disclosure": _optional_str(params.get("time_window_disclosure")),
    }


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    _validate_safe_values([text])
    return text[:500]


def _optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if value is None:
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def _execution_evidence_refs(execution: _LlmToolExecution) -> list[str]:
    refs = ["openai_agent_plan_contract"]
    if execution.status == "executed":
        refs.extend(
            [
                "approved_tool_registry",
                "approved_query_read_model_match",
                "manager_analytics_query_registry",
                "service_owned_read_model_execution",
                "aggregate_correctness_guardrails",
            ]
        )
        if _execution_has_data_quality_evidence(execution):
            refs.append("aggregate_read_model_data_quality_metrics")
    elif execution.status in {"no_match", "clarification_required"}:
        refs.append("manager_analytics_query_registry")
    return refs


def _execution_has_data_quality_evidence(execution: _LlmToolExecution) -> bool:
    if execution.output is None or execution.output.result is None:
        return False
    return isinstance(execution.output.result.get("data_quality_evidence"), dict)


def _manager_answer_eligibility_from_execution(
    *,
    run: AgentRuntimeRun,
    execution: _LlmToolExecution,
) -> AgentRuntimeManagerAnswerEligibilityOut:
    source_refs = _manager_answer_source_refs(run, execution)
    if execution.status != "executed":
        return AgentRuntimeManagerAnswerEligibilityOut(
            eligible=False,
            reason="Manager answer generation requires executed aggregate output.",
            answer_posture="blocked",
            execution_status=execution.status,  # type: ignore[arg-type]
            result_posture=execution.result_posture,  # type: ignore[arg-type]
            tool_id=execution.output.tool_id if execution.output else None,
            query_id=execution.query_match.query_id if execution.query_match else None,
            read_model_id=(
                execution.query_match.read_model_id if execution.query_match else None
            ),
            data_classes=execution.output.data_classes if execution.output else [],
        )
    if execution.output is None or execution.output.result is None:
        return AgentRuntimeManagerAnswerEligibilityOut(
            eligible=False,
            reason="Manager answer generation requires an aggregate result envelope.",
            answer_posture="blocked",
            execution_status=execution.status,  # type: ignore[arg-type]
            result_posture=execution.result_posture,  # type: ignore[arg-type]
            tool_id=None,
            data_classes=[],
        )
    if source_refs is None:
        return AgentRuntimeManagerAnswerEligibilityOut(
            eligible=False,
            reason="Manager answer generation requires approved source refs.",
            answer_posture="blocked",
            execution_status=execution.status,  # type: ignore[arg-type]
            result_posture=execution.result_posture,  # type: ignore[arg-type]
            tool_id=execution.output.tool_id,
            data_classes=execution.output.data_classes,
        )
    correctness_blockers = _manager_answer_correctness_blockers(execution)
    if correctness_blockers:
        correctness_metrics = _manager_answer_correctness_metrics(execution)
        correctness_evidence_refs = _manager_answer_correctness_evidence_refs(
            correctness_metrics
        )
        return AgentRuntimeManagerAnswerEligibilityOut(
            eligible=False,
            reason=correctness_blockers[0],
            answer_posture="blocked",
            execution_status=execution.status,  # type: ignore[arg-type]
            result_posture=execution.result_posture,  # type: ignore[arg-type]
            tool_id=source_refs.tool_id,
            query_id=source_refs.query_id,
            read_model_id=source_refs.read_model_id,
            data_classes=execution.output.data_classes,
            source_refs=source_refs,
            data_quality_evidence_refs=correctness_evidence_refs,
            data_quality_metrics=correctness_metrics,
            caveats=correctness_blockers,
        )
    data_quality_evidence_refs = _manager_answer_data_quality_evidence_refs(execution)
    data_quality_metrics = _manager_answer_data_quality_metrics(execution)
    caveats = _manager_answer_data_quality_caveats(execution)
    data_quality_blockers = _manager_answer_data_quality_blockers(execution)
    if data_quality_blockers:
        return AgentRuntimeManagerAnswerEligibilityOut(
            eligible=False,
            reason=data_quality_blockers[0],
            answer_posture="blocked",
            execution_status=execution.status,  # type: ignore[arg-type]
            result_posture=execution.result_posture,  # type: ignore[arg-type]
            tool_id=source_refs.tool_id,
            query_id=source_refs.query_id,
            read_model_id=source_refs.read_model_id,
            data_classes=execution.output.data_classes,
            source_refs=source_refs,
            data_quality_evidence_refs=data_quality_evidence_refs,
            data_quality_metrics=data_quality_metrics,
            caveats=caveats,
        )
    answer_posture: Literal["generated", "generated_with_caveat"] = (
        "generated_with_caveat"
        if data_quality_evidence_refs or data_quality_metrics or caveats
        else "generated"
    )
    return AgentRuntimeManagerAnswerEligibilityOut(
        eligible=True,
        reason=(
            "Approved aggregate execution can be summarized for managers with "
            "data-quality caveats."
            if answer_posture == "generated_with_caveat"
            else "Approved aggregate execution can be summarized for managers."
        ),
        answer_posture=answer_posture,
        execution_status=execution.status,  # type: ignore[arg-type]
        result_posture=execution.result_posture,  # type: ignore[arg-type]
        tool_id=source_refs.tool_id,
        query_id=source_refs.query_id,
        read_model_id=source_refs.read_model_id,
        data_classes=execution.output.data_classes,
        source_refs=source_refs,
        data_quality_evidence_refs=data_quality_evidence_refs,
        data_quality_metrics=data_quality_metrics,
        caveats=caveats,
    )


def _manager_answer_source_refs(
    run: AgentRuntimeRun,
    execution: _LlmToolExecution,
) -> AgentRuntimeManagerAnswerSourceRefsOut | None:
    if execution.output is None or execution.query_match is None:
        return None
    catalog_lineage = _catalog_lineage_from_execution(execution)
    return AgentRuntimeManagerAnswerSourceRefsOut(
        tool_id=execution.output.tool_id,
        query_id=execution.query_match.query_id,
        read_model_id=execution.query_match.read_model_id,
        execution_run_id=str(run.id),
        approved_catalog_version_refs=_string_list(
            catalog_lineage["approved_catalog_version_refs"]
        ),
        evidence_refs=_execution_evidence_refs(execution),
    )


def _manager_answer_correctness_blockers(
    execution: _LlmToolExecution,
) -> list[str]:
    if execution.output is None or execution.output.result is None:
        return []
    result = execution.output.result
    blockers: list[str] = []

    time_window = result.get("time_window")
    if not isinstance(time_window, dict):
        blockers.append(
            "Manager answer generation requires explicit or default time-window metadata."
        )
    else:
        missing_time_fields = [
            field
            for field in ("source", "preset", "created_from", "created_to", "disclosure")
            if _optional_str(time_window.get(field)) is None
        ]
        if missing_time_fields:
            blockers.append(
                "Manager answer generation requires complete time-window disclosure."
            )

    for metric in _manager_answer_correctness_metrics(execution):
        metric_value = f"{metric.value:g}"
        blockers.append(
            "Manager answer generation blocked: consultation aggregate "
            f"`{metric.evidence_ref}`={metric_value} exceeds the V1 "
            "correctness review threshold."
        )

    return blockers


def _manager_answer_correctness_metrics(
    execution: _LlmToolExecution,
) -> list[AgentRuntimeDataQualityMetricOut]:
    if execution.output is None or execution.output.result is None:
        return []
    result = execution.output.result
    metrics: list[AgentRuntimeDataQualityMetricOut] = []
    for path, value in _walk_numeric_aggregate_values(result):
        normalized_path = path.casefold()
        if "consult" not in normalized_path and "appointment" not in normalized_path:
            continue
        if value < _MANAGER_ANSWER_SUSPICIOUS_CONSULTATION_COUNT:
            continue
        metrics.append(
            AgentRuntimeDataQualityMetricOut(
                id="suspicious_consultation_aggregate_count",
                label="Suspicious consultation aggregate count",
                value=value,
                unit="count",
                denominator=float(_MANAGER_ANSWER_SUSPICIOUS_CONSULTATION_COUNT),
                status="blocked",
                evidence_ref=path,
            )
        )
    return metrics


def _manager_answer_correctness_evidence_refs(
    metrics: list[AgentRuntimeDataQualityMetricOut],
) -> list[str]:
    refs = ["aggregate_correctness_guardrails"]
    refs.extend(
        metric.evidence_ref
        for metric in metrics
        if metric.evidence_ref is not None
    )
    return list(dict.fromkeys(refs))


def _manager_answer_data_quality_evidence_refs(
    execution: _LlmToolExecution,
) -> list[str]:
    if execution.output is None or execution.output.result is None:
        return []
    result = execution.output.result
    refs = _string_list(result.get("data_quality_evidence_refs", []))
    data_quality_evidence = result.get("data_quality_evidence")
    if isinstance(data_quality_evidence, dict):
        refs.append("aggregate_read_model_data_quality_metrics")
        refs.extend(_string_list(data_quality_evidence.get("refs", [])))
        refs.extend(_string_list(data_quality_evidence.get("evidence_refs", [])))
        for metric in _data_quality_metric_dicts(data_quality_evidence):
            evidence_ref = _optional_str(metric.get("evidence_ref"))
            if evidence_ref is not None:
                refs.append(evidence_ref)
    if result.get("warnings"):
        refs.append("aggregate_execution_warnings")
    return list(dict.fromkeys(refs))


def _manager_answer_data_quality_metrics(
    execution: _LlmToolExecution,
) -> list[AgentRuntimeDataQualityMetricOut]:
    if execution.output is None or execution.output.result is None:
        return []
    data_quality_evidence = execution.output.result.get("data_quality_evidence")
    if not isinstance(data_quality_evidence, dict):
        return []
    metrics: list[AgentRuntimeDataQualityMetricOut] = []
    for metric in _data_quality_metric_dicts(data_quality_evidence):
        metrics.append(AgentRuntimeDataQualityMetricOut.model_validate(metric))
    return metrics


def _manager_answer_data_quality_blockers(
    execution: _LlmToolExecution,
) -> list[str]:
    if execution.output is None or execution.output.result is None:
        return []
    data_quality_evidence = execution.output.result.get("data_quality_evidence")
    if not isinstance(data_quality_evidence, dict):
        return []
    blockers = _string_list(data_quality_evidence.get("blockers", []))
    for metric in _data_quality_metric_dicts(data_quality_evidence):
        if _optional_str(metric.get("status")) == "blocked":
            label = _optional_str(metric.get("label")) or _optional_str(metric.get("id"))
            if label is not None:
                blockers.append(
                    f"Manager answer generation blocked by aggregate data-quality metric: {label}."
                )
    return list(dict.fromkeys(blockers))


def _manager_answer_data_quality_caveats(
    execution: _LlmToolExecution,
) -> list[str]:
    if execution.output is None or execution.output.result is None:
        return []
    result = execution.output.result
    caveats: list[str] = []
    caveats.extend(_string_list(result.get("warnings", [])))
    data_quality_evidence = result.get("data_quality_evidence")
    if isinstance(data_quality_evidence, dict):
        caveats.extend(_string_list(data_quality_evidence.get("caveats", [])))
    return list(dict.fromkeys(caveats))


def _data_quality_metric_dicts(
    data_quality_evidence: dict[str, object],
) -> list[dict[str, object]]:
    metrics = data_quality_evidence.get("metrics", [])
    if not isinstance(metrics, list):
        return []
    return [metric for metric in metrics if isinstance(metric, dict)]


def _walk_numeric_aggregate_values(value: object, *, path: str = "result"):
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        yield path, float(value)
        return
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield from _walk_numeric_aggregate_values(child, path=child_path)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_numeric_aggregate_values(child, path=f"{path}[{index}]")


def _manager_answer_question(plan: OpenAIAgentPlanOut) -> str:
    question = _safe_tool_question(plan.tool_arguments)
    if question is not None:
        return question
    return plan.intent[:500]


def _manager_answer_caveats(
    execution: _LlmToolExecution,
    *,
    eligibility: AgentRuntimeManagerAnswerEligibilityOut | None = None,
) -> list[str]:
    caveats = [
        "Answer is based on aggregate execution output only.",
        "No row-level rows, PHI, SQL text, or provider payload details are included.",
    ]
    time_window_disclosure = _manager_answer_time_window_disclosure(execution)
    if time_window_disclosure is not None:
        caveats.append(time_window_disclosure)
    if execution.output is not None and execution.output.row_count == 0:
        caveats.append("Aggregate result contains no rows for the selected filters.")
    if (
        execution.query_match is not None
        and execution.query_match.confidence != "high"
    ):
        caveats.append(
            "Question-to-query match confidence is "
            f"{execution.query_match.confidence}."
        )
    if eligibility is not None and eligibility.answer_posture == "generated_with_caveat":
        caveats.append("Aggregate data-quality evidence requires manager-facing caveats.")
        caveats.extend(eligibility.caveats)
    return caveats


def _merge_manager_answer_caveats(
    answer_caveats: list[str],
    execution: _LlmToolExecution,
    *,
    eligibility: AgentRuntimeManagerAnswerEligibilityOut | None = None,
) -> list[str]:
    merged: list[str] = []
    for caveat in [
        *answer_caveats,
        *_manager_answer_caveats(execution, eligibility=eligibility),
    ]:
        if caveat not in merged:
            merged.append(caveat)
    return merged


def _manager_answer_widgets(
    answer: OpenAIManagerAnswerOut,
    execution: _LlmToolExecution,
) -> list[AgentRuntimeManagerAnswerWidgetOut]:
    widgets: list[AgentRuntimeManagerAnswerWidgetOut] = []
    widgets.extend(_manager_answer_metric_widgets(answer))
    widgets.extend(_manager_answer_bar_chart_widgets(execution))
    return widgets[:8]


def _manager_answer_metric_widgets(
    answer: OpenAIManagerAnswerOut,
) -> list[AgentRuntimeManagerAnswerWidgetOut]:
    widgets: list[AgentRuntimeManagerAnswerWidgetOut] = []
    for index, key_number in enumerate(answer.key_numbers[:4]):
        value = _widget_numeric_value(key_number.value)
        if value is None:
            continue
        evidence_ref = f"manager_answer.key_numbers[{index}]"
        try:
            widgets.append(
                AgentRuntimeManagerAnswerWidgetOut(
                    id=f"key_number_{index + 1}",
                    title=key_number.label,
                    widget_type="metric",
                    unit=key_number.unit,
                    points=[
                        AgentRuntimeManagerAnswerWidgetPointOut(
                            label=key_number.label,
                            value=value,
                            unit=key_number.unit,
                            evidence_ref=evidence_ref,
                        )
                    ],
                    evidence_refs=[evidence_ref],
                )
            )
        except (PydanticValidationError, ValidationError):
            continue
    return widgets


def _manager_answer_bar_chart_widgets(
    execution: _LlmToolExecution,
) -> list[AgentRuntimeManagerAnswerWidgetOut]:
    if execution.output is None or execution.output.result is None:
        return []
    aggregate_result = execution.output.result.get("result")
    if not isinstance(aggregate_result, dict):
        return []

    widgets: list[AgentRuntimeManagerAnswerWidgetOut] = []
    for series_key, series_value in aggregate_result.items():
        if not isinstance(series_key, str) or not isinstance(series_value, list):
            continue
        points = _manager_answer_bar_chart_points(series_key, series_value)
        if not points:
            continue
        evidence_refs = [
            point.evidence_ref
            for point in points
            if point.evidence_ref is not None
        ]
        try:
            widgets.append(
                AgentRuntimeManagerAnswerWidgetOut(
                    id=f"{_widget_slug(series_key)}_bar_chart",
                    title=_widget_title(series_key),
                    widget_type="bar_chart",
                    unit=_widget_unit(points),
                    points=points,
                    evidence_refs=evidence_refs,
                )
            )
        except (PydanticValidationError, ValidationError):
            continue
    return widgets[:4]


def _manager_answer_bar_chart_points(
    series_key: str,
    rows: list[object],
) -> list[AgentRuntimeManagerAnswerWidgetPointOut]:
    points: list[AgentRuntimeManagerAnswerWidgetPointOut] = []
    for index, row in enumerate(rows[:12]):
        if not isinstance(row, dict):
            continue
        label = _widget_point_label(row)
        value_key, value = _widget_point_value(row)
        if label is None or value_key is None or value is None:
            continue
        evidence_ref = f"result.result.{series_key}[{index}].{value_key}"
        try:
            points.append(
                AgentRuntimeManagerAnswerWidgetPointOut(
                    label=label,
                    value=value,
                    unit="count" if value_key == "count" else None,
                    evidence_ref=evidence_ref,
                )
            )
        except (PydanticValidationError, ValidationError):
            continue
    return points


def _widget_point_label(row: dict[object, object]) -> str | None:
    # Keep this allowlist limited to approved aggregate dimension keys.
    for key in ("label", "key", "status", "source", "bucket"):
        try:
            label = _optional_str(row.get(key))
        except ValidationError:
            continue
        if label is not None:
            return label
    return None


def _widget_point_value(
    row: dict[object, object],
) -> tuple[str | None, int | float | None]:
    for key in ("count", "value", "total"):
        value = _widget_numeric_value(row.get(key))
        if value is not None:
            return key, value
    return None, None


def _widget_numeric_value(value: object) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _normalized_question_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _widget_slug(value: str) -> str:
    normalized = _normalized_question_text(value)
    chars = [char if char.isalnum() else "_" for char in normalized]
    slug = "_".join("".join(chars).split("_"))
    return (slug or "aggregate")[:120]


def _widget_title(value: str) -> str:
    title = value.replace("_", " ").strip().title()
    return title[:160] or "Aggregate"


def _widget_unit(
    points: list[AgentRuntimeManagerAnswerWidgetPointOut],
) -> str | None:
    units = [point.unit for point in points if point.unit is not None]
    if not units:
        return None
    first = units[0]
    return first if all(unit == first for unit in units) else None


def _manager_answer_widget_audit_summary(
    manager_answer: AgentRuntimeManagerAnswerOut,
) -> dict[str, object]:
    evidence_refs: list[str] = []
    widget_types: list[str] = []
    for widget in manager_answer.widgets:
        if widget.widget_type not in widget_types:
            widget_types.append(widget.widget_type)
        for evidence_ref in widget.evidence_refs:
            if evidence_ref not in evidence_refs:
                evidence_refs.append(evidence_ref)
    return {
        "count": len(manager_answer.widgets),
        "types": widget_types,
        "evidence_refs": evidence_refs,
    }


def _manager_answer_time_window_disclosure(
    execution: _LlmToolExecution,
) -> str | None:
    if execution.output is None or execution.output.result is None:
        return None
    time_window = execution.output.result.get("time_window")
    if not isinstance(time_window, dict):
        return None
    disclosure = _optional_str(time_window.get("disclosure"))
    if disclosure is not None:
        return disclosure
    preset = _optional_str(time_window.get("preset"))
    if preset is None:
        return None
    return f"Applied time window: {preset}."


def _apply_deterministic_manager_analytics_fallback(
    plan: OpenAIAgentPlanOut,
    *,
    user_prompt: str,
) -> OpenAIAgentPlanOut:
    if plan.outcome != "clarification_required" or plan.tool_id is not None:
        return plan

    match = select_manager_query_match(user_prompt)
    if match is None:
        return plan

    safety_notes = [
        *plan.safety_notes,
        _DETERMINISTIC_MANAGER_ANALYTICS_FALLBACK_NOTE,
    ][:8]
    return plan.model_copy(
        update={
            "outcome": "tool_plan",
            "intent": "manager_analytics_deterministic_fallback",
            "tool_id": "ask_manager_analytics",
            "tool_arguments": {"question": user_prompt},
            "confidence": match.confidence,
            "clarification_question": None,
            "refusal_reason": None,
            "safety_notes": safety_notes,
        },
    )


def _evaluate_llm_plan_policy(plan: OpenAIAgentPlanOut) -> _LlmPlanPolicy:
    if plan.outcome == "clarification_required":
        return _LlmPlanPolicy(
            result="blocked",
            run_status="blocked",
            final_outcome="blocked",
            reason="LLM requested clarification before selecting any tool.",
        )
    if plan.outcome == "refused":
        return _LlmPlanPolicy(
            result="denied",
            run_status="denied",
            final_outcome="denied",
            reason="LLM refused the request under the safe planning contract.",
        )
    if plan.tool_id is None or plan.tool_id not in ALL_TOOLS:
        return _LlmPlanPolicy(
            result="denied",
            run_status="denied",
            final_outcome="denied",
            reason="LLM selected a tool that is not in the Agent Runtime allowlist.",
        )

    tool = ALL_TOOLS[plan.tool_id]
    meta = _TOOL_METADATA.get(plan.tool_id, {})
    if "phi" in tool.touches:
        return _LlmPlanPolicy(
            result="denied",
            run_status="denied",
            final_outcome="denied",
            reason="PHI-bearing tools are not available to the LLM pilot.",
        )
    if bool(meta.get("requires_approval")):
        return _LlmPlanPolicy(
            result="approval_required",
            run_status="approval_required",
            final_outcome="approval_required",
            reason="Selected tool requires human approval before execution.",
            approval_required=True,
        )
    if plan.tool_id not in _SAFE_LLM_PLANNING_TOOL_IDS:
        return _LlmPlanPolicy(
            result="blocked",
            run_status="blocked",
            final_outcome="blocked",
            reason=(
                "Selected tool is not approved for aggregate-only LLM pilot "
                "planning."
            ),
        )
    return _LlmPlanPolicy(
        result="allowed",
        run_status="success",
        final_outcome="completed",
        reason=(
            "Deterministic approved matcher selected an aggregate manager tool."
            if _DETERMINISTIC_MANAGER_ANALYTICS_FALLBACK_NOTE in plan.safety_notes
            else "LLM returned a validated plan for an approved aggregate tool."
        ),
    )


def _llm_planning_audit_summary(
    *,
    data_classes: list[str],
    policy_result: str,
    final_outcome: str,
    planner_decision_result: str,
    planner_decision_reason: str,
    approval_required: bool = False,
    export: bool = False,
    evidence_refs: list[str] | None = None,
    execution: _LlmToolExecution | None = None,
) -> dict[str, object]:
    unique_data_classes = sorted(set(data_classes))
    executed = execution is not None and execution.status == "executed"
    compliance_notes = [
        "No prompt body, secret, provider payload, or sensitive output stored.",
        "Planning does not execute tools or access the database directly.",
    ]
    if executed:
        compliance_notes = [
            "No prompt body, secret, provider payload, or sensitive output stored.",
            "Approved aggregate tool execution used service-owned read-model code.",
            "No row-level drilldown, PHI output, or export was produced.",
        ]
    policy_decisions = [
        {
            "gate_id": "tenant_credential_scope",
            "result": "allowed",
            "reason": "Credential resolved server-side for current tenant.",
            "evidence_refs": ["tenant_credential_status"],
        },
        {
            "gate_id": "llm_prompt_envelope",
            "result": "allowed",
            "reason": "Prompt envelope contains only approved tool metadata.",
            "evidence_refs": ["safe_prompt_contract"],
        },
        {
            "gate_id": "llm_plan_schema_validation",
            "result": planner_decision_result,
            "reason": planner_decision_reason,
            "evidence_refs": ["agent_plan_v1"],
        },
    ]
    if execution is not None and execution.query_match is not None:
        policy_decisions.append(
            {
                "gate_id": "approved_query_read_model_match",
                "result": "allowed",
                "reason": execution.query_match.reason,
                "evidence_refs": [
                    execution.query_match.query_id,
                    execution.query_match.read_model_id,
                ],
            }
        )
    if execution is not None and execution.status != "not_applicable":
        policy_decisions.append(
            {
                "gate_id": "approved_tool_execution",
                "result": "allowed" if executed else "blocked",
                "reason": execution.policy_reason,
                "evidence_refs": _execution_evidence_refs(execution),
            }
        )
    if execution is not None and _execution_has_data_quality_evidence(execution):
        data_quality_blockers = _manager_answer_data_quality_blockers(execution)
        policy_decisions.append(
            {
                "gate_id": "aggregate_read_model_data_quality",
                "result": "blocked" if data_quality_blockers else "allowed",
                "reason": data_quality_blockers[0]
                if data_quality_blockers
                else "Service-owned aggregate data-quality metrics were attached to the read-model execution.",
                "evidence_refs": _manager_answer_data_quality_evidence_refs(execution),
            }
        )
    catalog_lineage = _catalog_lineage_from_execution(execution)
    return {
        "data_classes": unique_data_classes,
        "data_level": "aggregate_only" if executed else "metadata_only",
        "row_level": False,
        "phi": "phi" in unique_data_classes,
        "billing": "billing" in unique_data_classes,
        "export": export,
        "masked": True,
        "policy_result": policy_result,
        "policy_gate": "llm_plan_and_tool_execution"
        if executed
        else "llm_plan_contract",
        "policy_reason": execution.policy_reason
        if execution is not None and execution.status != "not_applicable"
        else "LLM planning stores safe metadata only.",
        "approval_required": approval_required,
        "final_outcome": final_outcome,
        "policy_decisions": policy_decisions,
        "evidence_refs": evidence_refs or ["openai_agent_plan_contract"],
        "compliance_notes": compliance_notes,
        "linked_approval_request_ids": [],
        "query_registry_refs": catalog_lineage["query_registry_refs"],
        "read_model_refs": catalog_lineage["read_model_refs"],
        "approved_catalog_version_refs": catalog_lineage[
            "approved_catalog_version_refs"
        ],
        "catalog_consumption_status": catalog_lineage[
            "catalog_consumption_status"
        ],
    }


def _catalog_lineage_from_execution(
    execution: _LlmToolExecution | None,
) -> dict[str, object]:
    if execution is None or execution.query_match is None:
        return {
            "query_registry_refs": [],
            "read_model_refs": [],
            "approved_catalog_version_refs": [],
            "catalog_consumption_status": "not_applicable",
        }
    metadata = analytics_query_metadata(execution.query_match.query_id)
    definition_versions = metadata.get("definition_versions", {})
    approved_catalog_version_refs: list[str] = []
    if isinstance(definition_versions, dict):
        approved_catalog_version_refs = [
            f"{term}:{version}"
            for term, version in sorted(definition_versions.items())
            if isinstance(term, str) and isinstance(version, str)
        ]
    return {
        "query_registry_refs": [execution.query_match.query_id],
        "read_model_refs": [execution.query_match.read_model_id],
        "approved_catalog_version_refs": approved_catalog_version_refs,
        "catalog_consumption_status": (
            "approved_version_refs"
            if approved_catalog_version_refs
            else "missing_catalog_version"
        ),
    }


def _validate_safe_values(values: list[str | None]) -> None:
    joined = " ".join(value for value in values if value).lower()
    for marker in _SENSITIVE_APPROVAL_MARKERS:
        if marker in joined:
            raise ValidationError(
                "Approval request contains unsafe detail for runtime storage.",
                details={"marker": marker},
            )
