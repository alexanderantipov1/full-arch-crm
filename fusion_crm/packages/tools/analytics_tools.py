"""Approved analytics tools for internal agents.

The tool surface is intentionally registry-shaped: agents choose a known
``query_id`` and structured parameters. They cannot submit SQL or free-form
database queries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from packages.audit.service import AuditService
from packages.core.exceptions import ValidationError
from packages.interaction.service import InteractionService
from packages.ops.service import OpsService

from .base import ToolContext

AnalyticsQueryId = Literal[
    "lead_source_profile.v1",
    "lead_conversion_funnel.v1",
    "paid_leads_by_source.v1",
    "consultation_followup_worklist.v1",
    "treatment_revenue_evidence.v1",
    "lead_source_profile",
    "conversion_funnel",
    "paid_leads",
    "consultation_followup",
    "revenue_evidence",
]

_QUERY_ALIASES: dict[str, str] = {
    "lead_source_profile": "lead_source_profile.v1",
    "lead_source_profile.v1": "lead_source_profile.v1",
    "conversion_funnel": "lead_conversion_funnel.v1",
    "lead_conversion_funnel.v1": "lead_conversion_funnel.v1",
    "paid_leads": "paid_leads_by_source.v1",
    "paid_leads_by_source.v1": "paid_leads_by_source.v1",
    "consultation_followup": "consultation_followup_worklist.v1",
    "consultation_followup_worklist.v1": "consultation_followup_worklist.v1",
    "revenue_evidence": "treatment_revenue_evidence.v1",
    "treatment_revenue_evidence.v1": "treatment_revenue_evidence.v1",
}

_QUERY_METADATA: dict[str, dict[str, object]] = {
    "lead_source_profile.v1": {
        "read_model_id": "lead_source_profile",
        "data_classes": ["ops", "integration_metadata"],
        "definition_versions": {"lead_source": "v1", "source_provider": "v1"},
        "warnings": [],
    },
    "lead_conversion_funnel.v1": {
        "read_model_id": "lead_conversion",
        "data_classes": ["ops", "integration_metadata"],
        "definition_versions": {
            "lead_source": "v1",
            "consultation_scheduled": "v1",
            "consultation_completed": "v1",
        },
        "warnings": [],
    },
    "paid_leads_by_source.v1": {
        "read_model_id": "paid_leads",
        "data_classes": ["ops", "integration_metadata"],
        "definition_versions": {"paid_lead": "v1", "lead_source": "v1"},
        "warnings": [
            "V1 paid lead classification uses CRM-safe source/campaign label heuristics."
        ],
    },
    "consultation_followup_worklist.v1": {
        "read_model_id": "consultation_followup",
        "data_classes": ["ops", "integration_metadata"],
        "definition_versions": {
            "consultation_completed": "v1",
            "stale_followup": "v1",
        },
        "warnings": [],
    },
    "treatment_revenue_evidence.v1": {
        "read_model_id": "treatment_revenue",
        "data_classes": ["billing", "integration_metadata"],
        "definition_versions": {
            "payment_received": "v1",
            "revenue_evidence": "v1",
        },
        "warnings": [],
    },
}

_EXPORTABLE_DATA_CLASSES = frozenset({"ops", "integration_metadata", "billing"})


def canonical_analytics_query_id(query_id: str) -> str:
    """Return the canonical versioned query id or raise validation error."""
    canonical_query_id = _QUERY_ALIASES.get(query_id)
    if canonical_query_id is None:
        raise ValidationError(
            "unknown analytics query",
            details={"query_id": query_id, "allowed": sorted(_QUERY_ALIASES)},
        )
    return canonical_query_id


def canonical_analytics_query_literal(query_id: str) -> AnalyticsQueryId:
    """Return canonical query id typed for internal tool dispatch."""
    return cast(AnalyticsQueryId, canonical_analytics_query_id(query_id))


def analytics_query_metadata(query_id: str) -> dict[str, object]:
    """Return metadata for a canonical or aliased analytics query id."""
    return dict(_QUERY_METADATA[canonical_analytics_query_id(query_id)])


async def run_analytics_query(
    ctx: ToolContext,
    *,
    query_id: AnalyticsQueryId,
    params: dict[str, object] | None = None,
) -> dict:
    """Run one approved analytics query and return JSON-friendly aggregates."""
    canonical_query_id = canonical_analytics_query_id(query_id)

    clean_params = params or {}
    _reject_unsupported_posture_params(clean_params)
    filters = _AnalyticsFilters.from_params(clean_params)
    metadata = _QUERY_METADATA[canonical_query_id]

    ops = OpsService(ctx.session)
    result: dict[str, object]
    data_quality_evidence: dict[str, object] | None = None

    if canonical_query_id == "lead_source_profile.v1":
        result = (
            await ops.get_lead_source_profile(
                ctx.tenant_id,
                created_from=filters.created_from,
                created_to=filters.created_to,
                source_provider=filters.source_provider,
                limit=filters.limit,
            )
        ).model_dump(mode="json")
        data_quality_evidence = await ops.get_lead_read_model_quality_evidence(
            ctx.tenant_id,
            read_model_id=str(metadata["read_model_id"]),
            created_from=filters.created_from,
            created_to=filters.created_to,
            source_provider=filters.source_provider,
            location_id=filters.location_id,
        )
    elif canonical_query_id == "lead_conversion_funnel.v1":
        result = (
            await ops.get_conversion_funnel_analytics(
                ctx.tenant_id,
                created_from=filters.created_from,
                created_to=filters.created_to,
                source_provider=filters.source_provider,
                lead_source=filters.lead_source,
                location_id=filters.location_id,
            )
        ).model_dump(mode="json")
        data_quality_evidence = await ops.get_lead_read_model_quality_evidence(
            ctx.tenant_id,
            read_model_id=str(metadata["read_model_id"]),
            created_from=filters.created_from,
            created_to=filters.created_to,
            source_provider=filters.source_provider,
            lead_source=filters.lead_source,
            location_id=filters.location_id,
        )
    elif canonical_query_id == "paid_leads_by_source.v1":
        result = (
            await ops.get_paid_leads_analytics(
                ctx.tenant_id,
                created_from=filters.created_from,
                created_to=filters.created_to,
                source_provider=filters.source_provider,
                limit=filters.limit,
            )
        ).model_dump(mode="json")
        data_quality_evidence = await ops.get_lead_read_model_quality_evidence(
            ctx.tenant_id,
            read_model_id=str(metadata["read_model_id"]),
            created_from=filters.created_from,
            created_to=filters.created_to,
            source_provider=filters.source_provider,
            location_id=filters.location_id,
        )
    elif canonical_query_id == "consultation_followup_worklist.v1":
        result = (
            await ops.get_consultation_followup_analytics(
                ctx.tenant_id,
                scheduled_from=filters.created_from,
                scheduled_to=filters.created_to,
                source_provider=filters.source_provider,
                location_id=filters.location_id,
                now=datetime.now(tz=UTC),
            )
        ).model_dump(mode="json")
        data_quality_evidence = await ops.get_lead_read_model_quality_evidence(
            ctx.tenant_id,
            read_model_id=str(metadata["read_model_id"]),
            created_from=filters.created_from,
            created_to=filters.created_to,
            source_provider=filters.source_provider,
            location_id=filters.location_id,
        )
    else:
        interaction = InteractionService(ctx.session)
        result = (
            await interaction.get_treatment_payment_aggregate(
                ctx.tenant_id,
                occurred_from=filters.created_from,
                occurred_to=filters.created_to,
                source_provider=filters.source_provider,
                location_id=filters.location_id,
            )
        ).model_dump(mode="json")
        data_quality_evidence = await interaction.get_treatment_payment_quality_evidence(
            ctx.tenant_id,
            occurred_from=filters.created_from,
            occurred_to=filters.created_to,
            source_provider=filters.source_provider,
            location_id=filters.location_id,
        )

    audit = AuditService(ctx.session)
    await audit.record_tool_call(
        principal=ctx.principal,
        tool_name="run_analytics_query",
        extra={
            "query_id": canonical_query_id,
            "param_keys": sorted(clean_params.keys()),
        },
    )

    envelope = {
        "query_id": canonical_query_id,
        "read_model_id": metadata["read_model_id"],
        "output_type": "aggregate",
        "aggregation_level": "aggregate",
        "data_classes": metadata["data_classes"],
        "definition_versions": metadata["definition_versions"],
        "filters": filters.model_dump(),
        "row_count": _result_row_count(result),
        "warnings": metadata["warnings"],
        "drilldown_available": False,
        "export_available": _is_csv_export_available(metadata),
        "result": result,
    }
    if data_quality_evidence is not None:
        envelope["data_quality_evidence"] = data_quality_evidence
    return envelope


class _AnalyticsFilters:
    def __init__(
        self,
        *,
        created_from: datetime | None,
        created_to: datetime | None,
        source_provider: str | None,
        lead_source: str | None,
        location_id: UUID | None,
        limit: int,
    ) -> None:
        self.created_from = created_from
        self.created_to = created_to
        self.source_provider = source_provider
        self.lead_source = lead_source
        self.location_id = location_id
        self.limit = limit

    @classmethod
    def from_params(cls, params: dict[str, object]) -> _AnalyticsFilters:
        return cls(
            created_from=_datetime_param(params.get("created_from") or params.get("from")),
            created_to=_datetime_param(params.get("created_to") or params.get("to")),
            source_provider=_source_provider_param(params.get("source_provider")),
            lead_source=_str_param(params.get("lead_source")),
            location_id=_uuid_param(params.get("location_id")),
            limit=_limit_param(params.get("limit")),
        )

    def model_dump(self) -> dict[str, object]:
        return {
            "created_from": self.created_from.isoformat()
            if self.created_from is not None
            else None,
            "created_to": self.created_to.isoformat()
            if self.created_to is not None
            else None,
            "source_provider": self.source_provider,
            "lead_source": self.lead_source,
            "location_id": str(self.location_id) if self.location_id is not None else None,
            "limit": self.limit,
        }


def _datetime_param(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValidationError(
                "invalid datetime parameter",
                details={"value": text},
            ) from exc
    raise ValidationError("invalid datetime parameter", details={"value": str(value)})


def _source_provider_param(value: object) -> str | None:
    text = _str_param(value)
    if text is None:
        return None
    if text not in {"salesforce", "carestack"}:
        raise ValidationError(
            "invalid source_provider",
            details={"source_provider": text, "allowed": ["salesforce", "carestack"]},
        )
    return text


def _uuid_param(value: object) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise ValidationError("invalid UUID parameter", details={"value": str(value)}) from exc


def _limit_param(value: object) -> int:
    if value is None:
        return 10
    try:
        limit = int(str(value))
    except ValueError as exc:
        raise ValidationError("invalid limit", details={"value": str(value)}) from exc
    if limit < 1 or limit > 50:
        raise ValidationError("limit must be between 1 and 50", details={"limit": limit})
    return limit


def _str_param(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _reject_unsupported_posture_params(params: dict[str, object]) -> None:
    output_level = _str_param(params.get("output_level") or params.get("level"))
    if output_level in {"row", "row_level", "drilldown", "export"}:
        raise ValidationError(
            "analytics query output level is not available in V1",
            details={"output_level": output_level, "allowed": ["aggregate"]},
        )
    if params.get("export") is True:
        raise ValidationError(
            "direct analytics query export is not available; use export_analytics_csv",
            details={"export": True},
        )


def _result_row_count(result: dict[str, object]) -> int:
    """Return the number of aggregate buckets in a result envelope."""
    total = 0
    for value in result.values():
        if isinstance(value, list):
            total += len(value)
    return total


def _is_csv_export_available(metadata: dict[str, object]) -> bool:
    data_classes = metadata.get("data_classes")
    if not isinstance(data_classes, list):
        return False
    return all(str(data_class) in _EXPORTABLE_DATA_CLASSES for data_class in data_classes)
