"""Audit repository — append-only inserts.

The audit log is append-only: there is no per-tenant read API at the
repository layer today (forensic queries land with M8). The one write
method (:meth:`add`) accepts a fully-built :class:`AccessLog` row whose
``tenant_id`` was set by the calling service from
``Principal.tenant_id`` — no per-method ``tenant_id`` argument is needed
because the row itself carries it.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from .models import AccessLog


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: AccessLog) -> AccessLog:
        self._session.add(entry)
        await self._session.flush()
        return entry
