"""HTTP contract tests for semantic catalog proposal review (ENG-315)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import (
    get_analytics_catalog_review_service,
    get_principal_with_tenant,
)
from apps.api.middleware import platform_error_handler
from apps.api.routers import semantic_catalog as semantic_catalog_router
from packages.analytics.repository import CatalogProposalRecord, InMemoryCatalogProposalRepository
from packages.analytics.schemas import (
    CatalogProposalHistoryEventOut,
    CatalogProposalHistoryOut,
    CatalogProposalImpactOut,
    CatalogProposalOut,
    CatalogVersionHistoryEntryOut,
    CatalogVersionHistoryOut,
)
from packages.analytics.service import AnalyticsCatalogReviewService
from packages.core.exceptions import PlatformError
from packages.core.security import Principal, Role
from packages.core.types import TenantId

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_ACTOR_ID = uuid.uuid4()


def _principal() -> Principal:
    return Principal(
        id=_ACTOR_ID,
        email="catalog-review@example.com",
        tenant_id=_TENANT_ID,
        roles=frozenset({Role.STAFF}),
    )


def _proposal_out(
    *,
    proposal_id: uuid.UUID | None = None,
    status: str = "proposed",
) -> CatalogProposalOut:
    now = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)
    return CatalogProposalOut(
        id=proposal_id or uuid.uuid4(),
        tenant_id=uuid.UUID(str(_TENANT_ID)),
        raw_value="IG June",
        source_system="salesforce",
        source_field="Lead.Campaign__c",
        suggested_term="lead_source_campaign",
        definition="Campaign value used to group lead source performance.",
        synonyms=["campaign"],
        confidence=0.84,
        reason="Observed in unmapped Salesforce lead values.",
        reviewer_note="",
        affected_questions=["MKT-001"],
        affected_read_models=["lead_conversion"],
        status=status,  # type: ignore[arg-type]
        source_type="agent",
        source_reference_id="profile-001",
        created_by_actor_id=None,
        reviewed_by_actor_id=None,
        reviewed_at=None,
        created_at=now,
        updated_at=now,
    )


def _proposal_record(
    *,
    proposal_id: uuid.UUID | None = None,
    status: str = "proposed",
) -> CatalogProposalRecord:
    proposal = _proposal_out(proposal_id=proposal_id, status=status)
    return CatalogProposalRecord(
        id=proposal.id,
        tenant_id=proposal.tenant_id,
        raw_value=proposal.raw_value,
        source_system=proposal.source_system,
        source_field=proposal.source_field,
        suggested_term=proposal.suggested_term,
        definition=proposal.definition,
        synonyms=list(proposal.synonyms),
        confidence=proposal.confidence,
        reason=proposal.reason,
        reviewer_note=proposal.reviewer_note,
        affected_questions=list(proposal.affected_questions),
        affected_read_models=list(proposal.affected_read_models),
        status=proposal.status,
        source_type=proposal.source_type,
        source_reference_id=proposal.source_reference_id,
        created_by_actor_id=proposal.created_by_actor_id,
        reviewed_by_actor_id=proposal.reviewed_by_actor_id,
        reviewed_at=proposal.reviewed_at,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
    )


def _build_app(svc: object) -> FastAPI:
    app = FastAPI()
    app.include_router(semantic_catalog_router.router)
    app.add_exception_handler(PlatformError, platform_error_handler)  # type: ignore[arg-type]
    app.dependency_overrides[get_analytics_catalog_review_service] = lambda: svc
    app.dependency_overrides[get_principal_with_tenant] = _principal
    return app


def test_list_catalog_proposals_returns_typed_items_and_calls_service() -> None:
    svc = MagicMock()
    proposal = _proposal_out()
    svc.list_proposals = AsyncMock(return_value=[proposal])
    client = TestClient(_build_app(svc))

    res = client.get("/semantic/catalog/proposals?status=proposed&limit=25")

    assert res.status_code == 200
    body = res.json()
    assert body["items"][0]["id"] == str(proposal.id)
    assert body["items"][0]["status"] == "proposed"
    assert body["items"][0]["affected_questions"] == ["MKT-001"]
    svc.list_proposals.assert_awaited_once_with(_TENANT_ID, status="proposed", limit=25)


def test_create_catalog_proposal_returns_created_contract() -> None:
    svc = MagicMock()
    proposal = _proposal_out()
    svc.create_proposal = AsyncMock(return_value=proposal)
    client = TestClient(_build_app(svc))

    res = client.post(
        "/semantic/catalog/proposals",
        json={
            "raw_value": "IG June",
            "source_system": "salesforce",
            "source_field": "Lead.Campaign__c",
            "suggested_term": "lead_source_campaign",
            "definition": "Campaign value used to group lead source performance.",
            "synonyms": ["campaign"],
            "confidence": 0.84,
            "reason": "Observed in unmapped Salesforce lead values.",
            "affected_questions": ["MKT-001"],
            "affected_read_models": ["lead_conversion"],
            "source_type": "manual",
        },
    )

    assert res.status_code == 201
    assert res.json()["suggested_term"] == "lead_source_campaign"
    args = svc.create_proposal.await_args.args
    assert args[0] == _TENANT_ID
    assert args[2] == _principal()


def test_impact_preview_route_returns_contract_without_route_metrics_logic() -> None:
    proposal_id = uuid.uuid4()
    svc = MagicMock()
    svc.preview_impact = AsyncMock(
        return_value={
            "proposal_id": proposal_id,
            "impact": CatalogProposalImpactOut(
                affected_questions=["MKT-001"],
                affected_read_models=["lead_conversion"],
            ),
            "can_approve": True,
            "blockers": [],
        }
    )
    client = TestClient(_build_app(svc))

    res = client.get(f"/semantic/catalog/proposals/{proposal_id}/impact-preview")

    assert res.status_code == 200
    body = res.json()
    assert body["proposal_id"] == str(proposal_id)
    assert body["impact"]["affected_questions"] == ["MKT-001"]
    svc.preview_impact.assert_awaited_once_with(_TENANT_ID, proposal_id)


def test_proposal_history_route_returns_review_events() -> None:
    proposal_id = uuid.uuid4()
    now = datetime(2026, 6, 2, 12, 10, tzinfo=UTC)
    svc = MagicMock()
    svc.proposal_review_history = AsyncMock(
        return_value=CatalogProposalHistoryOut(
            proposal_id=proposal_id,
            items=[
                CatalogProposalHistoryEventOut(
                    action="approved",
                    status="approved",
                    actor_id=_ACTOR_ID,
                    occurred_at=now,
                    reason="Human reviewer decision.",
                    reviewer_note="Approved by marketing.",
                    catalog_version_id=uuid.uuid4(),
                )
            ],
        )
    )
    client = TestClient(_build_app(svc))

    res = client.get(f"/semantic/catalog/proposals/{proposal_id}/history?limit=10")

    assert res.status_code == 200
    body = res.json()
    assert body["proposal_id"] == str(proposal_id)
    assert body["items"][0]["action"] == "approved"
    svc.proposal_review_history.assert_awaited_once_with(
        _TENANT_ID,
        proposal_id,
        limit=10,
    )


def test_version_history_route_uses_query_term_for_slash_terms() -> None:
    term = "paid_social/facebook"
    version_id = uuid.uuid4()
    proposal_id = uuid.uuid4()
    now = datetime(2026, 6, 2, 12, 20, tzinfo=UTC)
    svc = MagicMock()
    svc.term_version_history = AsyncMock(
        return_value=CatalogVersionHistoryOut(
            term=term,
            items=[
                CatalogVersionHistoryEntryOut(
                    id=version_id,
                    tenant_id=uuid.UUID(str(_TENANT_ID)),
                    term=term,
                    version=2,
                    review_status="approved",
                    definition="Paid social lead from Meta lead forms.",
                    synonyms=["Meta Lead Form"],
                    allowed_data_sources=["salesforce.LeadSource"],
                    data_classes=["ops"],
                    allowed_outputs=["aggregate"],
                    canonical_fields=[],
                    row_level_fields=[],
                    aggregate_metrics=[],
                    used_by=["lead_conversion"],
                    source_references=[],
                    previous_version_id=None,
                    proposal_id=proposal_id,
                    previous_value=None,
                    new_value={"term": term, "version": 2},
                    reason="Expanded approved source values.",
                    affected_questions=["Q16"],
                    affected_read_models=["lead_conversion"],
                    affected_reports=[],
                    affected_dashboard_panels=[],
                    affected_chat_answers=[],
                    affected_agent_briefs=[],
                    approved_by_actor_id=_ACTOR_ID,
                    approved_at=now,
                    created_at=now,
                    updated_at=now,
                )
            ],
        )
    )
    client = TestClient(_build_app(svc))

    res = client.get("/semantic/catalog/versions", params={"term": term, "limit": 5})

    assert res.status_code == 200
    body = res.json()
    assert body["term"] == term
    assert body["items"][0]["version"] == 2
    svc.term_version_history.assert_awaited_once_with(
        _TENANT_ID,
        term,
        limit=5,
    )


def test_invalid_review_transition_returns_platform_error_envelope() -> None:
    proposal_id = uuid.uuid4()
    repo = InMemoryCatalogProposalRepository(
        [_proposal_record(proposal_id=proposal_id, status="approved")]
    )
    svc = AnalyticsCatalogReviewService(repo)
    client = TestClient(_build_app(svc))

    res = client.post(
        f"/semantic/catalog/proposals/{proposal_id}/review",
        json={
            "status": "approved",
            "reason": "Approve again.",
            "reviewer_note": "Already approved.",
        },
    )

    assert res.status_code == 422
    body = res.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "catalog proposal review is closed"
    assert body["error"]["details"]["proposal_id"] == str(proposal_id)
