"""Service-owned Data Intelligence policy and discovery contract."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId
from packages.data_intelligence.schemas import (
    BoundedSampleOut,
    DataClass,
    DataIntelligenceAction,
    DatasetDiscoveryOut,
    DatasetPolicyOut,
    EvidenceCoverageOut,
    EvidenceMetricOut,
    FieldPolicyOut,
    FieldProfileOut,
    GapBriefFindingOut,
    GapBriefOut,
    LinkageCoverageOut,
    LinkageExampleOut,
    OutputLevel,
    PersonJourneyCatalogProposalDraftOut,
    PersonJourneyProposalCandidateOut,
    PersonJourneyRegistryEntryKind,
    PersonJourneyRegistryEntryOut,
    PersonJourneyRegistryProposalOut,
    PersonJourneyRegistryStatus,
    PolicyDecision,
    PolicyDefaultsOut,
    PolicyPreflightIn,
    PolicyPreflightOut,
    SemanticFieldContractOut,
    SemanticMappingCandidateOut,
    SemanticMappingProposalOut,
    TopValueOut,
)
from packages.identity.service import IdentityService
from packages.interaction.service import InteractionService
from packages.ops.service import OpsService

_DEFAULT_ROW_SAMPLE_LIMIT = 25
_HARD_ROW_SAMPLE_CAP = 100
_DEFAULT_TOP_VALUE_CAP = 50
_HARD_PROFILE_GROUP_CAP = 250

_POLICY_DEFAULTS = PolicyDefaultsOut(
    environment="local/dev first",
    role="authorized_internal_builder",
    row_level_samples="allowed_with_caps_masks_and_audit",
    default_row_sample_limit=_DEFAULT_ROW_SAMPLE_LIMIT,
    hard_row_sample_cap=_HARD_ROW_SAMPLE_CAP,
    default_top_value_cap=_DEFAULT_TOP_VALUE_CAP,
    hard_profile_group_cap=_HARD_PROFILE_GROUP_CAP,
    default_date_window_days=365,
    export_allowed=False,
    raw_payload_allowed=False,
    phi_allowed=False,
    audit_required=True,
)

_COMMON_DENIED_FIELDS = [
    "raw_payload",
    "raw_body",
    "payload",
    "clinical_notes",
    "diagnosis",
    "procedure_notes",
    "treatment_notes",
    "patient_dob",
    "ssn",
]
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\d)")


class DataIntelligenceService:
    """Own executable policy for Data Intelligence local tooling.

    This first slice is intentionally metadata-only. Later profiling methods
    will use package-local repositories behind this service; tools still call
    the service and never accept SQL.
    """

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    def list_datasets(self) -> DatasetDiscoveryOut:
        return DatasetDiscoveryOut(policy=_POLICY_DEFAULTS, datasets=list(_DATASETS))

    def preflight(self, request: PolicyPreflightIn) -> PolicyPreflightOut:
        dataset = _dataset_by_id(request.dataset_id)
        reasons: list[str] = []

        if dataset is None:
            return PolicyPreflightOut(
                decision=PolicyDecision.DENY,
                reasons=[f"Unknown dataset: {request.dataset_id}"],
                action=request.action,
                dataset_id=request.dataset_id,
                output_level=request.output_level,
                row_limit=request.row_limit,
                top_limit=_resolve_top_limit(request.top_limit),
                data_classes=[],
                fields=request.fields,
                masks=[],
            )

        if request.action not in dataset.allowed_actions:
            reasons.append(f"Action {request.action} is not allowlisted for {dataset.id}.")
        if request.output_level not in dataset.allowed_output_levels:
            reasons.append(
                f"Output level {request.output_level} is not allowlisted for {dataset.id}."
            )
        if request.include_phi:
            reasons.append("PHI output is denied in Data Intelligence V1.")
        if request.include_raw_payload:
            reasons.append("Raw provider payload output is denied.")
        if request.export:
            reasons.append("Exports are out of scope for this mission.")
        if request.write:
            reasons.append("Data Intelligence tools are read-only in V1.")

        requested_fields = _unique_fields(request.fields)
        allowed_field_names = {field.name for field in dataset.fields}
        denied_requested = [
            field
            for field in requested_fields
            if field in dataset.denied_fields or field not in allowed_field_names
        ]
        if denied_requested:
            reasons.append(
                "Fields are not allowlisted for Data Intelligence V1: "
                + ", ".join(sorted(denied_requested))
            )

        row_limit = _resolve_row_limit(request.output_level, request.row_limit)
        if row_limit is not None and (row_limit < 1 or row_limit > dataset.hard_row_sample_cap):
            reasons.append(
                f"Row sample limit must be between 1 and {dataset.hard_row_sample_cap}."
            )

        top_limit = _resolve_top_limit(request.top_limit)
        if top_limit < 1 or top_limit > dataset.hard_profile_group_cap:
            reasons.append(
                f"Top value limit must be between 1 and {dataset.hard_profile_group_cap}."
            )

        decision = PolicyDecision.DENY if reasons else PolicyDecision.ALLOW
        if not reasons:
            reasons.append("Request matches the approved Data Intelligence V1 policy.")

        return PolicyPreflightOut(
            decision=decision,
            reasons=reasons,
            action=request.action,
            dataset_id=dataset.id,
            output_level=request.output_level,
            row_limit=row_limit,
            top_limit=top_limit,
            data_classes=dataset.data_classes,
            fields=requested_fields,
            masks=dataset.masks,
        )

    async def profile_field(
        self,
        tenant_id: TenantId,
        *,
        dataset_id: str,
        field: str,
        top_limit: int | None = None,
    ) -> tuple[PolicyPreflightOut, FieldProfileOut | None]:
        """Profile one allowlisted field through existing service methods."""
        preflight = self.preflight(
            PolicyPreflightIn(
                action=DataIntelligenceAction.FIELD_PROFILE,
                dataset_id=dataset_id,
                fields=[field],
                output_level=OutputLevel.AGGREGATE,
                top_limit=top_limit,
            )
        )
        if preflight.decision is PolicyDecision.DENY:
            return preflight, None
        session = self._session
        if session is None:
            raise ValidationError("Data Intelligence profiling requires a DB session")

        dataset = _dataset_by_id(dataset_id)
        field_policy = _field_policy(dataset, field)
        if dataset is None or field_policy is None:
            return preflight, None

        profile = await self._profile_supported_field(
            tenant_id,
            session=session,
            dataset=dataset,
            field_policy=field_policy,
            top_limit=preflight.top_limit,
        )
        return preflight, profile

    async def source_linkage_coverage(
        self,
        tenant_id: TenantId,
        *,
        sample_limit: int | None = None,
    ) -> tuple[PolicyPreflightOut, LinkageCoverageOut | None]:
        """Return Salesforce-to-CareStack source linkage coverage."""
        resolved_sample_limit = sample_limit or _DEFAULT_ROW_SAMPLE_LIMIT
        preflight = self.preflight(
            PolicyPreflightIn(
                action=DataIntelligenceAction.LINKAGE_COVERAGE,
                dataset_id="identity_linkage",
                fields=[
                    "person_uid",
                    "salesforce_lead_id",
                    "carestack_patient_id",
                    "linkage_status",
                ],
                output_level=OutputLevel.ROW_SAMPLE,
                row_limit=resolved_sample_limit,
            )
        )
        if preflight.decision is PolicyDecision.DENY:
            return preflight, None
        session = self._session
        if session is None:
            raise ValidationError("Data Intelligence linkage coverage requires a DB session")

        coverage = await IdentityService(session).get_source_linkage_coverage(
            tenant_id,
            sample_limit=preflight.row_limit or resolved_sample_limit,
        )
        return preflight, LinkageCoverageOut(
            dataset_id="identity_linkage",
            decision=PolicyDecision.ALLOW,
            sample_limit=preflight.row_limit or resolved_sample_limit,
            data_classes=preflight.data_classes,
            total_persons=coverage.total_persons,
            salesforce_person_count=coverage.salesforce_person_count,
            carestack_person_count=coverage.carestack_person_count,
            linked_salesforce_carestack_count=coverage.linked_salesforce_carestack_count,
            salesforce_only_count=coverage.salesforce_only_count,
            carestack_only_count=coverage.carestack_only_count,
            salesforce_to_carestack_rate=coverage.salesforce_to_carestack_rate,
            carestack_to_salesforce_rate=coverage.carestack_to_salesforce_rate,
            examples=[
                LinkageExampleOut(
                    person_uid_masked=example.person_uid_masked,
                    linkage_status=example.linkage_status,
                    source_systems=example.source_systems,
                    salesforce_source_id_masked=example.salesforce_source_id_masked,
                    carestack_source_id_masked=example.carestack_source_id_masked,
                )
                for example in coverage.examples
            ],
            warnings=[
                "Examples are bounded and masked; no names, phone numbers, emails, or raw payloads are returned."
            ],
        )

    async def evidence_coverage(
        self,
        tenant_id: TenantId,
    ) -> tuple[list[PolicyPreflightOut], EvidenceCoverageOut | None]:
        """Return mission-wide evidence coverage for semantic analytics."""
        preflights = [
            self.preflight(
                PolicyPreflightIn(
                    action=DataIntelligenceAction.EVIDENCE_COVERAGE,
                    dataset_id="lead_source_profile",
                    fields=["lead_source", "campaign", "owner_id", "location_id"],
                    output_level=OutputLevel.AGGREGATE,
                )
            ),
            self.preflight(
                PolicyPreflightIn(
                    action=DataIntelligenceAction.EVIDENCE_COVERAGE,
                    dataset_id="consultation_followup",
                    fields=["consultation_status", "scheduled_at", "location_id"],
                    output_level=OutputLevel.AGGREGATE,
                )
            ),
            self.preflight(
                PolicyPreflightIn(
                    action=DataIntelligenceAction.EVIDENCE_COVERAGE,
                    dataset_id="treatment_revenue",
                    fields=["payment_kind", "treatment_status"],
                    output_level=OutputLevel.AGGREGATE,
                )
            ),
        ]
        if any(preflight.decision is PolicyDecision.DENY for preflight in preflights):
            return preflights, None
        session = self._session
        if session is None:
            raise ValidationError("Data Intelligence evidence coverage requires a DB session")

        ops = OpsService(session)
        interaction = InteractionService(session)
        metrics: list[EvidenceMetricOut] = []

        for field, label in (
            ("lead_source", "Lead source evidence"),
            ("campaign", "Campaign evidence"),
            ("owner_id", "Owner evidence"),
            ("location_id", "Lead location evidence"),
        ):
            profile = await ops.get_lead_field_profile(tenant_id, field=field)
            metrics.append(
                _evidence_metric_from_profile(
                    key=f"lead.{field}",
                    label=label,
                    total_count=profile.row_count,
                    null_count=profile.null_count,
                    data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
                    warnings=(
                        ["Lead location is currently profiled from assigned center evidence."]
                        if field == "location_id"
                        else []
                    ),
                )
            )

        for field, label in (
            ("consultation_status", "Consultation status evidence"),
            ("scheduled_at", "Consultation scheduled date evidence"),
            ("location_id", "Consultation location evidence"),
        ):
            profile = await ops.get_consultation_field_profile(tenant_id, field=field)
            metrics.append(
                _evidence_metric_from_profile(
                    key=f"consultation.{field}",
                    label=label,
                    total_count=profile.row_count,
                    null_count=profile.null_count,
                    data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
                )
            )

        payment_profile = await interaction.get_payment_event_field_profile(
            tenant_id,
            field="payment_kind",
        )
        metrics.append(
            _evidence_metric_from_profile(
                key="billing.payment_kind",
                label="Payment kind evidence",
                total_count=payment_profile.row_count,
                null_count=payment_profile.null_count,
                data_classes=[DataClass.BILLING, DataClass.INTEGRATION_METADATA],
                warnings=["Billing evidence is aggregate-only and excludes raw payment rows."],
            )
        )

        payment_aggregate = await interaction.get_treatment_payment_aggregate(
            tenant_id,
            source_provider="carestack",
        )
        treatment_total = (
            payment_aggregate.treatment_presented_count
            + payment_aggregate.treatment_completed_count
        )
        metrics.extend(
            [
                _count_metric(
                    key="treatment.treatment_status",
                    label="Treatment status evidence",
                    count=treatment_total,
                    data_classes=[DataClass.OPS, DataClass.BILLING],
                    warnings=[
                        "Treatment status coverage is event-count based in V1."
                    ],
                ),
                _count_metric(
                    key="billing.invoice_created",
                    label="Invoice evidence",
                    count=payment_aggregate.invoice_count,
                    data_classes=[DataClass.BILLING],
                ),
                _count_metric(
                    key="billing.payment_recorded",
                    label="Payment recorded evidence",
                    count=payment_aggregate.payment_event_count,
                    data_classes=[DataClass.BILLING],
                ),
            ]
        )

        return preflights, EvidenceCoverageOut(
            decision=PolicyDecision.ALLOW,
            metrics=metrics,
            warnings=[
                "Evidence coverage is aggregate-only; no raw provider payloads or row-level PHI are returned."
            ],
        )

    async def bounded_sample(
        self,
        tenant_id: TenantId,
        *,
        dataset_id: str,
        row_limit: int | None = None,
    ) -> tuple[PolicyPreflightOut, BoundedSampleOut | None]:
        """Return a bounded, masked row sample for one approved dataset."""
        dataset = _dataset_by_id(dataset_id)
        fields = [field.name for field in dataset.fields] if dataset is not None else []
        resolved_row_limit = row_limit or _DEFAULT_ROW_SAMPLE_LIMIT
        preflight = self.preflight(
            PolicyPreflightIn(
                action=DataIntelligenceAction.BOUNDED_SAMPLE,
                dataset_id=dataset_id,
                fields=fields,
                output_level=OutputLevel.ROW_SAMPLE,
                row_limit=resolved_row_limit,
            )
        )
        if preflight.decision is PolicyDecision.DENY:
            return preflight, None
        session = self._session
        if session is None:
            raise ValidationError("Data Intelligence bounded samples require a DB session")

        limit = preflight.row_limit or resolved_row_limit
        rows: list[dict[str, object]]
        warnings = [
            "Rows are bounded and masked; no names, phone numbers, emails, raw payloads, or PHI are returned."
        ]
        if dataset_id == "identity_linkage":
            coverage = await IdentityService(session).get_source_linkage_coverage(
                tenant_id,
                sample_limit=limit,
            )
            rows = [example.model_dump(mode="json") for example in coverage.examples]
        elif dataset_id == "lead_source_profile":
            rows = await OpsService(session).get_lead_masked_samples(tenant_id, limit=limit)
        elif dataset_id == "consultation_followup":
            rows = await OpsService(session).get_consultation_masked_samples(
                tenant_id,
                limit=limit,
            )
        elif dataset_id == "treatment_revenue":
            rows = await InteractionService(session).get_payment_event_masked_samples(
                tenant_id,
                limit=limit,
            )
            warnings.append("Billing samples use amount buckets and masked references only.")
        else:
            return preflight, None

        return preflight, BoundedSampleOut(
            dataset_id=dataset_id,
            decision=PolicyDecision.ALLOW,
            row_limit=limit,
            row_count=len(rows),
            data_classes=preflight.data_classes,
            masks=preflight.masks,
            rows=rows,
            warnings=warnings,
        )

    async def semantic_mapping_proposal(
        self,
        tenant_id: TenantId,
        *,
        top_limit: int | None = None,
    ) -> tuple[PolicyPreflightOut, SemanticMappingProposalOut | None]:
        """Propose review-only semantic mappings from CRM-safe source evidence."""
        preflight = self.preflight(
            PolicyPreflightIn(
                action=DataIntelligenceAction.SEMANTIC_MAPPING_PROPOSAL,
                dataset_id="lead_source_profile",
                fields=["lead_source", "campaign"],
                output_level=OutputLevel.AGGREGATE,
                top_limit=top_limit,
            )
        )
        if preflight.decision is PolicyDecision.DENY:
            return preflight, None
        session = self._session
        if session is None:
            raise ValidationError(
                "Data Intelligence semantic mapping proposals require a DB session"
            )

        ops = OpsService(session)
        candidates: list[SemanticMappingCandidateOut] = []
        seen: set[tuple[str, str]] = set()
        for field in ("lead_source", "campaign"):
            profile = await ops.get_lead_field_profile(
                tenant_id,
                field=field,
                limit=preflight.top_limit,
            )
            for bucket in profile.top_values:
                raw_value = str(bucket.value).strip()
                if not raw_value:
                    continue
                seen_key = (field, raw_value.lower())
                if seen_key in seen:
                    continue
                seen.add(seen_key)
                candidates.append(
                    _semantic_mapping_candidate(
                        source_field=field,
                        raw_value=raw_value,
                        evidence_count=int(bucket.count),
                    )
                )

        candidates.sort(
            key=lambda candidate: (
                candidate.proposed_term == "unknown/unmapped",
                -candidate.confidence,
                -candidate.evidence_count,
                candidate.source_field,
                candidate.raw_value,
            )
        )
        return preflight, SemanticMappingProposalOut(
            dataset_id="lead_source_profile",
            decision=PolicyDecision.ALLOW,
            source_fields=["lead_source", "campaign"],
            top_limit=preflight.top_limit,
            candidates=candidates,
            warnings=[
                "Mapping proposals are review-only. They do not mutate the semantic catalog.",
                "Only CRM-safe aggregate source and campaign values are inspected.",
            ],
        )

    def person_journey_registry_proposals(
        self,
        *,
        statuses: list[PersonJourneyRegistryStatus] | None = None,
        kinds: list[PersonJourneyRegistryEntryKind] | None = None,
    ) -> tuple[PolicyPreflightOut, PersonJourneyRegistryProposalOut | None]:
        """Project person-journey registry entries into review-only proposals."""
        entries = _filtered_person_journey_registry(statuses=statuses, kinds=kinds)
        preflight = self.preflight(
            PolicyPreflightIn(
                action=DataIntelligenceAction.PERSON_JOURNEY_PROPOSAL,
                dataset_id="person_journey_registry",
                fields=[entry.id for entry in entries],
                output_level=OutputLevel.AGGREGATE,
            )
        )
        if preflight.decision is PolicyDecision.DENY:
            return preflight, None

        candidates = [_person_journey_proposal_candidate(entry) for entry in entries]
        return preflight, PersonJourneyRegistryProposalOut(
            dataset_id="person_journey_registry",
            decision=PolicyDecision.ALLOW,
            source_fields=[entry.source_field for entry in entries],
            candidates=candidates,
            warnings=[
                "Person journey registry proposals are review-only and do not mutate the Semantic Catalog.",
                "Executable manager answers, charts, reports, and exports must wait for approved catalog versions and read-model/query binding.",
                "Blocked, internal-only, and deferred entries are included for reviewer visibility but cannot be submitted as approval candidates by this projection.",
            ],
        )

    async def gap_brief(
        self,
        tenant_id: TenantId,
        *,
        top_limit: int | None = None,
    ) -> tuple[list[PolicyPreflightOut], GapBriefOut | None]:
        """Summarize non-sensitive Data Intelligence gaps for follow-up work."""
        preflights = [
            self.preflight(
                PolicyPreflightIn(
                    action=DataIntelligenceAction.GAP_BRIEF,
                    dataset_id="lead_source_profile",
                    fields=["lead_source", "campaign", "owner_id", "location_id"],
                    output_level=OutputLevel.AGGREGATE,
                    top_limit=top_limit,
                )
            ),
            self.preflight(
                PolicyPreflightIn(
                    action=DataIntelligenceAction.GAP_BRIEF,
                    dataset_id="identity_linkage",
                    fields=["person_uid", "linkage_status", "source_provider"],
                    output_level=OutputLevel.AGGREGATE,
                    top_limit=top_limit,
                )
            ),
            self.preflight(
                PolicyPreflightIn(
                    action=DataIntelligenceAction.GAP_BRIEF,
                    dataset_id="consultation_followup",
                    fields=["consultation_status", "scheduled_at", "location_id"],
                    output_level=OutputLevel.AGGREGATE,
                    top_limit=top_limit,
                )
            ),
            self.preflight(
                PolicyPreflightIn(
                    action=DataIntelligenceAction.GAP_BRIEF,
                    dataset_id="treatment_revenue",
                    fields=["payment_kind", "treatment_status"],
                    output_level=OutputLevel.AGGREGATE,
                    top_limit=top_limit,
                )
            ),
        ]
        if any(preflight.decision is PolicyDecision.DENY for preflight in preflights):
            return preflights, None

        evidence_preflights, evidence = await self.evidence_coverage(tenant_id)
        mapping_preflight, mapping = await self.semantic_mapping_proposal(
            tenant_id,
            top_limit=top_limit,
        )
        linkage_preflight, linkage = await self.source_linkage_coverage(
            tenant_id,
            sample_limit=1,
        )
        all_preflights = [
            *preflights,
            *evidence_preflights,
            mapping_preflight,
            linkage_preflight,
        ]
        if (
            any(preflight.decision is PolicyDecision.DENY for preflight in all_preflights)
            or evidence is None
            or mapping is None
            or linkage is None
        ):
            return all_preflights, None

        findings: list[GapBriefFindingOut] = []
        for metric in evidence.metrics:
            finding = _evidence_gap_finding(metric)
            if finding is not None:
                findings.append(finding)

        findings.extend(_semantic_mapping_gap_findings(mapping))
        linkage_finding = _linkage_gap_finding(linkage)
        if linkage_finding is not None:
            findings.append(linkage_finding)

        findings.sort(key=lambda finding: (_severity_rank(finding.severity), finding.category))
        recommended_titles = _recommended_linear_titles(findings)
        if not findings:
            recommended_titles = []
            findings.append(
                GapBriefFindingOut(
                    category="no_critical_gap_detected",
                    severity="info",
                    summary="No critical Data Intelligence V1 gaps were detected.",
                    evidence=[
                        "Evidence, linkage, and semantic mapping checks returned within V1 thresholds."
                    ],
                    impacted_questions=[],
                    recommendation="Continue with the next approved Data Intelligence issue.",
                )
            )

        return all_preflights, GapBriefOut(
            decision=PolicyDecision.ALLOW,
            generated_from=[
                "data_intelligence_evidence_coverage",
                "data_intelligence_semantic_mapping_proposal",
                "data_intelligence_linkage_coverage",
            ],
            findings=findings,
            recommended_linear_titles=recommended_titles,
            warnings=[
                "Gap briefs are non-sensitive summaries. They do not expose PHI, raw payloads, or uncapped rows.",
                "Recommendations are planning aids and require human review before implementation.",
            ],
        )

    async def _profile_supported_field(
        self,
        tenant_id: TenantId,
        *,
        session: AsyncSession,
        dataset: DatasetPolicyOut,
        field_policy: FieldPolicyOut,
        top_limit: int,
    ) -> FieldProfileOut:
        if dataset.id == "lead_source_profile":
            ops_profile = await OpsService(session).get_lead_field_profile(
                tenant_id,
                field=field_policy.name,
                limit=top_limit,
            )
            warnings = []
            if field_policy.name == "location_id":
                warnings.append(
                    "V1 profiles lead location through Salesforce assigned center evidence."
                )
            return _profile_from_domain_profile(
                dataset=dataset,
                field_policy=field_policy,
                profile=ops_profile,
                warnings=warnings,
            )

        if dataset.id == "consultation_followup" and field_policy.name in {
            "consultation_status",
            "source_provider",
            "scheduled_at",
            "location_id",
        }:
            consultation_profile = await OpsService(session).get_consultation_field_profile(
                tenant_id,
                field=field_policy.name,
                limit=top_limit,
            )
            return _profile_from_domain_profile(
                dataset=dataset,
                field_policy=field_policy,
                profile=consultation_profile,
            )

        if dataset.id == "treatment_revenue" and field_policy.name == "payment_kind":
            payment_profile = await InteractionService(session).get_payment_event_field_profile(
                tenant_id,
                field=field_policy.name,
                limit=top_limit,
            )
            return _profile_from_domain_profile(
                dataset=dataset,
                field_policy=field_policy,
                profile=payment_profile,
                warnings=[
                    "Billing field profile is aggregate-only in V1 and does not expose payment rows."
                ],
            )

        return FieldProfileOut(
            dataset_id=dataset.id,
            field=field_policy.name,
            decision=PolicyDecision.CLARIFY,
            row_count=0,
            null_rate_posture="not_implemented_for_this_field_in_v1",
            top_values=[],
            data_class=field_policy.data_class,
            source_system=field_policy.source_system,
            masked_in_samples=field_policy.masked_in_samples,
            billing_sensitive=field_policy.billing_sensitive,
            warnings=[
                "This field is allowlisted, but no service-owned profile method exists yet."
            ],
        )


def _dataset_by_id(dataset_id: str) -> DatasetPolicyOut | None:
    for dataset in _DATASETS:
        if dataset.id == dataset_id:
            return dataset
    return None


def _field_policy(dataset: DatasetPolicyOut | None, field: str) -> FieldPolicyOut | None:
    if dataset is None:
        return None
    for candidate in dataset.fields:
        if candidate.name == field:
            return candidate
    return None


def _unique_fields(fields: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    clean_fields: list[str] = []
    for field in fields:
        clean = field.strip()
        if clean and clean not in seen:
            clean_fields.append(clean)
            seen.add(clean)
    return clean_fields


def _resolve_row_limit(output_level: OutputLevel, row_limit: int | None) -> int | None:
    if output_level == OutputLevel.AGGREGATE:
        return None
    return row_limit if row_limit is not None else _DEFAULT_ROW_SAMPLE_LIMIT


def _resolve_top_limit(top_limit: int | None) -> int:
    return top_limit if top_limit is not None else _DEFAULT_TOP_VALUE_CAP


def _field(
    name: str,
    *,
    data_class: DataClass,
    source_system: str,
    description: str,
    output_levels: list[OutputLevel] | None = None,
    masked_in_samples: bool = False,
    billing_sensitive: bool = False,
    business_meaning: str | None = None,
    source_precedence: list[str] | None = None,
    time_semantics: str = "Uses the service-owned read-model time semantics for any manager answer.",
    registry_status: str = "approved_dataset_field",
    manager_answer_posture: str = "generated_with_caveat",
    affected_read_models: list[str] | None = None,
    affected_manager_questions: list[str] | None = None,
    data_quality_evidence_refs: list[str] | None = None,
    data_quality_posture: str = "aggregate_evidence_required",
    caveats: list[str] | None = None,
) -> FieldPolicyOut:
    return FieldPolicyOut(
        name=name,
        data_class=data_class,
        source_system=source_system,
        description=description,
        output_levels=output_levels or [OutputLevel.AGGREGATE, OutputLevel.ROW_SAMPLE],
        masked_in_samples=masked_in_samples,
        billing_sensitive=billing_sensitive,
        semantic_contract=SemanticFieldContractOut(
            business_meaning=business_meaning or description,
            source_precedence=source_precedence or [source_system],
            time_semantics=time_semantics,
            registry_status=registry_status,
            manager_answer_posture=manager_answer_posture,
            affected_read_models=affected_read_models or [],
            affected_manager_questions=affected_manager_questions or [],
            data_quality_evidence_refs=data_quality_evidence_refs or [],
            data_quality_posture=data_quality_posture,
            caveats=caveats or [],
        ),
    )


def _profile_from_domain_profile(
    *,
    dataset: DatasetPolicyOut,
    field_policy: FieldPolicyOut,
    profile: Any,
    warnings: list[str] | None = None,
) -> FieldProfileOut:
    row_count = int(profile.row_count)
    null_count = int(profile.null_count)
    return FieldProfileOut(
        dataset_id=dataset.id,
        field=field_policy.name,
        decision=PolicyDecision.ALLOW,
        row_count=row_count,
        null_count=null_count,
        null_rate=(null_count / row_count) if row_count else None,
        null_rate_posture="computed",
        top_values=[
            TopValueOut(value=str(bucket.value), count=int(bucket.count))
            for bucket in profile.top_values
        ],
        data_class=field_policy.data_class,
        source_system=field_policy.source_system,
        masked_in_samples=field_policy.masked_in_samples,
        billing_sensitive=field_policy.billing_sensitive,
        warnings=warnings or [],
    )


def _evidence_metric_from_profile(
    *,
    key: str,
    label: str,
    total_count: int,
    null_count: int,
    data_classes: list[DataClass],
    warnings: list[str] | None = None,
) -> EvidenceMetricOut:
    evidence_count = max(total_count - null_count, 0)
    return EvidenceMetricOut(
        key=key,
        label=label,
        total_count=total_count,
        evidence_count=evidence_count,
        missing_count=null_count,
        coverage_rate=(evidence_count / total_count) if total_count else None,
        data_classes=data_classes,
        warnings=warnings or [],
    )


def _count_metric(
    *,
    key: str,
    label: str,
    count: int,
    data_classes: list[DataClass],
    warnings: list[str] | None = None,
) -> EvidenceMetricOut:
    return EvidenceMetricOut(
        key=key,
        label=label,
        total_count=count,
        evidence_count=count,
        missing_count=0,
        coverage_rate=1.0 if count else None,
        data_classes=data_classes,
        warnings=warnings or [],
    )


def _semantic_mapping_candidate(
    *,
    source_field: str,
    raw_value: str,
    evidence_count: int,
) -> SemanticMappingCandidateOut:
    raw_value = _redact_sensitive_text(raw_value).strip()
    normalized = raw_value.lower()
    proposed_term = "unknown/unmapped"
    confidence = 0.5
    rationale = "No deterministic V1 mapping rule matched this value."

    mapping_rules = (
        (
            ("facebook", "meta", "instagram", " ig ", "fb", "paid social"),
            "paid_social/facebook",
            0.9,
            "Matched a Facebook, Meta, Instagram, or paid-social source pattern.",
        ),
        (
            ("google", "adwords", "paid search", "ppc", "gclid"),
            "paid_search/google",
            0.9,
            "Matched a Google Ads, paid-search, PPC, or gclid source pattern.",
        ),
        (
            ("bing", "microsoft ads", "ms ads"),
            "paid_search/bing",
            0.85,
            "Matched a Bing or Microsoft Ads source pattern.",
        ),
        (
            ("website", "organic", "seo", "web"),
            "organic_search",
            0.75,
            "Matched an organic website or SEO source pattern.",
        ),
        (
            ("referral", "refer", "friend", "doctor"),
            "referral",
            0.75,
            "Matched a referral source pattern.",
        ),
        (
            ("phone", "call", "inbound"),
            "phone_inquiry",
            0.7,
            "Matched a phone or inbound-call source pattern.",
        ),
        (
            ("carestack", "existing patient", "patient"),
            "carestack_existing_patient",
            0.7,
            "Matched an existing-patient or CareStack source pattern.",
        ),
    )
    padded = f" {normalized} "
    for needles, term, score, matched_rationale in mapping_rules:
        if any(needle in padded for needle in needles):
            proposed_term = term
            confidence = score
            rationale = matched_rationale
            break

    return SemanticMappingCandidateOut(
        source_field=source_field,
        raw_value=raw_value,
        proposed_term=proposed_term,
        confidence=confidence,
        evidence_count=evidence_count,
        rationale=rationale,
    )


def _redact_sensitive_text(value: object) -> str:
    text = str(value)
    text = _EMAIL_RE.sub("[redacted]", text)
    return _PHONE_RE.sub("[redacted]", text)


def _evidence_gap_finding(metric: EvidenceMetricOut) -> GapBriefFindingOut | None:
    coverage_rate = metric.coverage_rate
    if coverage_rate is not None and coverage_rate >= 0.95:
        return None
    severity = _coverage_severity(coverage_rate)
    coverage_label = _format_rate(coverage_rate)
    return GapBriefFindingOut(
        category="evidence_coverage",
        severity=severity,
        summary=f"{metric.label} coverage is {coverage_label}.",
        evidence=[
            f"total_count={metric.total_count}",
            f"evidence_count={metric.evidence_count}",
            f"missing_count={metric.missing_count}",
        ],
        impacted_questions=_impacted_questions_for_metric(metric.key),
        recommendation=_recommendation_for_metric(metric.key),
    )


def _semantic_mapping_gap_findings(
    proposal: SemanticMappingProposalOut,
) -> list[GapBriefFindingOut]:
    unmapped = [
        candidate
        for candidate in proposal.candidates
        if candidate.proposed_term == "unknown/unmapped"
    ]
    if not unmapped:
        return []
    total_unmapped_evidence = sum(candidate.evidence_count for candidate in unmapped)
    examples = [
        f"{candidate.source_field}={candidate.raw_value} ({candidate.evidence_count})"
        for candidate in unmapped[:10]
    ]
    severity = "high" if total_unmapped_evidence >= 25 else "medium"
    return [
        GapBriefFindingOut(
            category="semantic_mapping",
            severity=severity,
            summary=(
                "Some lead source or campaign values are not mapped to a V1 "
                "semantic term."
            ),
            evidence=[
                f"unmapped_candidate_count={len(unmapped)}",
                f"unmapped_evidence_count={total_unmapped_evidence}",
                *examples,
            ],
            impacted_questions=[
                "Q01 Lead source performance",
                "Q02 Paid leads by source",
                "Q05 Facebook consultation conversion",
                "Q16 Revenue by lead source",
            ],
            recommendation=(
                "Review unknown/unmapped candidates and add approved semantic "
                "catalog mappings where the business meaning is clear."
            ),
        )
    ]


def _linkage_gap_finding(linkage: LinkageCoverageOut) -> GapBriefFindingOut | None:
    rates = [
        rate
        for rate in (
            linkage.salesforce_to_carestack_rate,
            linkage.carestack_to_salesforce_rate,
        )
        if rate is not None
    ]
    weakest_rate = min(rates) if rates else None
    if weakest_rate is not None and weakest_rate >= 0.9:
        return None
    return GapBriefFindingOut(
        category="identity_linkage",
        severity=_coverage_severity(weakest_rate),
        summary=(
            "Salesforce-to-CareStack source linkage is below the V1 readiness "
            f"threshold: {_format_rate(weakest_rate)}."
        ),
        evidence=[
            f"salesforce_person_count={linkage.salesforce_person_count}",
            f"carestack_person_count={linkage.carestack_person_count}",
            f"linked_salesforce_carestack_count={linkage.linked_salesforce_carestack_count}",
            f"salesforce_only_count={linkage.salesforce_only_count}",
            f"carestack_only_count={linkage.carestack_only_count}",
        ],
        impacted_questions=[
            "Q04 Salesforce to CareStack linkage quality",
            "Q06 Consultation conversion by source",
            "Q17 Paid leads with payment evidence",
            "Q20 Revenue evidence by campaign",
        ],
        recommendation=(
            "Investigate source-id linkage gaps before treating row-level "
            "conversion or revenue attribution as complete."
        ),
    )


def _coverage_severity(coverage_rate: float | None) -> str:
    if coverage_rate is None:
        return "medium"
    if coverage_rate < 0.7:
        return "high"
    if coverage_rate < 0.9:
        return "medium"
    return "low"


def _severity_rank(severity: str) -> int:
    return {"high": 0, "medium": 1, "low": 2, "info": 3}.get(severity, 4)


def _format_rate(rate: float | None) -> str:
    if rate is None:
        return "not available"
    return f"{rate:.1%}"


def _impacted_questions_for_metric(metric_key: str) -> list[str]:
    if metric_key.startswith("lead."):
        return [
            "Q01 Lead source performance",
            "Q02 Paid leads by source",
            "Q05 Facebook consultation conversion",
            "Q16 Revenue by lead source",
        ]
    if metric_key.startswith("consultation."):
        return [
            "Q06 Consultation conversion",
            "Q09 Consultations without next step",
            "Q12 Consultation follow-up backlog",
        ]
    if metric_key.startswith("billing.") or metric_key.startswith("treatment."):
        return [
            "Q17 Paid leads with payment evidence",
            "Q18 Treatment acceptance",
            "Q20 Revenue evidence by campaign",
        ]
    return ["Q00 Data Intelligence readiness"]


def _recommendation_for_metric(metric_key: str) -> str:
    if metric_key in {"lead.lead_source", "lead.campaign"}:
        return "Prioritize source and campaign normalization before expanding marketing attribution analytics."
    if metric_key in {"lead.owner_id", "lead.location_id", "consultation.location_id"}:
        return "Confirm owner/location projection coverage before comparing teams or centers."
    if metric_key.startswith("consultation."):
        return "Improve consultation status/date evidence before relying on follow-up or conversion read models."
    if metric_key.startswith("billing.") or metric_key.startswith("treatment."):
        return "Keep billing evidence aggregate and masked while validating revenue-readiness with finance stakeholders."
    return "Open a data quality follow-up for this evidence gap."


def _recommended_linear_titles(findings: list[GapBriefFindingOut]) -> list[str]:
    titles: list[str] = []
    for finding in findings:
        if finding.category == "semantic_mapping":
            titles.append("Review and approve unmapped lead source semantic mappings")
        elif finding.category == "identity_linkage":
            titles.append("Investigate Salesforce to CareStack linkage coverage gaps")
        elif finding.category == "evidence_coverage":
            titles.append(f"Improve {finding.summary.removesuffix('.').lower()}")
    return list(dict.fromkeys(titles))


def _person_journey_entry(
    entry_id: str,
    *,
    kind: PersonJourneyRegistryEntryKind,
    label: str,
    journey_phase: str,
    state_category: str,
    source_object: str,
    source_system: str,
    source_field: str,
    raw_or_canonical: str,
    transition_meaning: str,
    time_semantics: str,
    data_classes: list[DataClass],
    staff_ui_posture: str,
    agent_analytics_posture: str,
    registry_status: PersonJourneyRegistryStatus,
    suggested_term: str,
    suggested_definition: str,
    source_precedence: list[str] | None = None,
    sale_revenue_posture: str = "not_applicable",
    manager_answer_posture: str | None = None,
    data_quality_evidence_refs: list[str] | None = None,
    suggested_synonyms: list[str] | None = None,
    affected_questions: list[str] | None = None,
    affected_read_models: list[str] | None = None,
    downstream_surfaces: list[str] | None = None,
    risks: list[str] | None = None,
    notes: str = "",
) -> PersonJourneyRegistryEntryOut:
    return PersonJourneyRegistryEntryOut(
        id=entry_id,
        kind=kind,
        label=label,
        journey_phase=journey_phase,
        state_category=state_category,
        source_object=source_object,
        source_system=source_system,
        source_field=source_field,
        raw_or_canonical=raw_or_canonical,
        transition_meaning=transition_meaning,
        time_semantics=time_semantics,
        source_precedence=source_precedence or [source_system],
        sale_revenue_posture=sale_revenue_posture,
        manager_answer_posture=manager_answer_posture
        or _manager_answer_posture_for_registry_status(registry_status),
        data_quality_evidence_refs=data_quality_evidence_refs
        or _data_quality_evidence_refs_for_entry(
            affected_read_models=affected_read_models,
            data_classes=data_classes,
        ),
        data_classes=data_classes,
        staff_ui_posture=staff_ui_posture,
        agent_analytics_posture=agent_analytics_posture,
        registry_status=registry_status,
        suggested_term=suggested_term,
        suggested_definition=suggested_definition,
        suggested_synonyms=suggested_synonyms or [],
        affected_questions=affected_questions or [],
        affected_read_models=affected_read_models or [],
        downstream_surfaces=downstream_surfaces
        or ["semantic_catalog", "query_registry", "manager_answers", "charts"],
        risks=risks or [],
        notes=notes,
    )


def _manager_answer_posture_for_registry_status(
    registry_status: PersonJourneyRegistryStatus,
) -> str:
    if registry_status in {
        PersonJourneyRegistryStatus.BLOCKED,
        PersonJourneyRegistryStatus.INTERNAL_ONLY,
        PersonJourneyRegistryStatus.DEFERRED,
    }:
        return "blocked"
    if registry_status is PersonJourneyRegistryStatus.APPROVED_CANDIDATE:
        return "generated_with_caveat"
    return "review_only"


def _data_quality_evidence_refs_for_entry(
    *,
    affected_read_models: list[str] | None,
    data_classes: list[DataClass],
) -> list[str]:
    refs = ["data_intelligence_evidence_coverage"]
    read_models = set(affected_read_models or [])
    if "lead_conversion" in read_models or "lead_source_profile" in read_models:
        refs.append("lead_source_profile.aggregate_coverage")
    if "treatment_revenue" in read_models or DataClass.BILLING in data_classes:
        refs.append("treatment_revenue.aggregate_billing_evidence")
    if "person_journey_coverage" in read_models:
        refs.append("identity_linkage.aggregate_coverage")
    return refs


def _filtered_person_journey_registry(
    *,
    statuses: list[PersonJourneyRegistryStatus] | None,
    kinds: list[PersonJourneyRegistryEntryKind] | None,
) -> list[PersonJourneyRegistryEntryOut]:
    allowed_statuses = set(statuses or [])
    allowed_kinds = set(kinds or [])
    entries = [
        entry
        for entry in _PERSON_JOURNEY_REGISTRY
        if (not allowed_statuses or entry.registry_status in allowed_statuses)
        and (not allowed_kinds or entry.kind in allowed_kinds)
    ]
    return sorted(entries, key=lambda entry: (entry.kind, entry.id))


def _person_journey_proposal_candidate(
    entry: PersonJourneyRegistryEntryOut,
) -> PersonJourneyProposalCandidateOut:
    blockers = _person_journey_blockers(entry)
    can_submit = not blockers
    proposal = _person_journey_catalog_proposal(entry) if can_submit else None
    warnings = [
        "This projection is review-only; it never approves catalog meaning.",
        "Agent Runtime and manager analytics must treat this entry as non-executable until approved catalog/read-model binding exists.",
    ]
    if blockers:
        warnings.append("This entry is visible for review context but is not eligible for catalog proposal submission.")
    return PersonJourneyProposalCandidateOut(
        entry=entry,
        can_submit_for_review=can_submit,
        proposal=proposal,
        blockers=blockers,
        warnings=warnings,
    )


def _person_journey_blockers(entry: PersonJourneyRegistryEntryOut) -> list[str]:
    if DataClass.CALL_RECORDING_REF in entry.data_classes:
        return ["Call recording references require a dedicated policy review."]
    if DataClass.RAW_PAYLOAD in entry.data_classes:
        return ["Raw provider payload semantics are denied."]
    if DataClass.PHI in entry.data_classes:
        return ["PHI is denied in Data Intelligence V1."]
    if entry.registry_status is PersonJourneyRegistryStatus.BLOCKED:
        return ["Registry status is blocked."]
    if entry.registry_status is PersonJourneyRegistryStatus.INTERNAL_ONLY:
        return ["Registry status is internal_only; this is operational/debug metadata."]
    if entry.registry_status is PersonJourneyRegistryStatus.DEFERRED:
        return ["Registry status is deferred until deployment, policy, data quality, or audit gaps close."]
    return []


def _person_journey_catalog_proposal(
    entry: PersonJourneyRegistryEntryOut,
) -> PersonJourneyCatalogProposalDraftOut:
    confidence = (
        0.72
        if entry.registry_status is PersonJourneyRegistryStatus.APPROVED_CANDIDATE
        else 0.55
    )
    return PersonJourneyCatalogProposalDraftOut(
        raw_value=entry.label,
        source_system=entry.source_system,
        source_field=entry.source_field,
        suggested_term=entry.suggested_term,
        definition=entry.suggested_definition,
        synonyms=entry.suggested_synonyms,
        confidence=confidence,
        reason=(
            f"Person journey registry entry `{entry.id}` is {entry.registry_status}; "
            "Data Intelligence can submit it for human Semantic Catalog review only."
        ),
        affected_questions=entry.affected_questions,
        affected_read_models=entry.affected_read_models,
        source_reference_id=f"person_journey_registry:{entry.id}",
    )


_PERSON_JOURNEY_COMMON_QUESTIONS = [
    "Q01 Lead source performance",
    "Q02 Paid leads by source",
    "Q06 Consultation conversion by source",
    "Q20 Revenue evidence by campaign",
]

_PERSON_JOURNEY_REGISTRY: tuple[PersonJourneyRegistryEntryOut, ...] = (
    _person_journey_entry(
        "field.utm_source",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="UTM source",
        journey_phase="lead_attribution",
        state_category="source_attribution",
        source_object="Salesforce Lead",
        source_system="salesforce",
        source_field="Lead.extra.utm_source",
        raw_or_canonical="canonical key carrying provider value",
        transition_meaning="First-touch or campaign-source evidence for the lead.",
        time_semantics="Uses lead created/updated time until attribution precedence is approved.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="review-only until attribution model approved",
        registry_status=PersonJourneyRegistryStatus.APPROVED_CANDIDATE,
        suggested_term="attribution_source",
        suggested_definition="Source evidence used to group person journey and lead conversion attribution.",
        suggested_synonyms=["utm_source", "source"],
        affected_questions=_PERSON_JOURNEY_COMMON_QUESTIONS,
        affected_read_models=["lead_conversion", "campaign_opportunity_conversion"],
        risks=["Requires source precedence and backfill coverage before reporting."],
    ),
    _person_journey_entry(
        "field.utm_campaign",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="UTM campaign",
        journey_phase="lead_attribution",
        state_category="campaign_attribution",
        source_object="Salesforce Lead",
        source_system="salesforce",
        source_field="Lead.extra.utm_campaign",
        raw_or_canonical="canonical key carrying provider value",
        transition_meaning="Campaign evidence attached to lead creation or update.",
        time_semantics="Uses lead created/updated time until campaign precedence is approved.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="review-only until campaign taxonomy approved",
        registry_status=PersonJourneyRegistryStatus.APPROVED_CANDIDATE,
        suggested_term="utm_campaign",
        suggested_definition="Campaign evidence used to group lead and opportunity performance.",
        suggested_synonyms=["campaign"],
        affected_questions=_PERSON_JOURNEY_COMMON_QUESTIONS,
        affected_read_models=["lead_conversion", "campaign_opportunity_conversion"],
        risks=["Campaign values can drift or be missing before backfill."],
    ),
    _person_journey_entry(
        "field.last_touch_source",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Last-touch source",
        journey_phase="lead_attribution",
        state_category="source_attribution",
        source_object="Salesforce Lead",
        source_system="salesforce",
        source_field="Lead.extra.last_touch_source",
        raw_or_canonical="canonical key carrying provider value",
        transition_meaning="Most recent source evidence used by the lead-source explorer attribution model.",
        time_semantics="Uses lead created/updated time unless last_touch_date is present and approved.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="approved candidate for aggregate attribution after catalog review",
        registry_status=PersonJourneyRegistryStatus.APPROVED_CANDIDATE,
        suggested_term="last_touch_attribution_source",
        suggested_definition="Most recent source evidence used to attribute a lead or person to an acquisition source.",
        suggested_synonyms=["last_touch_source", "latest_source"],
        affected_questions=_PERSON_JOURNEY_COMMON_QUESTIONS,
        affected_read_models=["lead_conversion", "lead_source_profile", "paid_leads"],
        risks=[
            "Must be distinguished from first-touch and CRM fallback source labels in manager answers.",
            "Requires source precedence disclosure before product reporting.",
        ],
    ),
    _person_journey_entry(
        "field.last_touch_medium",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Last-touch medium",
        journey_phase="lead_attribution",
        state_category="medium_attribution",
        source_object="Salesforce Lead",
        source_system="salesforce",
        source_field="Lead.extra.last_touch_medium",
        raw_or_canonical="canonical key carrying provider value",
        transition_meaning="Most recent medium evidence used beneath source/channel grouping.",
        time_semantics="Uses lead created/updated time unless last_touch_date is present and approved.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="review-only until medium taxonomy is approved",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="last_touch_medium",
        suggested_definition="Most recent marketing medium evidence used for aggregate attribution drill-downs.",
        suggested_synonyms=["last_touch_medium", "latest_medium"],
        affected_questions=["Q01 Lead source performance", "Q02 Paid leads by source"],
        affected_read_models=["lead_conversion", "lead_source_profile", "paid_leads"],
        risks=["Medium values need taxonomy review before cross-channel comparison."],
    ),
    _person_journey_entry(
        "field.last_touch_campaign",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Last-touch campaign",
        journey_phase="lead_attribution",
        state_category="campaign_attribution",
        source_object="Salesforce Lead",
        source_system="salesforce",
        source_field="Lead.extra.last_touch_campaign",
        raw_or_canonical="canonical key carrying provider value",
        transition_meaning="Most recent campaign evidence used beneath source/channel grouping.",
        time_semantics="Uses lead created/updated time unless last_touch_date is present and approved.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="review-only until campaign taxonomy is approved",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="last_touch_campaign",
        suggested_definition="Most recent campaign evidence used for aggregate attribution drill-downs.",
        suggested_synonyms=["last_touch_campaign", "latest_campaign"],
        affected_questions=["Q01 Lead source performance", "Q02 Paid leads by source", "Q20 Revenue evidence by campaign"],
        affected_read_models=["lead_conversion", "lead_source_profile", "paid_leads"],
        risks=["Campaign labels can be sparse and must not override reviewed campaign taxonomy silently."],
    ),
    _person_journey_entry(
        "field.gclid",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Google click id",
        journey_phase="lead_attribution",
        state_category="paid_click_evidence",
        source_object="Salesforce Lead",
        source_system="salesforce",
        source_field="Lead.extra.gclid",
        raw_or_canonical="canonical key carrying provider value",
        transition_meaning="Paid-search click evidence that can support source mapping.",
        time_semantics="Click timestamp is not available; use lead created time only as fallback.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed with masking posture if needed",
        agent_analytics_posture="review-only mapping signal",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="paid_search_click_evidence",
        suggested_definition="Google Ads click evidence that can support paid-search attribution review.",
        suggested_synonyms=["gclid", "google_click_id"],
        affected_questions=["Q02 Paid leads by source", "Q20 Revenue evidence by campaign"],
        affected_read_models=["source_quality_by_opportunity"],
        risks=["Click ids are evidence, not a manager-facing source label by themselves."],
    ),
    _person_journey_entry(
        "field.referral_source",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Referral source",
        journey_phase="lead_attribution",
        state_category="referral_attribution",
        source_object="Salesforce Lead",
        source_system="salesforce",
        source_field="Lead.extra.referral_source",
        raw_or_canonical="canonical key carrying provider value",
        transition_meaning="Referral evidence attached to a lead or converted person.",
        time_semantics="Uses lead created/updated time until referral precedence is approved.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="review-only until referral taxonomy approved",
        registry_status=PersonJourneyRegistryStatus.APPROVED_CANDIDATE,
        suggested_term="referral_source",
        suggested_definition="Referral evidence used to group person journey source quality.",
        suggested_synonyms=["referral", "referer"],
        affected_questions=["Q01 Lead source performance", "Q06 Consultation conversion by source"],
        affected_read_models=["source_quality_by_opportunity"],
        risks=["Needs taxonomy for doctor, friend, internal, and partner referral meanings."],
    ),
    _person_journey_entry(
        "field.assigned_center",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Assigned center",
        journey_phase="lead_attribution",
        state_category="location_evidence",
        source_object="Salesforce Lead",
        source_system="salesforce",
        source_field="Lead.extra.assigned_center",
        raw_or_canonical="canonical key carrying provider value",
        transition_meaning="Free-text center/location evidence attached to a lead.",
        time_semantics="Current lead-location evidence; not a consultation occurrence time.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="approved candidate only after Fusion location mapping is disclosed",
        registry_status=PersonJourneyRegistryStatus.APPROVED_CANDIDATE,
        suggested_term="lead_assigned_center",
        suggested_definition="Salesforce lead center/location evidence used for aggregate location scoping after normalization.",
        suggested_synonyms=["assigned_center", "center", "clinic"],
        affected_questions=["Q01 Lead source performance", "Q06 Consultation conversion by source", "Q20 Revenue evidence by campaign"],
        affected_read_models=["lead_conversion", "lead_source_profile", "paid_leads"],
        risks=[
            "Free-text values can contain non-breaking spaces and stale centers.",
            "Evidence-based location scope must disclose consultation-location overrides.",
        ],
    ),
    _person_journey_entry(
        "field.business_unit",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Business unit",
        journey_phase="lead_attribution",
        state_category="business_segment",
        source_object="Salesforce Lead",
        source_system="salesforce",
        source_field="Lead.extra.business_unit",
        raw_or_canonical="canonical key carrying provider value",
        transition_meaning="Business-unit segmentation evidence attached to the lead.",
        time_semantics="Current lead segmentation evidence; not a lead creation or consultation occurrence time.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="review-only until business-unit taxonomy is approved",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="lead_business_unit",
        suggested_definition="Salesforce lead business-unit evidence used to segment aggregate manager analytics after taxonomy review.",
        suggested_synonyms=["business_unit", "business segment"],
        affected_questions=["Q01 Lead source performance", "Q06 Consultation conversion by source"],
        affected_read_models=["lead_conversion", "lead_source_profile"],
        risks=["Business-unit labels can drift across Salesforce configuration and must not silently redefine location or source semantics."],
    ),
    _person_journey_entry(
        "field.consultation_scheduled_at",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Consultation scheduled at",
        journey_phase="consultation",
        state_category="scheduled_time_evidence",
        source_object="Salesforce Lead",
        source_system="salesforce",
        source_field="Lead.extra.consultation_scheduled_at",
        raw_or_canonical="provider timestamp mirror",
        transition_meaning="Lead-level evidence that a consultation was scheduled.",
        time_semantics="Consultation occurrence time candidate; manager windows must prefer service-owned consultation scheduled/provider-created semantics when available.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="review-only until consultation timestamp precedence is approved",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="lead_consultation_scheduled_time",
        suggested_definition="Salesforce lead mirror of consultation scheduled time, used only as reviewed evidence for conversion analytics.",
        suggested_synonyms=["consultation_scheduled_at", "scheduled consult time"],
        affected_questions=["Q06 Consultation conversion by source", "Q12 Consultation follow-up backlog"],
        affected_read_models=["lead_conversion", "consultation_followup"],
        risks=["Must not be conflated with CareStack appointment provider-created time or completed consultation time."],
    ),
    _person_journey_entry(
        "field.location_mismatch",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Location mismatch flag",
        journey_phase="lead_attribution",
        state_category="data_quality_flag",
        source_object="Fusion lead-source explorer",
        source_system="fusion_ops",
        source_field="LeadSourceLeadItem.location_mismatch",
        raw_or_canonical="computed boolean",
        transition_meaning="A lead entered a location scope through consultation evidence while assigned_center points elsewhere.",
        time_semantics="Computed at read time from lead and consultation evidence; not an event timestamp.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed as data-quality marker",
        agent_analytics_posture="review-only caveat/quality signal, not a business event",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="location_evidence_mismatch",
        suggested_definition="Data-quality flag showing that lead center evidence disagrees with consultation-location evidence.",
        suggested_synonyms=["location_mismatch", "center_mismatch"],
        affected_questions=["Q06 Consultation conversion by source", "Q20 Revenue evidence by campaign"],
        affected_read_models=["lead_conversion", "lead_source_profile"],
        risks=[
            "Must be presented as evidence quality, not as patient movement or staff attribution.",
            "Manager answers should caveat location-scope counts when mismatch evidence is present.",
        ],
    ),
    _person_journey_entry(
        "field.lead_status",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Lead status",
        journey_phase="lead_capture",
        state_category="lead_lifecycle_state",
        source_object="Salesforce Lead",
        source_system="salesforce",
        source_field="Lead.status",
        raw_or_canonical="canonical CRM state",
        transition_meaning="Lead's current CRM lifecycle posture before or during conversion.",
        time_semantics="Status is current-state evidence; transition time requires lead update history.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="review-only until lead status taxonomy approved",
        registry_status=PersonJourneyRegistryStatus.APPROVED_CANDIDATE,
        suggested_term="lead_lifecycle_state",
        suggested_definition="Governed CRM lead status used to group pre-conversion person journey posture.",
        suggested_synonyms=["lead_status", "salesforce_lead_status"],
        affected_questions=["Q01 Lead source performance", "Q06 Consultation conversion by source"],
        affected_read_models=["lead_conversion", "lead_to_opportunity_journey"],
        risks=["Provider status labels need taxonomy review before cross-surface reporting."],
    ),
    _person_journey_entry(
        "field.lead_created_at",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Lead created at",
        journey_phase="lead_capture",
        state_category="created_time",
        source_object="Salesforce Lead",
        source_system="salesforce",
        source_field="Lead.created_at",
        raw_or_canonical="canonical timestamp",
        transition_meaning="Lead first entered the CRM.",
        time_semantics="Primary created-time anchor for lead-source and conversion windows.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="time-window candidate",
        registry_status=PersonJourneyRegistryStatus.APPROVED_CANDIDATE,
        suggested_term="lead_created_time",
        suggested_definition="Timestamp evidence for when a lead entered the CRM.",
        suggested_synonyms=["lead_created_at", "CreatedDate"],
        affected_questions=["Q01 Lead source performance", "Q02 Paid leads by source"],
        affected_read_models=["lead_conversion", "campaign_opportunity_conversion"],
        risks=["Timezone normalization must be explicit in manager answers."],
    ),
    _person_journey_entry(
        "field.converted_contact_id",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Converted contact id",
        journey_phase="contact_linkage",
        state_category="source_linkage",
        source_object="Salesforce Lead",
        source_system="salesforce",
        source_field="Lead.extra.converted_contact_id",
        raw_or_canonical="canonical key carrying provider id",
        transition_meaning="Lead converted into a Salesforce Contact source reference.",
        time_semantics="Conversion time must come from converted date or contact created time.",
        data_classes=[DataClass.OPS, DataClass.IDENTITY],
        staff_ui_posture="allowed as source reference",
        agent_analytics_posture="linkage candidate",
        registry_status=PersonJourneyRegistryStatus.APPROVED_CANDIDATE,
        suggested_term="lead_to_contact_linkage",
        suggested_definition="Source linkage evidence connecting a lead to its converted contact.",
        suggested_synonyms=["ConvertedContactId", "contact_link"],
        affected_questions=["Q04 Salesforce to CareStack linkage quality"],
        affected_read_models=["lead_to_opportunity_journey", "person_journey_coverage"],
        risks=["Requires duplicate-source and person-link confidence handling before reporting."],
    ),
    _person_journey_entry(
        "field.converted_account_id",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Converted account id",
        journey_phase="account_linkage",
        state_category="source_linkage",
        source_object="Salesforce Lead",
        source_system="salesforce",
        source_field="Lead.extra.converted_account_id",
        raw_or_canonical="canonical key carrying provider id",
        transition_meaning="Lead converted into a Salesforce Account source reference.",
        time_semantics="Conversion time must come from converted date or account created time.",
        data_classes=[DataClass.OPS, DataClass.IDENTITY],
        staff_ui_posture="allowed as source reference",
        agent_analytics_posture="linkage candidate after account source links are active",
        registry_status=PersonJourneyRegistryStatus.APPROVED_CANDIDATE,
        suggested_term="lead_to_account_linkage",
        suggested_definition="Source linkage evidence connecting a lead to its converted account.",
        suggested_synonyms=["ConvertedAccountId", "account_link"],
        affected_questions=["Q04 Salesforce to CareStack linkage quality"],
        affected_read_models=["lead_to_opportunity_journey", "person_journey_coverage"],
        risks=["Account semantics must stay identity-adjacent and not become household truth without review."],
    ),
    _person_journey_entry(
        "field.converted_opportunity_id",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Converted opportunity id",
        journey_phase="lead_conversion",
        state_category="source_linkage",
        source_object="Salesforce Lead",
        source_system="salesforce",
        source_field="Lead.extra.converted_opportunity_id",
        raw_or_canonical="canonical key carrying provider id",
        transition_meaning="Lead converted into an opportunity source reference.",
        time_semantics="Conversion time must come from Salesforce converted date or opportunity created time.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed as source reference",
        agent_analytics_posture="linkage candidate",
        registry_status=PersonJourneyRegistryStatus.APPROVED_CANDIDATE,
        suggested_term="lead_to_opportunity_linkage",
        suggested_definition="Source linkage evidence connecting a converted lead to a person-linked opportunity.",
        suggested_synonyms=["ConvertedOpportunityId", "opportunity_link"],
        affected_questions=["Q06 Consultation conversion by source", "Q20 Revenue evidence by campaign"],
        affected_read_models=["lead_to_opportunity_journey", "campaign_opportunity_conversion"],
        risks=["Requires linkage confidence and duplicate-source handling before reporting."],
    ),
    _person_journey_entry(
        "field.opportunity_stage_name",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Opportunity stage name",
        journey_phase="opportunity_stage",
        state_category="current_stage_state",
        source_object="Salesforce Opportunity",
        source_system="salesforce",
        source_field="Opportunity.stage_name",
        raw_or_canonical="provider stage label",
        transition_meaning="Opportunity's current sales-stage posture.",
        time_semantics="Current state only; transition time requires OpportunityHistory.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="review-only until stage taxonomy approved",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="opportunity_stage",
        suggested_definition="Governed opportunity sales-stage posture for person journey analytics.",
        suggested_synonyms=["stage_name", "sales_stage"],
        affected_questions=["Q20 Revenue evidence by campaign"],
        affected_read_models=["opportunity_stage_velocity", "lead_to_opportunity_journey"],
        risks=["Provider stage labels require taxonomy review before velocity or conversion reporting."],
    ),
    _person_journey_entry(
        "field.opportunity_close_date",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Opportunity close date",
        journey_phase="sale_conversion",
        state_category="closed_time",
        source_object="Salesforce Opportunity",
        source_system="salesforce",
        source_field="Opportunity.close_date",
        raw_or_canonical="provider timestamp/date",
        transition_meaning="Opportunity expected or actual close date evidence.",
        time_semantics="CloseDate is the sale-conversion anchor only after close/win posture review.",
        sale_revenue_posture="sale_timing_not_payment_revenue",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="review-only until close-date semantics approved",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="opportunity_close_time",
        suggested_definition="Date evidence for expected or actual opportunity close posture.",
        suggested_synonyms=["CloseDate", "closed_at"],
        affected_questions=["Q20 Revenue evidence by campaign"],
        affected_read_models=["campaign_opportunity_conversion", "opportunity_stage_velocity"],
        risks=["Expected close dates and actual closed-won dates must not be conflated."],
    ),
    _person_journey_entry(
        "field.opportunity_amount",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Opportunity amount",
        journey_phase="sale_conversion",
        state_category="sale_value_evidence",
        source_object="Salesforce Opportunity",
        source_system="salesforce",
        source_field="Opportunity.amount",
        raw_or_canonical="provider numeric value",
        transition_meaning="Salesforce opportunity value evidence, not collected revenue.",
        time_semantics="Use with opportunity close/stage time only after amount semantics review.",
        sale_revenue_posture="sale_value_not_collected_revenue",
        data_classes=[DataClass.OPS, DataClass.BILLING, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed by role as aggregate/bucketed value",
        agent_analytics_posture="review-only and aggregate-only",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="opportunity_value",
        suggested_definition="Salesforce opportunity value evidence that is distinct from collected treatment revenue.",
        suggested_synonyms=["amount", "opportunity_amount"],
        affected_questions=["Q20 Revenue evidence by campaign"],
        affected_read_models=["campaign_opportunity_conversion"],
        risks=["Must not be described as collected revenue or payment evidence."],
    ),
    _person_journey_entry(
        "field.opportunity_loss_reason",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Opportunity loss reason",
        journey_phase="sale_conversion",
        state_category="closed_lost_reason",
        source_object="Salesforce Opportunity",
        source_system="salesforce",
        source_field="Opportunity.loss_reason",
        raw_or_canonical="provider label",
        transition_meaning="Reason evidence when an opportunity is lost.",
        time_semantics="Use close/lost event time; raw reason values need taxonomy review.",
        sale_revenue_posture="lost_sale_context",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="review-only until loss taxonomy approved",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="opportunity_loss_reason",
        suggested_definition="Governed reason taxonomy for lost opportunity outcomes.",
        suggested_synonyms=["loss_reason", "closed_lost_reason"],
        affected_questions=["Q20 Revenue evidence by campaign"],
        affected_read_models=["campaign_opportunity_conversion"],
        risks=["Free-text or provider-specific loss reasons can be inconsistent."],
    ),
    _person_journey_entry(
        "field.treatment_status",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Treatment status",
        journey_phase="treatment",
        state_category="treatment_lifecycle_state",
        source_object="CareStack treatment evidence",
        source_system="carestack",
        source_field="treatment.status",
        raw_or_canonical="canonical treatment state",
        transition_meaning="Treatment plan or procedure moved through presented/completed posture.",
        time_semantics="Treatment presented/completed event time; exact clinical semantics remain service-owned.",
        sale_revenue_posture="treatment_progress_not_payment_revenue",
        data_classes=[DataClass.OPS, DataClass.BILLING],
        staff_ui_posture="allowed by role/posture",
        agent_analytics_posture="review-only to approved depending on term",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="treatment_lifecycle_state",
        suggested_definition="Governed treatment lifecycle posture used to distinguish plan progress from collected revenue.",
        suggested_synonyms=["treatment_status", "procedure_status"],
        affected_questions=["Q20 Revenue evidence by campaign"],
        affected_read_models=["treatment_revenue"],
        risks=["Treatment status must not expose clinical detail or PHI-bearing procedure notes."],
    ),
    _person_journey_entry(
        "field.payment_amount_bucket",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Payment amount bucket",
        journey_phase="billing_revenue",
        state_category="collected_revenue_evidence",
        source_object="CareStack accounting transaction",
        source_system="carestack",
        source_field="payment.amount_bucket",
        raw_or_canonical="masked aggregate bucket",
        transition_meaning="Collected payment evidence in an aggregate/bucketed posture.",
        time_semantics="Payment recorded date/time is the revenue evidence anchor.",
        sale_revenue_posture="collected_revenue_aggregate_only",
        data_classes=[DataClass.BILLING, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed by role as aggregate/bucketed value",
        agent_analytics_posture="aggregate-only with billing policy",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="collected_revenue",
        suggested_definition="Aggregate collected payment evidence distinct from opportunity amount and treatment status.",
        suggested_synonyms=["payment_amount", "collected", "revenue"],
        affected_questions=["Q20 Revenue evidence by campaign"],
        affected_read_models=["treatment_revenue"],
        risks=["Must remain aggregate-only until export/audit and billing policy are approved."],
    ),
    _person_journey_entry(
        "field.collected_amount_aggregate",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Collected amount aggregate",
        journey_phase="billing_revenue",
        state_category="collected_revenue_evidence",
        source_object="Fusion interaction aggregate",
        source_system="fusion_interaction",
        source_field="LeadSourceNode.collected_amount",
        raw_or_canonical="computed aggregate",
        transition_meaning="Net collected cash aggregate attributed to source nodes.",
        time_semantics="Uses payment recorded/reversal/refund event times from the service-owned read model.",
        sale_revenue_posture="collected_revenue_aggregate_only",
        data_classes=[DataClass.BILLING, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed by role as aggregate amount",
        agent_analytics_posture="aggregate-only with billing and attribution caveats",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="collected_amount_aggregate",
        suggested_definition="Service-owned aggregate of collected cash net of refunds/reversals and excluding allocation legs.",
        suggested_synonyms=["collected_amount", "net_collected", "cash_collected"],
        affected_questions=["Q02 Paid leads by source", "Q20 Revenue evidence by campaign"],
        affected_read_models=["treatment_revenue", "lead_source_profile"],
        risks=[
            "Must not include payment_applied allocation legs.",
            "Revenue attribution to lead source requires identity/person linkage coverage disclosure.",
        ],
    ),
    _person_journey_entry(
        "field.payment_applied_exclusion",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Payment applied exclusion",
        journey_phase="billing_revenue",
        state_category="allocation_leg_exclusion",
        source_object="CareStack accounting transaction",
        source_system="carestack",
        source_field="interaction.event.kind.payment_applied",
        raw_or_canonical="normalized billing kind",
        transition_meaning="Allocation-leg rows are excluded from Collected aggregates.",
        time_semantics="Allocation timestamps are not collected-revenue event times for manager answers.",
        sale_revenue_posture="excluded_from_collected_revenue",
        data_classes=[DataClass.BILLING, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed as explanatory accounting metadata",
        agent_analytics_posture="review-only accounting caveat",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="payment_applied_allocation_leg",
        suggested_definition="CareStack allocation-leg payment event that must be excluded from collected cash aggregates.",
        suggested_synonyms=["payment_applied", "allocation_leg"],
        affected_questions=["Q17 Paid leads with payment evidence", "Q20 Revenue evidence by campaign"],
        affected_read_models=["treatment_revenue"],
        risks=["Including allocation legs can inflate collected revenue and manager answer totals."],
    ),
    _person_journey_entry(
        "field.unchanged_count",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Unchanged count",
        journey_phase="internal_health",
        state_category="sync_health",
        source_object="Fusion ingest summary",
        source_system="fusion_ingest",
        source_field="sync_summary.unchanged_count",
        raw_or_canonical="internal computed",
        transition_meaning="No person journey transition; sync health only.",
        time_semantics="Sync run time only; not business event time.",
        data_classes=[DataClass.INTERNAL],
        staff_ui_posture="engineering only",
        agent_analytics_posture="not allowed",
        registry_status=PersonJourneyRegistryStatus.INTERNAL_ONLY,
        suggested_term="ingest_unchanged_count",
        suggested_definition="Internal sync counter used for engineering diagnostics only.",
        downstream_surfaces=["engineering_audit"],
        risks=["Not business meaning and must not enter Semantic Catalog approval."],
    ),
    _person_journey_entry(
        "field.raw_provider_payload",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Raw provider payload fields",
        journey_phase="blocked_raw_payload",
        state_category="raw_payload",
        source_object="Ingest raw event",
        source_system="ingest",
        source_field="raw_event.payload",
        raw_or_canonical="raw provider payload",
        transition_meaning="No approved business transition may be inferred from raw payloads.",
        time_semantics="Provider payload time fields are not trusted without allowlist review.",
        data_classes=[DataClass.RAW_PAYLOAD],
        staff_ui_posture="inspector-only by policy",
        agent_analytics_posture="not allowed",
        registry_status=PersonJourneyRegistryStatus.BLOCKED,
        suggested_term="raw_provider_payload",
        suggested_definition="Raw provider payload data that must not be treated as business semantics.",
        downstream_surfaces=["blocked"],
        risks=["Can contain sensitive or unstable provider-specific fields."],
    ),
    _person_journey_entry(
        "field.call_recording_ref",
        kind=PersonJourneyRegistryEntryKind.FIELD,
        label="Call recording reference",
        journey_phase="follow_up_activity",
        state_category="call_artifact_reference",
        source_object="Interaction event",
        source_system="interaction",
        source_field="Event.data_class.call_recording_ref",
        raw_or_canonical="artifact reference",
        transition_meaning="Call artifact was referenced; not approved as analytics meaning.",
        time_semantics="Event time only; recording content/time is not inspected.",
        data_classes=[DataClass.CALL_RECORDING_REF],
        staff_ui_posture="limited / pending review",
        agent_analytics_posture="not allowed",
        registry_status=PersonJourneyRegistryStatus.BLOCKED,
        suggested_term="call_recording_reference",
        suggested_definition="Reference to a call artifact that requires dedicated policy before analytics use.",
        downstream_surfaces=["blocked"],
        risks=["Requires policy review before analytics, answers, or charts."],
    ),
    _person_journey_entry(
        "event.lead_created",
        kind=PersonJourneyRegistryEntryKind.EVENT,
        label="Lead created",
        journey_phase="lead_capture",
        state_category="created_event",
        source_object="Salesforce Lead",
        source_system="salesforce",
        source_field="Event.kind.lead_created",
        raw_or_canonical="normalized timeline event",
        transition_meaning="Person journey started as a Salesforce lead.",
        time_semantics="Lead CreatedDate or normalized event occurred_at.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="approved aggregate candidate",
        registry_status=PersonJourneyRegistryStatus.APPROVED_CANDIDATE,
        suggested_term="lead_created_event",
        suggested_definition="Lead creation evidence used as the first CRM journey anchor.",
        suggested_synonyms=["salesforce_lead_created"],
        affected_questions=["Q01 Lead source performance", "Q02 Paid leads by source"],
        affected_read_models=["lead_conversion", "person_journey_coverage"],
        risks=["Timezone normalization must be explicit for period-based answers."],
    ),
    _person_journey_entry(
        "event.lead_updated",
        kind=PersonJourneyRegistryEntryKind.EVENT,
        label="Lead updated",
        journey_phase="lead_capture",
        state_category="updated_event",
        source_object="Salesforce Lead",
        source_system="salesforce",
        source_field="Event.kind.lead_updated",
        raw_or_canonical="normalized timeline event",
        transition_meaning="Lead record changed; field-level business meaning requires allowlist review.",
        time_semantics="Lead LastModifiedDate or normalized event occurred_at.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="review-only for change analytics",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="lead_updated_event",
        suggested_definition="Lead update evidence that requires field-level semantics before analytics use.",
        suggested_synonyms=["salesforce_lead_updated"],
        affected_questions=["Q01 Lead source performance"],
        affected_read_models=["person_journey_coverage"],
        risks=["A lead update is not itself a business stage transition without changed-field semantics."],
    ),
    _person_journey_entry(
        "event.contact_created",
        kind=PersonJourneyRegistryEntryKind.EVENT,
        label="Contact created",
        journey_phase="contact_linkage",
        state_category="identity_linkage_event",
        source_object="Salesforce Contact",
        source_system="salesforce",
        source_field="Event.kind.contact_created",
        raw_or_canonical="normalized timeline event",
        transition_meaning="Lead/person gained Salesforce Contact evidence.",
        time_semantics="Salesforce Contact CreatedDate or normalized event occurred_at.",
        data_classes=[DataClass.OPS, DataClass.IDENTITY],
        staff_ui_posture="allowed when backend deployed",
        agent_analytics_posture="person journey candidate",
        registry_status=PersonJourneyRegistryStatus.DEFERRED,
        suggested_term="contact_created_event",
        suggested_definition="Post-conversion Salesforce contact evidence in the person journey timeline.",
        suggested_synonyms=["salesforce_contact_created"],
        affected_questions=["Q04 Salesforce to CareStack linkage quality"],
        affected_read_models=["lead_to_opportunity_journey"],
        risks=["Frontend enum support can precede backend/migration production readiness."],
    ),
    _person_journey_entry(
        "event.account_created",
        kind=PersonJourneyRegistryEntryKind.EVENT,
        label="Account created",
        journey_phase="account_linkage",
        state_category="identity_linkage_event",
        source_object="Salesforce Account",
        source_system="salesforce",
        source_field="Event.kind.account_created",
        raw_or_canonical="normalized timeline event",
        transition_meaning="Person journey gained Salesforce Account evidence.",
        time_semantics="Salesforce Account CreatedDate or normalized event occurred_at.",
        data_classes=[DataClass.OPS, DataClass.IDENTITY],
        staff_ui_posture="allowed when backend deployed",
        agent_analytics_posture="person journey candidate",
        registry_status=PersonJourneyRegistryStatus.DEFERRED,
        suggested_term="account_created_event",
        suggested_definition="Salesforce account evidence connected to a person journey.",
        suggested_synonyms=["salesforce_account_created"],
        affected_questions=["Q04 Salesforce to CareStack linkage quality"],
        affected_read_models=["person_journey_coverage"],
        risks=["Account semantics must not become household/family meaning without review."],
    ),
    _person_journey_entry(
        "event.opportunity_created",
        kind=PersonJourneyRegistryEntryKind.EVENT,
        label="Opportunity created",
        journey_phase="opportunity",
        state_category="created_event",
        source_object="Salesforce Opportunity",
        source_system="salesforce",
        source_field="Event.kind.opportunity_created",
        raw_or_canonical="normalized timeline event",
        transition_meaning="A person-linked opportunity was created.",
        time_semantics="Opportunity CreatedDate or normalized event occurred_at.",
        sale_revenue_posture="sale_pipeline_not_revenue",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="approved candidate for opportunity analytics",
        registry_status=PersonJourneyRegistryStatus.APPROVED_CANDIDATE,
        suggested_term="opportunity_created_event",
        suggested_definition="Opportunity creation evidence for lead-to-sale journey coverage.",
        suggested_synonyms=["salesforce_opportunity_created"],
        affected_questions=["Q20 Revenue evidence by campaign"],
        affected_read_models=["lead_to_opportunity_journey", "campaign_opportunity_conversion"],
        risks=["Requires person linkage confidence before source-quality reporting."],
    ),
    _person_journey_entry(
        "event.opportunity_stage_changed",
        kind=PersonJourneyRegistryEntryKind.EVENT,
        label="Opportunity stage changed",
        journey_phase="opportunity_stage",
        state_category="stage_transition",
        source_object="Salesforce OpportunityHistory",
        source_system="salesforce",
        source_field="Event.kind.opportunity_stage_changed",
        raw_or_canonical="normalized timeline event",
        transition_meaning="Opportunity moved from one stage posture to another.",
        time_semantics="Stage-history created time is the transition time.",
        data_classes=[DataClass.OPS],
        staff_ui_posture="allowed when backend deployed",
        agent_analytics_posture="stage velocity candidate",
        registry_status=PersonJourneyRegistryStatus.DEFERRED,
        suggested_term="opportunity_stage_velocity",
        suggested_definition="Stage movement evidence used to measure opportunity progression over time.",
        suggested_synonyms=["stage_change", "opportunity_history"],
        affected_questions=["Q20 Revenue evidence by campaign"],
        affected_read_models=["opportunity_stage_velocity"],
        risks=["Requires stage taxonomy, timestamp semantics, and deployment confirmation."],
    ),
    _person_journey_entry(
        "event.opportunity_won",
        kind=PersonJourneyRegistryEntryKind.EVENT,
        label="Opportunity won",
        journey_phase="sale_conversion",
        state_category="closed_won_state",
        source_object="Salesforce Opportunity",
        source_system="salesforce",
        source_field="Event.kind.opportunity_won",
        raw_or_canonical="normalized timeline event",
        transition_meaning="Opportunity reached won or closed-won posture.",
        time_semantics="Opportunity CloseDate or normalized closed-won event time.",
        sale_revenue_posture="sale_evidence_not_revenue_recognition",
        data_classes=[DataClass.OPS],
        staff_ui_posture="allowed",
        agent_analytics_posture="conversion quality candidate",
        registry_status=PersonJourneyRegistryStatus.APPROVED_CANDIDATE,
        suggested_term="opportunity_won",
        suggested_definition="Opportunity reached won or closed-won posture.",
        suggested_synonyms=["closed_won"],
        affected_questions=["Q20 Revenue evidence by campaign"],
        affected_read_models=["campaign_opportunity_conversion"],
        risks=["Needs win definition review before source-quality reporting."],
    ),
    _person_journey_entry(
        "event.opportunity_lost",
        kind=PersonJourneyRegistryEntryKind.EVENT,
        label="Opportunity lost",
        journey_phase="sale_conversion",
        state_category="closed_lost_state",
        source_object="Salesforce Opportunity",
        source_system="salesforce",
        source_field="Event.kind.opportunity_lost",
        raw_or_canonical="normalized timeline event",
        transition_meaning="Opportunity reached lost or closed-lost posture.",
        time_semantics="Opportunity CloseDate or normalized closed-lost event time.",
        sale_revenue_posture="lost_sale_context",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed",
        agent_analytics_posture="conversion quality candidate after loss taxonomy review",
        registry_status=PersonJourneyRegistryStatus.APPROVED_CANDIDATE,
        suggested_term="opportunity_lost",
        suggested_definition="Opportunity reached lost or closed-lost posture.",
        suggested_synonyms=["closed_lost"],
        affected_questions=["Q20 Revenue evidence by campaign"],
        affected_read_models=["campaign_opportunity_conversion"],
        risks=["Loss reason taxonomy is required before detailed manager reporting."],
    ),
    _person_journey_entry(
        "event.task_completed",
        kind=PersonJourneyRegistryEntryKind.EVENT,
        label="Task completed",
        journey_phase="follow_up_activity",
        state_category="follow_up_completion",
        source_object="Salesforce Task",
        source_system="salesforce",
        source_field="Event.kind.task_completed",
        raw_or_canonical="normalized timeline event",
        transition_meaning="A follow-up task was completed for the person journey.",
        time_semantics="Task completed date/time or normalized event occurred_at.",
        data_classes=[DataClass.OPS],
        staff_ui_posture="allowed",
        agent_analytics_posture="review-only until task-type taxonomy approved",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="follow_up_completed_event",
        suggested_definition="Operational follow-up completion evidence for journey recovery analytics.",
        suggested_synonyms=["task_completed", "follow_up_completed"],
        affected_questions=["Q12 Consultation follow-up backlog"],
        affected_read_models=["consultation_followup", "person_journey_coverage"],
        risks=["Task type and owner semantics must be reviewed before productivity reporting."],
    ),
    _person_journey_entry(
        "event.case_opened",
        kind=PersonJourneyRegistryEntryKind.EVENT,
        label="Case opened",
        journey_phase="support_case",
        state_category="support_state",
        source_object="Salesforce Case",
        source_system="salesforce",
        source_field="Event.kind.case_opened",
        raw_or_canonical="normalized timeline event",
        transition_meaning="Support or service case opened during the person journey.",
        time_semantics="Case CreatedDate or normalized event occurred_at.",
        data_classes=[DataClass.OPS],
        staff_ui_posture="allowed",
        agent_analytics_posture="review-only until case taxonomy approved",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="support_case_opened_event",
        suggested_definition="Support case evidence that may explain journey friction after review.",
        suggested_synonyms=["case_opened"],
        affected_questions=["Q12 Consultation follow-up backlog"],
        affected_read_models=["person_journey_coverage"],
        risks=["Case taxonomy and sensitivity policy must be reviewed before manager reporting."],
    ),
    _person_journey_entry(
        "event.call_reference_found",
        kind=PersonJourneyRegistryEntryKind.EVENT,
        label="Call reference found",
        journey_phase="follow_up_activity",
        state_category="call_artifact_reference",
        source_object="Salesforce Task",
        source_system="salesforce",
        source_field="Event.kind.call_reference_found",
        raw_or_canonical="normalized timeline event with artifact reference",
        transition_meaning="Call artifact reference was detected; not analytics meaning.",
        time_semantics="Task/event time only; recording metadata is not inspected.",
        data_classes=[DataClass.CALL_RECORDING_REF],
        staff_ui_posture="pending review",
        agent_analytics_posture="not allowed",
        registry_status=PersonJourneyRegistryStatus.BLOCKED,
        suggested_term="call_reference_found",
        suggested_definition="Call recording/reference evidence detected in timeline data.",
        downstream_surfaces=["blocked"],
        risks=["Must not be used until call recording policy is approved."],
    ),
    _person_journey_entry(
        "event.carestack_consultation",
        kind=PersonJourneyRegistryEntryKind.EVENT,
        label="CareStack consultation event",
        journey_phase="consultation",
        state_category="appointment_lifecycle",
        source_object="CareStack Appointment",
        source_system="carestack",
        source_field="Event.kind.consultation_*",
        raw_or_canonical="normalized timeline event",
        transition_meaning="Person moved through scheduled/completed/cancelled/no-show consultation posture.",
        time_semantics="CareStack appointment scheduled/start/status time; timezone normalization required.",
        data_classes=[DataClass.OPS],
        staff_ui_posture="allowed",
        agent_analytics_posture="approved aggregate candidate",
        registry_status=PersonJourneyRegistryStatus.APPROVED_CANDIDATE,
        suggested_term="consultation_lifecycle_event",
        suggested_definition="CareStack consultation lifecycle evidence used for aggregate consultation analytics.",
        suggested_synonyms=["consultation", "appointment"],
        affected_questions=["Q06 Consultation conversion by source", "Q12 Consultation follow-up backlog"],
        affected_read_models=["lead_conversion", "consultation_followup"],
        risks=["Timezone shifts must be resolved before exact period claims."],
    ),
    _person_journey_entry(
        "event.carestack_treatment_completed",
        kind=PersonJourneyRegistryEntryKind.EVENT,
        label="CareStack treatment completed",
        journey_phase="treatment",
        state_category="treatment_completed_event",
        source_object="CareStack treatment evidence",
        source_system="carestack",
        source_field="Event.kind.treatment_completed",
        raw_or_canonical="normalized timeline event",
        transition_meaning="Treatment reached completed posture.",
        time_semantics="Treatment completed event time; exact clinical timestamps remain service-owned.",
        sale_revenue_posture="treatment_completion_not_payment_revenue",
        data_classes=[DataClass.OPS, DataClass.BILLING],
        staff_ui_posture="allowed by role/posture",
        agent_analytics_posture="review-only to approved depending on term",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="treatment_completed_event",
        suggested_definition="Treatment completion evidence that is distinct from collected payment evidence.",
        suggested_synonyms=["treatment_completed"],
        affected_questions=["Q20 Revenue evidence by campaign"],
        affected_read_models=["treatment_revenue"],
        risks=["Must not expose clinical notes or PHI-bearing procedure detail."],
    ),
    _person_journey_entry(
        "event.carestack_payment_recorded",
        kind=PersonJourneyRegistryEntryKind.EVENT,
        label="CareStack payment recorded",
        journey_phase="billing_revenue",
        state_category="payment_recorded_event",
        source_object="CareStack accounting transaction",
        source_system="carestack",
        source_field="Event.kind.payment_recorded",
        raw_or_canonical="normalized aggregate billing event",
        transition_meaning="Collected payment evidence was recorded.",
        time_semantics="Payment transaction recorded time is the collected-revenue anchor.",
        sale_revenue_posture="collected_revenue_aggregate_only",
        data_classes=[DataClass.BILLING, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed by role as aggregate/bucketed value",
        agent_analytics_posture="aggregate-only with billing policy",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="payment_recorded_event",
        suggested_definition="Aggregate payment-recorded evidence for collected revenue analytics.",
        suggested_synonyms=["payment_recorded", "collected_payment"],
        affected_questions=["Q20 Revenue evidence by campaign"],
        affected_read_models=["treatment_revenue"],
        risks=["Must remain aggregate-only until export/audit and billing policy are approved."],
    ),
    _person_journey_entry(
        "event.carestack_payment_applied",
        kind=PersonJourneyRegistryEntryKind.EVENT,
        label="CareStack payment applied allocation leg",
        journey_phase="billing_revenue",
        state_category="allocation_leg_event",
        source_object="CareStack accounting transaction",
        source_system="carestack",
        source_field="Event.kind.payment_applied",
        raw_or_canonical="normalized billing event",
        transition_meaning="CareStack allocation leg was recorded; it is accounting plumbing, not collected cash.",
        time_semantics="Allocation event time must not be used as collected-revenue timing.",
        sale_revenue_posture="excluded_from_collected_revenue",
        data_classes=[DataClass.BILLING, DataClass.INTEGRATION_METADATA],
        staff_ui_posture="allowed as explanatory accounting metadata",
        agent_analytics_posture="review-only accounting caveat",
        registry_status=PersonJourneyRegistryStatus.REVIEW_ONLY,
        suggested_term="payment_applied_allocation_event",
        suggested_definition="Allocation-leg payment event excluded from collected cash and manager revenue answers.",
        suggested_synonyms=["payment_applied", "allocation_leg"],
        affected_questions=["Q17 Paid leads with payment evidence", "Q20 Revenue evidence by campaign"],
        affected_read_models=["treatment_revenue"],
        risks=["If treated as revenue, allocation legs can multiply collected totals."],
    ),
)


_DATASETS: tuple[DatasetPolicyOut, ...] = (
    DatasetPolicyOut(
        id="person_journey_registry",
        title="Person Journey Field/Event Registry",
        purpose="Project governed person-linked fields and timeline events into review-only semantic catalog proposal candidates.",
        data_classes=sorted(
            {
                data_class
                for entry in _PERSON_JOURNEY_REGISTRY
                for data_class in entry.data_classes
            }
        ),
        allowed_actions=[
            DataIntelligenceAction.DATASET_DISCOVERY,
            DataIntelligenceAction.PERSON_JOURNEY_PROPOSAL,
            DataIntelligenceAction.GAP_BRIEF,
        ],
        allowed_output_levels=[OutputLevel.AGGREGATE],
        default_row_sample_limit=0,
        hard_row_sample_cap=0,
        default_top_value_cap=_DEFAULT_TOP_VALUE_CAP,
        hard_profile_group_cap=_HARD_PROFILE_GROUP_CAP,
        fields=[
            _field(
                entry.id,
                data_class=entry.data_classes[0],
                source_system=entry.source_system,
                description=entry.suggested_definition,
                output_levels=[OutputLevel.AGGREGATE],
                business_meaning=entry.transition_meaning,
                source_precedence=entry.source_precedence,
                time_semantics=entry.time_semantics,
                registry_status=entry.registry_status,
                manager_answer_posture=entry.manager_answer_posture,
                affected_read_models=entry.affected_read_models,
                affected_manager_questions=entry.affected_questions,
                data_quality_evidence_refs=entry.data_quality_evidence_refs,
                data_quality_posture=(
                    "blocked"
                    if entry.manager_answer_posture == "blocked"
                    else "aggregate_evidence_required"
                ),
                caveats=entry.risks,
            )
            for entry in _PERSON_JOURNEY_REGISTRY
        ],
        denied_fields=_COMMON_DENIED_FIELDS,
        masks=[],
        warnings=[
            "Registry entries are metadata only and never executable manager analytics by themselves.",
            "Blocked, internal-only, and deferred entries are visible for reviewer context but fail closed.",
        ],
    ),
    DatasetPolicyOut(
        id="lead_source_profile",
        title="Lead Source Profile",
        purpose="Profile lead source, provider, campaign, status, and location coverage.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        allowed_actions=[
            DataIntelligenceAction.DATASET_DISCOVERY,
            DataIntelligenceAction.FIELD_PROFILE,
            DataIntelligenceAction.EVIDENCE_COVERAGE,
            DataIntelligenceAction.BOUNDED_SAMPLE,
            DataIntelligenceAction.SEMANTIC_MAPPING_PROPOSAL,
            DataIntelligenceAction.GAP_BRIEF,
        ],
        allowed_output_levels=[OutputLevel.AGGREGATE, OutputLevel.ROW_SAMPLE],
        default_row_sample_limit=_DEFAULT_ROW_SAMPLE_LIMIT,
        hard_row_sample_cap=_HARD_ROW_SAMPLE_CAP,
        default_top_value_cap=_DEFAULT_TOP_VALUE_CAP,
        hard_profile_group_cap=_HARD_PROFILE_GROUP_CAP,
        fields=[
            _field(
                "lead_source",
                data_class=DataClass.OPS,
                source_system="salesforce",
                description="CRM-safe lead source label.",
                business_meaning="Fallback CRM lead source grouping for acquisition and conversion analytics.",
                source_precedence=["last_touch_source", "lead_source", "campaign"],
                time_semantics="Lead-source manager windows use lead created time unless an approved attribution timestamp exists.",
                affected_read_models=["lead_conversion", "lead_source_profile", "paid_leads"],
                affected_manager_questions=_PERSON_JOURNEY_COMMON_QUESTIONS,
                data_quality_evidence_refs=["lead.lead_source", "lead.campaign"],
                caveats=["Source labels can be missing or unmapped until catalog review approves attribution terms."],
            ),
            _field("source_provider", data_class=DataClass.INTEGRATION_METADATA, source_system="fusion", description="Originating provider key."),
            _field(
                "campaign",
                data_class=DataClass.OPS,
                source_system="salesforce",
                description="CRM-safe campaign/source detail.",
                business_meaning="Campaign evidence used below source/channel grouping.",
                source_precedence=["last_touch_campaign", "campaign"],
                time_semantics="Campaign windows follow the service-owned lead attribution window.",
                affected_read_models=["lead_conversion", "campaign_opportunity_conversion"],
                affected_manager_questions=_PERSON_JOURNEY_COMMON_QUESTIONS,
                data_quality_evidence_refs=["lead.campaign"],
                caveats=["Campaign values can be sparse and require taxonomy review before confident drill-down answers."],
            ),
            _field(
                "last_touch_source",
                data_class=DataClass.OPS,
                source_system="salesforce",
                description="Most recent source evidence used by approved attribution read models.",
                business_meaning="Preferred source evidence for last-touch acquisition attribution.",
                source_precedence=["last_touch_source", "lead_source", "campaign"],
                time_semantics="Uses lead created/updated time unless last-touch event time is approved by the read model.",
                affected_read_models=["lead_conversion", "lead_source_profile", "paid_leads"],
                affected_manager_questions=_PERSON_JOURNEY_COMMON_QUESTIONS,
                data_quality_evidence_refs=["lead.lead_source", "lead.campaign"],
                caveats=["Manager answers must disclose attribution fallback when last-touch evidence is missing."],
            ),
            _field("last_touch_medium", data_class=DataClass.OPS, source_system="salesforce", description="Most recent medium evidence used beneath source/channel grouping."),
            _field("last_touch_campaign", data_class=DataClass.OPS, source_system="salesforce", description="Most recent campaign evidence used beneath source/channel grouping."),
            _field(
                "assigned_center",
                data_class=DataClass.INTEGRATION_METADATA,
                source_system="salesforce",
                description="Free-text lead center evidence used for Fusion location mapping.",
                business_meaning="Lead location evidence before consultation-location override.",
                source_precedence=["consultation.location_id", "lead.assigned_center", "lead.location_id"],
                time_semantics="Current lead-location evidence; not a consultation occurrence time.",
                affected_read_models=["lead_conversion", "lead_source_profile", "paid_leads"],
                affected_manager_questions=["Q01 Lead source performance", "Q06 Consultation conversion by source", "Q20 Revenue evidence by campaign"],
                data_quality_evidence_refs=["lead.location_id", "consultation.location_id"],
                caveats=["Free-text center values can be stale and should be caveated when mismatch evidence is present."],
            ),
            _field(
                "business_unit",
                data_class=DataClass.OPS,
                source_system="salesforce",
                description="Salesforce business-unit segmentation evidence.",
                business_meaning="Lead business-unit segment used for aggregate manager analytics only after taxonomy review.",
                source_precedence=["lead.business_unit"],
                time_semantics="Current lead segmentation evidence; not an event timestamp.",
                registry_status="review_only_taxonomy_required",
                manager_answer_posture="generated_with_caveat",
                affected_read_models=["lead_conversion", "lead_source_profile"],
                affected_manager_questions=["Q01 Lead source performance", "Q06 Consultation conversion by source"],
                data_quality_evidence_refs=["lead.business_unit"],
                data_quality_posture="taxonomy_review_required",
                caveats=["Business-unit labels require taxonomy review before manager answers compare segments."],
            ),
            _field(
                "consultation_scheduled_at",
                data_class=DataClass.OPS,
                source_system="salesforce",
                description="Salesforce lead mirror of consultation scheduled timestamp.",
                business_meaning="Lead-level consultation scheduled-time evidence for conversion analytics.",
                source_precedence=["consultation.scheduled_at", "lead.consultation_scheduled_at"],
                time_semantics="Consultation occurrence time candidate; service-owned consultation read models remain authoritative for manager answer windows.",
                registry_status="review_only_time_semantics",
                manager_answer_posture="generated_with_caveat",
                affected_read_models=["lead_conversion", "consultation_followup"],
                affected_manager_questions=["Q06 Consultation conversion by source", "Q12 Consultation follow-up backlog"],
                data_quality_evidence_refs=["lead.consultation_scheduled_at", "consultation.scheduled_at"],
                data_quality_posture="time_semantics_review_required",
                caveats=["Must not be conflated with provider-created time or completed consultation time."],
            ),
            _field(
                "location_mismatch",
                data_class=DataClass.INTEGRATION_METADATA,
                source_system="fusion",
                description="Computed data-quality flag for assigned-center vs consultation-location disagreement.",
                output_levels=[OutputLevel.AGGREGATE],
                business_meaning="Aggregate data-quality signal for lead-center and consultation-location disagreement.",
                source_precedence=["consultation.location_id", "lead.assigned_center"],
                time_semantics="Computed at read time from aggregate lead and consultation evidence.",
                registry_status="review_only_quality_signal",
                manager_answer_posture="generated_with_caveat",
                affected_read_models=["lead_conversion", "lead_source_profile"],
                affected_manager_questions=["Q06 Consultation conversion by source", "Q20 Revenue evidence by campaign"],
                data_quality_evidence_refs=["lead.location_id", "consultation.location_id", "location_mismatch.aggregate"],
                data_quality_posture="caveat_when_present",
                caveats=["Location mismatch is evidence quality, not patient movement or staff attribution."],
            ),
            _field("owner_id", data_class=DataClass.INTEGRATION_METADATA, source_system="salesforce", description="CRM-safe Salesforce owner evidence.", masked_in_samples=True),
            _field("lead_status", data_class=DataClass.OPS, source_system="salesforce", description="Lead lifecycle status."),
            _field("created_at", data_class=DataClass.OPS, source_system="salesforce", description="Lead creation timestamp."),
            _field("location_id", data_class=DataClass.INTEGRATION_METADATA, source_system="fusion", description="Fusion location id."),
        ],
        denied_fields=_COMMON_DENIED_FIELDS,
        masks=["person_uid", "external_id", "phone", "email", "name"],
    ),
    DatasetPolicyOut(
        id="identity_linkage",
        title="Identity Linkage Coverage",
        purpose="Measure Salesforce lead to Fusion person to CareStack patient linkage coverage.",
        data_classes=[DataClass.IDENTITY, DataClass.INTEGRATION_METADATA],
        allowed_actions=[
            DataIntelligenceAction.DATASET_DISCOVERY,
            DataIntelligenceAction.LINKAGE_COVERAGE,
            DataIntelligenceAction.BOUNDED_SAMPLE,
            DataIntelligenceAction.GAP_BRIEF,
        ],
        allowed_output_levels=[OutputLevel.AGGREGATE, OutputLevel.ROW_SAMPLE],
        default_row_sample_limit=_DEFAULT_ROW_SAMPLE_LIMIT,
        hard_row_sample_cap=_HARD_ROW_SAMPLE_CAP,
        default_top_value_cap=_DEFAULT_TOP_VALUE_CAP,
        hard_profile_group_cap=_HARD_PROFILE_GROUP_CAP,
        fields=[
            _field("person_uid", data_class=DataClass.IDENTITY, source_system="fusion", description="Canonical Fusion person id.", masked_in_samples=True),
            _field("salesforce_lead_id", data_class=DataClass.INTEGRATION_METADATA, source_system="salesforce", description="Salesforce lead id.", masked_in_samples=True),
            _field("carestack_patient_id", data_class=DataClass.INTEGRATION_METADATA, source_system="carestack", description="CareStack patient id.", masked_in_samples=True),
            _field("linkage_status", data_class=DataClass.INTEGRATION_METADATA, source_system="fusion", description="Computed linkage state."),
            _field("source_provider", data_class=DataClass.INTEGRATION_METADATA, source_system="fusion", description="Originating provider key."),
        ],
        denied_fields=_COMMON_DENIED_FIELDS,
        masks=["person_uid", "salesforce_lead_id", "carestack_patient_id"],
    ),
    DatasetPolicyOut(
        id="consultation_followup",
        title="Consultation Follow-up Evidence",
        purpose="Profile consultation status, stale follow-up, owner, location, and next-action evidence.",
        data_classes=[DataClass.OPS, DataClass.INTEGRATION_METADATA],
        allowed_actions=[
            DataIntelligenceAction.DATASET_DISCOVERY,
            DataIntelligenceAction.FIELD_PROFILE,
            DataIntelligenceAction.EVIDENCE_COVERAGE,
            DataIntelligenceAction.BOUNDED_SAMPLE,
            DataIntelligenceAction.GAP_BRIEF,
        ],
        allowed_output_levels=[OutputLevel.AGGREGATE, OutputLevel.ROW_SAMPLE],
        default_row_sample_limit=_DEFAULT_ROW_SAMPLE_LIMIT,
        hard_row_sample_cap=_HARD_ROW_SAMPLE_CAP,
        default_top_value_cap=_DEFAULT_TOP_VALUE_CAP,
        hard_profile_group_cap=_HARD_PROFILE_GROUP_CAP,
        fields=[
            _field("consultation_status", data_class=DataClass.OPS, source_system="carestack", description="Consultation lifecycle status."),
            _field("scheduled_at", data_class=DataClass.OPS, source_system="carestack", description="Consultation scheduled timestamp."),
            _field("last_followup_at", data_class=DataClass.OPS, source_system="fusion", description="Last recorded follow-up timestamp."),
            _field("owner_id", data_class=DataClass.INTEGRATION_METADATA, source_system="fusion", description="Owner/operator id.", masked_in_samples=True),
            _field("location_id", data_class=DataClass.INTEGRATION_METADATA, source_system="fusion", description="Fusion location id."),
        ],
        denied_fields=_COMMON_DENIED_FIELDS,
        masks=["person_uid", "owner_id", "external_id", "phone", "email", "name"],
    ),
    DatasetPolicyOut(
        id="treatment_revenue",
        title="Treatment Revenue Evidence",
        purpose="Profile bounded billing evidence for collected revenue analytics.",
        data_classes=[DataClass.BILLING, DataClass.INTEGRATION_METADATA],
        allowed_actions=[
            DataIntelligenceAction.DATASET_DISCOVERY,
            DataIntelligenceAction.FIELD_PROFILE,
            DataIntelligenceAction.EVIDENCE_COVERAGE,
            DataIntelligenceAction.BOUNDED_SAMPLE,
            DataIntelligenceAction.GAP_BRIEF,
        ],
        allowed_output_levels=[OutputLevel.AGGREGATE, OutputLevel.ROW_SAMPLE],
        default_row_sample_limit=_DEFAULT_ROW_SAMPLE_LIMIT,
        hard_row_sample_cap=_HARD_ROW_SAMPLE_CAP,
        default_top_value_cap=_DEFAULT_TOP_VALUE_CAP,
        hard_profile_group_cap=_HARD_PROFILE_GROUP_CAP,
        fields=[
            _field("payment_amount_bucket", data_class=DataClass.BILLING, source_system="carestack", description="Bucketed payment amount, not raw card/payment detail.", billing_sensitive=True),
            _field(
                "collected_amount_aggregate",
                data_class=DataClass.BILLING,
                source_system="fusion_interaction",
                description="Net collected cash aggregate excluding payment_applied allocation legs.",
                output_levels=[OutputLevel.AGGREGATE],
                billing_sensitive=True,
                business_meaning="Aggregate net collected cash evidence, distinct from opportunity amount and treatment status.",
                source_precedence=["payment_recorded", "payment_refunded", "payment_reversed", "payment_applied_exclusion"],
                time_semantics="Uses payment recorded/refund/reversal event time from the service-owned aggregate.",
                registry_status="review_only_aggregate_billing",
                manager_answer_posture="generated_with_caveat",
                affected_read_models=["treatment_revenue", "lead_source_profile"],
                affected_manager_questions=["Q02 Paid leads by source", "Q17 Paid leads with payment evidence", "Q20 Revenue evidence by campaign"],
                data_quality_evidence_refs=["billing.payment_recorded", "billing.payment_kind", "payment_applied_exclusion.aggregate"],
                data_quality_posture="aggregate_billing_evidence_required",
                caveats=["Must remain aggregate-only and must not include payment_applied allocation legs."],
            ),
            _field("payment_date", data_class=DataClass.BILLING, source_system="carestack", description="Payment event date.", billing_sensitive=True),
            _field("payment_kind", data_class=DataClass.BILLING, source_system="carestack", description="Normalized payment/refund/adjustment kind.", billing_sensitive=True),
            _field(
                "payment_applied_exclusion",
                data_class=DataClass.BILLING,
                source_system="carestack",
                description="Allocation-leg payment_applied evidence excluded from Collected.",
                output_levels=[OutputLevel.AGGREGATE],
                billing_sensitive=True,
                business_meaning="Aggregate evidence that allocation legs are excluded from collected revenue answers.",
                source_precedence=["payment_recorded", "payment_refunded", "payment_reversed", "payment_applied"],
                time_semantics="Allocation timestamps are not collected-revenue event times for manager answers.",
                registry_status="review_only_accounting_caveat",
                manager_answer_posture="generated_with_caveat",
                affected_read_models=["treatment_revenue"],
                affected_manager_questions=["Q17 Paid leads with payment evidence", "Q20 Revenue evidence by campaign"],
                data_quality_evidence_refs=["billing.payment_kind", "payment_applied_exclusion.aggregate"],
                data_quality_posture="caveat_when_present",
                caveats=["Including allocation legs can inflate collected revenue and must remain excluded."],
            ),
            _field("treatment_status", data_class=DataClass.OPS, source_system="carestack", description="Treatment lifecycle status."),
            _field("location_id", data_class=DataClass.INTEGRATION_METADATA, source_system="fusion", description="Fusion location id."),
        ],
        denied_fields=_COMMON_DENIED_FIELDS + ["card_number", "payment_token"],
        masks=["person_uid", "external_id", "payment_reference", "phone", "email", "name"],
        warnings=["Billing-sensitive fields must stay capped, masked, and audited."],
    ),
)
