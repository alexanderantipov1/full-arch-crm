"""Service tests for semantic catalog proposal review audit integration."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from packages.analytics.repository import (
    CatalogProposalRecord,
    InMemoryCatalogProposalRepository,
)
from packages.analytics.schemas import CatalogProposalReviewIn, CatalogProposalUpdateIn
from packages.analytics.service import AnalyticsCatalogReviewService
from packages.core.security import Principal, Role
from packages.core.types import TenantId


def _principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=uuid4(),
        email="reviewer@fusiondentalimplants.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.STAFF}),
    )


def _proposal(
    tenant_id: TenantId,
    *,
    status: str = "proposed",
) -> CatalogProposalRecord:
    now = datetime.now(UTC)
    return CatalogProposalRecord(
        id=uuid4(),
        tenant_id=UUID(str(tenant_id)),
        raw_value="Jane Patient from provider payload",
        source_system="salesforce",
        source_field="LeadSource",
        suggested_term="paid_social",
        definition="Leads from paid social campaigns.",
        synonyms=["facebook ads"],
        confidence=0.91,
        reason="Observed source values map to paid social.",
        reviewer_note="Do not put this note in audit extra.",
        affected_questions=["lead-source-profile"],
        affected_read_models=["lead_conversion"],
        status=status,  # type: ignore[arg-type]
        source_type="agent",
        source_reference_id="profile-run-1",
        created_by_actor_id=None,
        reviewed_by_actor_id=None,
        reviewed_at=None,
        created_at=now,
        updated_at=now,
    )


def _service(
    row: CatalogProposalRecord,
) -> tuple[AnalyticsCatalogReviewService, MagicMock]:
    audit = MagicMock()
    audit.log_catalog_review_action = AsyncMock()
    repo = InMemoryCatalogProposalRepository([row])
    return AnalyticsCatalogReviewService(repo, audit=audit), audit


@pytest.mark.asyncio
async def test_update_proposal_writes_edit_audit_without_sensitive_fields() -> None:
    tenant_id = TenantId(uuid4())
    principal = _principal(tenant_id)
    row = _proposal(tenant_id)
    service, audit = _service(row)

    await service.update_proposal(
        tenant_id,
        row.id,
        CatalogProposalUpdateIn(
            suggested_term="paid_leads",
            reason="Reviewer corrected the approved business term.",
        ),
        principal,
    )

    audit.log_catalog_review_action.assert_awaited_once()
    kwargs = audit.log_catalog_review_action.await_args.kwargs
    assert kwargs["principal"] == principal
    assert kwargs["review_action"] == "edit"
    assert kwargs["proposal_id"] == row.id
    assert kwargs["reason"] == "Reviewer corrected the approved business term."
    assert kwargs["target_status"] == "proposed"
    assert kwargs["changed_fields"] == ["reason", "suggested_term"]
    assert kwargs["affected_analytics"] == ["lead-source-profile", "lead_conversion"]
    assert kwargs["extra"] == {
        "source_system": "salesforce",
        "source_field": "LeadSource",
        "suggested_term": "paid_leads",
    }
    rendered = repr(kwargs)
    assert "Jane Patient" not in rendered
    assert "reviewer_note" not in rendered


@pytest.mark.asyncio
async def test_proposal_and_term_history_read_paths_use_reviewed_records() -> None:
    tenant_id = TenantId(uuid4())
    principal = _principal(tenant_id)
    row = _proposal(tenant_id)
    service, _ = _service(row)

    reviewed = await service.review_proposal(
        tenant_id,
        row.id,
        CatalogProposalReviewIn(
            status="approved",
            reviewer_note="Approved for reporting.",
            reason="Human reviewer decision.",
        ),
        principal,
    )

    proposal_history = await service.proposal_review_history(tenant_id, row.id)
    assert [event.action for event in proposal_history.items] == [
        "created",
        "approved",
    ]
    assert proposal_history.items[1].actor_id == principal.id
    assert proposal_history.items[1].reviewer_note == "Approved for reporting."

    version_history = await service.term_version_history(
        tenant_id,
        reviewed.proposal.suggested_term,
    )
    assert [entry.version for entry in version_history.items] == [1]
    assert version_history.items[0].proposal_id == row.id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "review_action"),
    [
        ("approved", "approve"),
        ("rejected", "reject"),
        ("unresolved", "unresolved"),
    ],
)
async def test_review_proposal_writes_decision_audit(
    status: str,
    review_action: str,
) -> None:
    tenant_id = TenantId(uuid4())
    principal = _principal(tenant_id)
    row = _proposal(tenant_id)
    service, audit = _service(row)

    await service.review_proposal(
        tenant_id,
        row.id,
        CatalogProposalReviewIn(
            status=status,  # type: ignore[arg-type]
            reviewer_note="Keep note out of audit extra.",
            reason="Human reviewer decision.",
        ),
        principal,
    )

    audit.log_catalog_review_action.assert_awaited_once()
    kwargs = audit.log_catalog_review_action.await_args.kwargs
    assert kwargs["review_action"] == review_action
    assert kwargs["proposal_id"] == row.id
    assert kwargs["reason"] == "Human reviewer decision."
    assert kwargs["target_status"] == status
    assert kwargs["changed_fields"] == ["reviewer_note", "status"]
    assert kwargs["affected_analytics"] == ["lead-source-profile", "lead_conversion"]
    rendered = repr(kwargs)
    assert "Jane Patient" not in rendered
    assert "Keep note out of audit extra." not in rendered
