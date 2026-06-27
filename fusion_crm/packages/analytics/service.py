"""Service layer for semantic catalog proposal review contracts."""

from __future__ import annotations

from uuid import UUID

from packages.analytics.repository import (
    CatalogProposalRecord,
    CatalogProposalRepositoryProtocol,
    InMemoryCatalogProposalRepository,
)
from packages.analytics.schemas import (
    CatalogDraftPatchIn,
    CatalogDraftPatchOut,
    CatalogProposalCreateIn,
    CatalogProposalHistoryEventOut,
    CatalogProposalHistoryOut,
    CatalogProposalImpactOut,
    CatalogProposalImpactPreviewOut,
    CatalogProposalIngestionOut,
    CatalogProposalIngestionSkippedOut,
    CatalogProposalOut,
    CatalogProposalReviewIn,
    CatalogProposalReviewOut,
    CatalogProposalStatus,
    CatalogProposalUpdateIn,
    CatalogVersionHistoryEntryOut,
    CatalogVersionHistoryOut,
)
from packages.audit.service import AuditService, CatalogReviewAction
from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.data_intelligence.schemas import (
    PersonJourneyProposalCandidateOut,
    PersonJourneyRegistryProposalOut,
)
from packages.insight.schemas import (
    CatalogProposalApprovalIn as InsightCatalogProposalApprovalIn,
)
from packages.insight.schemas import (
    CatalogProposalReviewIn as InsightCatalogProposalReviewIn,
)
from packages.insight.schemas import (
    SemanticCatalogProposalIn,
    SemanticCatalogProposalOut,
    SemanticCatalogProposalUpdate,
    SemanticCatalogVersionOut,
)
from packages.insight.service import InsightCatalogService

_OPEN_REVIEW_STATUSES: set[CatalogProposalStatus] = {"proposed", "unresolved"}
_FINAL_REVIEW_STATUSES: set[CatalogProposalStatus] = {"approved", "rejected"}
_REVIEW_AUDIT_ACTION: dict[CatalogProposalStatus, CatalogReviewAction] = {
    "approved": "approve",
    "rejected": "reject",
    "unresolved": "unresolved",
    "proposed": "edit",
}


class AnalyticsCatalogReviewService:
    """Human-review service for semantic catalog proposal contracts."""

    def __init__(
        self,
        repository: CatalogProposalRepositoryProtocol | None = None,
        audit: AuditService | None = None,
        insight: InsightCatalogService | None = None,
    ) -> None:
        self._repo = repository or InMemoryCatalogProposalRepository()
        self._audit = audit
        self._insight = insight

    async def list_proposals(
        self,
        tenant_id: TenantId,
        *,
        status: CatalogProposalStatus | None = None,
        limit: int = 100,
    ) -> list[CatalogProposalOut]:
        rows = await self._list_records(tenant_id, status=status, limit=limit)
        return [self._to_out(row) for row in rows]

    async def create_proposal(
        self,
        tenant_id: TenantId,
        payload: CatalogProposalCreateIn,
        principal: Principal,
    ) -> CatalogProposalOut:
        self._assert_non_phi_source(payload.source_system, payload.source_field)
        row = await self._create_record(tenant_id, payload, principal)
        return self._to_out(row)

    async def ingest_person_journey_registry_proposals(
        self,
        tenant_id: TenantId,
        projection: PersonJourneyRegistryProposalOut,
        principal: Principal,
    ) -> CatalogProposalIngestionOut:
        """Persist eligible DIA person-journey drafts as review proposals."""
        created: list[CatalogProposalOut] = []
        skipped: list[CatalogProposalIngestionSkippedOut] = []

        for candidate in projection.candidates:
            if not candidate.can_submit_for_review or candidate.proposal is None:
                skipped.append(_skipped_person_journey_candidate(candidate))
                continue
            payload = CatalogProposalCreateIn.model_validate(
                candidate.proposal.model_dump()
            )
            created.append(await self.create_proposal(tenant_id, payload, principal))

        return CatalogProposalIngestionOut(
            source="data_intelligence_person_journey_proposals",
            created_count=len(created),
            skipped_count=len(skipped),
            created=created,
            skipped=skipped,
            warnings=[
                "Ingested proposals remain review-only until a human reviewer approves them.",
                "Skipped entries were not persisted and cannot become approved catalog truth through ingestion.",
                "Manager answers, charts, reports, and exports must still wait for approved catalog versions and read-model/query binding.",
            ],
        )

    async def update_proposal(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
        payload: CatalogProposalUpdateIn,
        principal: Principal | None = None,
    ) -> CatalogProposalOut:
        current = await self._require_open_proposal(tenant_id, proposal_id)
        next_source_system = payload.source_system or current.source_system
        next_source_field = payload.source_field or current.source_field
        self._assert_non_phi_source(next_source_system, next_source_field)
        row = await self._update_record(tenant_id, proposal_id, payload)
        if row is None:
            raise NotFoundError(
                "catalog proposal not found",
                details={"proposal_id": str(proposal_id)},
            )
        if principal is not None:
            await self._record_review_audit(
                principal=principal,
                review_action="edit",
                proposal=row,
                reason=payload.reason or "catalog_proposal_edit",
                changed_fields=payload.model_fields_set,
            )
        return self._to_out(row)

    async def preview_impact(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
    ) -> CatalogProposalImpactPreviewOut:
        proposal = await self._require_proposal(tenant_id, proposal_id)
        impact = self._impact_for(proposal)
        blockers = self._approval_blockers(proposal)
        return CatalogProposalImpactPreviewOut(
            proposal_id=proposal.id,
            impact=impact,
            can_approve=not blockers,
            blockers=blockers,
        )

    async def review_proposal(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
        payload: CatalogProposalReviewIn,
        principal: Principal,
    ) -> CatalogProposalReviewOut:
        proposal = await self._require_open_proposal(tenant_id, proposal_id)
        self._validate_transition(proposal.status, payload.status)
        if payload.status == "approved":
            if principal.has_role(Role.SYSTEM):
                raise ValidationError(
                    "catalog proposals require human approval",
                    details={"proposal_id": str(proposal_id)},
                )
            blockers = self._approval_blockers(proposal)
            if blockers:
                raise ValidationError(
                    "catalog proposal cannot be approved",
                    details={
                        "proposal_id": str(proposal_id),
                        "blockers": blockers,
                    },
                )
        row, catalog_version_id, previous_catalog_version_id = await self._review_record(
            tenant_id,
            proposal_id,
            payload,
            principal,
        )
        if row is None:
            raise NotFoundError(
                "catalog proposal not found",
                details={"proposal_id": str(proposal_id)},
            )
        await self._record_review_audit(
            principal=principal,
            review_action=_REVIEW_AUDIT_ACTION[payload.status],
            proposal=row,
            reason=payload.reason,
            changed_fields={"status", "reviewer_note"},
            catalog_version_id=catalog_version_id,
            previous_catalog_version_id=previous_catalog_version_id,
        )
        if catalog_version_id is not None:
            await self._record_catalog_version_change_audit(
                principal=principal,
                proposal=row,
                reason=payload.reason,
                catalog_version_id=catalog_version_id,
                previous_catalog_version_id=previous_catalog_version_id,
            )
        return CatalogProposalReviewOut(
            proposal=self._to_out(row),
            impact=self._impact_for(row),
            catalog_version_id=catalog_version_id,
        )

    async def draft_catalog_patch(
        self,
        tenant_id: TenantId,
        payload: CatalogDraftPatchIn,
    ) -> CatalogDraftPatchOut:
        rows = await self._approved_rows_for_patch(tenant_id, payload.proposal_ids)
        return CatalogDraftPatchOut(
            proposal_ids=[row.id for row in rows],
            patch=[self._patch_entry(row) for row in rows],
            catalog_version_id=None,
        )

    async def proposal_review_history(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
        *,
        limit: int = 100,
    ) -> CatalogProposalHistoryOut:
        if self._insight is not None:
            return await self._proposal_review_history_from_insight(
                tenant_id,
                proposal_id,
                limit=limit,
            )

        proposal = await self._require_proposal(tenant_id, proposal_id)
        return CatalogProposalHistoryOut(
            proposal_id=proposal.id,
            items=_history_events_from_record(proposal, catalog_version_id=None)[:limit],
        )

    async def term_version_history(
        self,
        tenant_id: TenantId,
        term: str,
        *,
        limit: int = 100,
    ) -> CatalogVersionHistoryOut:
        if self._insight is not None:
            versions = await self._insight.list_versions_for_term(
                tenant_id,
                term,
                limit=limit,
            )
            return CatalogVersionHistoryOut(
                term=term,
                items=[_version_history_entry_from_insight(row) for row in versions],
            )

        rows = [
            row
            for row in await self._list_records(tenant_id, status="approved", limit=500)
            if row.suggested_term == term
        ][:limit]
        return CatalogVersionHistoryOut(
            term=term,
            items=[
                _version_history_entry_from_record(row, version=index + 1)
                for index, row in enumerate(rows)
            ],
        )

    async def _approved_rows_for_patch(
        self,
        tenant_id: TenantId,
        proposal_ids: list[UUID],
    ) -> list[CatalogProposalRecord]:
        if proposal_ids:
            rows = []
            for proposal_id in proposal_ids:
                row = await self._require_proposal(tenant_id, proposal_id)
                if row.status != "approved":
                    raise ValidationError(
                        "catalog patch can only include approved proposals",
                        details={"proposal_id": str(proposal_id), "status": row.status},
                    )
                rows.append(row)
            return rows
        return await self._list_records(tenant_id, status="approved", limit=500)

    async def _proposal_review_history_from_insight(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
        *,
        limit: int,
    ) -> CatalogProposalHistoryOut:
        assert self._insight is not None
        proposal = await self._insight.get_proposal(tenant_id, proposal_id)
        versions = await self._insight.list_versions_for_proposal(
            tenant_id,
            proposal_id,
            limit=limit,
        )
        catalog_version_id = versions[0].id if versions else proposal.approved_version_id
        items = _history_events_from_insight(
            proposal,
            catalog_version_id=catalog_version_id,
        )
        return CatalogProposalHistoryOut(proposal_id=proposal.id, items=items[:limit])

    async def _require_proposal(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
    ) -> CatalogProposalRecord:
        row = await self._get_record(tenant_id, proposal_id)
        if row is None:
            raise NotFoundError(
                "catalog proposal not found",
                details={"proposal_id": str(proposal_id)},
            )
        return row

    async def _require_open_proposal(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
    ) -> CatalogProposalRecord:
        row = await self._require_proposal(tenant_id, proposal_id)
        if row.status in _FINAL_REVIEW_STATUSES:
            raise ValidationError(
                "catalog proposal review is closed",
                details={"proposal_id": str(proposal_id), "status": row.status},
            )
        return row

    def _validate_transition(
        self,
        current: CatalogProposalStatus,
        requested: CatalogProposalStatus,
    ) -> None:
        if current in _FINAL_REVIEW_STATUSES:
            raise ValidationError(
                "catalog proposal review is closed",
                details={"current_status": current, "requested_status": requested},
            )
        if requested == "proposed" and current not in _OPEN_REVIEW_STATUSES:
            raise ValidationError(
                "invalid catalog proposal transition",
                details={"current_status": current, "requested_status": requested},
            )

    def _approval_blockers(self, proposal: CatalogProposalRecord) -> list[str]:
        blockers: list[str] = []
        if self._is_phi_source(proposal.source_system, proposal.source_field):
            blockers.append("phi_review_lane_required")
        if not proposal.definition.strip():
            blockers.append("definition_required")
        if not proposal.reason.strip():
            blockers.append("reason_required")
        return blockers

    def _impact_for(self, proposal: CatalogProposalRecord) -> CatalogProposalImpactOut:
        return CatalogProposalImpactOut(
            affected_questions=list(proposal.affected_questions),
            affected_read_models=list(proposal.affected_read_models),
        )

    def _assert_non_phi_source(self, source_system: str, source_field: str) -> None:
        if self._is_phi_source(source_system, source_field):
            raise ValidationError(
                "PHI fields require a separate catalog review lane",
                details={
                    "source_system": source_system,
                    "source_field": source_field,
                },
            )

    def _is_phi_source(self, source_system: str, source_field: str) -> bool:
        text = f"{source_system}.{source_field}".lower()
        return text.startswith("phi.") or ".phi_" in text or "clinical" in text

    def _patch_entry(self, proposal: CatalogProposalRecord) -> dict[str, object]:
        return {
            "term": proposal.suggested_term,
            "definition": proposal.definition,
            "synonyms": list(proposal.synonyms),
            "source": {
                "source_system": proposal.source_system,
                "source_field": proposal.source_field,
                "raw_value": proposal.raw_value,
                "confidence": proposal.confidence,
            },
            "review": {
                "status": proposal.status,
                "reviewer_note": proposal.reviewer_note,
                "reviewed_by_actor_id": (
                    str(proposal.reviewed_by_actor_id) if proposal.reviewed_by_actor_id else None
                ),
                "reviewed_at": (proposal.reviewed_at.isoformat() if proposal.reviewed_at else None),
            },
            "affected_questions": list(proposal.affected_questions),
            "affected_read_models": list(proposal.affected_read_models),
        }

    async def _list_records(
        self,
        tenant_id: TenantId,
        *,
        status: CatalogProposalStatus | None = None,
        limit: int,
    ) -> list[CatalogProposalRecord]:
        if self._insight is None:
            return await self._repo.list(tenant_id, status=status, limit=limit)
        rows = await self._insight.list_proposals(tenant_id, status=status, limit=limit)
        return [_record_from_insight(row) for row in rows]

    async def _get_record(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
    ) -> CatalogProposalRecord | None:
        if self._insight is None:
            return await self._repo.get(tenant_id, proposal_id)
        try:
            row = await self._insight.get_proposal(tenant_id, proposal_id)
        except NotFoundError:
            return None
        return _record_from_insight(row)

    async def _create_record(
        self,
        tenant_id: TenantId,
        payload: CatalogProposalCreateIn,
        principal: Principal,
    ) -> CatalogProposalRecord:
        if self._insight is None:
            return await self._repo.create(tenant_id, payload, actor_id=principal.id)
        row = await self._insight.create_proposal(
            tenant_id,
            _insight_create_from_analytics(payload),
            principal=principal,
        )
        return _record_from_insight(row)

    async def _update_record(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
        payload: CatalogProposalUpdateIn,
    ) -> CatalogProposalRecord | None:
        if self._insight is None:
            return await self._repo.update(tenant_id, proposal_id, payload)
        try:
            row = await self._insight.update_proposal(
                tenant_id,
                proposal_id,
                _insight_update_from_analytics(payload),
            )
        except NotFoundError:
            return None
        return _record_from_insight(row)

    async def _review_record(
        self,
        tenant_id: TenantId,
        proposal_id: UUID,
        payload: CatalogProposalReviewIn,
        principal: Principal,
    ) -> tuple[CatalogProposalRecord | None, UUID | None, UUID | None]:
        if self._insight is None:
            row = await self._repo.set_status(
                tenant_id,
                proposal_id,
                status=payload.status,
                reviewer_note=payload.reviewer_note,
                reviewed_by_actor_id=principal.id,
            )
            return row, None, None

        try:
            if payload.status == "approved":
                approval = await self._insight.approve_proposal(
                    tenant_id,
                    proposal_id,
                    InsightCatalogProposalApprovalIn(
                        reason=payload.reason,
                        reviewer_note=payload.reviewer_note,
                    ),
                    principal=principal,
                )
                return (
                    _record_from_insight(approval.proposal),
                    approval.version.id,
                    approval.version.previous_version_id,
                )
            if payload.status == "rejected":
                rejected = await self._insight.reject_proposal(
                    tenant_id,
                    proposal_id,
                    InsightCatalogProposalReviewIn(
                        reviewer_note=payload.reviewer_note,
                    ),
                    principal=principal,
                )
                return _record_from_insight(rejected), None, None
            if payload.status == "unresolved":
                unresolved = await self._insight.mark_proposal_unresolved(
                    tenant_id,
                    proposal_id,
                    InsightCatalogProposalReviewIn(
                        reviewer_note=payload.reviewer_note,
                    ),
                    principal=principal,
                )
                return _record_from_insight(unresolved), None, None
            proposed = await self._insight.mark_proposal_proposed(
                tenant_id,
                proposal_id,
                InsightCatalogProposalReviewIn(
                    reviewer_note=payload.reviewer_note,
                ),
                principal=principal,
            )
        except NotFoundError:
            return None, None, None
        return _record_from_insight(proposed), None, None

    async def _record_review_audit(
        self,
        *,
        principal: Principal,
        review_action: CatalogReviewAction,
        proposal: CatalogProposalRecord,
        reason: str,
        changed_fields: set[str],
        catalog_version_id: UUID | None = None,
        previous_catalog_version_id: UUID | None = None,
    ) -> None:
        if self._audit is None:
            return
        await self._audit.log_catalog_review_action(
            principal=principal,
            review_action=review_action,
            proposal_id=proposal.id,
            catalog_version_id=catalog_version_id,
            previous_catalog_version_id=previous_catalog_version_id,
            reason=_audit_reason(reason),
            target_status=proposal.status,
            changed_fields=sorted(changed_fields),
            affected_analytics=[
                *proposal.affected_questions,
                *proposal.affected_read_models,
            ],
            extra={
                "source_system": proposal.source_system,
                "source_field": proposal.source_field,
                "suggested_term": proposal.suggested_term,
            },
        )

    async def _record_catalog_version_change_audit(
        self,
        *,
        principal: Principal,
        proposal: CatalogProposalRecord,
        reason: str,
        catalog_version_id: UUID,
        previous_catalog_version_id: UUID | None,
    ) -> None:
        if self._audit is None:
            return
        await self._audit.log_catalog_version_change(
            principal=principal,
            catalog_version_id=catalog_version_id,
            previous_catalog_version_id=previous_catalog_version_id,
            metric_id=proposal.suggested_term,
            change_summary=f"Approved semantic catalog version for {proposal.suggested_term}",
            reason=_audit_reason(reason),
            changed_fields=[
                "definition",
                "synonyms",
                "source_mappings",
                "affected_analytics",
            ],
            affected_analytics=[
                *proposal.affected_questions,
                *proposal.affected_read_models,
            ],
            extra={
                "source_system": proposal.source_system,
                "source_field": proposal.source_field,
            },
        )

    def _to_out(self, row: CatalogProposalRecord) -> CatalogProposalOut:
        return CatalogProposalOut.model_validate(row)


def _audit_reason(reason: str) -> str:
    reason = reason.strip() or "catalog_review_action"
    return reason[:256]


def _skipped_person_journey_candidate(
    candidate: PersonJourneyProposalCandidateOut,
) -> CatalogProposalIngestionSkippedOut:
    entry = candidate.entry
    return CatalogProposalIngestionSkippedOut(
        source_reference_id=f"person_journey_registry:{entry.id}",
        registry_status=entry.registry_status,
        source_system=entry.source_system,
        source_field=entry.source_field,
        suggested_term=entry.suggested_term,
        blockers=list(candidate.blockers or ["candidate is not eligible for review"]),
    )


def _insight_create_from_analytics(
    payload: CatalogProposalCreateIn,
) -> SemanticCatalogProposalIn:
    return SemanticCatalogProposalIn(
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
        source_references=_source_references(
            payload.source_type,
            payload.source_reference_id,
        ),
    )


def _insight_update_from_analytics(
    payload: CatalogProposalUpdateIn,
) -> SemanticCatalogProposalUpdate:
    data = payload.model_dump(exclude_unset=True)
    if "source_reference_id" in data:
        data.pop("source_reference_id")
    return SemanticCatalogProposalUpdate.model_validate(data)


def _record_from_insight(row: SemanticCatalogProposalOut) -> CatalogProposalRecord:
    source_type, source_reference_id = _source_metadata(row.source_references)
    return CatalogProposalRecord(
        id=row.id,
        tenant_id=row.tenant_id,
        raw_value=row.raw_value,
        source_system=row.source_system,
        source_field=row.source_field,
        suggested_term=row.suggested_term,
        definition=row.definition,
        synonyms=list(row.synonyms),
        confidence=0.0 if row.confidence is None else row.confidence,
        reason=row.reason,
        reviewer_note=row.reviewer_note or "",
        affected_questions=list(row.affected_questions),
        affected_read_models=list(row.affected_read_models),
        status=row.status,
        source_type=source_type,
        source_reference_id=source_reference_id,
        created_by_actor_id=row.created_by_actor_id,
        reviewed_by_actor_id=row.reviewed_by_actor_id,
        reviewed_at=row.reviewed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _history_events_from_record(
    row: CatalogProposalRecord,
    *,
    catalog_version_id: UUID | None,
) -> list[CatalogProposalHistoryEventOut]:
    events = [
        CatalogProposalHistoryEventOut(
            action="created",
            status="proposed",
            actor_id=row.created_by_actor_id,
            occurred_at=row.created_at,
            reason=row.reason,
            reviewer_note=None,
            catalog_version_id=None,
        )
    ]
    if row.reviewed_at is not None:
        events.append(
            CatalogProposalHistoryEventOut(
                action=row.status,
                status=row.status,
                actor_id=row.reviewed_by_actor_id,
                occurred_at=row.reviewed_at,
                reason=row.reason,
                reviewer_note=row.reviewer_note or None,
                catalog_version_id=catalog_version_id,
            )
        )
    return events


def _history_events_from_insight(
    row: SemanticCatalogProposalOut,
    *,
    catalog_version_id: UUID | None,
) -> list[CatalogProposalHistoryEventOut]:
    return _history_events_from_record(
        _record_from_insight(row),
        catalog_version_id=catalog_version_id,
    )


def _version_history_entry_from_insight(
    row: SemanticCatalogVersionOut,
) -> CatalogVersionHistoryEntryOut:
    return CatalogVersionHistoryEntryOut(
        id=row.id,
        tenant_id=row.tenant_id,
        term=row.term,
        version=row.version,
        review_status=row.review_status,
        definition=row.definition,
        synonyms=list(row.synonyms),
        allowed_data_sources=list(row.allowed_data_sources),
        data_classes=list(row.data_classes),
        allowed_outputs=list(row.allowed_outputs),
        canonical_fields=list(row.canonical_fields),
        row_level_fields=list(row.row_level_fields),
        aggregate_metrics=list(row.aggregate_metrics),
        used_by=list(row.used_by),
        source_references=[dict(item) for item in row.source_references],
        previous_version_id=row.previous_version_id,
        proposal_id=row.proposal_id,
        previous_value=row.previous_value,
        new_value=row.new_value,
        reason=row.reason,
        affected_questions=list(row.affected_questions),
        affected_read_models=list(row.affected_read_models),
        affected_reports=list(row.affected_reports),
        affected_dashboard_panels=list(row.affected_dashboard_panels),
        affected_chat_answers=list(row.affected_chat_answers),
        affected_agent_briefs=list(row.affected_agent_briefs),
        approved_by_actor_id=row.approved_by_actor_id,
        approved_at=row.approved_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _version_history_entry_from_record(
    row: CatalogProposalRecord,
    *,
    version: int,
) -> CatalogVersionHistoryEntryOut:
    value = {
        "term": row.suggested_term,
        "version": version,
        "review_status": "approved",
        "definition": row.definition,
        "synonyms": list(row.synonyms),
        "source_system": row.source_system,
        "source_field": row.source_field,
    }
    return CatalogVersionHistoryEntryOut(
        id=row.id,
        tenant_id=row.tenant_id,
        term=row.suggested_term,
        version=version,
        review_status="approved",
        definition=row.definition,
        synonyms=list(row.synonyms),
        allowed_data_sources=[f"{row.source_system}.{row.source_field}"],
        data_classes=[],
        allowed_outputs=[],
        canonical_fields=[],
        row_level_fields=[],
        aggregate_metrics=[],
        used_by=[],
        source_references=_source_references(row.source_type, row.source_reference_id),
        previous_version_id=None,
        proposal_id=row.id,
        previous_value=None,
        new_value=value,
        reason=row.reason,
        affected_questions=list(row.affected_questions),
        affected_read_models=list(row.affected_read_models),
        affected_reports=[],
        affected_dashboard_panels=[],
        affected_chat_answers=[],
        affected_agent_briefs=[],
        approved_by_actor_id=row.reviewed_by_actor_id,
        approved_at=row.reviewed_at or row.updated_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _source_references(
    source_type: str,
    source_reference_id: str | None,
) -> list[dict[str, object]]:
    metadata: dict[str, object] = {"source_type": source_type}
    if source_reference_id is not None:
        metadata["source_reference_id"] = source_reference_id
    return [metadata]


def _source_metadata(source_references: list[dict[str, object]]) -> tuple[str, str | None]:
    if not source_references:
        return "manual", None
    first = source_references[0]
    raw_source_type = str(first.get("source_type") or "manual")
    source_type = raw_source_type if raw_source_type in {"agent", "manual", "import"} else "manual"
    raw_reference = first.get("source_reference_id")
    return source_type, None if raw_reference is None else str(raw_reference)
