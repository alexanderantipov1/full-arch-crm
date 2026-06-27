"""Insight services — semantic catalog proposal and version storage."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.security import Principal, Role
from packages.core.types import TenantId

from .models import (
    CATALOG_PROPOSAL_STATUSES,
    CatalogProposalStatus,
    CatalogReviewStatus,
    SemanticCatalogProposal,
    SemanticCatalogVersion,
)
from .repository import (
    SemanticCatalogProposalRepository,
    SemanticCatalogVersionRepository,
)
from .schemas import (
    CatalogApprovalOut,
    CatalogProposalApprovalIn,
    CatalogProposalReviewIn,
    SemanticCatalogProposalIn,
    SemanticCatalogProposalOut,
    SemanticCatalogProposalUpdate,
    SemanticCatalogVersionOut,
)


class InsightCatalogService:
    """Public service surface for governed semantic catalog review."""

    def __init__(self, session: AsyncSession) -> None:
        self._proposal_repo = SemanticCatalogProposalRepository(session)
        self._version_repo = SemanticCatalogVersionRepository(session)

    async def create_proposal(
        self,
        tenant_id: TenantId,
        payload: SemanticCatalogProposalIn,
        *,
        principal: Principal,
    ) -> SemanticCatalogProposalOut:
        proposal = SemanticCatalogProposal(
            tenant_id=tenant_id,
            proposal_type=payload.proposal_type,
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
            affected_reports=list(payload.affected_reports),
            affected_dashboard_panels=list(payload.affected_dashboard_panels),
            affected_chat_answers=list(payload.affected_chat_answers),
            affected_agent_briefs=list(payload.affected_agent_briefs),
            source_references=list(payload.source_references),
            status=CatalogProposalStatus.PROPOSED.value,
            created_by_actor_id=principal.id,
        )
        await self._proposal_repo.add(proposal)
        return SemanticCatalogProposalOut.model_validate(proposal)

    async def list_proposals(
        self,
        tenant_id: TenantId,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[SemanticCatalogProposalOut]:
        if status is not None and status not in CATALOG_PROPOSAL_STATUSES:
            raise ValidationError(
                "unknown catalog proposal status",
                details={
                    "status": status,
                    "allowed": list(CATALOG_PROPOSAL_STATUSES),
                },
            )
        proposals = await self._proposal_repo.list_for_tenant(
            tenant_id,
            status=status,
            limit=limit,
        )
        return [SemanticCatalogProposalOut.model_validate(row) for row in proposals]

    async def get_proposal(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
    ) -> SemanticCatalogProposalOut:
        proposal = await self._get_proposal(tenant_id, proposal_id)
        return SemanticCatalogProposalOut.model_validate(proposal)

    async def update_proposal(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
        payload: SemanticCatalogProposalUpdate,
    ) -> SemanticCatalogProposalOut:
        proposal = await self._get_proposal(tenant_id, proposal_id)
        self._require_not_approved(proposal)

        for field_name in payload.model_fields_set:
            setattr(proposal, field_name, getattr(payload, field_name))
        return SemanticCatalogProposalOut.model_validate(proposal)

    async def approve_proposal(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
        payload: CatalogProposalApprovalIn,
        *,
        principal: Principal,
    ) -> CatalogApprovalOut:
        self._require_human_reviewer(principal)
        proposal = await self._get_proposal(tenant_id, proposal_id)
        self._require_not_approved(proposal)

        approved_at = datetime.now(UTC)
        term = payload.term or proposal.suggested_term
        definition = payload.definition or proposal.definition
        latest = await self._version_repo.latest_for_term(tenant_id, term)
        version_number = 1 if latest is None else latest.version + 1
        reason = payload.reason or proposal.reason

        version = SemanticCatalogVersion(
            tenant_id=tenant_id,
            term=term,
            version=version_number,
            review_status=CatalogReviewStatus.APPROVED.value,
            definition=definition,
            synonyms=list(
                proposal.synonyms if payload.synonyms is None else payload.synonyms
            ),
            allowed_data_sources=list(
                payload.allowed_data_sources
                if payload.allowed_data_sources is not None
                else [f"{proposal.source_system}.{proposal.source_field}"]
            ),
            data_classes=list(payload.data_classes or []),
            allowed_outputs=list(payload.allowed_outputs or []),
            canonical_fields=list(payload.canonical_fields or []),
            row_level_fields=list(payload.row_level_fields or []),
            aggregate_metrics=list(payload.aggregate_metrics or []),
            used_by=list(payload.used_by or []),
            source_references=list(
                proposal.source_references
                if payload.source_references is None
                else payload.source_references
            ),
            previous_version_id=None if latest is None else latest.id,
            proposal_id=proposal.id,
            previous_value=None if latest is None else _snapshot_version(latest),
            new_value={},
            reason=reason,
            affected_questions=list(
                proposal.affected_questions
                if payload.affected_questions is None
                else payload.affected_questions
            ),
            affected_read_models=list(
                proposal.affected_read_models
                if payload.affected_read_models is None
                else payload.affected_read_models
            ),
            affected_reports=list(
                proposal.affected_reports
                if payload.affected_reports is None
                else payload.affected_reports
            ),
            affected_dashboard_panels=list(
                proposal.affected_dashboard_panels
                if payload.affected_dashboard_panels is None
                else payload.affected_dashboard_panels
            ),
            affected_chat_answers=list(
                proposal.affected_chat_answers
                if payload.affected_chat_answers is None
                else payload.affected_chat_answers
            ),
            affected_agent_briefs=list(
                proposal.affected_agent_briefs
                if payload.affected_agent_briefs is None
                else payload.affected_agent_briefs
            ),
            approved_by_actor_id=principal.id,
            approved_at=approved_at,
        )
        version.new_value = _snapshot_version(version)
        await self._version_repo.add(version)

        proposal.status = CatalogProposalStatus.APPROVED.value
        proposal.reviewer_note = payload.reviewer_note
        proposal.reviewed_by_actor_id = principal.id
        proposal.reviewed_at = approved_at
        proposal.approved_version_id = version.id

        return CatalogApprovalOut(
            proposal=SemanticCatalogProposalOut.model_validate(proposal),
            version=SemanticCatalogVersionOut.model_validate(version),
        )

    async def reject_proposal(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
        payload: CatalogProposalReviewIn,
        *,
        principal: Principal,
    ) -> SemanticCatalogProposalOut:
        self._require_human_reviewer(principal)
        proposal = await self._get_proposal(tenant_id, proposal_id)
        self._require_not_approved(proposal)
        proposal.status = CatalogProposalStatus.REJECTED.value
        proposal.reviewer_note = payload.reviewer_note
        proposal.reviewed_by_actor_id = principal.id
        proposal.reviewed_at = datetime.now(UTC)
        return SemanticCatalogProposalOut.model_validate(proposal)

    async def mark_proposal_unresolved(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
        payload: CatalogProposalReviewIn,
        *,
        principal: Principal,
    ) -> SemanticCatalogProposalOut:
        self._require_human_reviewer(principal)
        proposal = await self._get_proposal(tenant_id, proposal_id)
        self._require_not_approved(proposal)
        proposal.status = CatalogProposalStatus.UNRESOLVED.value
        proposal.reviewer_note = payload.reviewer_note
        proposal.reviewed_by_actor_id = principal.id
        proposal.reviewed_at = datetime.now(UTC)
        return SemanticCatalogProposalOut.model_validate(proposal)

    async def mark_proposal_proposed(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
        payload: CatalogProposalReviewIn,
        *,
        principal: Principal,
    ) -> SemanticCatalogProposalOut:
        self._require_human_reviewer(principal)
        proposal = await self._get_proposal(tenant_id, proposal_id)
        self._require_not_approved(proposal)
        proposal.status = CatalogProposalStatus.PROPOSED.value
        proposal.reviewer_note = payload.reviewer_note
        proposal.reviewed_by_actor_id = principal.id
        proposal.reviewed_at = datetime.now(UTC)
        return SemanticCatalogProposalOut.model_validate(proposal)

    async def list_approved_catalog_entries(
        self,
        tenant_id: TenantId,
        *,
        limit: int = 1000,
    ) -> list[SemanticCatalogVersionOut]:
        versions = await self._version_repo.list_approved_for_tenant(
            tenant_id,
            limit=limit,
        )
        latest_by_term: dict[str, SemanticCatalogVersion] = {}
        for version in versions:
            latest_by_term.setdefault(version.term, version)
        return [
            SemanticCatalogVersionOut.model_validate(version)
            for version in latest_by_term.values()
        ]

    async def list_versions_for_term(
        self,
        tenant_id: TenantId,
        term: str,
        *,
        limit: int = 100,
    ) -> list[SemanticCatalogVersionOut]:
        versions = await self._version_repo.list_for_term(
            tenant_id,
            term,
            limit=limit,
        )
        return [SemanticCatalogVersionOut.model_validate(row) for row in versions]

    async def list_versions_for_proposal(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
        *,
        limit: int = 100,
    ) -> list[SemanticCatalogVersionOut]:
        versions = await self._version_repo.list_for_proposal(
            tenant_id,
            proposal_id,
            limit=limit,
        )
        return [SemanticCatalogVersionOut.model_validate(row) for row in versions]

    async def _get_proposal(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
    ) -> SemanticCatalogProposal:
        proposal = await self._proposal_repo.get_for_tenant(tenant_id, proposal_id)
        if proposal is None:
            raise NotFoundError(
                "catalog proposal not found",
                details={
                    "tenant_id": str(tenant_id),
                    "proposal_id": str(proposal_id),
                },
            )
        return proposal

    @staticmethod
    def _require_not_approved(proposal: SemanticCatalogProposal) -> None:
        if proposal.status == CatalogProposalStatus.APPROVED.value:
            raise ValidationError(
                "approved catalog proposals cannot be changed",
                details={"proposal_id": str(proposal.id)},
            )

    @staticmethod
    def _require_human_reviewer(principal: Principal) -> None:
        human_roles = {Role.STAFF, Role.CLINICIAN, Role.ADMIN}
        if principal.has_role(Role.SYSTEM) and not principal.roles.intersection(human_roles):
            raise ValidationError(
                "system-only principals cannot review catalog proposals",
                details={"principal_id": str(principal.id) if principal.id else None},
            )


def _snapshot_version(version: SemanticCatalogVersion) -> dict[str, Any]:
    return {
        "term": version.term,
        "version": version.version,
        "review_status": version.review_status,
        "definition": version.definition,
        "synonyms": list(version.synonyms),
        "allowed_data_sources": list(version.allowed_data_sources),
        "data_classes": list(version.data_classes),
        "allowed_outputs": list(version.allowed_outputs),
        "canonical_fields": list(version.canonical_fields),
        "row_level_fields": list(version.row_level_fields),
        "aggregate_metrics": list(version.aggregate_metrics),
        "used_by": list(version.used_by),
        "source_references": list(version.source_references),
    }
