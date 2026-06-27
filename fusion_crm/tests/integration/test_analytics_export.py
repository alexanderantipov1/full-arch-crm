"""ENG-508 — CSV/XLSX export + metric→patient drill-down over a real Postgres.

Seeds ``analytics.fact_patient_journey`` directly (the projection is the single
source for these pages) and drives ``AnalyticsExportService`` /
``AnalyticsPagesService.metric_drilldown``. Asserts the export carries the exact
page numbers, that ``location`` (and the rest of the filter bar) flows through,
and that the drill-down is filtered, deterministically ordered, and bounded.
Skips cleanly when no test DB is available.
"""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from packages.analytics.export_service import AnalyticsExportService
from packages.analytics.filters import AnalyticsFilters
from packages.analytics.metrics_service import AnalyticsPagesService
from packages.analytics.models import FactPatientJourney
from packages.analytics.queries import FactAnalyticsQueries
from packages.core.types import TenantId
from packages.marketing.service import MarketingService
from packages.tenant.service import LocationService, TenantService
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session

_NOW = datetime(2026, 6, 18, 18, 0, tzinfo=UTC)
_WIN_START = datetime(2026, 1, 1, tzinfo=UTC)
_WIN_END = datetime(2026, 2, 1, tzinfo=UTC)

_L1 = uuid.uuid4()
_L2 = uuid.uuid4()

# Person A — full journey through "show", paid inside the month (location 1).
_A = uuid.uuid4()
# Person B — lead + consult, no show (location 2).
_B = uuid.uuid4()
# Person C — bare lead, no money, no source/location.
_C = uuid.uuid4()


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


def _pages(session: AsyncSession) -> AnalyticsPagesService:
    return AnalyticsPagesService(
        queries=FactAnalyticsQueries(session),
        marketing=MarketingService(session),
        tenant=TenantService(session),
        location=LocationService(session),
    )


def _export(session: AsyncSession) -> AnalyticsExportService:
    return AnalyticsExportService(pages=_pages(session))


async def _seed_facts(session: AsyncSession) -> None:
    session.add_all(
        [
            FactPatientJourney(
                person_uid=_A,
                source="google_ads",
                location_id=_L1,
                lead_date=datetime(2026, 1, 10, 9, 0, tzinfo=UTC),
                first_contact_date=datetime(2026, 1, 11, 9, 0, tzinfo=UTC),
                consult_scheduled_date=datetime(2026, 1, 15, 9, 0, tzinfo=UTC),
                show_date=datetime(2026, 1, 15, 10, 0, tzinfo=UTC),
                first_payment_date=datetime(2026, 1, 25, 9, 0, tzinfo=UTC),
                revenue_amount=10000.0,
                collected_amount=6000.0,
            ),
            FactPatientJourney(
                person_uid=_B,
                source="facebook",
                location_id=_L2,
                lead_date=datetime(2026, 1, 12, 9, 0, tzinfo=UTC),
                consult_scheduled_date=datetime(2026, 1, 16, 9, 0, tzinfo=UTC),
                revenue_amount=8000.0,
                collected_amount=2000.0,
            ),
            FactPatientJourney(
                person_uid=_C,
                lead_date=datetime(2026, 1, 20, 9, 0, tzinfo=UTC),
            ),
        ]
    )
    await session.flush()


def _jan_filters(**kwargs: object) -> AnalyticsFilters:
    return AnalyticsFilters(
        time_range="custom",
        custom_start=_WIN_START,
        custom_end=_WIN_END,
        **kwargs,  # type: ignore[arg-type]
    )


def _csv_sections(content: bytes) -> dict[str, list[list[str]]]:
    """Parse the multi-section export CSV into ``{section: data_rows}``."""
    sections: dict[str, list[list[str]]] = {}
    current: str | None = None
    rows_iter = csv.reader(io.StringIO(content.decode("utf-8")))
    for row in rows_iter:
        if not row:
            continue
        if len(row) == 1 and row[0].startswith("# "):
            current = row[0][2:]
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(row)
    return sections


async def test_funnel_export_carries_page_numbers(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="exp")
    await _seed_facts(db_session)

    result = await _export(db_session).export_page(
        tenant_id, page="funnel", fmt="csv", filters=_jan_filters()
    )
    assert result.filename == "analytics_funnel_custom.csv"
    sections = _csv_sections(result.content)

    funnel = {r[0]: r for r in sections["Funnel"][1:]}  # skip header row
    assert funnel["leads"][2] == "3"
    assert funnel["reached"][2] == "1"
    assert funnel["consults"][2] == "2"
    assert funnel["shows"][2] == "1"
    # B1-unresolved stages are honest zeros.
    assert funnel["surgery_completed"][2] == "0"

    summary = {r[0]: r[1] for r in sections["Summary"][1:]}
    assert summary["patients"] == "3"
    assert summary["revenue_total"] == "18000.0"


async def test_export_honors_location_filter(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="loc")
    await _seed_facts(db_session)

    result = await _export(db_session).export_page(
        tenant_id, page="funnel", fmt="csv", filters=_jan_filters(location_id=_L1)
    )
    sections = _csv_sections(result.content)

    # Location 1 holds only person A: one lead, one show, $10k presented.
    funnel = {r[0]: r for r in sections["Funnel"][1:]}
    assert funnel["leads"][2] == "1"
    assert funnel["shows"][2] == "1"
    summary = {r[0]: r[1] for r in sections["Summary"][1:]}
    assert summary["patients"] == "1"
    assert summary["revenue_total"] == "10000.0"
    # The applied location is echoed in the self-describing Report header.
    report = {r[0]: r[1] for r in sections["Report"][1:]}
    assert report["location_id"] == str(_L1)


async def test_revenue_and_cohort_and_executive_exports(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="pages")
    await _seed_facts(db_session)
    export = _export(db_session)

    for page in ("executive", "revenue", "cohort"):
        result = await export.export_page(
            tenant_id, page=page, fmt="csv", filters=_jan_filters()  # type: ignore[arg-type]
        )
        assert result.content  # non-empty
        sections = _csv_sections(result.content)
        assert "Report" in sections

    revenue = _csv_sections(
        (
            await export.export_page(
                tenant_id, page="revenue", fmt="csv", filters=_jan_filters()
            )
        ).content
    )
    summary = {r[0]: r[1] for r in revenue["Summary"][1:]}
    assert summary["gross_total"] == "18000.0"
    assert summary["collected_total"] == "8000.0"


async def test_xlsx_export_is_valid_workbook(db_session: AsyncSession) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="xlsx")
    await _seed_facts(db_session)

    result = await _export(db_session).export_page(
        tenant_id, page="funnel", fmt="xlsx", filters=_jan_filters()
    )
    assert result.filename.endswith(".xlsx")
    workbook = openpyxl.load_workbook(io.BytesIO(result.content))
    assert "Funnel" in workbook.sheetnames


async def test_drilldown_filters_and_orders(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="drill")
    await _seed_facts(db_session)
    pages = _pages(db_session)

    # "shows" → only person A reached a show.
    shows = await pages.metric_drilldown(
        tenant_id, _jan_filters(), metric="shows", now=_NOW, tz="UTC"
    )
    assert shows.person_uids == [_A]
    assert shows.total == 1
    assert shows.truncated is False

    # "leads" → all three, deterministically ordered by person_uid.
    leads = await pages.metric_drilldown(
        tenant_id, _jan_filters(), metric="leads", now=_NOW, tz="UTC"
    )
    assert leads.person_uids == sorted([_A, _B, _C])
    assert leads.total == 3

    # location filter narrows the cohort to person A.
    scoped = await pages.metric_drilldown(
        tenant_id, _jan_filters(location_id=_L2), metric="leads", now=_NOW, tz="UTC"
    )
    assert scoped.person_uids == [_B]


async def test_drilldown_is_bounded(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="bound")
    await _seed_facts(db_session)

    out = await _pages(db_session).metric_drilldown(
        tenant_id, _jan_filters(), metric="leads", limit=1, now=_NOW, tz="UTC"
    )
    assert out.total == 3
    assert out.returned == 1
    assert out.truncated is True
    # The single returned uid is the first in the deterministic order.
    assert out.person_uids == [sorted([_A, _B, _C])[0]]
