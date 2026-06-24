"""Repositories for safe Agent Runtime summaries."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId

from .models import AgentRuntimeApprovalRequest, AgentRuntimeRun


class AgentRuntimeRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, run: AgentRuntimeRun) -> AgentRuntimeRun:
        self._session.add(run)
        await self._session.flush()
        return run

    async def list_recent(
        self,
        tenant_id: TenantId,
        *,
        limit: int = 25,
        status: str | None = None,
        triggered_by: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
    ) -> list[AgentRuntimeRun]:
        stmt = select(AgentRuntimeRun).where(
            AgentRuntimeRun.tenant_id == tenant_id,
        )
        if status is not None:
            stmt = stmt.where(AgentRuntimeRun.status == status)
        if triggered_by is not None:
            stmt = stmt.where(AgentRuntimeRun.trigger_actor_email == triggered_by)
        if started_after is not None:
            stmt = stmt.where(AgentRuntimeRun.started_at >= started_after)
        if started_before is not None:
            stmt = stmt.where(AgentRuntimeRun.started_at <= started_before)
        stmt = stmt.order_by(AgentRuntimeRun.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars())


class AgentRuntimeApprovalRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        approval: AgentRuntimeApprovalRequest,
    ) -> AgentRuntimeApprovalRequest:
        self._session.add(approval)
        await self._session.flush()
        return approval

    async def get_for_tenant(
        self,
        tenant_id: TenantId,
        approval_id: uuid.UUID,
    ) -> AgentRuntimeApprovalRequest | None:
        stmt = select(AgentRuntimeApprovalRequest).where(
            AgentRuntimeApprovalRequest.tenant_id == tenant_id,
            AgentRuntimeApprovalRequest.id == approval_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_recent(
        self,
        tenant_id: TenantId,
        *,
        status: str | None = None,
        limit: int = 25,
    ) -> list[AgentRuntimeApprovalRequest]:
        stmt = select(AgentRuntimeApprovalRequest).where(
            AgentRuntimeApprovalRequest.tenant_id == tenant_id,
        )
        if status is not None:
            stmt = stmt.where(AgentRuntimeApprovalRequest.status == status)
        stmt = (
            stmt.order_by(AgentRuntimeApprovalRequest.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars())
