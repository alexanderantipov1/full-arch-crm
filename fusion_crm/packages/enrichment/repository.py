"""Enrichment repository — data access only.

Takes an ``AsyncSession`` and returns ORM entities. Never commits and never
rolls back (the unit-of-work caller's responsibility). Cross-package callers
go through :class:`packages.enrichment.service.EnrichmentService`; nothing
outside ``packages.enrichment`` may import this module.

Every read is tenant-scoped via :func:`packages.db.tenant_scope.for_tenant`
so a stray UUID cannot leak rows across tenants.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.tenant_scope import for_tenant

from .models import RecordAnnotation


class RecordAnnotationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, annotation: RecordAnnotation) -> RecordAnnotation:
        self._session.add(annotation)
        await self._session.flush()
        return annotation

    async def list_for_subject(
        self,
        tenant_id: UUID,
        subject_type: str,
        subject_id: UUID,
    ) -> list[RecordAnnotation]:
        """Return all annotations for a subject, newest first.

        Append-friendly history: a single ``key`` may appear multiple times.
        Ordering is ``created_at`` descending so the freshest row per key is
        the first one a caller encounters.
        """
        stmt = (
            for_tenant(select(RecordAnnotation), tenant_id, RecordAnnotation)
            .where(RecordAnnotation.subject_type == subject_type)
            .where(RecordAnnotation.subject_id == subject_id)
            .order_by(RecordAnnotation.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())
