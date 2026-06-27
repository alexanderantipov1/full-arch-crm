"""Integration tests for analytics catalog review backed by insight storage."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.analytics.schemas import (
    CatalogDraftPatchIn,
    CatalogProposalCreateIn,
    CatalogProposalReviewIn,
)
from packages.analytics.service import AnalyticsCatalogReviewService
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.insight.models import SemanticCatalogProposal, SemanticCatalogVersion
from packages.insight.service import InsightCatalogService


def _principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="catalog-review@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.STAFF}),
    )


def _payload(**overrides: Any) -> CatalogProposalCreateIn:
    data: dict[str, object] = {
        "raw_value": "IG Campaign June",
        "source_system": "salesforce",
        "source_field": "LeadSource",
        "suggested_term": "paid_social/facebook",
        "definition": "Paid social lead from Meta campaigns.",
        "synonyms": ["Facebook", "Meta"],
        "confidence": 0.91,
        "reason": "Observed source pattern in lead data.",
        "affected_questions": ["Q16"],
        "affected_read_models": ["paid_leads"],
        "source_type": "agent",
        "source_reference_id": "profile-run-1",
    }
    data.update(overrides)
    return CatalogProposalCreateIn.model_validate(data)


def _set_persisted_fields(row: Any) -> Any:
    row.id = row.id or uuid.uuid4()
    row.created_at = row.created_at or datetime(2026, 6, 2, 9, 0, tzinfo=UTC)
    row.updated_at = row.updated_at or datetime(2026, 6, 2, 9, 0, tzinfo=UTC)
    return row


class _ProposalRepo:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, SemanticCatalogProposal] = {}

    async def add(self, proposal: SemanticCatalogProposal) -> SemanticCatalogProposal:
        _set_persisted_fields(proposal)
        self.rows[proposal.id] = proposal
        return proposal

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        proposal_id: uuid.UUID,
    ) -> SemanticCatalogProposal | None:
        proposal = self.rows.get(proposal_id)
        if proposal is None or proposal.tenant_id != tenant_id:
            return None
        return proposal

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[SemanticCatalogProposal]:
        rows = [row for row in self.rows.values() if row.tenant_id == tenant_id]
        if status is not None:
            rows = [row for row in rows if row.status == status]
        return rows[:limit]


class _VersionRepo:
    def __init__(self) -> None:
        self.rows: list[SemanticCatalogVersion] = []

    async def latest_for_term(
        self,
        tenant_id: uuid.UUID,
        term: str,
    ) -> SemanticCatalogVersion | None:
        versions = [
            row for row in self.rows if row.tenant_id == tenant_id and row.term == term
        ]
        if not versions:
            return None
        return max(versions, key=lambda row: row.version)

    async def list_approved_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        limit: int = 1000,
    ) -> list[SemanticCatalogVersion]:
        rows = [
            row
            for row in self.rows
            if row.tenant_id == tenant_id and row.review_status == "approved"
        ]
        return sorted(rows, key=lambda row: (row.term, -row.version))[:limit]

    async def list_for_term(
        self,
        tenant_id: uuid.UUID,
        term: str,
        *,
        limit: int = 100,
    ) -> list[SemanticCatalogVersion]:
        rows = [
            row
            for row in self.rows
            if row.tenant_id == tenant_id and row.term == term
        ]
        return sorted(rows, key=lambda row: -row.version)[:limit]

    async def list_for_proposal(
        self,
        tenant_id: uuid.UUID,
        proposal_id: uuid.UUID,
        *,
        limit: int = 100,
    ) -> list[SemanticCatalogVersion]:
        rows = [
            row
            for row in self.rows
            if row.tenant_id == tenant_id and row.proposal_id == proposal_id
        ]
        return sorted(rows, key=lambda row: -row.version)[:limit]

    async def add(self, version: SemanticCatalogVersion) -> SemanticCatalogVersion:
        _set_persisted_fields(version)
        self.rows.append(version)
        return version


def _service(audit: Any | None = None) -> AnalyticsCatalogReviewService:
    insight = InsightCatalogService(session=None)  # type: ignore[arg-type]
    insight._proposal_repo = _ProposalRepo()  # type: ignore[assignment]
    insight._version_repo = _VersionRepo()  # type: ignore[assignment]
    return AnalyticsCatalogReviewService(audit=audit, insight=insight)


@pytest.mark.asyncio
async def test_catalog_review_uses_insight_storage_for_approved_versions() -> None:
    tenant_id = TenantId(uuid.uuid4())
    principal = _principal(tenant_id)
    audit = MagicMock()
    audit.log_catalog_review_action = AsyncMock()
    audit.log_catalog_version_change = AsyncMock()
    service = _service(audit=audit)

    created = await service.create_proposal(tenant_id, _payload(), principal)
    listed = await service.list_proposals(tenant_id)
    assert [item.id for item in listed] == [created.id]
    assert listed[0].source_type == "agent"
    assert listed[0].source_reference_id == "profile-run-1"

    reviewed = await service.review_proposal(
        tenant_id,
        created.id,
        CatalogProposalReviewIn(
            status="approved",
            reason="Marketing owner approved source mapping.",
            reviewer_note="Approved for paid leads.",
        ),
        principal,
    )

    assert reviewed.proposal.status == "approved"
    assert reviewed.catalog_version_id is not None

    patch = await service.draft_catalog_patch(tenant_id, CatalogDraftPatchIn())
    assert patch.proposal_ids == [created.id]
    assert patch.patch[0]["term"] == "paid_social/facebook"

    proposal_history = await service.proposal_review_history(tenant_id, created.id)
    assert [event.action for event in proposal_history.items] == [
        "created",
        "approved",
    ]
    assert proposal_history.items[1].catalog_version_id == reviewed.catalog_version_id

    version_history = await service.term_version_history(
        tenant_id,
        "paid_social/facebook",
    )
    assert [entry.version for entry in version_history.items] == [1]
    assert version_history.items[0].proposal_id == created.id

    audit.log_catalog_review_action.assert_awaited_once()
    audit.log_catalog_version_change.assert_awaited_once()
    version_change_kwargs = audit.log_catalog_version_change.await_args.kwargs
    assert version_change_kwargs["catalog_version_id"] == reviewed.catalog_version_id
    assert version_change_kwargs["metric_id"] == "paid_social/facebook"
