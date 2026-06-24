"""Service-level tests for AuditService helpers.

Repo is mocked: we assert the AccessLog row that the service hands to
``AuditRepository.add`` carries the right action / resource / extra
shape. End-to-end coverage with a real session lands with the alembic
migration in FUS-32.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from packages.audit.models import AccessLog
from packages.audit.service import AuditService, explain_catalog_metric_change
from packages.core.security import Principal, Role
from packages.core.types import TenantId


def _principal() -> Principal:
    return Principal(
        id=uuid4(),
        email="oncall@fusiondentalimplants.com",
        tenant_id=TenantId(uuid4()),
        roles=frozenset({Role.STAFF}),
    )


def _mock_service() -> tuple[AuditService, AsyncMock]:
    session = MagicMock()
    service = AuditService(session)
    add_mock = AsyncMock(side_effect=lambda entry: entry)
    service._repo.add = add_mock  # type: ignore[method-assign]
    return service, add_mock


def _captured_entry(add_mock: AsyncMock) -> AccessLog:
    add_mock.assert_awaited_once()
    call = add_mock.await_args
    assert call is not None
    (entry,) = call.args
    assert isinstance(entry, AccessLog)
    return entry


# --- log_oauth_event ---


@pytest.mark.asyncio
async def test_log_oauth_event_connect_sets_action_and_resource() -> None:
    service, add_mock = _mock_service()
    principal = _principal()
    account_id = uuid4()

    await service.log_oauth_event(
        principal=principal,
        provider="salesforce",
        event="connect",
        account_id=account_id,
        outcome="success",
    )

    entry = _captured_entry(add_mock)
    assert entry.action == "oauth.connect"
    assert entry.resource == "integration.account"
    assert entry.principal_id == principal.id
    assert entry.principal_email == principal.email
    assert entry.tenant_id == principal.tenant_id
    assert entry.person_uid is None
    assert entry.extra == {
        "provider": "salesforce",
        "account_id": str(account_id),
        "outcome": "success",
    }


@pytest.mark.asyncio
async def test_log_oauth_event_error_omits_optional_fields() -> None:
    service, add_mock = _mock_service()

    await service.log_oauth_event(
        principal=_principal(),
        provider="carestack",
        event="error",
        reason="token_refresh_failed",
    )

    entry = _captured_entry(add_mock)
    assert entry.action == "oauth.error"
    assert entry.reason == "token_refresh_failed"
    assert entry.extra == {"provider": "carestack"}


@pytest.mark.asyncio
async def test_log_oauth_event_extra_is_merged_on_top() -> None:
    """Caller-supplied ``extra`` is layered over the derived fields, but
    never silently drops them — derived keys come first, caller keys win
    on collision (intentional: caller knows their context best)."""
    service, add_mock = _mock_service()
    account_id = uuid4()

    await service.log_oauth_event(
        principal=_principal(),
        provider="salesforce",
        event="refresh",
        account_id=account_id,
        outcome="success",
        extra={"refresh_age_seconds": 3500, "outcome": "partial"},
    )

    entry = _captured_entry(add_mock)
    assert entry.extra["provider"] == "salesforce"
    assert entry.extra["account_id"] == str(account_id)
    assert entry.extra["refresh_age_seconds"] == 3500
    assert entry.extra["outcome"] == "partial"


# --- log_sync_run_summary ---


@pytest.mark.asyncio
async def test_log_sync_run_summary_full_payload() -> None:
    service, add_mock = _mock_service()
    principal = _principal()
    sync_run_id = uuid4()

    await service.log_sync_run_summary(
        principal=principal,
        provider="salesforce",
        sync_run_id=sync_run_id,
        outcome="success",
        entity_kind="lead",
        item_count=42,
        error_count=0,
    )

    entry = _captured_entry(add_mock)
    assert entry.action == "integrations.sync_run.complete"
    assert entry.resource == "integration.sync_run"
    assert entry.principal_id == principal.id
    assert entry.tenant_id == principal.tenant_id
    assert entry.person_uid is None
    assert entry.extra == {
        "provider": "salesforce",
        "sync_run_id": str(sync_run_id),
        "outcome": "success",
        "entity_kind": "lead",
        "item_count": 42,
        "error_count": 0,
    }


@pytest.mark.asyncio
async def test_log_sync_run_summary_partial_outcome_minimal_payload() -> None:
    service, add_mock = _mock_service()
    sync_run_id = uuid4()

    await service.log_sync_run_summary(
        principal=_principal(),
        provider="carestack",
        sync_run_id=sync_run_id,
        outcome="partial",
    )

    entry = _captured_entry(add_mock)
    assert entry.action == "integrations.sync_run.complete"
    assert entry.extra == {
        "provider": "carestack",
        "sync_run_id": str(sync_run_id),
        "outcome": "partial",
    }


@pytest.mark.asyncio
async def test_log_sync_run_summary_serialises_uuid_to_string() -> None:
    """The audit row's ``extra`` is JSONB — UUIDs must be strings, not raw
    UUID objects, so the row is round-trippable through JSON."""
    service, add_mock = _mock_service()
    sync_run_id = UUID("00000000-0000-0000-0000-0000000000ff")

    await service.log_sync_run_summary(
        principal=_principal(),
        provider="salesforce",
        sync_run_id=sync_run_id,
        outcome="failure",
    )

    entry = _captured_entry(add_mock)
    assert entry.extra["sync_run_id"] == "00000000-0000-0000-0000-0000000000ff"
    assert isinstance(entry.extra["sync_run_id"], str)


# --- semantic catalog review ---


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("review_action", "expected_action"),
    [
        ("approve", "semantic_catalog.review.approve"),
        ("edit", "semantic_catalog.review.edit"),
        ("reject", "semantic_catalog.review.reject"),
        ("unresolved", "semantic_catalog.review.unresolved"),
    ],
)
async def test_log_catalog_review_action_sets_stable_action_taxonomy(
    review_action: str,
    expected_action: str,
) -> None:
    service, add_mock = _mock_service()
    principal = _principal()
    proposal_id = uuid4()
    catalog_version_id = uuid4()
    previous_catalog_version_id = uuid4()

    await service.log_catalog_review_action(
        principal=principal,
        review_action=review_action,  # type: ignore[arg-type]
        proposal_id=proposal_id,
        catalog_version_id=catalog_version_id,
        previous_catalog_version_id=previous_catalog_version_id,
        target_status="approved",
        changed_fields=["definition", "synonyms"],
        affected_analytics=["lead_conversion_funnel.v1"],
        reason="reviewed_mapping",
        extra={"source_system": "salesforce", "source_field": "LeadSource"},
    )

    entry = _captured_entry(add_mock)
    assert entry.action == expected_action
    assert entry.resource == "semantic_catalog.proposal"
    assert entry.reason == "reviewed_mapping"
    assert entry.principal_id == principal.id
    assert entry.tenant_id == principal.tenant_id
    assert entry.person_uid is None
    assert entry.extra == {
        "proposal_id": str(proposal_id),
        "review_action": review_action,
        "catalog_version_id": str(catalog_version_id),
        "previous_catalog_version_id": str(previous_catalog_version_id),
        "target_status": "approved",
        "changed_fields": ["definition", "synonyms"],
        "affected_analytics": ["lead_conversion_funnel.v1"],
        "source_system": "salesforce",
        "source_field": "LeadSource",
    }


@pytest.mark.asyncio
async def test_log_catalog_review_action_redacts_sensitive_extra_fields() -> None:
    service, add_mock = _mock_service()

    await service.log_catalog_review_action(
        principal=_principal(),
        review_action="edit",
        proposal_id="proposal-123",
        reason="edited_mapping",
        extra={
            "source_system": "carestack",
            "raw_value": "Jane Patient",
            "reviewer_note": "Call Jane at 555-1212",
            "raw_provider_payload": {"PatientName": "Jane Patient"},
            "nested": {
                "safe_flag": True,
                "email": "jane.patient@example.test",
                "api_token": "secret-token",
            },
            "examples": [{"phone_number": "555-1212"}, {"safe": "kept"}],
        },
    )

    entry = _captured_entry(add_mock)
    assert entry.extra["source_system"] == "carestack"
    assert entry.extra["raw_value"] == "[redacted]"
    assert entry.extra["reviewer_note"] == "[redacted]"
    assert entry.extra["raw_provider_payload"] == "[redacted]"
    assert entry.extra["nested"] == {
        "safe_flag": True,
        "email": "[redacted]",
        "api_token": "[redacted]",
    }
    assert entry.extra["examples"] == [
        {"phone_number": "[redacted]"},
        {"safe": "kept"},
    ]
    rendered = repr(entry.extra)
    assert "Jane Patient" not in rendered
    assert "555-1212" not in rendered
    assert "secret-token" not in rendered


@pytest.mark.asyncio
async def test_log_catalog_version_change_records_metric_explanation_payload() -> None:
    service, add_mock = _mock_service()
    catalog_version_id = uuid4()
    previous_catalog_version_id = uuid4()

    await service.log_catalog_version_change(
        principal=_principal(),
        catalog_version_id=catalog_version_id,
        previous_catalog_version_id=previous_catalog_version_id,
        metric_id="lead_conversion",
        change_summary="Lead source grouping moved paid social aliases under paid leads",
        reason="approved_source_mapping",
        changed_fields=["source_aliases"],
        affected_analytics=["lead_conversion_funnel.v1", "paid_leads.v1"],
        extra={"raw_value": "facebook ads", "source_field": "LeadSource"},
    )

    entry = _captured_entry(add_mock)
    assert entry.action == "semantic_catalog.version.change"
    assert entry.resource == "semantic_catalog.version"
    assert entry.reason == "approved_source_mapping"
    assert entry.extra == {
        "catalog_version_id": str(catalog_version_id),
        "metric_id": "lead_conversion",
        "change_summary": ("Lead source grouping moved paid social aliases under paid leads"),
        "change_reason": "approved_source_mapping",
        "previous_catalog_version_id": str(previous_catalog_version_id),
        "changed_fields": ["source_aliases"],
        "affected_analytics": ["lead_conversion_funnel.v1", "paid_leads.v1"],
        "raw_value": "[redacted]",
        "source_field": "LeadSource",
    }


def test_explain_catalog_metric_change_includes_version_reason_and_fields() -> None:
    explanation = explain_catalog_metric_change(
        {
            "catalog_version_id": "catalog-v4",
            "previous_catalog_version_id": "catalog-v3",
            "metric_id": "lead_conversion",
            "change_summary": "Lead source grouping changed",
            "change_reason": "approved_source_mapping",
            "changed_fields": ["source_aliases", "definition"],
        }
    )

    assert explanation == (
        "lead_conversion changed in catalog version catalog-v3 -> catalog-v4: "
        "Lead source grouping changed. Reason: approved_source_mapping. "
        "Changed fields: source_aliases, definition."
    )
