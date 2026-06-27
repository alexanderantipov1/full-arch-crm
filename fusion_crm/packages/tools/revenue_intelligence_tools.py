"""Revenue Intelligence analytics page tools for AI agents (ENG-528).

Exposes the full set of :class:`~packages.analytics.metrics_service.AnalyticsPagesService`
pages as governed read-only tools so a future AI agent can consume revenue
intelligence data through the **services layer only** — never direct DB access.

Architecture hooks: see ``docs/architecture/REVENUE_INTELLIGENCE_AI_HOOKS.md``.

Hard rules (mirror packages/tools/CLAUDE.md):
- Tool calls services only; never repositories, models, or raw session queries.
- Inputs are JSON-friendly primitives; outputs are JSON dicts via
  ``BaseModel.model_dump(mode="json")``.
- Each tool emits an audit row via ``AuditService.record_tool_call``.
- No PHI is logged.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from packages.analytics.filters import AnalyticsFilters, TimeRangePreset
from packages.analytics.metrics_service import AnalyticsPagesService
from packages.analytics.queries import FactAnalyticsQueries
from packages.audit.service import AuditService
from packages.core.exceptions import ValidationError
from packages.marketing.service import MarketingService
from packages.tenant.service import LocationService, TenantService

from .base import ToolContext

# ---------------------------------------------------------------------------
# Page name literal — governs dispatch, doubles as the audit key.
# ---------------------------------------------------------------------------

RevenueIntelligencePage = Literal[
    "executive_overview",
    "funnel_stages",
    "revenue_intelligence",
    "marketing_performance",
    "cohort_analytics",
    "caller_performance",
    "coordinator_performance",
    "doctor_performance",
    "cost_intelligence",
    "bottleneck_detection",
    "vendor_performance",
    "attribution_analytics",
    "revenue_influence_matrix",
]

_VALID_PAGES: frozenset[str] = frozenset(
    {
        "executive_overview",
        "funnel_stages",
        "revenue_intelligence",
        "marketing_performance",
        "cohort_analytics",
        "caller_performance",
        "coordinator_performance",
        "doctor_performance",
        "cost_intelligence",
        "bottleneck_detection",
        "vendor_performance",
        "attribution_analytics",
        "revenue_influence_matrix",
    }
)

# Per-page metadata surfaced in the envelope so callers know what they are
# reading without inspecting the DTO schema.
_PAGE_METADATA: dict[str, dict[str, object]] = {
    "executive_overview": {
        "data_classes": ["ops", "billing", "integration_metadata"],
        "description": "Top-level KPIs: leads, consultations, surgeries, revenue.",
        "ai_hook": "no_show_prediction",
    },
    "funnel_stages": {
        "data_classes": ["ops"],
        "description": "Stage-by-stage funnel with conversion rates.",
        "ai_hook": "bottleneck_detection",
    },
    "revenue_intelligence": {
        "data_classes": ["billing"],
        "description": "Revenue breakdown by dimension (procedure, location, doctor).",
        "ai_hook": "budget_allocation_recommendation",
    },
    "marketing_performance": {
        "data_classes": ["ops", "integration_metadata"],
        "description": "Campaign-level spend, leads, CPL, show rate.",
        "ai_hook": "budget_allocation_recommendation",
    },
    "cohort_analytics": {
        "data_classes": ["ops", "billing"],
        "description": "Time-cohort revenue retention curves.",
        "ai_hook": "treatment_acceptance_probability",
    },
    "caller_performance": {
        "data_classes": ["ops"],
        "description": "Per-caller booking rate and volume.",
        "ai_hook": "bottleneck_detection",
    },
    "coordinator_performance": {
        "data_classes": ["ops", "billing"],
        "description": "Per-coordinator surgery conversion and revenue.",
        "ai_hook": "treatment_acceptance_probability",
    },
    "doctor_performance": {
        "data_classes": ["ops", "billing"],
        "description": "Per-doctor consultation and treatment acceptance.",
        "ai_hook": "treatment_acceptance_probability",
    },
    "cost_intelligence": {
        "data_classes": ["billing", "integration_metadata"],
        "description": "Cost-per-lead and cost-per-surgery by source/vendor.",
        "ai_hook": "budget_allocation_recommendation",
    },
    "bottleneck_detection": {
        "data_classes": ["ops"],
        "description": "Automatically flagged stage-drop bottlenecks and top performers.",
        "ai_hook": "bottleneck_detection",
    },
    "vendor_performance": {
        "data_classes": ["ops", "integration_metadata"],
        "description": "Per-vendor lead quality, CPL, surgery conversion.",
        "ai_hook": "budget_allocation_recommendation",
    },
    "attribution_analytics": {
        "data_classes": ["ops", "integration_metadata"],
        "description": "Multi-touch lead attribution by source and campaign.",
        "ai_hook": "no_show_prediction",
    },
    "revenue_influence_matrix": {
        "data_classes": ["billing"],
        "description": "Cross-dimensional revenue influence (double-counted by design).",
        "ai_hook": "budget_allocation_recommendation",
    },
}


# ---------------------------------------------------------------------------
# Helper — build AnalyticsPagesService from the tool context.
# Tools must not import repositories or models directly.
# ---------------------------------------------------------------------------


def _build_pages_service(ctx: ToolContext) -> AnalyticsPagesService:
    """Construct AnalyticsPagesService wired to ctx.session (no direct DB)."""
    return AnalyticsPagesService(
        queries=FactAnalyticsQueries(ctx.session),
        marketing=MarketingService(ctx.session),
        tenant=TenantService(ctx.session),
        location=LocationService(ctx.session),
    )


# ---------------------------------------------------------------------------
# Filter parsing (mirrors _AnalyticsFilters in analytics_tools.py but uses
# the shared AnalyticsFilters Pydantic model that AnalyticsPagesService
# expects rather than the legacy internal class).
# ---------------------------------------------------------------------------


def _parse_filters(params: dict[str, object]) -> AnalyticsFilters:
    """Parse agent-supplied params into the shared AnalyticsFilters contract."""
    time_range_raw = params.get("time_range") or params.get("preset") or "last_30_days"
    if not isinstance(time_range_raw, str) or time_range_raw not in {
        "today",
        "yesterday",
        "last_7_days",
        "last_30_days",
        "last_90_days",
        "this_month",
        "this_quarter",
        "this_year",
        "custom",
    }:
        raise ValidationError(
            "invalid time_range",
            details={
                "time_range": time_range_raw,
                "allowed": [
                    "today",
                    "yesterday",
                    "last_7_days",
                    "last_30_days",
                    "last_90_days",
                    "this_month",
                    "this_quarter",
                    "this_year",
                    "custom",
                ],
            },
        )
    time_range: TimeRangePreset = time_range_raw  # type: ignore[assignment]

    def _uuid(key: str) -> UUID | None:
        v = params.get(key)
        if v is None:
            return None
        try:
            return UUID(str(v))
        except ValueError as exc:
            raise ValidationError(
                f"invalid UUID for {key!r}", details={"value": str(v)}
            ) from exc

    def _str(key: str) -> str | None:
        v = params.get(key)
        if v is None:
            return None
        text = str(v).strip()
        return text or None

    def _dt(key: str) -> datetime | None:
        v = params.get(key)
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(str(v).strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValidationError(
                f"invalid datetime for {key!r}", details={"value": str(v)}
            ) from exc

    return AnalyticsFilters(
        time_range=time_range,
        custom_start=_dt("custom_start"),
        custom_end=_dt("custom_end"),
        location_id=_uuid("location_id"),
        campaign_id=_uuid("campaign_id"),
        source=_str("source"),
        vendor_id=_uuid("vendor_id"),
        caller_id=_uuid("caller_id"),
        coordinator_id=_uuid("coordinator_id"),
        doctor_id=_uuid("doctor_id"),
    )


# ---------------------------------------------------------------------------
# Public tool — read_revenue_intelligence_page
# ---------------------------------------------------------------------------


async def read_revenue_intelligence_page(
    ctx: ToolContext,
    *,
    page: RevenueIntelligencePage,
    params: dict[str, object] | None = None,
) -> dict:
    """Read one Revenue Intelligence analytics page and return JSON-safe aggregates.

    This is the **AI hook point** for all four future analytics AI capabilities:
    no-show prediction, treatment-acceptance probability, budget-allocation
    recommendation, and bottleneck / high-performer detection. A future model
    calls this tool to consume the pre-computed read model; it never touches the
    database directly.

    ``page`` selects which ``AnalyticsPagesService`` method to invoke:

    - ``executive_overview``        — top KPIs (leads, consults, surgeries, revenue)
    - ``funnel_stages``             — stage conversion rates
    - ``revenue_intelligence``      — revenue by procedure/location/doctor
    - ``marketing_performance``     — campaign spend, CPL, show rate
    - ``cohort_analytics``          — time-cohort revenue retention
    - ``caller_performance``        — per-caller booking rate
    - ``coordinator_performance``   — per-coordinator surgery conversion
    - ``doctor_performance``        — per-doctor treatment acceptance
    - ``cost_intelligence``         — CPL / cost-per-surgery by source
    - ``bottleneck_detection``      — flagged drops and top performers
    - ``vendor_performance``        — per-vendor lead quality and CPL
    - ``attribution_analytics``     — multi-touch source attribution
    - ``revenue_influence_matrix``  — cross-dimensional revenue influence

    ``params`` supports:
    - ``time_range`` (str, default ``"last_30_days"``): preset name
    - ``custom_start`` / ``custom_end`` (ISO-8601 strings): required for ``"custom"``
    - ``location_id``, ``campaign_id``, ``vendor_id``, ``caller_id``,
      ``coordinator_id``, ``doctor_id`` (UUID strings): optional scope filters
    - ``source`` (str): optional lead-source equality filter
    """
    if page not in _VALID_PAGES:
        raise ValidationError(
            "unknown revenue intelligence page",
            details={"page": page, "allowed": sorted(_VALID_PAGES)},
        )

    clean_params = params or {}
    filters = _parse_filters(clean_params)
    now = datetime.now(tz=UTC)
    pages_svc = _build_pages_service(ctx)
    tenant_id = ctx.tenant_id
    metadata = _PAGE_METADATA[page]

    # Dispatch — one branch per page; no raw SQL, no model import.
    # result is typed Any because each branch returns a different Pydantic DTO;
    # we only need .model_dump(mode="json") on it — the service guarantees that.
    result: Any
    if page == "executive_overview":
        result = await pages_svc.executive_overview(tenant_id, filters, now=now)
    elif page == "funnel_stages":
        result = await pages_svc.funnel_stages(tenant_id, filters, now=now)
    elif page == "revenue_intelligence":
        result = await pages_svc.revenue_intelligence(tenant_id, filters, now=now)
    elif page == "marketing_performance":
        result = await pages_svc.marketing_performance(tenant_id, filters, now=now)
    elif page == "cohort_analytics":
        result = await pages_svc.cohort_analytics(tenant_id, filters, now=now)
    elif page == "caller_performance":
        result = await pages_svc.caller_performance(tenant_id, filters, now=now)
    elif page == "coordinator_performance":
        result = await pages_svc.coordinator_performance(tenant_id, filters, now=now)
    elif page == "doctor_performance":
        result = await pages_svc.doctor_performance(tenant_id, filters, now=now)
    elif page == "cost_intelligence":
        result = await pages_svc.cost_intelligence(tenant_id, filters, now=now)
    elif page == "bottleneck_detection":
        result = await pages_svc.bottleneck_detection(tenant_id, filters, now=now)
    elif page == "vendor_performance":
        result = await pages_svc.vendor_performance(tenant_id, filters, now=now)
    elif page == "attribution_analytics":
        result = await pages_svc.attribution_analytics(tenant_id, filters, now=now)
    else:  # revenue_influence_matrix
        result = await pages_svc.revenue_influence_matrix(tenant_id, filters, now=now)

    audit = AuditService(ctx.session)
    await audit.record_tool_call(
        principal=ctx.principal,
        tool_name="read_revenue_intelligence_page",
        extra={
            "page": page,
            "time_range": filters.time_range,
            "has_location_filter": filters.location_id is not None,
        },
    )

    return {
        "page": page,
        "data_classes": metadata["data_classes"],
        "description": metadata["description"],
        "ai_hook": metadata["ai_hook"],
        "filters": filters.model_dump(mode="json"),
        "result": result.model_dump(mode="json"),
    }
