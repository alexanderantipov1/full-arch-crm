"""PHI repository — data access only.

This is internal to the phi package. All callers MUST go through ``PhiService``,
which performs authorisation and audit logging.

Every per-tenant read filters by ``tenant_id`` via :func:`for_tenant`
(ENG-128). The ``tenant_id`` first-arg pattern is identical to the other
domains so the auto-discovered cross-tenant isolation sweep
(``tests/integration/test_tenant_isolation.py``) treats every method
uniformly.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.db.tenant_scope import for_tenant

from .models import Consultation, PatientProfile


class PhiRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_profile(
        self, tenant_id: TenantId, person_uid: UUID
    ) -> PatientProfile | None:
        stmt = (
            for_tenant(select(PatientProfile), tenant_id, PatientProfile)
            .where(PatientProfile.person_uid == person_uid)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_profile(self, profile: PatientProfile) -> PatientProfile:
        self._session.add(profile)
        await self._session.flush()
        return profile

    async def recent_consultations(
        self, tenant_id: TenantId, person_uid: UUID, limit: int = 10
    ) -> list[Consultation]:
        stmt = (
            for_tenant(select(Consultation), tenant_id, Consultation)
            .where(Consultation.person_uid == person_uid)
            .order_by(Consultation.occurred_at.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_consultations_between(
        self, tenant_id: TenantId, start: datetime, end: datetime
    ) -> int:
        stmt = (
            for_tenant(
                select(func.count()).select_from(Consultation),
                tenant_id,
                Consultation,
            )
            .where(Consultation.occurred_at >= start)
            .where(Consultation.occurred_at < end)
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def person_uids_with_consultation(
        self, tenant_id: TenantId, person_uids: list[UUID]
    ) -> set[UUID]:
        if not person_uids:
            return set()
        stmt = (
            for_tenant(
                select(Consultation.person_uid).distinct(),
                tenant_id,
                Consultation,
            )
            .where(Consultation.person_uid.in_(person_uids))
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return set(rows)
