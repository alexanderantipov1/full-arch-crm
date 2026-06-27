"""Data Intelligence local tooling entrypoints.

These tools expose service-owned policy and discovery metadata to internal
agents. They do not accept SQL and do not read repositories directly.
"""

from __future__ import annotations

from packages.audit.service import AuditService
from packages.data_intelligence.schemas import (
    DataIntelligenceAction,
    OutputLevel,
    PersonJourneyRegistryEntryKind,
    PersonJourneyRegistryStatus,
    PolicyPreflightIn,
    PolicyPreflightOut,
)
from packages.data_intelligence.service import DataIntelligenceService

from .base import ToolContext

_AUDIT_VERSION = "data_intelligence_v1"


async def data_intelligence_discover(ctx: ToolContext) -> dict:
    """List approved Data Intelligence datasets and policy defaults."""
    service = DataIntelligenceService()
    discovery = service.list_datasets()
    audit = AuditService(ctx.session)
    await audit.record_tool_call(
        principal=ctx.principal,
        tool_name="data_intelligence_discover",
        extra=_base_audit_extra(
            result_posture="policy_metadata",
            dataset_count=len(discovery.datasets),
            dataset_ids=[dataset.id for dataset in discovery.datasets],
            data_classes=sorted(
                {
                    data_class
                    for dataset in discovery.datasets
                    for data_class in dataset.data_classes
                }
            ),
            row_level_samples=discovery.policy.row_level_samples,
            default_row_sample_limit=discovery.policy.default_row_sample_limit,
            hard_row_sample_cap=discovery.policy.hard_row_sample_cap,
            default_top_value_cap=discovery.policy.default_top_value_cap,
            hard_profile_group_cap=discovery.policy.hard_profile_group_cap,
            audit_required=discovery.policy.audit_required,
            raw_payload_allowed=discovery.policy.raw_payload_allowed,
            phi_allowed=discovery.policy.phi_allowed,
            export_allowed=discovery.policy.export_allowed,
        ),
    )
    return discovery.model_dump(mode="json")


async def data_intelligence_preflight(
    ctx: ToolContext,
    *,
    action: DataIntelligenceAction,
    dataset_id: str,
    fields: list[str] | None = None,
    output_level: OutputLevel = OutputLevel.AGGREGATE,
    row_limit: int | None = None,
    top_limit: int | None = None,
    include_phi: bool = False,
    include_raw_payload: bool = False,
    export: bool = False,
    write: bool = False,
) -> dict:
    """Evaluate a Data Intelligence request against the V1 policy."""
    service = DataIntelligenceService()
    result = service.preflight(
        PolicyPreflightIn(
            action=action,
            dataset_id=dataset_id,
            fields=fields or [],
            output_level=output_level,
            row_limit=row_limit,
            top_limit=top_limit,
            include_phi=include_phi,
            include_raw_payload=include_raw_payload,
            export=export,
            write=write,
        )
    )
    audit = AuditService(ctx.session)
    await audit.record_tool_call(
        principal=ctx.principal,
        tool_name="data_intelligence_preflight",
        extra=_preflight_audit_extra(
            result,
            result_posture="policy_preflight",
        ),
    )
    return result.model_dump(mode="json")


async def data_intelligence_profile_field(
    ctx: ToolContext,
    *,
    dataset_id: str,
    field: str,
    top_limit: int | None = None,
) -> dict:
    """Profile one allowlisted field through service-owned aggregates."""
    service = DataIntelligenceService(ctx.session)
    preflight, profile = await service.profile_field(
        ctx.tenant_id,
        dataset_id=dataset_id,
        field=field,
        top_limit=top_limit,
    )
    audit = AuditService(ctx.session)
    await audit.record_tool_call(
        principal=ctx.principal,
        tool_name="data_intelligence_profile_field",
        extra=_preflight_audit_extra(
            preflight,
            result_posture="aggregate_profile" if profile is not None else "denied",
            profile_available=profile is not None,
        ),
    )
    return {
        "preflight": preflight.model_dump(mode="json"),
        "profile": profile.model_dump(mode="json") if profile is not None else None,
    }


async def data_intelligence_linkage_coverage(
    ctx: ToolContext,
    *,
    sample_limit: int | None = None,
) -> dict:
    """Measure Salesforce-to-CareStack source linkage coverage."""
    service = DataIntelligenceService(ctx.session)
    preflight, coverage = await service.source_linkage_coverage(
        ctx.tenant_id,
        sample_limit=sample_limit,
    )
    audit = AuditService(ctx.session)
    await audit.record_tool_call(
        principal=ctx.principal,
        tool_name="data_intelligence_linkage_coverage",
        extra=_preflight_audit_extra(
            preflight,
            result_posture="bounded_masked_sample" if coverage is not None else "denied",
            example_count=len(coverage.examples) if coverage is not None else 0,
        ),
    )
    return {
        "preflight": preflight.model_dump(mode="json"),
        "coverage": coverage.model_dump(mode="json") if coverage is not None else None,
    }


async def data_intelligence_evidence_coverage(ctx: ToolContext) -> dict:
    """Measure aggregate evidence coverage for semantic analytics."""
    service = DataIntelligenceService(ctx.session)
    preflights, coverage = await service.evidence_coverage(ctx.tenant_id)
    audit = AuditService(ctx.session)
    await audit.record_tool_call(
        principal=ctx.principal,
        tool_name="data_intelligence_evidence_coverage",
        extra=_multi_preflight_audit_extra(
            preflights,
            result_posture="aggregate_evidence" if coverage is not None else "denied",
            metric_count=len(coverage.metrics) if coverage is not None else 0,
        ),
    )
    return {
        "preflights": [
            preflight.model_dump(mode="json") for preflight in preflights
        ],
        "coverage": coverage.model_dump(mode="json") if coverage is not None else None,
    }


async def data_intelligence_bounded_sample(
    ctx: ToolContext,
    *,
    dataset_id: str,
    row_limit: int | None = None,
) -> dict:
    """Return a bounded, masked sample for one approved dataset."""
    service = DataIntelligenceService(ctx.session)
    preflight, sample = await service.bounded_sample(
        ctx.tenant_id,
        dataset_id=dataset_id,
        row_limit=row_limit,
    )
    audit = AuditService(ctx.session)
    await audit.record_tool_call(
        principal=ctx.principal,
        tool_name="data_intelligence_bounded_sample",
        extra=_preflight_audit_extra(
            preflight,
            result_posture="bounded_masked_sample" if sample is not None else "denied",
            row_count=sample.row_count if sample is not None else 0,
        ),
    )
    return {
        "preflight": preflight.model_dump(mode="json"),
        "sample": sample.model_dump(mode="json") if sample is not None else None,
    }


async def data_intelligence_semantic_mapping_proposal(
    ctx: ToolContext,
    *,
    top_limit: int | None = None,
) -> dict:
    """Propose review-only semantic source mappings from allowlisted evidence."""
    service = DataIntelligenceService(ctx.session)
    preflight, proposal = await service.semantic_mapping_proposal(
        ctx.tenant_id,
        top_limit=top_limit,
    )
    audit = AuditService(ctx.session)
    await audit.record_tool_call(
        principal=ctx.principal,
        tool_name="data_intelligence_semantic_mapping_proposal",
        extra=_preflight_audit_extra(
            preflight,
            result_posture=(
                "review_only_semantic_proposal" if proposal is not None else "denied"
            ),
            candidate_count=len(proposal.candidates) if proposal is not None else 0,
        ),
    )
    return {
        "preflight": preflight.model_dump(mode="json"),
        "proposal": proposal.model_dump(mode="json") if proposal is not None else None,
    }


async def data_intelligence_person_journey_proposals(
    ctx: ToolContext,
    *,
    statuses: list[PersonJourneyRegistryStatus] | None = None,
    kinds: list[PersonJourneyRegistryEntryKind] | None = None,
) -> dict:
    """Project person journey registry entries into review-only proposals."""
    service = DataIntelligenceService()
    preflight, projection = service.person_journey_registry_proposals(
        statuses=statuses,
        kinds=kinds,
    )
    audit = AuditService(ctx.session)
    candidates = projection.candidates if projection is not None else []
    await audit.record_tool_call(
        principal=ctx.principal,
        tool_name="data_intelligence_person_journey_proposals",
        extra=_preflight_audit_extra(
            preflight,
            result_posture=(
                "review_only_person_journey_registry_projection"
                if projection is not None
                else "denied"
            ),
            candidate_count=len(candidates),
            submittable_candidate_count=sum(
                1 for candidate in candidates if candidate.can_submit_for_review
            ),
            blocked_candidate_count=sum(1 for candidate in candidates if candidate.blockers),
        ),
    )
    return {
        "preflight": preflight.model_dump(mode="json"),
        "projection": projection.model_dump(mode="json") if projection is not None else None,
    }


async def data_intelligence_gap_brief(
    ctx: ToolContext,
    *,
    top_limit: int | None = None,
) -> dict:
    """Generate a non-sensitive Data Intelligence gap brief."""
    service = DataIntelligenceService(ctx.session)
    preflights, brief = await service.gap_brief(
        ctx.tenant_id,
        top_limit=top_limit,
    )
    audit = AuditService(ctx.session)
    await audit.record_tool_call(
        principal=ctx.principal,
        tool_name="data_intelligence_gap_brief",
        extra=_multi_preflight_audit_extra(
            preflights,
            result_posture="non_sensitive_gap_brief" if brief is not None else "denied",
            finding_count=len(brief.findings) if brief is not None else 0,
        ),
    )
    return {
        "preflights": [
            preflight.model_dump(mode="json") for preflight in preflights
        ],
        "brief": brief.model_dump(mode="json") if brief is not None else None,
    }


def _base_audit_extra(
    *,
    result_posture: str,
    **extra: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "audit_version": _AUDIT_VERSION,
        "result_posture": result_posture,
        "raw_sql_allowed": False,
        "raw_payload_allowed": False,
        "phi_allowed": False,
        "export_allowed": False,
        "write_allowed": False,
    }
    payload.update(extra)
    return payload


def _preflight_audit_extra(
    preflight: PolicyPreflightOut,
    *,
    result_posture: str,
    **extra: object,
) -> dict[str, object]:
    return _base_audit_extra(
        result_posture=result_posture,
        decision=preflight.decision,
        action=preflight.action,
        dataset_id=preflight.dataset_id,
        dataset_ids=[preflight.dataset_id],
        output_level=preflight.output_level,
        output_levels=[preflight.output_level],
        row_limit=preflight.row_limit,
        top_limit=preflight.top_limit,
        fields=preflight.fields,
        field_count=len(preflight.fields),
        data_classes=preflight.data_classes,
        masks=preflight.masks,
        audit_required=preflight.audit_required,
        raw_payload_allowed=preflight.raw_payload_allowed,
        phi_allowed=preflight.phi_allowed,
        export_allowed=preflight.export_allowed,
        write_allowed=preflight.write_allowed,
        **extra,
    )


def _multi_preflight_audit_extra(
    preflights: list[PolicyPreflightOut],
    *,
    result_posture: str,
    **extra: object,
) -> dict[str, object]:
    return _base_audit_extra(
        result_posture=result_posture,
        decisions=[preflight.decision for preflight in preflights],
        actions=sorted({preflight.action for preflight in preflights}),
        dataset_ids=[preflight.dataset_id for preflight in preflights],
        output_levels=sorted({preflight.output_level for preflight in preflights}),
        row_limits=[preflight.row_limit for preflight in preflights],
        top_limits=[preflight.top_limit for preflight in preflights],
        fields=sorted(
            {
                field
                for preflight in preflights
                for field in preflight.fields
            }
        ),
        field_count=sum(len(preflight.fields) for preflight in preflights),
        data_classes=sorted(
            {
                data_class
                for preflight in preflights
                for data_class in preflight.data_classes
            }
        ),
        masks=sorted(
            {
                mask
                for preflight in preflights
                for mask in preflight.masks
            }
        ),
        audit_required=all(preflight.audit_required for preflight in preflights),
        raw_payload_allowed=any(preflight.raw_payload_allowed for preflight in preflights),
        phi_allowed=any(preflight.phi_allowed for preflight in preflights),
        export_allowed=any(preflight.export_allowed for preflight in preflights),
        write_allowed=any(preflight.write_allowed for preflight in preflights),
        **extra,
    )
