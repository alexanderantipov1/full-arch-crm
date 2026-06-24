"""Storage contract for semantic catalog proposal review."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from packages.analytics.schemas import (
    CatalogProposalCreateIn,
    CatalogProposalStatus,
    CatalogProposalUpdateIn,
)
from packages.core.types import TenantId


@dataclass(frozen=True, slots=True)
class CatalogProposalRecord:
    """Storage-neutral proposal record consumed by the service layer."""

    id: UUID
    tenant_id: UUID
    raw_value: str
    source_system: str
    source_field: str
    suggested_term: str
    definition: str
    synonyms: list[str]
    confidence: float
    reason: str
    reviewer_note: str
    affected_questions: list[str]
    affected_read_models: list[str]
    status: CatalogProposalStatus
    source_type: str
    source_reference_id: str | None
    created_by_actor_id: UUID | None
    reviewed_by_actor_id: UUID | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CatalogProposalRepositoryProtocol(Protocol):
    """Repository contract expected from ENG-314 storage."""

    async def list(
        self,
        tenant_id: TenantId,
        *,
        status: CatalogProposalStatus | None = None,
        limit: int = 100,
    ) -> list[CatalogProposalRecord]:
        """Return tenant-scoped proposals."""

    async def get(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
    ) -> CatalogProposalRecord | None:
        """Return one tenant-scoped proposal."""

    async def create(
        self,
        tenant_id: TenantId,
        payload: CatalogProposalCreateIn,
        *,
        actor_id: UUID | None,
    ) -> CatalogProposalRecord:
        """Persist a proposal draft."""

    async def update(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
        payload: CatalogProposalUpdateIn,
    ) -> CatalogProposalRecord | None:
        """Persist editable proposal fields."""

    async def set_status(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
        *,
        status: CatalogProposalStatus,
        reviewer_note: str,
        reviewed_by_actor_id: UUID | None,
    ) -> CatalogProposalRecord | None:
        """Persist a human review transition."""


class InMemoryCatalogProposalRepository:
    """Contract stub until ENG-314 provides durable storage.

    This implementation is intentionally process-local. It exists so API and
    service contracts can be exercised without introducing migrations in
    ENG-315.
    """

    def __init__(
        self,
        seed: Iterable[CatalogProposalRecord] | None = None,
    ) -> None:
        self._items: dict[tuple[UUID, UUID], CatalogProposalRecord] = {}
        for item in seed or ():
            self._items[(item.tenant_id, item.id)] = item

    async def list(
        self,
        tenant_id: TenantId,
        *,
        status: CatalogProposalStatus | None = None,
        limit: int = 100,
    ) -> list[CatalogProposalRecord]:
        rows = [
            item
            for (item_tenant_id, _), item in self._items.items()
            if item_tenant_id == UUID(str(tenant_id))
            and (status is None or item.status == status)
        ]
        return sorted(rows, key=lambda row: row.updated_at, reverse=True)[:limit]

    async def get(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
    ) -> CatalogProposalRecord | None:
        return self._items.get((UUID(str(tenant_id)), proposal_id))

    async def create(
        self,
        tenant_id: TenantId,
        payload: CatalogProposalCreateIn,
        *,
        actor_id: UUID | None,
    ) -> CatalogProposalRecord:
        now = datetime.now(UTC)
        row = CatalogProposalRecord(
            id=uuid4(),
            tenant_id=UUID(str(tenant_id)),
            raw_value=payload.raw_value,
            source_system=payload.source_system,
            source_field=payload.source_field,
            suggested_term=payload.suggested_term,
            definition=payload.definition,
            synonyms=list(payload.synonyms),
            confidence=payload.confidence,
            reason=payload.reason,
            reviewer_note=payload.reviewer_note,
            affected_questions=list(payload.affected_questions),
            affected_read_models=list(payload.affected_read_models),
            status="proposed",
            source_type=payload.source_type,
            source_reference_id=payload.source_reference_id,
            created_by_actor_id=actor_id,
            reviewed_by_actor_id=None,
            reviewed_at=None,
            created_at=now,
            updated_at=now,
        )
        self._items[(row.tenant_id, row.id)] = row
        return row

    async def update(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
        payload: CatalogProposalUpdateIn,
    ) -> CatalogProposalRecord | None:
        row = await self.get(tenant_id, proposal_id)
        if row is None:
            return None
        changes = payload.model_dump(exclude_unset=True)
        updated = replace(row, **changes, updated_at=datetime.now(UTC))
        self._items[(updated.tenant_id, updated.id)] = updated
        return updated

    async def set_status(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
        *,
        status: CatalogProposalStatus,
        reviewer_note: str,
        reviewed_by_actor_id: UUID | None,
    ) -> CatalogProposalRecord | None:
        row = await self.get(tenant_id, proposal_id)
        if row is None:
            return None
        updated = replace(
            row,
            status=status,
            reviewer_note=reviewer_note,
            reviewed_by_actor_id=reviewed_by_actor_id,
            reviewed_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self._items[(updated.tenant_id, updated.id)] = updated
        return updated
