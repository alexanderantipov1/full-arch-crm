"""Unit tests for the analytics export serializers + service shaping (ENG-508).

Pure tests — no DB. They prove:

* CSV / XLSX value formatting and multi-table layout,
* the defensive row cap raises rather than truncating,
* CSV works with ``openpyxl`` absent and XLSX degrades to a ``PlatformError``
  (the dependency is imported lazily), and
* ``AnalyticsExportService`` wraps the page service, passing the active filters
  straight through and emitting the page's own numbers.
"""

from __future__ import annotations

import builtins
import io
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.analytics.export_service import AnalyticsExportService
from packages.analytics.exporters import EXPORT_MAX_ROWS, ExportTable, to_csv, to_xlsx
from packages.analytics.filters import AnalyticsFilters
from packages.analytics.schemas import (
    AnalyticsFiltersEchoOut,
    AnalyticsWindowOut,
    FunnelStageOut,
    FunnelStagesOut,
)
from packages.core.exceptions import ValidationError
from packages.core.types import TenantId

_WINDOW = AnalyticsWindowOut(
    preset="last_30_days",
    start=datetime(2026, 1, 1, tzinfo=UTC),
    end=datetime(2026, 2, 1, tzinfo=UTC),
    tz="UTC",
)


def test_to_csv_formats_values_and_sections() -> None:
    uid = uuid4()
    tables = [
        ExportTable("First", ["a", "b"], [[1, None]]),
        ExportTable("Second", ["id", "when"], [[uid, _WINDOW.start]]),
    ]
    text = to_csv(tables).decode("utf-8")
    lines = text.splitlines()

    assert lines[0] == "# First"
    assert lines[1] == "a,b"
    # None renders as an empty cell (the export "—"); ints stay numeric.
    assert lines[2] == "1,"
    # Blank separator line between sections, then the second title.
    assert "# Second" in lines
    # UUID + datetime render as str / ISO-8601.
    assert str(uid) in text
    assert "2026-01-01T00:00:00+00:00" in text


def test_to_csv_row_cap_raises() -> None:
    oversized = ExportTable("big", ["x"], [[i] for i in range(EXPORT_MAX_ROWS + 1)])
    with pytest.raises(ValidationError):
        to_csv([oversized])


def test_to_xlsx_round_trips_one_sheet_per_table() -> None:
    openpyxl = pytest.importorskip("openpyxl")
    tables = [
        ExportTable("Funnel", ["key", "count"], [["leads", 3], ["shows", 1]]),
        ExportTable("Summary", ["metric", "value"], [["patients", 3]]),
    ]
    workbook = openpyxl.load_workbook(io.BytesIO(to_xlsx(tables)))
    assert workbook.sheetnames == ["Funnel", "Summary"]
    funnel = workbook["Funnel"]
    assert [c.value for c in funnel[1]] == ["key", "count"]
    assert [c.value for c in funnel[2]] == ["leads", 3]


def test_csv_independent_of_openpyxl_and_xlsx_degrades(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def _blocked(name: str, *args: object, **kwargs: object) -> object:
        if name == "openpyxl" or name.startswith("openpyxl."):
            raise ImportError("openpyxl is not installed")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", _blocked)
    tables = [ExportTable("t", ["x"], [[1]])]

    # CSV never imports openpyxl, so it still serializes.
    assert to_csv(tables)
    # XLSX needs it and fails cleanly with a PlatformError (not ImportError).
    with pytest.raises(ValidationError):
        to_xlsx(tables)


class _StubPages:
    """Minimal stand-in recording the filters the export forwards to the page."""

    def __init__(self, dto: FunnelStagesOut) -> None:
        self._dto = dto
        self.received: AnalyticsFilters | None = None

    async def funnel_stages(
        self,
        tenant_id: TenantId,
        filters: AnalyticsFilters,
        *,
        now: datetime | None = None,
        tz: str | None = None,
    ) -> FunnelStagesOut:
        self.received = filters
        return self._dto


def _funnel_dto() -> FunnelStagesOut:
    return FunnelStagesOut(
        window=_WINDOW,
        filters=AnalyticsFiltersEchoOut(time_range="last_30_days"),
        stages=[
            FunnelStageOut(
                key="leads", label="Leads", count=3, revenue=100.0, collected=60.0
            ),
            FunnelStageOut(
                key="shows",
                label="Shows",
                count=1,
                revenue=100.0,
                collected=60.0,
                conversion=0.33,
                cost=None,
            ),
        ],
        spend=None,
        patients=3,
        revenue_total=100.0,
        collected_total=60.0,
    )


async def test_export_service_passes_filters_and_emits_page_numbers() -> None:
    location = uuid4()
    stub = _StubPages(_funnel_dto())
    service = AnalyticsExportService(pages=stub)  # type: ignore[arg-type]
    filters = AnalyticsFilters(time_range="last_30_days", location_id=location)

    result = await service.export_page(
        TenantId(uuid4()), page="funnel", fmt="csv", filters=filters
    )

    # Location (and the rest of the filter bar) is forwarded verbatim.
    assert stub.received is not None
    assert stub.received.location_id == location
    assert result.media_type.startswith("text/csv")
    assert result.filename == "analytics_funnel_last_30_days.csv"

    text = result.content.decode("utf-8")
    # The page's own numbers land in the CSV verbatim.
    assert "leads,Leads,3,100.0,60.0" in text
    assert "patients,3" in text


async def test_export_service_xlsx_media_type() -> None:
    pytest.importorskip("openpyxl")
    stub = _StubPages(_funnel_dto())
    service = AnalyticsExportService(pages=stub)  # type: ignore[arg-type]
    result = await service.export_page(
        TenantId(uuid4()),
        page="funnel",
        fmt="xlsx",
        filters=AnalyticsFilters(time_range="last_30_days"),
    )
    assert result.filename.endswith(".xlsx")
    assert "spreadsheetml.sheet" in result.media_type
    assert result.content[:2] == b"PK"  # XLSX is a zip container.
