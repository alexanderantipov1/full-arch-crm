"""Agent runtime HTTP routes.

This router is the API entry point for Fusion-owned agent orchestration.
Provider-specific SDK details stay in ``packages.integrations`` and
business tool execution stays in ``packages.tools``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db, get_principal_with_tenant
from packages.agent_runtime.schemas import (
    AgentRuntimeApprovalDecisionIn,
    AgentRuntimeApprovalRequestCreateIn,
    AgentRuntimeApprovalRequestOut,
    AgentRuntimeApprovalRequestsOut,
    AgentRuntimeApprovalStatus,
    AgentRuntimeConnectionCheckOut,
    AgentRuntimeDiaCatalogLinkagesOut,
    AgentRuntimeFinalOutcome,
    AgentRuntimeLlmPlanIn,
    AgentRuntimeLlmPlanOut,
    AgentRuntimeRunHistoryOut,
    AgentRuntimeRunStatus,
    AgentRuntimeToolsProjectionOut,
)
from packages.agent_runtime.service import AgentRuntimeService
from packages.core.exceptions import AuthorizationError
from packages.core.security import Principal, Role

PrincipalDep = Annotated[Principal, Depends(get_principal_with_tenant)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


def _require_agent_runtime_access(principal: PrincipalDep) -> None:
    """Keep Agent Runtime control-plane routes staff-owned."""

    if not (principal.has_role(Role.ADMIN) or principal.has_role(Role.SYSTEM)):
        raise AuthorizationError(
            "Agent Runtime control plane requires an admin or system principal."
        )


router = APIRouter(
    prefix="/agent-runtime",
    tags=["agent-runtime"],
    dependencies=[Depends(_require_agent_runtime_access)],
)


@router.post("/providers/openai/test", response_model=AgentRuntimeConnectionCheckOut)
async def test_openai_provider(
    principal: PrincipalDep,
    db: DbDep,
) -> AgentRuntimeConnectionCheckOut:
    """Run a safe OpenAI Agents SDK health check for the current tenant."""

    return await AgentRuntimeService(db).test_openai_connection(principal)


@router.get("/tools", response_model=AgentRuntimeToolsProjectionOut)
async def list_agent_runtime_tools(
    principal: PrincipalDep,
    db: DbDep,
) -> AgentRuntimeToolsProjectionOut:
    """List safe metadata for approved and planned agent runtime tools."""

    principal.require_tenant()
    return AgentRuntimeService(db).list_tools_projection()


@router.get("/dia-catalog-linkages", response_model=AgentRuntimeDiaCatalogLinkagesOut)
async def list_agent_runtime_dia_catalog_linkages(
    principal: PrincipalDep,
    db: DbDep,
) -> AgentRuntimeDiaCatalogLinkagesOut:
    """List safe DIA output to Semantic Catalog review linkage projections."""

    principal.require_tenant()
    return AgentRuntimeService(db).list_dia_catalog_linkages()


@router.get("/runs", response_model=AgentRuntimeRunHistoryOut)
async def list_agent_runtime_runs(
    principal: PrincipalDep,
    db: DbDep,
    limit: int = 25,
    status: AgentRuntimeRunStatus | None = None,
    tool_id: str | None = None,
    policy_result: str | None = None,
    final_outcome: AgentRuntimeFinalOutcome | None = None,
    triggered_by: str | None = None,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
) -> AgentRuntimeRunHistoryOut:
    """List safe recent agent runtime runs for the current tenant."""

    capped_limit = max(1, min(limit, 100))
    return await AgentRuntimeService(db).list_run_history(
        principal.require_tenant(),
        limit=capped_limit,
        status=status,
        tool_id=tool_id,
        policy_result=policy_result,
        final_outcome=final_outcome,
        triggered_by=triggered_by,
        started_after=started_after,
        started_before=started_before,
    )


@router.post("/llm/plans", response_model=AgentRuntimeLlmPlanOut)
async def create_agent_runtime_llm_plan(
    payload: AgentRuntimeLlmPlanIn,
    principal: PrincipalDep,
    db: DbDep,
) -> AgentRuntimeLlmPlanOut:
    """Run a constrained LLM planning turn and return safe metadata only."""

    return await AgentRuntimeService(db).generate_llm_plan(principal, payload)


@router.get("/approvals", response_model=AgentRuntimeApprovalRequestsOut)
async def list_agent_runtime_approvals(
    principal: PrincipalDep,
    db: DbDep,
    status: AgentRuntimeApprovalStatus | None = None,
    limit: int = 25,
) -> AgentRuntimeApprovalRequestsOut:
    """List safe recent agent runtime approval requests for the current tenant."""

    capped_limit = max(1, min(limit, 100))
    return await AgentRuntimeService(db).list_approval_requests(
        principal.require_tenant(),
        status=status,
        limit=capped_limit,
    )


@router.post("/approvals", response_model=AgentRuntimeApprovalRequestOut)
async def create_agent_runtime_approval(
    payload: AgentRuntimeApprovalRequestCreateIn,
    principal: PrincipalDep,
    db: DbDep,
) -> AgentRuntimeApprovalRequestOut:
    """Create a safe human approval boundary for an agent proposal."""

    return await AgentRuntimeService(db).create_approval_request(principal, payload)


@router.post(
    "/approvals/{approval_id}/decision",
    response_model=AgentRuntimeApprovalRequestOut,
)
async def decide_agent_runtime_approval(
    approval_id: uuid.UUID,
    payload: AgentRuntimeApprovalDecisionIn,
    principal: PrincipalDep,
    db: DbDep,
) -> AgentRuntimeApprovalRequestOut:
    """Record a human decision for an approval request."""

    return await AgentRuntimeService(db).decide_approval_request(
        principal,
        approval_id,
        payload,
    )
