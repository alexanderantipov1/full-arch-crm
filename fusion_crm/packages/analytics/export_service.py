"""CSV/XLSX export of the fact-backed analytics pages (ENG-508).

The export wraps :class:`AnalyticsPagesService` and shapes the page DTO it
returns — it never re-queries the fact independently. So an export of a page is,
by construction, byte-for-byte the same numbers the page shows on screen for the
same :class:`AnalyticsFilters` (time range, location, and the other dimensions).

Layering: this is a service. It produces neutral :class:`ExportTable` grids from
the page DTOs and hands them to the format-only :mod:`packages.analytics.exporters`
serializers. The route maps query params → filters → ``export_page`` and wraps
the returned bytes in an HTTP response — no shaping or serialization in the route.

PHI posture: the page DTOs carry aggregates, reference ids, dates, and money —
no patient identifiers, no clinical text, no raw provider payloads. The export
adds nothing, so it stays PHI-free. Logs never carry row content.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId

from .exporters import ExportTable, to_csv, to_xlsx
from .filters import AnalyticsFilters
from .metrics_service import AnalyticsPagesService
from .schemas import (
    AnalyticsExportFormat,
    AnalyticsExportPage,
    AnalyticsFiltersEchoOut,
    AnalyticsWindowOut,
    CohortAnalyticsOut,
    DerivedMetricsOut,
    ExecutiveOverviewOut,
    FunnelStageOut,
    FunnelStagesOut,
    RevenueIntelligenceOut,
)

_CSV_MEDIA_TYPE = "text/csv; charset=utf-8"
_XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

_FUNNEL_HEADERS = ["key", "label", "count", "revenue", "collected", "conversion", "cost"]


@dataclass(frozen=True)
class ExportResult:
    """One serialized export: the bytes plus how to deliver them."""

    filename: str
    media_type: str
    content: bytes


class AnalyticsExportService:
    """Serialize a fact-backed page to CSV/XLSX for the active filters (ENG-508)."""

    def __init__(self, *, pages: AnalyticsPagesService) -> None:
        self._pages = pages

    async def export_page(
        self,
        tenant_id: TenantId,
        *,
        page: AnalyticsExportPage,
        fmt: AnalyticsExportFormat,
        filters: AnalyticsFilters,
        now: datetime | None = None,
        tz: str | None = None,
    ) -> ExportResult:
        """Render ``page`` to ``fmt`` bytes — the page's own numbers, tabulated.

        Delegates the numbers to ``AnalyticsPagesService`` (so the export equals
        the screen), shapes the DTO into tables, and serializes. ``location`` and
        every other filter flow through unchanged.
        """
        if page == "executive":
            exec_dto = await self._pages.executive_overview(
                tenant_id, filters, now=now, tz=tz
            )
            tables, preset = _executive_tables(exec_dto), exec_dto.window.preset
        elif page == "funnel":
            funnel_dto = await self._pages.funnel_stages(
                tenant_id, filters, now=now, tz=tz
            )
            tables, preset = _funnel_tables(funnel_dto), funnel_dto.window.preset
        elif page == "revenue":
            revenue_dto = await self._pages.revenue_intelligence(
                tenant_id, filters, now=now, tz=tz
            )
            tables, preset = _revenue_tables(revenue_dto), revenue_dto.window.preset
        elif page == "cohort":
            cohort_dto = await self._pages.cohort_analytics(
                tenant_id, filters, now=now, tz=tz
            )
            tables, preset = _cohort_tables(cohort_dto), cohort_dto.window.preset
        else:  # pragma: no cover - guarded by the Literal at the route boundary
            raise ValidationError(
                "unsupported analytics export page", details={"page": page}
            )

        if fmt == "csv":
            return ExportResult(
                filename=f"analytics_{page}_{preset}.csv",
                media_type=_CSV_MEDIA_TYPE,
                content=to_csv(tables),
            )
        if fmt == "xlsx":
            return ExportResult(
                filename=f"analytics_{page}_{preset}.xlsx",
                media_type=_XLSX_MEDIA_TYPE,
                content=to_xlsx(tables),
            )
        # pragma: no cover - guarded by the Literal at the route boundary
        raise ValidationError(
            "unsupported analytics export format", details={"format": fmt}
        )


def _meta_table(
    page: str, window: AnalyticsWindowOut, filters: AnalyticsFiltersEchoOut
) -> ExportTable:
    """Self-describing header: which page + the exact filters/window applied."""
    return ExportTable(
        name="Report",
        headers=["field", "value"],
        rows=[
            ["page", page],
            ["time_range", window.preset],
            ["window_start", window.start],
            ["window_end", window.end],
            ["timezone", window.tz],
            ["location_id", filters.location_id],
            ["campaign_id", filters.campaign_id],
            ["source", filters.source],
            ["vendor_id", filters.vendor_id],
            ["caller_id", filters.caller_id],
            ["coordinator_id", filters.coordinator_id],
            ["doctor_id", filters.doctor_id],
        ],
    )


def _funnel_rows(stages: list[FunnelStageOut]) -> list[list[object]]:
    return [
        [s.key, s.label, s.count, s.revenue, s.collected, s.conversion, s.cost]
        for s in stages
    ]


def _derived_table(derived: DerivedMetricsOut) -> ExportTable:
    return ExportTable(
        name="Derived Metrics",
        headers=["metric", "value"],
        rows=[[key, value] for key, value in derived.model_dump().items()],
    )


def _executive_tables(dto: ExecutiveOverviewOut) -> list[ExportTable]:
    return [
        _meta_table("executive", dto.window, dto.filters),
        ExportTable("Funnel", _FUNNEL_HEADERS, _funnel_rows(dto.funnel)),
        _derived_table(dto.derived),
        ExportTable(
            "Revenue Widgets",
            ["preset", "label", "gross", "collected", "payers"],
            [[w.preset, w.label, w.gross, w.collected, w.payers] for w in dto.revenue_widgets],
        ),
        ExportTable(
            "Summary",
            ["metric", "value"],
            [
                ["spend", dto.spend],
                ["revenue_total", dto.revenue_total],
                ["collected_total", dto.collected_total],
                ["outstanding_total", dto.outstanding_total],
                ["patients", dto.patients],
            ],
        ),
    ]


def _funnel_tables(dto: FunnelStagesOut) -> list[ExportTable]:
    return [
        _meta_table("funnel", dto.window, dto.filters),
        ExportTable("Funnel", _FUNNEL_HEADERS, _funnel_rows(dto.stages)),
        ExportTable(
            "Summary",
            ["metric", "value"],
            [
                ["spend", dto.spend],
                ["patients", dto.patients],
                ["revenue_total", dto.revenue_total],
                ["collected_total", dto.collected_total],
            ],
        ),
    ]


def _revenue_tables(dto: RevenueIntelligenceOut) -> list[ExportTable]:
    tables = [
        _meta_table("revenue", dto.window, dto.filters),
        ExportTable(
            "Summary",
            ["metric", "value"],
            [
                ["gross_total", dto.gross_total],
                ["collected_total", dto.collected_total],
                ["outstanding_total", dto.outstanding_total],
                ["avg_case_value", dto.avg_case_value],
                ["case_count", dto.case_count],
            ],
        ),
    ]
    for dim in dto.dimensions:
        status = "resolved" if dim.resolved else "unattributed"
        tables.append(
            ExportTable(
                name=f"Revenue by {dim.dimension} ({status})",
                headers=[
                    "group_id",
                    "group_label",
                    "gross",
                    "collected",
                    "outstanding",
                    "case_count",
                    "avg_case_value",
                ],
                rows=[
                    [
                        g.group_id,
                        g.group_label,
                        g.gross,
                        g.collected,
                        g.outstanding,
                        g.case_count,
                        g.avg_case_value,
                    ]
                    for g in dim.groups
                ],
            )
        )
    return tables


def _cohort_tables(dto: CohortAnalyticsOut) -> list[ExportTable]:
    horizon_headers = [f"d{n}" for n in dto.horizons]
    headers = ["cohort_month", "lead_count", *horizon_headers, "collected_total"]
    rows: list[list[object]] = []
    for c in dto.cohorts:
        horizon_values = [getattr(c.revenue, f"d{n}") for n in dto.horizons]
        rows.append([c.cohort_month, c.lead_count, *horizon_values, c.collected_total])
    return [
        _meta_table("cohort", dto.window, dto.filters),
        ExportTable("Cohorts", headers, rows),
    ]
