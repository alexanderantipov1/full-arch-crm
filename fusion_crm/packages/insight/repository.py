"""Insight repositories — strictly data access."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import SemanticCatalogProposal, SemanticCatalogVersion


class SemanticCatalogProposalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_tenant(
        self,
        tenant_id: UUID,
        proposal_id: UUID,
    ) -> SemanticCatalogProposal | None:
        stmt = (
            select(SemanticCatalogProposal)
            .where(SemanticCatalogProposal.tenant_id == tenant_id)
            .where(SemanticCatalogProposal.id == proposal_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[SemanticCatalogProposal]:
        stmt = (
            select(SemanticCatalogProposal)
            .where(SemanticCatalogProposal.tenant_id == tenant_id)
            .order_by(SemanticCatalogProposal.created_at.desc())
            .limit(limit)
        )
        if status is not None:
            stmt = stmt.where(SemanticCatalogProposal.status == status)
        return list((await self._session.execute(stmt)).scalars().all())

    async def add(self, proposal: SemanticCatalogProposal) -> SemanticCatalogProposal:
        self._session.add(proposal)
        await self._session.flush()
        return proposal


class SemanticCatalogVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def latest_for_term(
        self,
        tenant_id: UUID,
        term: str,
    ) -> SemanticCatalogVersion | None:
        stmt = (
            select(SemanticCatalogVersion)
            .where(SemanticCatalogVersion.tenant_id == tenant_id)
            .where(SemanticCatalogVersion.term == term)
            .where(SemanticCatalogVersion.review_status == "approved")
            .order_by(SemanticCatalogVersion.version.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_approved_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int = 1000,
    ) -> list[SemanticCatalogVersion]:
        stmt = (
            select(SemanticCatalogVersion)
            .where(SemanticCatalogVersion.tenant_id == tenant_id)
            .where(SemanticCatalogVersion.review_status == "approved")
            .order_by(
                SemanticCatalogVersion.term.asc(),
                SemanticCatalogVersion.version.desc(),
            )
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_for_term(
        self,
        tenant_id: UUID,
        term: str,
        *,
        limit: int = 100,
    ) -> list[SemanticCatalogVersion]:
        stmt = (
            select(SemanticCatalogVersion)
            .where(SemanticCatalogVersion.tenant_id == tenant_id)
            .where(SemanticCatalogVersion.term == term)
            .order_by(SemanticCatalogVersion.version.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_for_proposal(
        self,
        tenant_id: UUID,
        proposal_id: UUID,
        *,
        limit: int = 100,
    ) -> list[SemanticCatalogVersion]:
        stmt = (
            select(SemanticCatalogVersion)
            .where(SemanticCatalogVersion.tenant_id == tenant_id)
            .where(SemanticCatalogVersion.proposal_id == proposal_id)
            .order_by(SemanticCatalogVersion.version.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def add(self, version: SemanticCatalogVersion) -> SemanticCatalogVersion:
        self._session.add(version)
        await self._session.flush()
        return version
