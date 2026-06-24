"""Tool registry — the single source of truth for what AI agents can call."""

from __future__ import annotations

from .analytics_tools import run_analytics_query
from .base import ToolSpec
from .data_intelligence_tools import (
    data_intelligence_bounded_sample,
    data_intelligence_discover,
    data_intelligence_evidence_coverage,
    data_intelligence_gap_brief,
    data_intelligence_linkage_coverage,
    data_intelligence_person_journey_proposals,
    data_intelligence_preflight,
    data_intelligence_profile_field,
    data_intelligence_semantic_mapping_proposal,
)
from .export_tools import export_analytics_csv, save_analytics_report_definition
from .manager_chat_tools import ask_manager_analytics
from .ops_tools import create_followup_task, get_ops_person_snapshot
from .person_tools import resolve_person
from .phi_tools import get_phi_person_snapshot
from .revenue_intelligence_tools import read_revenue_intelligence_page

ALL_TOOLS: dict[str, ToolSpec] = {
    "resolve_person": ToolSpec(
        name="resolve_person",
        description=(
            "Resolve a Person by phone or email. "
            "Returns person_uid + display_name or None."
        ),
        fn=resolve_person,
        touches=frozenset({"identity"}),
    ),
    "get_ops_person_snapshot": ToolSpec(
        name="get_ops_person_snapshot",
        description="PHI-free profile of a person: open follow-ups, last lead status.",
        fn=get_ops_person_snapshot,
        touches=frozenset({"ops", "identity"}),
    ),
    "create_followup_task": ToolSpec(
        name="create_followup_task",
        description="Create an OPEN follow-up task for a person.",
        fn=create_followup_task,
        touches=frozenset({"ops"}),
    ),
    "get_phi_person_snapshot": ToolSpec(
        name="get_phi_person_snapshot",
        description="Clinically aware snapshot. Requires a PHI-read principal. Audited.",
        fn=get_phi_person_snapshot,
        touches=frozenset({"phi"}),
    ),
    "run_analytics_query": ToolSpec(
        name="run_analytics_query",
        description=(
            "Run an approved aggregate analytics query by query_id. "
            "No SQL or free-form database access."
        ),
        fn=run_analytics_query,
        touches=frozenset({"ops", "interaction"}),
    ),
    "ask_manager_analytics": ToolSpec(
        name="ask_manager_analytics",
        description=(
            "Plan and optionally execute an approved aggregate manager analytics "
            "question. Deterministic V1; no SQL or free-form DB access."
        ),
        fn=ask_manager_analytics,
        touches=frozenset({"ops", "interaction"}),
    ),
    "export_analytics_csv": ToolSpec(
        name="export_analytics_csv",
        description=(
            "Export an approved aggregate analytics result as CSV. "
            "No XLSX, scheduled, row-level, PHI, or raw payload exports in V1."
        ),
        fn=export_analytics_csv,
        touches=frozenset({"ops", "interaction"}),
    ),
    "save_analytics_report_definition": ToolSpec(
        name="save_analytics_report_definition",
        description=(
            "Create an audited saved aggregate CSV report definition artifact. "
            "No scheduled delivery in V1."
        ),
        fn=save_analytics_report_definition,
        touches=frozenset({"ops", "interaction"}),
    ),
    "data_intelligence_discover": ToolSpec(
        name="data_intelligence_discover",
        description=(
            "List approved Data Intelligence datasets, fields, data classes, "
            "limits, masks, and policy defaults. No SQL or database access."
        ),
        fn=data_intelligence_discover,
        touches=frozenset({"ops", "identity", "interaction"}),
    ),
    "data_intelligence_preflight": ToolSpec(
        name="data_intelligence_preflight",
        description=(
            "Check a proposed Data Intelligence action against the V1 allowlist "
            "before execution. Denies raw payloads, PHI, exports, writes, and "
            "uncapped samples."
        ),
        fn=data_intelligence_preflight,
        touches=frozenset({"ops", "identity", "interaction"}),
    ),
    "data_intelligence_profile_field": ToolSpec(
        name="data_intelligence_profile_field",
        description=(
            "Profile one allowlisted Data Intelligence field through service-owned "
            "aggregates. No SQL, raw payload output, PHI output, exports, or writes."
        ),
        fn=data_intelligence_profile_field,
        touches=frozenset({"ops", "identity", "interaction"}),
    ),
    "data_intelligence_linkage_coverage": ToolSpec(
        name="data_intelligence_linkage_coverage",
        description=(
            "Measure Salesforce-to-CareStack source linkage coverage with bounded "
            "masked examples. No SQL, raw payload output, PHI output, exports, or writes."
        ),
        fn=data_intelligence_linkage_coverage,
        touches=frozenset({"identity"}),
    ),
    "data_intelligence_evidence_coverage": ToolSpec(
        name="data_intelligence_evidence_coverage",
        description=(
            "Measure aggregate semantic evidence coverage for lead source, campaign, "
            "owner, location, consultation, treatment, invoice, and payment evidence. "
            "No SQL, raw payload output, PHI output, exports, or writes."
        ),
        fn=data_intelligence_evidence_coverage,
        touches=frozenset({"ops", "interaction"}),
    ),
    "data_intelligence_bounded_sample": ToolSpec(
        name="data_intelligence_bounded_sample",
        description=(
            "Return a bounded, masked row sample for an approved Data Intelligence "
            "dataset. No SQL, raw payload output, PHI output, exports, or writes."
        ),
        fn=data_intelligence_bounded_sample,
        touches=frozenset({"ops", "identity", "interaction"}),
    ),
    "data_intelligence_semantic_mapping_proposal": ToolSpec(
        name="data_intelligence_semantic_mapping_proposal",
        description=(
            "Generate review-only semantic mapping candidates for lead source and "
            "campaign values. No catalog mutation, SQL, raw payload output, PHI "
            "output, exports, or writes."
        ),
        fn=data_intelligence_semantic_mapping_proposal,
        touches=frozenset({"ops"}),
    ),
    "data_intelligence_person_journey_proposals": ToolSpec(
        name="data_intelligence_person_journey_proposals",
        description=(
            "Project governed person journey field/event registry entries into "
            "review-only Semantic Catalog proposal drafts. Blocked, internal-only, "
            "and deferred entries fail closed. No catalog mutation, SQL, raw payload "
            "output, PHI output, exports, or writes."
        ),
        fn=data_intelligence_person_journey_proposals,
        touches=frozenset({"ops", "identity", "interaction"}),
    ),
    "data_intelligence_gap_brief": ToolSpec(
        name="data_intelligence_gap_brief",
        description=(
            "Generate a non-sensitive Data Intelligence gap brief from approved "
            "coverage and mapping tools. No SQL, raw payload output, PHI output, "
            "exports, or writes."
        ),
        fn=data_intelligence_gap_brief,
        touches=frozenset({"ops", "identity", "interaction"}),
    ),
    "read_revenue_intelligence_page": ToolSpec(
        name="read_revenue_intelligence_page",
        description=(
            "Read one Revenue Intelligence analytics page (executive_overview, "
            "funnel_stages, revenue_intelligence, marketing_performance, "
            "cohort_analytics, caller_performance, coordinator_performance, "
            "doctor_performance, cost_intelligence, bottleneck_detection, "
            "vendor_performance, attribution_analytics, "
            "revenue_influence_matrix). "
            "Services-only; no SQL or direct DB access. "
            "AI hook point for future no-show prediction, "
            "treatment-acceptance probability, budget-allocation recommendation, "
            "and bottleneck / high-performer detection models."
        ),
        fn=read_revenue_intelligence_page,
        touches=frozenset({"ops", "billing", "interaction"}),
    ),
}


def get_tool(name: str) -> ToolSpec:
    if name not in ALL_TOOLS:
        raise KeyError(f"unknown tool: {name}")
    return ALL_TOOLS[name]
