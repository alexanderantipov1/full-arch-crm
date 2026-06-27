"""Service-level tests for semantic catalog proposals and versions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from packages.core.exceptions import ValidationError
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.insight.models import (
    CatalogProposalStatus,
    SemanticCatalogProposal,
    SemanticCatalogVersion,
)
from packages.insight.schemas import (
    CatalogProposalApprovalIn,
    CatalogProposalReviewIn,
    SemanticCatalogProposalIn,
    SemanticCatalogProposalUpdate,
)
from packages.insight.service import InsightCatalogService


def _principal(*, roles: frozenset[Role] = frozenset({Role.STAFF})) -> Principal:
    return Principal(id=uuid.uuid4(), email="reviewer@example.com", roles=roles)


def _proposal_payload(**overrides: Any) -> SemanticCatalogProposalIn:
    payload = {
        "raw_value": "IG Campaign June",
        "source_system": "salesforce",
        "source_field": "LeadSource",
        "suggested_term": "paid_social/facebook",
        "definition": "Paid social lead from Meta campaigns.",
        "synonyms": ["Facebook", "Meta", "Instagram"],
        "confidence": 0.91,
        "reason": "Observed source pattern in lead data.",
        "affected_questions": ["Q16", "Q19"],
        "affected_read_models": ["paid_leads", "lead_conversion"],
    }
    payload.update(overrides)
    return SemanticCatalogProposalIn(**payload)


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


def _make_service() -> tuple[InsightCatalogService, _ProposalRepo, _VersionRepo]:
    service = InsightCatalogService(session=None)  # type: ignore[arg-type]
    proposal_repo = _ProposalRepo()
    version_repo = _VersionRepo()
    service._proposal_repo = proposal_repo  # type: ignore[assignment]
    service._version_repo = version_repo  # type: ignore[assignment]
    return service, proposal_repo, version_repo


@pytest.mark.asyncio
async def test_create_update_and_list_proposals() -> None:
    service, _, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())

    created = await service.create_proposal(
        tenant_id,
        _proposal_payload(),
        principal=_principal(),
    )
    assert created.status == CatalogProposalStatus.PROPOSED.value
    assert created.suggested_term == "paid_social/facebook"

    updated = await service.update_proposal(
        tenant_id,
        created.id,
        SemanticCatalogProposalUpdate(
            definition="Paid social lead from Meta, Facebook, or Instagram.",
            reviewer_note="Ready for marketing owner review.",
        ),
    )
    assert updated.definition.endswith("Instagram.")
    assert updated.reviewer_note == "Ready for marketing owner review."

    proposals = await service.list_proposals(tenant_id, status="proposed")
    assert [proposal.id for proposal in proposals] == [created.id]


@pytest.mark.asyncio
async def test_reject_and_unresolved_do_not_create_versions() -> None:
    service, _, version_repo = _make_service()
    tenant_id = TenantId(uuid.uuid4())

    rejected = await service.create_proposal(
        tenant_id,
        _proposal_payload(raw_value="Unknown Source", suggested_term="unknown"),
        principal=_principal(),
    )
    rejected_out = await service.reject_proposal(
        tenant_id,
        rejected.id,
        CatalogProposalReviewIn(reviewer_note="Not enough evidence."),
        principal=_principal(),
    )
    assert rejected_out.status == CatalogProposalStatus.REJECTED.value

    unresolved = await service.create_proposal(
        tenant_id,
        _proposal_payload(raw_value="New paid code", suggested_term="paid_social/new"),
        principal=_principal(),
    )
    unresolved_out = await service.mark_proposal_unresolved(
        tenant_id,
        unresolved.id,
        CatalogProposalReviewIn(reviewer_note="Needs Linear follow-up."),
        principal=_principal(),
    )
    assert unresolved_out.status == CatalogProposalStatus.UNRESOLVED.value
    assert version_repo.rows == []


@pytest.mark.asyncio
async def test_approve_proposal_creates_version_and_excludes_unreviewed_truth() -> None:
    service, _, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    reviewer = _principal()

    approved = await service.create_proposal(
        tenant_id,
        _proposal_payload(),
        principal=_principal(),
    )
    await service.create_proposal(
        tenant_id,
        _proposal_payload(raw_value="TikTok Ads", suggested_term="paid_social/tiktok"),
        principal=_principal(),
    )

    result = await service.approve_proposal(
        tenant_id,
        approved.id,
        CatalogProposalApprovalIn(
            data_classes=["ops", "integration_metadata"],
            allowed_outputs=["aggregate", "row_level"],
            used_by=["paid_leads", "lead_conversion"],
            reviewer_note="Approved by marketing.",
        ),
        principal=reviewer,
    )

    assert result.proposal.status == CatalogProposalStatus.APPROVED.value
    assert result.proposal.approved_version_id == result.version.id
    assert result.version.version == 1
    assert result.version.previous_value is None
    assert result.version.new_value["term"] == "paid_social/facebook"
    assert result.version.reason == "Observed source pattern in lead data."

    approved_truth = await service.list_approved_catalog_entries(tenant_id)
    assert [entry.term for entry in approved_truth] == ["paid_social/facebook"]


@pytest.mark.asyncio
async def test_approving_existing_term_creates_next_immutable_version() -> None:
    service, _, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())

    first = await service.create_proposal(
        tenant_id,
        _proposal_payload(),
        principal=_principal(),
    )
    first_approval = await service.approve_proposal(
        tenant_id,
        first.id,
        CatalogProposalApprovalIn(data_classes=["ops"]),
        principal=_principal(),
    )

    second = await service.create_proposal(
        tenant_id,
        _proposal_payload(
            raw_value="Meta Lead Form",
            definition="Paid social lead from Meta lead forms.",
            synonyms=["Meta Lead Form", "Facebook Lead Form"],
        ),
        principal=_principal(),
    )
    second_approval = await service.approve_proposal(
        tenant_id,
        second.id,
        CatalogProposalApprovalIn(reason="Expanded approved source values."),
        principal=_principal(),
    )

    assert first_approval.version.version == 1
    assert second_approval.version.version == 2
    assert second_approval.version.previous_version_id == first_approval.version.id
    assert second_approval.version.previous_value is not None
    assert second_approval.version.previous_value["definition"] == (
        "Paid social lead from Meta campaigns."
    )
    assert first_approval.version.definition == "Paid social lead from Meta campaigns."

    history = await service.list_versions_for_term(
        tenant_id,
        "paid_social/facebook",
    )
    assert [entry.version for entry in history] == [2, 1]

    proposal_history = await service.list_versions_for_proposal(
        tenant_id,
        second.id,
    )
    assert [entry.id for entry in proposal_history] == [second_approval.version.id]


@pytest.mark.asyncio
async def test_approved_proposal_cannot_be_changed_or_reviewed_again() -> None:
    service, _, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    proposal = await service.create_proposal(
        tenant_id,
        _proposal_payload(),
        principal=_principal(),
    )
    await service.approve_proposal(
        tenant_id,
        proposal.id,
        CatalogProposalApprovalIn(),
        principal=_principal(),
    )

    with pytest.raises(ValidationError):
        await service.update_proposal(
            tenant_id,
            proposal.id,
            SemanticCatalogProposalUpdate(definition="Changed after approval."),
        )
    with pytest.raises(ValidationError):
        await service.reject_proposal(
            tenant_id,
            proposal.id,
            CatalogProposalReviewIn(reviewer_note="Second review"),
            principal=_principal(),
        )


@pytest.mark.asyncio
async def test_system_only_principal_cannot_approve() -> None:
    service, _, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    proposal = await service.create_proposal(
        tenant_id,
        _proposal_payload(),
        principal=_principal(roles=frozenset({Role.SYSTEM})),
    )

    with pytest.raises(ValidationError):
        await service.approve_proposal(
            tenant_id,
            proposal.id,
            CatalogProposalApprovalIn(),
            principal=_principal(roles=frozenset({Role.SYSTEM})),
        )
