"""Tenant repositories — data access only.

Repositories take an ``AsyncSession`` and return ORM entities. They do not
commit (the unit-of-work caller's responsibility). Cross-package callers
go through the service layer; nothing outside ``packages.tenant`` may
import this module.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import IntegrationCredential, Location, Setting, Tenant


class TenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Tenant ---
    async def get(self, tenant_id: UUID) -> Tenant | None:
        return await self._session.get(Tenant, tenant_id)

    async def get_by_slug(self, slug: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.slug == slug).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add(self, tenant: Tenant) -> Tenant:
        self._session.add(tenant)
        await self._session.flush()
        return tenant

    async def list_all(self) -> list[Tenant]:
        stmt = select(Tenant).order_by(Tenant.slug)
        return list((await self._session.execute(stmt)).scalars().all())

    # --- Settings ---
    async def get_setting(self, tenant_id: UUID, key: str) -> Setting | None:
        stmt = (
            select(Setting).where(Setting.tenant_id == tenant_id).where(Setting.key == key).limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_settings(self, tenant_id: UUID) -> list[Setting]:
        stmt = select(Setting).where(Setting.tenant_id == tenant_id).order_by(Setting.key)
        return list((await self._session.execute(stmt)).scalars().all())

    async def add_setting(self, setting: Setting) -> Setting:
        self._session.add(setting)
        await self._session.flush()
        return setting

    # --- Integration credentials ---
    async def get_credential(
        self, tenant_id: UUID, credential_id: UUID
    ) -> IntegrationCredential | None:
        stmt = (
            select(IntegrationCredential)
            .where(IntegrationCredential.tenant_id == tenant_id)
            .where(IntegrationCredential.id == credential_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_credentials(
        self,
        tenant_id: UUID,
        provider_kind: str | None = None,
        *,
        include_revoked: bool = False,
    ) -> list[IntegrationCredential]:
        stmt = select(IntegrationCredential).where(IntegrationCredential.tenant_id == tenant_id)
        if provider_kind is not None:
            stmt = stmt.where(IntegrationCredential.provider_kind == provider_kind)
        if not include_revoked:
            stmt = stmt.where(IntegrationCredential.status != "revoked")
        stmt = stmt.order_by(IntegrationCredential.created_at.desc())
        return list((await self._session.execute(stmt)).scalars().all())

    async def add_credential(self, credential: IntegrationCredential) -> IntegrationCredential:
        self._session.add(credential)
        await self._session.flush()
        return credential


class LocationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, location_id: UUID) -> Location | None:
        return await self._session.get(Location, location_id)

    async def find_by_name(self, tenant_id: UUID, name: str) -> Location | None:
        stmt = (
            select(Location)
            .where(Location.tenant_id == tenant_id)
            .where(Location.name == name)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_tenant(
        self, tenant_id: UUID, *, only_active: bool = False
    ) -> list[Location]:
        stmt = select(Location).where(Location.tenant_id == tenant_id)
        if only_active:
            stmt = stmt.where(Location.is_active.is_(True))
        stmt = stmt.order_by(Location.name)
        return list((await self._session.execute(stmt)).scalars().all())

    async def add(self, location: Location) -> Location:
        self._session.add(location)
        await self._session.flush()
        return location

    async def find_by_carestack_id(
        self, tenant_id: UUID, carestack_location_id: int
    ) -> Location | None:
        """Look up a location by ``external_ref->>'carestack_location_id'``.

        CareStack location ids are integers; we store them in JSONB as
        integers but compare via the ``->>`` text operator (the most
        index-friendly form). Returns ``None`` when no row matches.
        """
        stmt = (
            select(Location)
            .where(Location.tenant_id == tenant_id)
            .where(
                Location.external_ref["carestack_location_id"].astext == str(carestack_location_id)
            )
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
