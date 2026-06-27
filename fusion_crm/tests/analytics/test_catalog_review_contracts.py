"""Service contract tests for semantic catalog proposal review (ENG-315)."""

from __future__ import annotations

import uuid

import pytest

from packages.analytics.repository import InMemoryCatalogProposalRepository
from packages.analytics.schemas import (
    CatalogDraftPatchIn,
    CatalogProposalCreateIn,
    CatalogProposalReviewIn,
    CatalogProposalUpdateIn,
)
from packages.analytics.service import AnalyticsCatalogReviewService
from packages.core.exceptions import ValidationError
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.data_intelligence.schemas import (
    PersonJourneyRegistryStatus,
)
from packages.data_intelligence.service import DataIntelligenceService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_ACTOR_ID = uuid.uuid4()


def _principal() -> Principal:
    return Principal(
        id=_ACTOR_ID,
        email="catalog-review@example.com",
        tenant_id=_TENANT_ID,
        roles=frozenset({Role.STAFF}),
    )


def _system_principal() -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="data-intelligence-agent@example.com",
        tenant_id=_TENANT_ID,
        roles=frozenset({Role.SYSTEM}),
    )


def _proposal_payload(**overrides: object) -> CatalogProposalCreateIn:
    data: dict[str, object] = {
        "raw_value": "IG June",
        "source_system": "salesforce",
        "source_field": "Lead.Campaign__c",
        "suggested_term": "lead_source_campaign",
        "definition": "Campaign value used to group lead source performance.",
        "synonyms": ["campaign"],
        "confidence": 0.84,
        "reason": "Observed in unmapped Salesforce lead values.",
        "reviewer_note": "",
        "affected_questions": ["MKT-001"],
        "affected_read_models": ["lead_conversion"],
        "source_type": "agent",
        "source_reference_id": "profile-001",
    }
    data.update(overrides)
    return CatalogProposalCreateIn.model_validate(data)


@pytest.mark.asyncio
async def test_review_approval_sets_status_and_returns_impact() -> None:
    service = AnalyticsCatalogReviewService(InMemoryCatalogProposalRepository())
    proposal = await service.create_proposal(_TENANT_ID, _proposal_payload(), _principal())

    result = await service.review_proposal(
        _TENANT_ID,
        proposal.id,
        CatalogProposalReviewIn(
            status="approved",
            reason="Mapping reviewed by operations owner.",
            reviewer_note="Approved for lead source reporting.",
        ),
        _principal(),
    )

    assert result.proposal.status == "approved"
    assert result.proposal.reviewed_by_actor_id == _ACTOR_ID
    assert result.impact.affected_questions == ["MKT-001"]
    assert result.catalog_version_id is None


@pytest.mark.asyncio
async def test_closed_proposal_cannot_be_edited_or_reviewed_again() -> None:
    service = AnalyticsCatalogReviewService(InMemoryCatalogProposalRepository())
    proposal = await service.create_proposal(_TENANT_ID, _proposal_payload(), _principal())
    await service.review_proposal(
        _TENANT_ID,
        proposal.id,
        CatalogProposalReviewIn(
            status="rejected",
            reason="The raw value is not a stable campaign source.",
        ),
        _principal(),
    )

    with pytest.raises(ValidationError) as edit_error:
        await service.update_proposal(
            _TENANT_ID,
            proposal.id,
            CatalogProposalUpdateIn(suggested_term="lead_source_paid_social"),
            _principal(),
        )
    assert edit_error.value.details["status"] == "rejected"

    with pytest.raises(ValidationError) as review_error:
        await service.review_proposal(
            _TENANT_ID,
            proposal.id,
            CatalogProposalReviewIn(
                status="approved",
                reason="Trying to reopen without storage workflow.",
            ),
            _principal(),
        )
    assert review_error.value.details["status"] == "rejected"


@pytest.mark.asyncio
async def test_phi_source_is_denied_before_review() -> None:
    service = AnalyticsCatalogReviewService(InMemoryCatalogProposalRepository())

    with pytest.raises(ValidationError) as excinfo:
        await service.create_proposal(
            _TENANT_ID,
            _proposal_payload(source_system="phi", source_field="condition"),
            _principal(),
        )

    assert excinfo.value.details["source_system"] == "phi"


@pytest.mark.asyncio
async def test_system_principal_cannot_approve_catalog_proposals() -> None:
    service = AnalyticsCatalogReviewService(InMemoryCatalogProposalRepository())
    proposal = await service.create_proposal(
        _TENANT_ID,
        _proposal_payload(source_type="agent"),
        _system_principal(),
    )

    with pytest.raises(ValidationError) as excinfo:
        await service.review_proposal(
            _TENANT_ID,
            proposal.id,
            CatalogProposalReviewIn(
                status="approved",
                reason="Agent attempted to approve its own mapping.",
            ),
            _system_principal(),
        )

    assert excinfo.value.message == "catalog proposals require human approval"


@pytest.mark.asyncio
async def test_ingest_person_journey_registry_proposals_creates_only_eligible_drafts() -> None:
    service = AnalyticsCatalogReviewService(InMemoryCatalogProposalRepository())
    _, projection = DataIntelligenceService().person_journey_registry_proposals()
    assert projection is not None

    result = await service.ingest_person_journey_registry_proposals(
        _TENANT_ID,
        projection,
        _system_principal(),
    )

    created_refs = {proposal.source_reference_id for proposal in result.created}
    skipped_refs = {item.source_reference_id for item in result.skipped}

    assert result.created_count == len(result.created)
    assert result.skipped_count == len(result.skipped)
    assert "person_journey_registry:field.utm_source" in created_refs
    assert "person_journey_registry:field.gclid" in created_refs
    assert "person_journey_registry:field.unchanged_count" in skipped_refs
    assert "person_journey_registry:field.raw_provider_payload" in skipped_refs
    assert "person_journey_registry:event.contact_created" in skipped_refs
    assert all(proposal.status == "proposed" for proposal in result.created)
    assert all(proposal.source_type == "agent" for proposal in result.created)
    assert all(item.blockers for item in result.skipped)


@pytest.mark.asyncio
async def test_ingested_person_journey_proposals_still_require_human_approval() -> None:
    service = AnalyticsCatalogReviewService(InMemoryCatalogProposalRepository())
    _, projection = DataIntelligenceService().person_journey_registry_proposals(
        statuses=[PersonJourneyRegistryStatus.APPROVED_CANDIDATE],
    )
    assert projection is not None

    ingestion = await service.ingest_person_journey_registry_proposals(
        _TENANT_ID,
        projection,
        _system_principal(),
    )
    proposal = ingestion.created[0]

    with pytest.raises(ValidationError) as excinfo:
        await service.review_proposal(
            _TENANT_ID,
            proposal.id,
            CatalogProposalReviewIn(
                status="approved",
                reason="Agent attempted to approve an ingested person journey proposal.",
            ),
            _system_principal(),
        )

    assert excinfo.value.message == "catalog proposals require human approval"


@pytest.mark.asyncio
async def test_draft_patch_requires_approved_proposals() -> None:
    service = AnalyticsCatalogReviewService(InMemoryCatalogProposalRepository())
    approved = await service.create_proposal(_TENANT_ID, _proposal_payload(), _principal())
    proposed = await service.create_proposal(
        _TENANT_ID,
        _proposal_payload(raw_value="Google PMax", source_reference_id="profile-002"),
        _principal(),
    )
    await service.review_proposal(
        _TENANT_ID,
        approved.id,
        CatalogProposalReviewIn(
            status="approved",
            reason="Approved by catalog owner.",
            reviewer_note="Ready for catalog version draft.",
        ),
        _principal(),
    )

    patch = await service.draft_catalog_patch(_TENANT_ID, CatalogDraftPatchIn())
    assert patch.proposal_ids == [approved.id]
    assert patch.patch[0]["term"] == "lead_source_campaign"

    with pytest.raises(ValidationError) as excinfo:
        await service.draft_catalog_patch(
            _TENANT_ID,
            CatalogDraftPatchIn(proposal_ids=[proposed.id]),
        )
    assert excinfo.value.details["status"] == "proposed"
