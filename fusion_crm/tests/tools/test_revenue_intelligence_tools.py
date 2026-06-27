"""Unit tests for read_revenue_intelligence_page (ENG-528).

Verifies:
- Tool calls AnalyticsPagesService (service), not the DB directly.
- Tool emits an audit row.
- Output envelope contains expected keys.
- Invalid page raises ValidationError.
- No repository or model import in the tool module.
"""

from __future__ import annotations

import importlib
import uuid
from unittest.mock import MagicMock

import pytest

from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.tools import revenue_intelligence_tools
from packages.tools.base import ToolContext
from packages.tools.revenue_intelligence_tools import read_revenue_intelligence_page

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx() -> ToolContext:
    tenant_id = TenantId(uuid.uuid4())
    principal = Principal(
        id=uuid.uuid4(),
        email="agent@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )
    session = MagicMock()
    return ToolContext(principal=principal, session=session)


class _FakePageResult:
    """Minimal stand-in for any page DTO."""

    def model_dump(self, *, mode: str = "json") -> dict:
        return {"fake": "page_data"}


class _FakeAuditService:
    def __init__(self, session):
        self.session = session
        self.calls: list[dict] = []

    async def record_tool_call(self, **kwargs):
        self.calls.append(kwargs)


class _FakePagesService:
    """Records which page was called and returns a stub DTO."""

    def __init__(self):
        self.called_page: str | None = None

    async def executive_overview(self, tenant_id, filters, *, now=None, tz=None):
        self.called_page = "executive_overview"
        return _FakePageResult()

    async def funnel_stages(self, tenant_id, filters, *, now=None, tz=None):
        self.called_page = "funnel_stages"
        return _FakePageResult()

    async def revenue_intelligence(self, tenant_id, filters, *, now=None, tz=None):
        self.called_page = "revenue_intelligence"
        return _FakePageResult()

    async def marketing_performance(self, tenant_id, filters, *, now=None, tz=None):
        self.called_page = "marketing_performance"
        return _FakePageResult()

    async def cohort_analytics(self, tenant_id, filters, *, now=None, tz=None):
        self.called_page = "cohort_analytics"
        return _FakePageResult()

    async def caller_performance(self, tenant_id, filters, *, now=None, tz=None):
        self.called_page = "caller_performance"
        return _FakePageResult()

    async def coordinator_performance(self, tenant_id, filters, *, now=None, tz=None):
        self.called_page = "coordinator_performance"
        return _FakePageResult()

    async def doctor_performance(self, tenant_id, filters, *, now=None, tz=None):
        self.called_page = "doctor_performance"
        return _FakePageResult()

    async def cost_intelligence(self, tenant_id, filters, *, now=None, tz=None):
        self.called_page = "cost_intelligence"
        return _FakePageResult()

    async def bottleneck_detection(self, tenant_id, filters, *, now=None, tz=None):
        self.called_page = "bottleneck_detection"
        return _FakePageResult()

    async def vendor_performance(self, tenant_id, filters, *, now=None, tz=None):
        self.called_page = "vendor_performance"
        return _FakePageResult()

    async def attribution_analytics(self, tenant_id, filters, *, now=None, tz=None):
        self.called_page = "attribution_analytics"
        return _FakePageResult()

    async def revenue_influence_matrix(self, tenant_id, filters, *, now=None, tz=None):
        self.called_page = "revenue_influence_matrix"
        return _FakePageResult()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "page",
    [
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
    ],
)
async def test_tool_calls_service_not_db(monkeypatch, page: str) -> None:
    """Tool must delegate to AnalyticsPagesService and return an envelope."""
    ctx = _make_ctx()
    fake_pages = _FakePagesService()
    captured_audit: list[dict] = []

    class _FakeAudit:
        def __init__(self, session):
            pass

        async def record_tool_call(self, **kwargs):
            captured_audit.append(kwargs)

    monkeypatch.setattr(
        revenue_intelligence_tools, "_build_pages_service", lambda _ctx: fake_pages
    )
    monkeypatch.setattr(revenue_intelligence_tools, "AuditService", _FakeAudit)

    result = await read_revenue_intelligence_page(ctx, page=page)  # type: ignore[arg-type]

    # Correct page was dispatched
    assert fake_pages.called_page == page

    # Audit row was recorded
    assert len(captured_audit) == 1
    assert captured_audit[0]["tool_name"] == "read_revenue_intelligence_page"
    assert captured_audit[0]["extra"]["page"] == page

    # Envelope shape
    assert result["page"] == page
    assert "data_classes" in result
    assert "description" in result
    assert "ai_hook" in result
    assert "filters" in result
    assert result["result"] == {"fake": "page_data"}


@pytest.mark.asyncio
async def test_invalid_page_raises_validation_error(monkeypatch) -> None:
    """Unknown page name must raise ValidationError before hitting any service."""
    from packages.core.exceptions import ValidationError

    ctx = _make_ctx()

    with pytest.raises(ValidationError) as exc_info:
        await read_revenue_intelligence_page(ctx, page="not_a_real_page")  # type: ignore[arg-type]

    assert "unknown revenue intelligence page" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_default_filters_applied(monkeypatch) -> None:
    """Calling with no params should default to last_30_days."""
    ctx = _make_ctx()
    fake_pages = _FakePagesService()

    class _FakeAudit:
        def __init__(self, session):
            pass

        async def record_tool_call(self, **kwargs):
            pass

    monkeypatch.setattr(
        revenue_intelligence_tools, "_build_pages_service", lambda _ctx: fake_pages
    )
    monkeypatch.setattr(revenue_intelligence_tools, "AuditService", _FakeAudit)

    result = await read_revenue_intelligence_page(ctx, page="executive_overview")  # type: ignore[arg-type]

    assert result["filters"]["time_range"] == "last_30_days"
    assert result["filters"]["location_id"] is None


def test_tool_has_no_db_or_model_imports() -> None:
    """The tool module must not import any repository, model, or raw session query."""

    mod = importlib.import_module("packages.tools.revenue_intelligence_tools")
    # Collect all names reachable from the module's global namespace
    all_names = set(dir(mod))

    # Forbidden: anything that sounds like a raw DB/model import
    forbidden_patterns = [
        "FactPatientJourney",  # ORM model
        "FactPatientJourneyRepository",  # repository
        "select",  # SQLAlchemy select()
        "text",  # SQLAlchemy text()
        "AsyncSession",  # direct session — should only be in ToolContext
    ]
    for name in forbidden_patterns:
        assert name not in all_names, (
            f"revenue_intelligence_tools should not expose {name!r} — "
            "tools must be services-only"
        )


def test_tool_registered_in_all_tools() -> None:
    """read_revenue_intelligence_page must appear in the tool registry."""
    from packages.tools.registry import ALL_TOOLS

    assert "read_revenue_intelligence_page" in ALL_TOOLS
    spec = ALL_TOOLS["read_revenue_intelligence_page"]
    assert spec.fn is read_revenue_intelligence_page
    assert "ops" in spec.touches
    assert "billing" in spec.touches
