"""Integrations repository — data access only. NO business logic.

Repositories take ``AsyncSession`` and return ORM entities. They never commit
(unit-of-work caller is the boundary).

Every per-tenant read filters by ``tenant_id`` via :func:`for_tenant`
(ENG-128). The child tables (``object_mapping``, ``sync_run``,
``cdc_cursor``, ``external_entity``) FK to ``integration_account.id`` and
also carry their own ``tenant_id`` column — the explicit filter is defence
in depth and matches the cross-tenant isolation sweep contract.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.db.tenant_scope import for_tenant

from .models import (
    CDCCursor,
    ExternalEntity,
    IntegrationAccount,
    ObjectMapping,
    SyncRun,
)


class IntegrationsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- IntegrationAccount ---

    async def get_account(
        self, tenant_id: TenantId, account_id: UUID
    ) -> IntegrationAccount | None:
        stmt = for_tenant(
            select(IntegrationAccount), tenant_id, IntegrationAccount
        ).where(IntegrationAccount.id == account_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_account(
        self,
        tenant_id: TenantId,
        provider: str,
        company_uid: UUID,
    ) -> IntegrationAccount | None:
        stmt = (
            for_tenant(select(IntegrationAccount), tenant_id, IntegrationAccount)
            .where(IntegrationAccount.provider == provider)
            .where(IntegrationAccount.company_uid == company_uid)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_account(self, account: IntegrationAccount) -> IntegrationAccount:
        self._session.add(account)
        await self._session.flush()
        return account

    # --- ObjectMapping ---

    async def find_mapping(
        self,
        tenant_id: TenantId,
        account_id: UUID,
        sf_object: str,
    ) -> ObjectMapping | None:
        stmt = (
            for_tenant(select(ObjectMapping), tenant_id, ObjectMapping)
            .where(ObjectMapping.account_id == account_id)
            .where(ObjectMapping.sf_object == sf_object)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_mappings(
        self, tenant_id: TenantId, account_id: UUID
    ) -> list[ObjectMapping]:
        stmt = (
            for_tenant(select(ObjectMapping), tenant_id, ObjectMapping)
            .where(ObjectMapping.account_id == account_id)
            .order_by(ObjectMapping.sf_object)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def add_mapping(self, mapping: ObjectMapping) -> ObjectMapping:
        self._session.add(mapping)
        await self._session.flush()
        return mapping

    # --- SyncRun ---

    async def get_sync_run(
        self, tenant_id: TenantId, sync_run_id: UUID
    ) -> SyncRun | None:
        stmt = for_tenant(select(SyncRun), tenant_id, SyncRun).where(
            SyncRun.id == sync_run_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_sync_run(self, sync_run: SyncRun) -> SyncRun:
        self._session.add(sync_run)
        await self._session.flush()
        return sync_run

    async def list_recent_runs(
        self,
        tenant_id: TenantId,
        account_id: UUID,
        limit: int = 20,
    ) -> list[SyncRun]:
        stmt = (
            for_tenant(select(SyncRun), tenant_id, SyncRun)
            .where(SyncRun.account_id == account_id)
            .order_by(SyncRun.started_at.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_latest_runs_for_tenant(
        self,
        tenant_id: TenantId,
        *,
        provider: str | None = None,
        limit: int = 20,
    ) -> list[tuple[SyncRun, str]]:
        """Return latest sync runs with provider labels for dashboard health."""
        stmt = (
            for_tenant(select(SyncRun, IntegrationAccount.provider), tenant_id, SyncRun)
            .join(IntegrationAccount, IntegrationAccount.id == SyncRun.account_id)
            .where(IntegrationAccount.tenant_id == tenant_id)
            .order_by(SyncRun.started_at.desc())
            .limit(limit)
        )
        if provider is not None:
            stmt = stmt.where(IntegrationAccount.provider == provider)
        rows = (await self._session.execute(stmt)).all()
        return [(run, str(provider)) for run, provider in rows]

    # --- CDCCursor ---

    async def find_cursor(
        self,
        tenant_id: TenantId,
        account_id: UUID,
        channel: str,
    ) -> CDCCursor | None:
        stmt = (
            for_tenant(select(CDCCursor), tenant_id, CDCCursor)
            .where(CDCCursor.account_id == account_id)
            .where(CDCCursor.channel == channel)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_cursor(self, cursor: CDCCursor) -> CDCCursor:
        self._session.add(cursor)
        await self._session.flush()
        return cursor

    # --- ExternalEntity ---

    async def find_external_entity(
        self,
        tenant_id: TenantId,
        account_id: UUID,
        object_type: str,
        external_id: str,
    ) -> ExternalEntity | None:
        stmt = (
            for_tenant(select(ExternalEntity), tenant_id, ExternalEntity)
            .where(ExternalEntity.account_id == account_id)
            .where(ExternalEntity.object_type == object_type)
            .where(ExternalEntity.external_id == external_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_external_entity(self, entity: ExternalEntity) -> ExternalEntity:
        self._session.add(entity)
        await self._session.flush()
        return entity
