"""Pydantic DTOs for Data Intelligence local tooling."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DataClass(StrEnum):
    OPS = "ops"
    IDENTITY = "identity"
    INTEGRATION_METADATA = "integration_metadata"
    BILLING = "billing"
    PHI_ADJACENT = "phi_adjacent"
    PHI = "phi"
    RAW_PAYLOAD = "raw_payload"
    CALL_RECORDING_REF = "call_recording_ref"
    INTERNAL = "internal"


class OutputLevel(StrEnum):
    AGGREGATE = "aggregate"
    ROW_SAMPLE = "row_sample"


class DataIntelligenceAction(StrEnum):
    DATASET_DISCOVERY = "dataset_discovery"
    FIELD_PROFILE = "field_profile"
    LINKAGE_COVERAGE = "linkage_coverage"
    EVIDENCE_COVERAGE = "evidence_coverage"
    BOUNDED_SAMPLE = "bounded_sample"
    SEMANTIC_MAPPING_PROPOSAL = "semantic_mapping_proposal"
    PERSON_JOURNEY_PROPOSAL = "person_journey_proposal"
    GAP_BRIEF = "gap_brief"


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    CLARIFY = "clarify"


class SemanticFieldContractOut(BaseModel):
    business_meaning: str
    source_precedence: list[str]
    time_semantics: str
    registry_status: str
    manager_answer_posture: str
    affected_read_models: list[str] = Field(default_factory=list)
    affected_manager_questions: list[str] = Field(default_factory=list)
    data_quality_evidence_refs: list[str] = Field(default_factory=list)
    data_quality_posture: str = "not_evaluated"
    caveats: list[str] = Field(default_factory=list)


class FieldPolicyOut(BaseModel):
    name: str
    data_class: DataClass
    source_system: str
    output_levels: list[OutputLevel]
    masked_in_samples: bool = False
    billing_sensitive: bool = False
    description: str
    semantic_contract: SemanticFieldContractOut


class DatasetPolicyOut(BaseModel):
    id: str
    title: str
    status: str = "approved"
    purpose: str
    data_classes: list[DataClass]
    allowed_actions: list[DataIntelligenceAction]
    allowed_output_levels: list[OutputLevel]
    default_row_sample_limit: int
    hard_row_sample_cap: int
    default_top_value_cap: int
    hard_profile_group_cap: int
    fields: list[FieldPolicyOut]
    denied_fields: list[str]
    masks: list[str]
    warnings: list[str] = Field(default_factory=list)


class PolicyDefaultsOut(BaseModel):
    environment: str
    role: str
    row_level_samples: str
    default_row_sample_limit: int
    hard_row_sample_cap: int
    default_top_value_cap: int
    hard_profile_group_cap: int
    default_date_window_days: int
    export_allowed: bool
    raw_payload_allowed: bool
    phi_allowed: bool
    audit_required: bool


class DatasetDiscoveryOut(BaseModel):
    policy: PolicyDefaultsOut
    datasets: list[DatasetPolicyOut]


class PolicyPreflightIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: DataIntelligenceAction
    dataset_id: str
    fields: list[str] = Field(default_factory=list)
    output_level: OutputLevel = OutputLevel.AGGREGATE
    row_limit: int | None = None
    top_limit: int | None = None
    include_phi: bool = False
    include_raw_payload: bool = False
    export: bool = False
    write: bool = False


class PolicyPreflightOut(BaseModel):
    decision: PolicyDecision
    reasons: list[str]
    action: DataIntelligenceAction
    dataset_id: str
    output_level: OutputLevel
    row_limit: int | None
    top_limit: int
    data_classes: list[DataClass]
    fields: list[str]
    masks: list[str]
    audit_required: bool = True
    raw_sql_allowed: bool = False
    raw_payload_allowed: bool = False
    phi_allowed: bool = False
    export_allowed: bool = False
    write_allowed: bool = False


class TopValueOut(BaseModel):
    value: str
    count: int


class FieldProfileOut(BaseModel):
    dataset_id: str
    field: str
    decision: PolicyDecision
    row_count: int
    null_count: int | None = None
    null_rate: float | None = None
    null_rate_posture: str
    top_values: list[TopValueOut]
    data_class: DataClass
    source_system: str
    output_level: OutputLevel = OutputLevel.AGGREGATE
    masked_in_samples: bool
    billing_sensitive: bool
    warnings: list[str] = Field(default_factory=list)


class LinkageExampleOut(BaseModel):
    person_uid_masked: str
    linkage_status: str
    source_systems: list[str]
    salesforce_source_id_masked: str | None = None
    carestack_source_id_masked: str | None = None


class LinkageCoverageOut(BaseModel):
    dataset_id: str
    decision: PolicyDecision
    output_level: OutputLevel = OutputLevel.ROW_SAMPLE
    sample_limit: int
    data_classes: list[DataClass]
    total_persons: int
    salesforce_person_count: int
    carestack_person_count: int
    linked_salesforce_carestack_count: int
    salesforce_only_count: int
    carestack_only_count: int
    salesforce_to_carestack_rate: float | None
    carestack_to_salesforce_rate: float | None
    examples: list[LinkageExampleOut]
    warnings: list[str] = Field(default_factory=list)


class EvidenceMetricOut(BaseModel):
    key: str
    label: str
    total_count: int
    evidence_count: int
    missing_count: int
    coverage_rate: float | None
    data_classes: list[DataClass]
    warnings: list[str] = Field(default_factory=list)


class EvidenceCoverageOut(BaseModel):
    decision: PolicyDecision
    output_level: OutputLevel = OutputLevel.AGGREGATE
    metrics: list[EvidenceMetricOut]
    warnings: list[str] = Field(default_factory=list)


class BoundedSampleOut(BaseModel):
    dataset_id: str
    decision: PolicyDecision
    output_level: OutputLevel = OutputLevel.ROW_SAMPLE
    row_limit: int
    row_count: int
    data_classes: list[DataClass]
    masks: list[str]
    rows: list[dict[str, object]]
    warnings: list[str] = Field(default_factory=list)


class SemanticMappingCandidateOut(BaseModel):
    source_field: str
    raw_value: str
    proposed_term: str
    confidence: float
    evidence_count: int
    rationale: str
    review_status: str = "proposed"


class SemanticMappingProposalOut(BaseModel):
    dataset_id: str
    decision: PolicyDecision
    output_level: OutputLevel = OutputLevel.AGGREGATE
    source_fields: list[str]
    top_limit: int
    candidates: list[SemanticMappingCandidateOut]
    warnings: list[str] = Field(default_factory=list)


class PersonJourneyRegistryStatus(StrEnum):
    APPROVED_CANDIDATE = "approved_candidate"
    REVIEW_ONLY = "review_only"
    BLOCKED = "blocked"
    INTERNAL_ONLY = "internal_only"
    DEFERRED = "deferred"


class PersonJourneyRegistryEntryKind(StrEnum):
    FIELD = "field"
    EVENT = "event"


class PersonJourneyRegistryEntryOut(BaseModel):
    id: str
    kind: PersonJourneyRegistryEntryKind
    label: str
    journey_phase: str
    state_category: str
    source_object: str
    source_system: str
    source_field: str
    raw_or_canonical: str
    transition_meaning: str
    time_semantics: str
    source_precedence: list[str] = Field(default_factory=list)
    sale_revenue_posture: str = "not_applicable"
    manager_answer_posture: str = "generated_with_caveat"
    data_quality_evidence_refs: list[str] = Field(default_factory=list)
    data_classes: list[DataClass]
    staff_ui_posture: str
    agent_analytics_posture: str
    registry_status: PersonJourneyRegistryStatus
    suggested_term: str
    suggested_definition: str
    suggested_synonyms: list[str] = Field(default_factory=list)
    affected_questions: list[str] = Field(default_factory=list)
    affected_read_models: list[str] = Field(default_factory=list)
    downstream_surfaces: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    notes: str = ""


class PersonJourneyCatalogProposalDraftOut(BaseModel):
    raw_value: str
    source_system: str
    source_field: str
    suggested_term: str
    definition: str
    synonyms: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    reason: str
    reviewer_note: str = ""
    affected_questions: list[str] = Field(default_factory=list)
    affected_read_models: list[str] = Field(default_factory=list)
    source_type: str = "agent"
    source_reference_id: str


class PersonJourneyProposalCandidateOut(BaseModel):
    entry: PersonJourneyRegistryEntryOut
    review_only: bool = True
    can_submit_for_review: bool
    executable: bool = False
    approval_allowed: bool = False
    proposal: PersonJourneyCatalogProposalDraftOut | None = None
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PersonJourneyRegistryProposalOut(BaseModel):
    dataset_id: str
    decision: PolicyDecision
    output_level: OutputLevel = OutputLevel.AGGREGATE
    source_fields: list[str]
    candidates: list[PersonJourneyProposalCandidateOut]
    warnings: list[str] = Field(default_factory=list)


class GapBriefFindingOut(BaseModel):
    category: str
    severity: str
    summary: str
    evidence: list[str]
    impacted_questions: list[str]
    recommendation: str


class GapBriefOut(BaseModel):
    decision: PolicyDecision
    output_level: OutputLevel = OutputLevel.AGGREGATE
    generated_from: list[str]
    findings: list[GapBriefFindingOut]
    recommended_linear_titles: list[str]
    warnings: list[str] = Field(default_factory=list)
