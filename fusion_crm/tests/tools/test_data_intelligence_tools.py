"""Tests for Data Intelligence local tooling policy and registry exposure."""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar, cast

import pytest

from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.data_intelligence.schemas import (
    DataClass,
    DataIntelligenceAction,
    EvidenceMetricOut,
    OutputLevel,
    PersonJourneyRegistryEntryKind,
    PersonJourneyRegistryStatus,
    PolicyDecision,
    PolicyPreflightIn,
)
from packages.data_intelligence.service import (
    DataIntelligenceService,
    _evidence_gap_finding,
    _semantic_mapping_candidate,
)
from packages.interaction.models import Event
from packages.interaction.service import _payment_event_masked_sample
from packages.ops.models import Consultation, ConsultationKind, ConsultationStatus, Lead, LeadStatus
from packages.ops.service import _consultation_masked_sample, _lead_masked_sample
from packages.tools import data_intelligence_tools
from packages.tools.base import ToolContext
from packages.tools.registry import ALL_TOOLS


def test_discovery_lists_allowlisted_datasets_without_unsafe_defaults() -> None:
    discovery = DataIntelligenceService().list_datasets()

    assert discovery.policy.raw_payload_allowed is False
    assert discovery.policy.phi_allowed is False
    assert discovery.policy.export_allowed is False
    assert discovery.policy.audit_required is True
    assert {dataset.id for dataset in discovery.datasets} >= {
        "lead_source_profile",
        "identity_linkage",
        "consultation_followup",
        "treatment_revenue",
    }


def test_preflight_allows_bounded_row_sample_for_allowlisted_fields() -> None:
    result = DataIntelligenceService().preflight(
        PolicyPreflightIn(
            action=DataIntelligenceAction.BOUNDED_SAMPLE,
            dataset_id="identity_linkage",
            fields=["person_uid", "linkage_status"],
            output_level=OutputLevel.ROW_SAMPLE,
            row_limit=25,
        )
    )

    assert result.decision is PolicyDecision.ALLOW
    assert result.row_limit == 25
    assert result.raw_sql_allowed is False
    assert result.raw_payload_allowed is False
    assert result.phi_allowed is False


def test_preflight_denies_raw_payload_phi_exports_writes_and_uncapped_samples() -> None:
    result = DataIntelligenceService().preflight(
        PolicyPreflightIn(
            action=DataIntelligenceAction.BOUNDED_SAMPLE,
            dataset_id="lead_source_profile",
            fields=["lead_source", "raw_payload"],
            output_level=OutputLevel.ROW_SAMPLE,
            row_limit=101,
            include_phi=True,
            include_raw_payload=True,
            export=True,
            write=True,
        )
    )

    assert result.decision is PolicyDecision.DENY
    reasons = " ".join(result.reasons)
    assert "PHI output is denied" in reasons
    assert "Raw provider payload output is denied" in reasons
    assert "Exports are out of scope" in reasons
    assert "read-only" in reasons
    assert "raw_payload" in reasons
    assert "between 1 and 100" in reasons


def test_preflight_denies_unknown_fields_and_unknown_dataset() -> None:
    unknown_field = DataIntelligenceService().preflight(
        PolicyPreflightIn(
            action=DataIntelligenceAction.FIELD_PROFILE,
            dataset_id="lead_source_profile",
            fields=["unknown_column"],
        )
    )
    unknown_dataset = DataIntelligenceService().preflight(
        PolicyPreflightIn(
            action=DataIntelligenceAction.FIELD_PROFILE,
            dataset_id="not_real",
            fields=["lead_source"],
        )
    )

    assert unknown_field.decision is PolicyDecision.DENY
    assert unknown_dataset.decision is PolicyDecision.DENY


def test_data_intelligence_tools_are_registered_without_sql_argument() -> None:
    sample = ALL_TOOLS["data_intelligence_bounded_sample"]
    discover = ALL_TOOLS["data_intelligence_discover"]
    preflight = ALL_TOOLS["data_intelligence_preflight"]
    profile = ALL_TOOLS["data_intelligence_profile_field"]
    linkage = ALL_TOOLS["data_intelligence_linkage_coverage"]
    evidence = ALL_TOOLS["data_intelligence_evidence_coverage"]
    mapping = ALL_TOOLS["data_intelligence_semantic_mapping_proposal"]
    person_journey = ALL_TOOLS["data_intelligence_person_journey_proposals"]
    gap_brief = ALL_TOOLS["data_intelligence_gap_brief"]

    assert "data_intelligence" in sample.name
    assert "data_intelligence" in discover.name
    assert "data_intelligence" in preflight.name
    assert "data_intelligence" in profile.name
    assert "data_intelligence" in linkage.name
    assert "data_intelligence" in evidence.name
    assert "data_intelligence" in mapping.name
    assert "data_intelligence" in person_journey.name
    assert "data_intelligence" in gap_brief.name
    assert "sql" not in inspect.signature(sample.fn).parameters
    assert "sql" not in inspect.signature(discover.fn).parameters
    assert "sql" not in inspect.signature(preflight.fn).parameters
    assert "sql" not in inspect.signature(profile.fn).parameters
    assert "sql" not in inspect.signature(linkage.fn).parameters
    assert "sql" not in inspect.signature(evidence.fn).parameters
    assert "sql" not in inspect.signature(mapping.fn).parameters
    assert "sql" not in inspect.signature(person_journey.fn).parameters
    assert "sql" not in inspect.signature(gap_brief.fn).parameters
    assert "query" not in inspect.signature(sample.fn).parameters
    assert "query" not in inspect.signature(preflight.fn).parameters
    assert "query" not in inspect.signature(profile.fn).parameters
    assert "query" not in inspect.signature(linkage.fn).parameters
    assert "query" not in inspect.signature(evidence.fn).parameters
    assert "query" not in inspect.signature(mapping.fn).parameters
    assert "query" not in inspect.signature(person_journey.fn).parameters
    assert "query" not in inspect.signature(gap_brief.fn).parameters


async def test_profile_field_returns_denial_before_needing_db_session() -> None:
    preflight, profile = await DataIntelligenceService().profile_field(
        TenantId(uuid.uuid4()),
        dataset_id="lead_source_profile",
        field="raw_payload",
    )

    assert preflight.decision is PolicyDecision.DENY
    assert profile is None


async def test_linkage_coverage_denies_uncapped_samples_before_db_session() -> None:
    preflight, coverage = await DataIntelligenceService().source_linkage_coverage(
        TenantId(uuid.uuid4()),
        sample_limit=101,
    )

    assert preflight.decision is PolicyDecision.DENY
    assert coverage is None


async def test_bounded_sample_denies_uncapped_samples_before_db_session() -> None:
    preflight, sample = await DataIntelligenceService().bounded_sample(
        TenantId(uuid.uuid4()),
        dataset_id="lead_source_profile",
        row_limit=101,
    )

    assert preflight.decision is PolicyDecision.DENY
    assert sample is None


def test_evidence_coverage_preflight_allows_approved_fields() -> None:
    service = DataIntelligenceService()
    lead = service.preflight(
        PolicyPreflightIn(
            action=DataIntelligenceAction.EVIDENCE_COVERAGE,
            dataset_id="lead_source_profile",
            fields=["lead_source", "campaign", "owner_id", "location_id"],
        )
    )
    treatment = service.preflight(
        PolicyPreflightIn(
            action=DataIntelligenceAction.EVIDENCE_COVERAGE,
            dataset_id="treatment_revenue",
            fields=["payment_kind", "treatment_status"],
        )
    )

    assert lead.decision is PolicyDecision.ALLOW
    assert treatment.decision is PolicyDecision.ALLOW


def test_semantic_mapping_proposal_preflight_allows_source_fields() -> None:
    result = DataIntelligenceService().preflight(
        PolicyPreflightIn(
            action=DataIntelligenceAction.SEMANTIC_MAPPING_PROPOSAL,
            dataset_id="lead_source_profile",
            fields=["lead_source", "campaign"],
        )
    )

    assert result.decision is PolicyDecision.ALLOW
    assert result.output_level is OutputLevel.AGGREGATE
    assert result.raw_sql_allowed is False
    assert result.write_allowed is False


async def test_semantic_mapping_proposal_denies_uncapped_profile_before_db_session() -> None:
    preflight, proposal = await DataIntelligenceService().semantic_mapping_proposal(
        TenantId(uuid.uuid4()),
        top_limit=251,
    )

    assert preflight.decision is PolicyDecision.DENY
    assert proposal is None


def test_person_journey_registry_proposals_fail_closed_by_status() -> None:
    preflight, projection = DataIntelligenceService().person_journey_registry_proposals()

    assert preflight.decision is PolicyDecision.ALLOW
    assert projection is not None
    candidates = {candidate.entry.id: candidate for candidate in projection.candidates}

    approved = candidates["field.utm_source"]
    assert approved.can_submit_for_review is True
    assert approved.review_only is True
    assert approved.executable is False
    assert approved.approval_allowed is False
    assert approved.proposal is not None
    assert approved.proposal.source_type == "agent"
    assert approved.proposal.source_reference_id == "person_journey_registry:field.utm_source"

    review_only = candidates["field.gclid"]
    assert review_only.can_submit_for_review is True
    assert review_only.proposal is not None
    assert review_only.proposal.confidence == 0.55

    last_touch = candidates["field.last_touch_source"]
    assert last_touch.can_submit_for_review is True
    assert last_touch.proposal is not None
    assert last_touch.proposal.source_reference_id == (
        "person_journey_registry:field.last_touch_source"
    )
    assert "last_touch_attribution_source" == last_touch.proposal.suggested_term

    location_mismatch = candidates["field.location_mismatch"]
    assert location_mismatch.can_submit_for_review is True
    assert location_mismatch.proposal is not None
    assert location_mismatch.proposal.suggested_term == "location_evidence_mismatch"

    payment_applied = candidates["field.payment_applied_exclusion"]
    assert payment_applied.can_submit_for_review is True
    assert payment_applied.proposal is not None
    assert payment_applied.proposal.suggested_term == "payment_applied_allocation_leg"

    internal = candidates["field.unchanged_count"]
    assert internal.can_submit_for_review is False
    assert internal.proposal is None
    assert any("internal_only" in blocker for blocker in internal.blockers)

    blocked = candidates["field.raw_provider_payload"]
    assert blocked.can_submit_for_review is False
    assert blocked.proposal is None
    assert any("Raw provider payload" in blocker for blocker in blocked.blockers)

    call_ref = candidates["field.call_recording_ref"]
    assert call_ref.can_submit_for_review is False
    assert call_ref.proposal is None
    assert any("Call recording" in blocker for blocker in call_ref.blockers)

    deferred = candidates["event.contact_created"]
    assert deferred.can_submit_for_review is False
    assert deferred.proposal is None
    assert any("deferred" in blocker for blocker in deferred.blockers)


def test_person_journey_registry_projection_filters_status_and_kind() -> None:
    preflight, projection = DataIntelligenceService().person_journey_registry_proposals(
        statuses=[PersonJourneyRegistryStatus.APPROVED_CANDIDATE],
        kinds=[PersonJourneyRegistryEntryKind.EVENT],
    )

    assert preflight.decision is PolicyDecision.ALLOW
    assert projection is not None
    assert {candidate.entry.id for candidate in projection.candidates} == {
        "event.carestack_consultation",
        "event.lead_created",
        "event.opportunity_created",
        "event.opportunity_lost",
        "event.opportunity_won",
    }
    assert all(candidate.can_submit_for_review for candidate in projection.candidates)


def test_person_journey_registry_covers_lead_to_sale_and_revenue_phases() -> None:
    preflight, projection = DataIntelligenceService().person_journey_registry_proposals()

    assert preflight.decision is PolicyDecision.ALLOW
    assert projection is not None
    entries = [candidate.entry for candidate in projection.candidates]
    phases = {entry.journey_phase for entry in entries}
    source_objects = {entry.source_object for entry in entries}

    assert {
        "lead_attribution",
        "lead_capture",
        "contact_linkage",
        "account_linkage",
        "opportunity",
        "opportunity_stage",
        "sale_conversion",
        "follow_up_activity",
        "consultation",
        "treatment",
        "billing_revenue",
        "internal_health",
    }.issubset(phases)
    assert {
        "Salesforce Lead",
        "Salesforce Contact",
        "Salesforce Account",
        "Salesforce Opportunity",
        "Salesforce OpportunityHistory",
        "Salesforce Task",
        "CareStack Appointment",
        "CareStack treatment evidence",
        "CareStack accounting transaction",
    }.issubset(source_objects)
    assert all(entry.state_category for entry in entries)
    assert all(entry.transition_meaning for entry in entries)
    assert all(entry.time_semantics for entry in entries)


def test_data_intelligence_discovery_exposes_recent_attribution_fields() -> None:
    discovery = DataIntelligenceService().list_datasets()
    datasets = {dataset.id: dataset for dataset in discovery.datasets}
    lead_fields = {field.name for field in datasets["lead_source_profile"].fields}
    revenue_fields = {field.name for field in datasets["treatment_revenue"].fields}
    registry_fields = {field.name for field in datasets["person_journey_registry"].fields}

    assert {
        "last_touch_source",
        "last_touch_medium",
        "last_touch_campaign",
        "assigned_center",
        "business_unit",
        "consultation_scheduled_at",
        "location_mismatch",
    }.issubset(lead_fields)
    assert {
        "collected_amount_aggregate",
        "payment_applied_exclusion",
    }.issubset(revenue_fields)
    assert {
        "field.last_touch_source",
        "field.business_unit",
        "field.consultation_scheduled_at",
        "field.location_mismatch",
        "field.payment_applied_exclusion",
        "event.carestack_payment_applied",
    }.issubset(registry_fields)


def test_data_intelligence_discovery_exposes_manager_answer_semantic_contracts() -> None:
    discovery = DataIntelligenceService().list_datasets()
    datasets = {dataset.id: dataset for dataset in discovery.datasets}
    lead_fields = {
        field.name: field for field in datasets["lead_source_profile"].fields
    }
    revenue_fields = {
        field.name: field for field in datasets["treatment_revenue"].fields
    }
    registry_fields = {
        field.name: field for field in datasets["person_journey_registry"].fields
    }

    lead_source = lead_fields["lead_source"].semantic_contract
    business_unit = lead_fields["business_unit"].semantic_contract
    consultation_scheduled_at = lead_fields[
        "consultation_scheduled_at"
    ].semantic_contract
    location_mismatch = lead_fields["location_mismatch"].semantic_contract
    collected = revenue_fields["collected_amount_aggregate"].semantic_contract
    allocation_exclusion = registry_fields[
        "field.payment_applied_exclusion"
    ].semantic_contract

    assert lead_source.manager_answer_posture == "generated_with_caveat"
    assert lead_source.source_precedence == [
        "last_touch_source",
        "lead_source",
        "campaign",
    ]
    assert "lead_conversion" in lead_source.affected_read_models
    assert "Q01 Lead source performance" in lead_source.affected_manager_questions
    assert "lead.lead_source" in lead_source.data_quality_evidence_refs
    assert business_unit.registry_status == "review_only_taxonomy_required"
    assert "lead_conversion" in business_unit.affected_read_models
    assert "taxonomy review" in business_unit.caveats[0]
    assert consultation_scheduled_at.registry_status == "review_only_time_semantics"
    assert "consultation_followup" in consultation_scheduled_at.affected_read_models
    assert "provider-created time" in consultation_scheduled_at.caveats[0]
    assert location_mismatch.data_quality_posture == "caveat_when_present"
    assert location_mismatch.manager_answer_posture == "generated_with_caveat"
    assert collected.manager_answer_posture == "generated_with_caveat"
    assert "billing.payment_recorded" in collected.data_quality_evidence_refs
    assert allocation_exclusion.manager_answer_posture == "review_only"
    assert "treatment_revenue" in allocation_exclusion.affected_read_models
    assert allocation_exclusion.time_semantics


def test_person_journey_sale_and_revenue_entries_are_policy_gated() -> None:
    _, projection = DataIntelligenceService().person_journey_registry_proposals()
    assert projection is not None
    candidates = {candidate.entry.id: candidate for candidate in projection.candidates}

    opportunity_amount = candidates["field.opportunity_amount"]
    payment_bucket = candidates["field.payment_amount_bucket"]
    payment_recorded = candidates["event.carestack_payment_recorded"]

    assert opportunity_amount.entry.sale_revenue_posture == "sale_value_not_collected_revenue"
    assert payment_bucket.entry.sale_revenue_posture == "collected_revenue_aggregate_only"
    assert payment_recorded.entry.sale_revenue_posture == "collected_revenue_aggregate_only"
    assert opportunity_amount.executable is False
    assert payment_bucket.executable is False
    assert payment_recorded.executable is False
    assert payment_bucket.can_submit_for_review is True
    assert payment_recorded.can_submit_for_review is True
    assert DataClass.BILLING in payment_bucket.entry.data_classes


def test_person_journey_registry_preflight_denies_unknown_entry() -> None:
    result = DataIntelligenceService().preflight(
        PolicyPreflightIn(
            action=DataIntelligenceAction.PERSON_JOURNEY_PROPOSAL,
            dataset_id="person_journey_registry",
            fields=["field.not_real"],
        )
    )

    assert result.decision is PolicyDecision.DENY
    assert "field.not_real" in " ".join(result.reasons)


def test_semantic_mapping_candidate_is_review_only_and_deterministic() -> None:
    candidate = _semantic_mapping_candidate(
        source_field="lead_source",
        raw_value="Meta Facebook Lead Ads",
        evidence_count=42,
    )

    assert candidate.proposed_term == "paid_social/facebook"
    assert candidate.review_status == "proposed"
    assert candidate.confidence >= 0.9
    assert candidate.evidence_count == 42


def test_semantic_mapping_candidate_redacts_email_and_phone_like_text() -> None:
    candidate = _semantic_mapping_candidate(
        source_field="campaign",
        raw_value="Facebook lead for jane@example.com 916-555-1212",
        evidence_count=3,
    )

    assert "jane@example.com" not in candidate.raw_value
    assert "916-555-1212" not in candidate.raw_value
    assert "[redacted]" in candidate.raw_value
    assert candidate.review_status == "proposed"


def test_lead_masked_sample_masks_identifiers_and_redacts_free_text() -> None:
    person_uid = uuid.uuid4()
    lead = Lead(
        tenant_id=uuid.uuid4(),
        person_uid=person_uid,
        source="Google Ads jane@example.com 916-555-1212",
        status=LeadStatus.NEW,
        created_at=datetime(2026, 6, 1, tzinfo=UTC),
        extra={
            "sf_lead_id": "00QVw00000N8vzbMAB",
            "campaign": "Implants call 530.555.0199",
            "owner_name": "operator@example.com",
            "assigned_center": "El Dorado 916 555 1212",
        },
    )

    sample = _lead_masked_sample(lead)

    assert sample["person_uid_masked"] != str(person_uid)
    assert sample["owner_id_masked"] != "operator@example.com"
    rendered = " ".join(str(value) for value in sample.values() if value is not None)
    assert "jane@example.com" not in rendered
    assert "operator@example.com" not in rendered
    assert "916-555-1212" not in rendered
    assert "530.555.0199" not in rendered
    assert "916 555 1212" not in rendered


def test_consultation_masked_sample_masks_source_external_id() -> None:
    person_uid = uuid.uuid4()
    external_id = "CS-APPT-123456789"
    consultation = Consultation(
        tenant_id=uuid.uuid4(),
        person_uid=person_uid,
        source_provider="carestack",
        source_instance="carestack-main",
        external_id=external_id,
        scheduled_at=datetime(2026, 6, 1, tzinfo=UTC),
        status=ConsultationStatus.COMPLETED,
        consultation_kind=ConsultationKind.INITIAL,
    )

    sample = _consultation_masked_sample(consultation)

    assert sample["person_uid_masked"] != str(person_uid)
    assert sample["source_external_id_masked"] != external_id
    assert "external_id" not in sample
    assert "phone" not in sample
    assert "email" not in sample
    assert "name" not in sample


def test_payment_event_masked_sample_buckets_amount_and_masks_source_id() -> None:
    person_uid = uuid.uuid4()
    source_external_id = "CS-PAYMENT-123456789"
    event = Event(
        tenant_id=uuid.uuid4(),
        person_uid=person_uid,
        kind="payment_recorded",
        source_provider="carestack",
        source_kind="carestack_accounting_transaction",
        source_external_id=source_external_id,
        data_class="billing",
        review_status="auto",
        occurred_at=datetime(2026, 6, 1, tzinfo=UTC),
        summary="Payment recorded in CareStack CS-PAYMENT-123456789",
        payload={"amount": "425.67", "location_id": str(uuid.uuid4())},
    )

    sample = _payment_event_masked_sample(event)

    assert sample["person_uid_masked"] != str(person_uid)
    assert sample["source_external_id_masked"] != source_external_id
    assert sample["amount_bucket"] == "100-499"
    assert "amount" not in sample
    assert "payload" not in sample


def test_gap_brief_preflight_allows_approved_datasets() -> None:
    service = DataIntelligenceService()
    result = service.preflight(
        PolicyPreflightIn(
            action=DataIntelligenceAction.GAP_BRIEF,
            dataset_id="consultation_followup",
            fields=["consultation_status", "scheduled_at", "location_id"],
        )
    )

    assert result.decision is PolicyDecision.ALLOW
    assert result.raw_sql_allowed is False
    assert result.write_allowed is False


async def test_gap_brief_denies_uncapped_profile_before_db_session() -> None:
    preflights, brief = await DataIntelligenceService().gap_brief(
        TenantId(uuid.uuid4()),
        top_limit=251,
    )

    assert any(preflight.decision is PolicyDecision.DENY for preflight in preflights)
    assert brief is None


def test_gap_brief_evidence_finding_is_non_sensitive_summary() -> None:
    finding = _evidence_gap_finding(
        metric=EvidenceMetricOut(
            key="lead.lead_source",
            label="Lead source evidence",
            total_count=100,
            evidence_count=60,
            missing_count=40,
            coverage_rate=0.6,
            data_classes=[DataClass.OPS],
        )
    )

    assert finding is not None
    assert finding.severity == "high"
    assert "Lead source evidence" in finding.summary
    assert any("Lead source" in question for question in finding.impacted_questions)


async def test_data_intelligence_preflight_audit_payload_includes_policy_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeAuditService.records = []
    monkeypatch.setattr(data_intelligence_tools, "AuditService", _FakeAuditService)
    ctx = ToolContext(
        principal=_principal(),
        session=cast(Any, object()),
    )

    await data_intelligence_tools.data_intelligence_preflight(
        ctx,
        action=DataIntelligenceAction.BOUNDED_SAMPLE,
        dataset_id="lead_source_profile",
        fields=["lead_source", "raw_payload"],
        output_level=OutputLevel.ROW_SAMPLE,
        row_limit=101,
        include_phi=True,
        include_raw_payload=True,
        export=True,
        write=True,
    )

    assert len(_FakeAuditService.records) == 1
    record = _FakeAuditService.records[0]
    extra = record["extra"]
    assert record["tool_name"] == "data_intelligence_preflight"
    assert extra["audit_version"] == "data_intelligence_v1"
    assert extra["decision"] is PolicyDecision.DENY
    assert extra["dataset_id"] == "lead_source_profile"
    assert extra["dataset_ids"] == ["lead_source_profile"]
    assert extra["output_level"] is OutputLevel.ROW_SAMPLE
    assert extra["row_limit"] == 101
    assert extra["top_limit"] == 50
    assert extra["fields"] == ["lead_source", "raw_payload"]
    assert extra["field_count"] == 2
    assert DataClass.OPS in extra["data_classes"]
    assert "person_uid" in extra["masks"]
    assert extra["audit_required"] is True
    assert extra["raw_sql_allowed"] is False
    assert extra["raw_payload_allowed"] is False
    assert extra["phi_allowed"] is False
    assert extra["export_allowed"] is False
    assert extra["write_allowed"] is False
    assert extra["result_posture"] == "policy_preflight"


async def test_data_intelligence_gap_brief_denial_is_audited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeAuditService.records = []
    monkeypatch.setattr(data_intelligence_tools, "AuditService", _FakeAuditService)
    ctx = ToolContext(
        principal=_principal(),
        session=cast(Any, object()),
    )

    await data_intelligence_tools.data_intelligence_gap_brief(ctx, top_limit=251)

    assert len(_FakeAuditService.records) == 1
    record = _FakeAuditService.records[0]
    extra = record["extra"]
    assert record["tool_name"] == "data_intelligence_gap_brief"
    assert extra["audit_version"] == "data_intelligence_v1"
    assert PolicyDecision.DENY in extra["decisions"]
    assert "lead_source_profile" in extra["dataset_ids"]
    assert DataClass.BILLING in extra["data_classes"]
    assert extra["top_limits"] == [251, 251, 251, 251]
    assert extra["finding_count"] == 0
    assert extra["result_posture"] == "denied"
    assert extra["raw_sql_allowed"] is False
    assert extra["raw_payload_allowed"] is False
    assert extra["phi_allowed"] is False
    assert extra["export_allowed"] is False
    assert extra["write_allowed"] is False


async def test_person_journey_registry_projection_audit_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeAuditService.records = []
    monkeypatch.setattr(data_intelligence_tools, "AuditService", _FakeAuditService)
    ctx = ToolContext(
        principal=_principal(),
        session=cast(Any, object()),
    )

    await data_intelligence_tools.data_intelligence_person_journey_proposals(
        ctx,
        statuses=[PersonJourneyRegistryStatus.BLOCKED],
    )

    assert len(_FakeAuditService.records) == 1
    record = _FakeAuditService.records[0]
    extra = record["extra"]
    assert record["tool_name"] == "data_intelligence_person_journey_proposals"
    assert extra["audit_version"] == "data_intelligence_v1"
    assert extra["decision"] is PolicyDecision.ALLOW
    assert extra["dataset_id"] == "person_journey_registry"
    assert extra["candidate_count"] == 3
    assert extra["submittable_candidate_count"] == 0
    assert extra["blocked_candidate_count"] == 3
    assert extra["result_posture"] == "review_only_person_journey_registry_projection"
    assert extra["raw_sql_allowed"] is False
    assert extra["raw_payload_allowed"] is False
    assert extra["phi_allowed"] is False
    assert extra["export_allowed"] is False
    assert extra["write_allowed"] is False


def _principal() -> Principal:
    tenant_id = TenantId(uuid.uuid4())
    return Principal(
        id=uuid.uuid4(),
        email="agent@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
    )


class _FakeAuditService:
    records: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, session: object) -> None:
        self._session = session

    async def record_tool_call(
        self,
        *,
        principal: Principal,
        tool_name: str,
        person_uid: object | None = None,
        reason: str | None = None,
        extra: dict[str, object] | None = None,
    ) -> object:
        self.records.append(
            {
                "principal": principal,
                "tool_name": tool_name,
                "person_uid": person_uid,
                "reason": reason,
                "extra": extra or {},
            }
        )
        return object()
