"""Tests for approved analytics tool execution envelopes."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.ops.schemas import AnalyticsBucketOut, LeadSourceProfileOut
from packages.tools import analytics_tools
from packages.tools.analytics_tools import run_analytics_query
from packages.tools.base import ToolContext


@pytest.mark.asyncio
async def test_run_analytics_query_attaches_service_owned_quality_evidence(
    monkeypatch,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    captured: dict[str, object] = {}

    class FakeOpsService:
        def __init__(self, session):
            captured["ops_session"] = session

        async def get_lead_source_profile(self, tenant_id_arg, **kwargs):
            captured["tenant_id"] = tenant_id_arg
            captured["profile_kwargs"] = kwargs
            return LeadSourceProfileOut(
                total_leads=4,
                sources=[
                    AnalyticsBucketOut(key="google", label="Google", count=3),
                    AnalyticsBucketOut(key="unknown", label="Unknown", count=1),
                ],
            )

        async def get_lead_read_model_quality_evidence(
            self,
            tenant_id_arg,
            **kwargs,
        ):
            captured["quality_tenant_id"] = tenant_id_arg
            captured["quality_kwargs"] = kwargs
            return {
                "refs": ["lead.person_uid", "lead.lead_source"],
                "metrics": [
                    {
                        "id": "source_attribution_coverage",
                        "label": "Source attribution coverage",
                        "value": 0.75,
                        "unit": "ratio",
                        "numerator": 3,
                        "denominator": 4,
                        "status": "caveat",
                        "evidence_ref": "lead.lead_source",
                    }
                ],
                "caveats": ["1 lead aggregate row lacks source attribution."],
                "blockers": [],
            }

    class FakeAuditService:
        def __init__(self, session):
            captured["audit_session"] = session

        async def record_tool_call(self, **kwargs):
            captured["audit_call"] = kwargs

    monkeypatch.setattr(analytics_tools, "OpsService", FakeOpsService)
    monkeypatch.setattr(analytics_tools, "AuditService", FakeAuditService)

    session = MagicMock()
    principal = Principal(
        id=uuid.uuid4(),
        email="manager@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )

    result = await run_analytics_query(
        ToolContext(principal=principal, session=session),
        query_id="lead_source_profile.v1",
        params={"limit": 5},
    )

    assert result["query_id"] == "lead_source_profile.v1"
    assert result["read_model_id"] == "lead_source_profile"
    assert result["data_quality_evidence"] == {
        "refs": ["lead.person_uid", "lead.lead_source"],
        "metrics": [
            {
                "id": "source_attribution_coverage",
                "label": "Source attribution coverage",
                "value": 0.75,
                "unit": "ratio",
                "numerator": 3,
                "denominator": 4,
                "status": "caveat",
                "evidence_ref": "lead.lead_source",
            }
        ],
        "caveats": ["1 lead aggregate row lacks source attribution."],
        "blockers": [],
    }
    assert captured["tenant_id"] == tenant_id
    assert captured["quality_tenant_id"] == tenant_id
    assert captured["quality_kwargs"] == {
        "read_model_id": "lead_source_profile",
        "created_from": None,
        "created_to": None,
        "source_provider": None,
        "location_id": None,
    }
    assert "raw_sql" not in str(result)
