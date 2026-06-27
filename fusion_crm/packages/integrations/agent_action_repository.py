"""Agent action proposal repository — data access only (ENG-440, Block G).

Takes an ``AsyncSession`` and returns ORM entities. Never commits and never
rolls back — the caller boundary (the worker job, an API dependency, a test)
owns the unit of work. Cross-package callers go through
:class:`packages.integrations.chat.agent_actions.AgentActionService`; nothing
outside ``packages.integrations`` may import this module.

Every read is tenant-scoped via :func:`packages.db.tenant_scope.for_tenant`
so a stray proposal_ref cannot leak rows across tenants.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.db.tenant_scope import for_tenant

from .models import AgentActionProposal


class AgentActionProposalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, proposal: AgentActionProposal) -> AgentActionProposal:
        self._session.add(proposal)
        await self._session.flush()
        return proposal

    async def get_by_ref(
        self, tenant_id: TenantId, proposal_ref: str
    ) -> AgentActionProposal | None:
        """Locate a proposal by its opaque ``proposal_ref`` within a tenant."""
        stmt = for_tenant(
            select(AgentActionProposal), tenant_id, AgentActionProposal
        ).where(AgentActionProposal.proposal_ref == proposal_ref)
        return (await self._session.execute(stmt)).scalar_one_or_none()


__all__ = ["AgentActionProposalRepository"]
