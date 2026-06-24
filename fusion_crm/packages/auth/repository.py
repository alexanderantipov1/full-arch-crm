"""Auth repository — data access only. NO business logic.

Every per-tenant read filters by ``tenant_id`` via :func:`for_tenant`
(ENG-128). Sessions and API keys are issued in a tenant context, and the
credential record is owned by the tenant of its subject — every method
takes ``tenant_id`` so that a token issued for tenant A cannot be
resolved against tenant B's session table.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.db.tenant_scope import for_tenant

from .models import ApiKey, Credential, Session


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Credential ---

    async def find_active_credential(
        self,
        tenant_id: TenantId,
        subject_type: str,
        subject_id: UUID,
        credential_kind: str,
    ) -> Credential | None:
        stmt = (
            for_tenant(select(Credential), tenant_id, Credential)
            .where(Credential.subject_type == subject_type)
            .where(Credential.subject_id == subject_id)
            .where(Credential.credential_kind == credential_kind)
            .where(Credential.status == "active")
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_credential(self, credential: Credential) -> Credential:
        self._session.add(credential)
        await self._session.flush()
        return credential

    # --- Session ---

    async def get_session(
        self, tenant_id: TenantId, session_id: UUID
    ) -> Session | None:
        stmt = for_tenant(select(Session), tenant_id, Session).where(
            Session.id == session_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_session_by_token_hash(
        self, tenant_id: TenantId, token_hash: str
    ) -> Session | None:
        stmt = for_tenant(select(Session), tenant_id, Session).where(
            Session.token_hash == token_hash
        ).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_session(self, session_row: Session) -> Session:
        self._session.add(session_row)
        await self._session.flush()
        return session_row

    # --- ApiKey ---

    async def get_api_key(
        self, tenant_id: TenantId, api_key_id: UUID
    ) -> ApiKey | None:
        stmt = for_tenant(select(ApiKey), tenant_id, ApiKey).where(
            ApiKey.id == api_key_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_api_key_by_token_hash(
        self, tenant_id: TenantId, token_hash: str
    ) -> ApiKey | None:
        stmt = for_tenant(select(ApiKey), tenant_id, ApiKey).where(
            ApiKey.token_hash == token_hash
        ).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_api_key(self, api_key: ApiKey) -> ApiKey:
        self._session.add(api_key)
        await self._session.flush()
        return api_key
