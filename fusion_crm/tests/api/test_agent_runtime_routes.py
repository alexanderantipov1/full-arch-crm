"""HTTP-level tests for the agent runtime routes."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db, get_principal_with_tenant
from apps.api.middleware import (
    RequestContextMiddleware,
    platform_error_handler,
    request_validation_error_handler,
)
from apps.api.routers import agent_runtime as agent_runtime_router
from packages.agent_runtime.schemas import (
    AgentRuntimeApprovalDecisionIn,
    AgentRuntimeApprovalRequestCreateIn,
    AgentRuntimeApprovalRequestOut,
    AgentRuntimeApprovalRequestsOut,
    AgentRuntimeAuditSummaryOut,
    AgentRuntimeConnectionCheckOut,
    AgentRuntimeDiaCatalogLinkagesOut,
    AgentRuntimeLlmPlanOut,
    AgentRuntimeRunHistoryOut,
    AgentRuntimeRunSummaryOut,
    AgentRuntimeToolProjectionOut,
    AgentRuntimeToolsProjectionOut,
)
from packages.core.exceptions import PlatformError, ValidationError
from packages.core.security import Principal, Role
from packages.core.types import TenantId


def _principal(tenant_id: uuid.UUID) -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="ops@example.com",
        tenant_id=TenantId(tenant_id),
        roles=frozenset({Role.ADMIN}),
    )


def _build_app(
    *,
    tenant_id: uuid.UUID,
    db_session: Any,
    principal: Principal | None = None,
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(PlatformError, platform_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(
        RequestValidationError,
        request_validation_error_handler,  # type: ignore[arg-type]
    )
    app.include_router(agent_runtime_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_principal_with_tenant] = lambda: principal or _principal(
        tenant_id
    )
    return app


def test_openai_provider_connection_check_returns_safe_metadata(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    captured: dict[str, Any] = {}

    async def _fake_test_openai_connection(self, principal):
        captured["tenant_id"] = principal.require_tenant()
        captured["principal_email"] = principal.email
        return AgentRuntimeConnectionCheckOut(
            ok=True,
            model="gpt-4.1-mini",
            last_agent="Fusion OpenAI Health Check",
            output="ok",
        )

    monkeypatch.setattr(
        agent_runtime_router.AgentRuntimeService,
        "test_openai_connection",
        _fake_test_openai_connection,
    )

    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.post("/agent-runtime/providers/openai/test")

    assert res.status_code == 200
    assert res.json() == {
        "ok": True,
        "runtime": "agent_runtime",
        "provider_kind": "openai",
        "credential_kind": "api_key",
        "model": "gpt-4.1-mini",
        "last_agent": "Fusion OpenAI Health Check",
        "output": "ok",
    }
    assert "sk-" not in res.text
    assert captured["tenant_id"] == TenantId(tenant_id)
    assert captured["principal_email"] == "ops@example.com"


def test_agent_runtime_tools_projection_returns_safe_metadata(monkeypatch) -> None:
    tenant_id = uuid.uuid4()

    def _fake_list_tools_projection(self):
        return AgentRuntimeToolsProjectionOut(
            tools=[
                AgentRuntimeToolProjectionOut(
                    id="data_intelligence_profile_field",
                    title="Data Intelligence Profile Field",
                    description="Profile one allowlisted field.",
                    owner_package="packages.tools.data_intelligence_tools",
                    status="available",
                    callable=True,
                    data_classes=["ops"],
                    input_posture="allowlisted dataset and field",
                    output_posture="aggregate field profile",
                    policy_posture="service-owned aggregates only",
                    limits=["aggregate output"],
                    downstream_surfaces=["data_intelligence"],
                )
            ],
        )

    monkeypatch.setattr(
        agent_runtime_router.AgentRuntimeService,
        "list_tools_projection",
        _fake_list_tools_projection,
    )

    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.get("/agent-runtime/tools")

    assert res.status_code == 200
    body = res.json()
    assert body["runtime"] == "agent_runtime"
    assert body["source"] == "packages.tools.registry"
    assert body["tools"][0]["id"] == "data_intelligence_profile_field"
    assert body["tools"][0]["callable"] is True
    assert body["tools"][0]["output_posture"] == "aggregate field profile"
    assert "sk-" not in res.text
    assert "raw_provider_payload" not in res.text


def test_agent_runtime_routes_reject_non_admin_principal(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    principal = Principal(
        id=uuid.uuid4(),
        email="staff@example.com",
        tenant_id=TenantId(tenant_id),
        roles=frozenset({Role.STAFF}),
    )

    client = TestClient(
        _build_app(
            tenant_id=tenant_id,
            db_session=MagicMock(),
            principal=principal,
        )
    )
    res = client.get("/agent-runtime/tools")

    assert res.status_code == 403
    assert res.json()["error"]["code"] == "forbidden"


def test_agent_runtime_routes_allow_admin_principal_in_production() -> None:
    tenant_id = uuid.uuid4()

    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.get("/agent-runtime/tools")

    assert res.status_code == 200
    assert res.json()["runtime"] == "agent_runtime"


def test_agent_runtime_dia_catalog_linkages_returns_safe_projection(monkeypatch) -> None:
    tenant_id = uuid.uuid4()

    def _fake_list_dia_catalog_linkages(self):
        return AgentRuntimeDiaCatalogLinkagesOut.model_validate(
            {
                "linkages": [
                    {
                        "id": "dia-lead-source-mapping-to-catalog-review",
                        "title": (
                            "DIA lead source mapping candidate to Semantic Catalog review"
                        ),
                        "source_agent": "Data Intelligence Mapping Helper",
                        "output_kind": "mapping_proposal",
                        "runtime_run_id": "run-semantic-proposal-planned",
                        "approval_request_id": "approval-semantic-catalog-1",
                        "catalog_proposal_ref": "lead-source-google-ads",
                        "approved_catalog_version_ref": None,
                        "review_posture": "review_only_no_auto_approval",
                        "downstream_consumption": "approved_version_only",
                        "data_classes": ["ops", "integration_metadata"],
                        "evidence_refs": ["mapping_coverage_summary"],
                        "impact_surfaces": [
                            {
                                "surface": "semantic_catalog",
                                "confidence": "known",
                                "reason": (
                                    "Human review proposal is the only path into "
                                    "catalog meaning."
                                ),
                            }
                        ],
                        "path": [
                            {
                                "id": "agent_run",
                                "title": "Agent run",
                                "status": "ready",
                                "owner": "packages.agent_runtime",
                                "contract": "Safe run summary only.",
                            },
                            {
                                "id": "approved_version",
                                "title": "Approved catalog version",
                                "status": "planned",
                                "owner": "packages.insight",
                                "contract": (
                                    "Downstream consumers read approved versions only."
                                ),
                            },
                        ],
                        "notes": [
                            "Agent suggestions are never approved catalog truth by themselves."
                        ],
                    }
                ]
            }
        )

    monkeypatch.setattr(
        agent_runtime_router.AgentRuntimeService,
        "list_dia_catalog_linkages",
        _fake_list_dia_catalog_linkages,
    )

    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.get("/agent-runtime/dia-catalog-linkages")

    assert res.status_code == 200
    body = res.json()
    assert body["runtime"] == "agent_runtime"
    assert body["source"] == "agent_runtime_projection"
    assert body["linkages"][0]["review_posture"] == "review_only_no_auto_approval"
    assert body["linkages"][0]["downstream_consumption"] == "approved_version_only"
    assert body["linkages"][0]["approved_catalog_version_ref"] is None
    assert "sk-" not in res.text
    assert "raw_provider_payload" not in res.text


def test_agent_runtime_runs_returns_safe_history(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    captured: dict[str, Any] = {}

    async def _fake_list_run_history(
        self,
        tenant_id_arg,
        *,
        limit,
        status=None,
        tool_id=None,
        policy_result=None,
        final_outcome=None,
        triggered_by=None,
        started_after=None,
        started_before=None,
    ):
        captured["tenant_id"] = tenant_id_arg
        captured["limit"] = limit
        captured["status"] = status
        captured["tool_id"] = tool_id
        captured["policy_result"] = policy_result
        captured["final_outcome"] = final_outcome
        captured["triggered_by"] = triggered_by
        captured["started_after"] = started_after
        captured["started_before"] = started_before
        return AgentRuntimeRunHistoryOut(
            filters={
                "limit": limit,
                "status": status,
                "tool_id": tool_id,
                "policy_result": policy_result,
                "final_outcome": final_outcome,
                "triggered_by": triggered_by,
                "started_after": started_after,
                "started_before": started_before,
            },
            runs=[
                AgentRuntimeRunSummaryOut(
                    id=str(uuid.uuid4()),
                    agent_name="Fusion OpenAI Health Check",
                    provider_kind="openai",
                    model="gpt-4.1-mini",
                    run_kind="provider_health_check",
                    status="success",
                    started_at="2026-06-05T16:00:00Z",
                    completed_at="2026-06-05T16:00:00Z",
                    duration_ms=20,
                    triggered_by="ops@example.com",
                    tool_calls=[],
                    result_posture="safe_metadata_only",
                    audit_summary=AgentRuntimeAuditSummaryOut(
                        data_classes=["integration_metadata"],
                        data_level="metadata_only",
                        row_level=False,
                        phi=False,
                        billing=False,
                        export=False,
                        masked=True,
                        policy_result="allowed",
                        policy_gate="provider_credential_health_check",
                        policy_reason=(
                            "Tenant OpenAI credential check uses metadata only."
                        ),
                        approval_required=False,
                        final_outcome="completed",
                        policy_decisions=[
                            {
                                "gate_id": "tenant_credential_scope",
                                "result": "allowed",
                                "reason": (
                                    "Credential resolved server-side for current tenant."
                                ),
                                "evidence_refs": ["tenant_credential_status"],
                            }
                        ],
                        evidence_refs=["provider_health_check"],
                        compliance_notes=["No sensitive details stored."],
                        linked_approval_request_ids=[],
                    ),
                )
            ]
        )

    monkeypatch.setattr(
        agent_runtime_router.AgentRuntimeService,
        "list_run_history",
        _fake_list_run_history,
    )

    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.get(
        "/agent-runtime/runs?limit=500&status=success"
        "&tool_id=run_analytics_query&policy_result=allowed"
        "&final_outcome=completed&triggered_by=ops@example.com"
        "&started_after=2026-06-05T15:00:00Z"
        "&started_before=2026-06-05T17:00:00Z"
    )

    assert res.status_code == 200
    body = res.json()
    assert body["runtime"] == "agent_runtime"
    assert body["filters"]["limit"] == 100
    assert body["filters"]["status"] == "success"
    assert body["filters"]["tool_id"] == "run_analytics_query"
    assert body["filters"]["policy_result"] == "allowed"
    assert body["filters"]["final_outcome"] == "completed"
    assert body["filters"]["triggered_by"] == "ops@example.com"
    assert body["runs"][0]["agent_name"] == "Fusion OpenAI Health Check"
    assert body["runs"][0]["status"] == "success"
    assert body["runs"][0]["audit_summary"]["phi"] is False
    assert body["runs"][0]["audit_summary"]["policy_result"] == "allowed"
    assert body["runs"][0]["audit_summary"]["data_level"] == "metadata_only"
    assert body["runs"][0]["audit_summary"]["final_outcome"] == "completed"
    assert (
        body["runs"][0]["audit_summary"]["policy_decisions"][0]["gate_id"]
        == "tenant_credential_scope"
    )
    assert captured["tenant_id"] == TenantId(tenant_id)
    assert captured["limit"] == 100
    assert captured["status"] == "success"
    assert captured["tool_id"] == "run_analytics_query"
    assert captured["policy_result"] == "allowed"
    assert captured["final_outcome"] == "completed"
    assert captured["triggered_by"] == "ops@example.com"
    assert captured["started_after"].isoformat() == "2026-06-05T15:00:00+00:00"
    assert captured["started_before"].isoformat() == "2026-06-05T17:00:00+00:00"
    assert "sk-" not in res.text
    assert "raw_provider_payload" not in res.text
    assert "raw_sql" not in res.text


def test_agent_runtime_llm_plan_returns_safe_success(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    captured: dict[str, Any] = {}

    async def _fake_generate_llm_plan(self, principal, payload):
        captured["tenant_id"] = principal.require_tenant()
        captured["principal_email"] = principal.email
        captured["payload"] = payload
        return AgentRuntimeLlmPlanOut(
            run_id=str(uuid.uuid4()),
            model="gpt-4.1-mini",
            last_agent="Fusion Agent Runtime Planner",
            outcome="tool_plan",
            intent="manager_analytics",
            tool_id="ask_manager_analytics",
            tool_arguments={"question_kind": "lead_conversion"},
            confidence="high",
            safety_notes=["Aggregate-only planning."],
            policy_result="allowed",
            policy_reason="LLM returned a validated plan for an approved aggregate tool.",
            approval_required=False,
        )

    monkeypatch.setattr(
        agent_runtime_router.AgentRuntimeService,
        "generate_llm_plan",
        _fake_generate_llm_plan,
    )

    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.post(
        "/agent-runtime/llm/plans",
        json={"user_prompt": "How are lead conversions trending?"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["runtime"] == "agent_runtime"
    assert body["provider_kind"] == "openai"
    assert body["outcome"] == "tool_plan"
    assert body["tool_id"] == "ask_manager_analytics"
    assert body["policy_result"] == "allowed"
    assert body["approval_required"] is False
    assert body["result_posture"] == "safe_llm_plan_metadata_only"
    assert "How are lead conversions trending?" not in res.text
    assert "sk-" not in res.text
    assert "raw_provider_payload" not in res.text
    assert captured["tenant_id"] == TenantId(tenant_id)
    assert captured["principal_email"] == "ops@example.com"
    assert captured["payload"].user_prompt == "How are lead conversions trending?"


def test_agent_runtime_llm_plan_returns_safe_denial(monkeypatch) -> None:
    tenant_id = uuid.uuid4()

    async def _fake_generate_llm_plan(self, principal, payload):
        return AgentRuntimeLlmPlanOut(
            run_id=str(uuid.uuid4()),
            model="gpt-4.1-mini",
            last_agent="Fusion Agent Runtime Planner",
            outcome="tool_plan",
            intent="clinical_snapshot",
            tool_id="get_phi_person_snapshot",
            tool_arguments={},
            confidence="medium",
            policy_result="denied",
            policy_reason="PHI-bearing tools are not available to the LLM pilot.",
            approval_required=False,
        )

    monkeypatch.setattr(
        agent_runtime_router.AgentRuntimeService,
        "generate_llm_plan",
        _fake_generate_llm_plan,
    )

    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.post(
        "/agent-runtime/llm/plans",
        json={"user_prompt": "Show a clinical patient snapshot."},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["policy_result"] == "denied"
    assert body["approval_required"] is False
    assert "PHI-bearing tools" in body["policy_reason"]
    assert "sk-" not in res.text
    assert "raw_provider_payload" not in res.text


def test_agent_runtime_llm_plan_returns_safe_platform_error(monkeypatch) -> None:
    tenant_id = uuid.uuid4()

    async def _fake_generate_llm_plan(self, principal, payload):
        raise ValidationError("OpenAI planning failed safely.")

    monkeypatch.setattr(
        agent_runtime_router.AgentRuntimeService,
        "generate_llm_plan",
        _fake_generate_llm_plan,
    )

    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.post(
        "/agent-runtime/llm/plans",
        json={"user_prompt": "Plan a safe aggregate answer."},
    )

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"
    assert "sk-" not in res.text
    assert "raw_provider_payload" not in res.text


def test_agent_runtime_llm_plan_rejects_unsafe_prompt_body() -> None:
    tenant_id = uuid.uuid4()
    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    for prompt in (
        "Use raw_provider_payload for this answer.",
        "Run raw_sql against the database.",
        "select * from phi.patient",
    ):
        res = client.post(
            "/agent-runtime/llm/plans",
            json={"user_prompt": prompt},
        )

        assert res.status_code == 422
        assert "sk-" not in res.text
        assert "raw_provider_payload" not in res.text
        assert "select *" not in res.text.lower()


def test_agent_runtime_approvals_returns_safe_requests(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    captured: dict[str, Any] = {}
    approval_id = str(uuid.uuid4())

    async def _fake_list_approval_requests(self, tenant_id_arg, *, status, limit):
        captured["tenant_id"] = tenant_id_arg
        captured["status"] = status
        captured["limit"] = limit
        return AgentRuntimeApprovalRequestsOut(
            approvals=[
                AgentRuntimeApprovalRequestOut(
                    id=approval_id,
                    source_run_id=None,
                    agent_name="Data Intelligence Mapping Helper",
                    tool_id="data_intelligence_semantic_mapping_proposal",
                    target_kind="semantic_catalog_mapping_proposal",
                    target_ref="lead-source-google-ads",
                    title="Review mapping candidate",
                    reason="Repeated source values need human review.",
                    evidence_summary="Aggregate coverage only.",
                    requested_action="Create Semantic Catalog review draft.",
                    status="pending",
                    requested_at="2026-06-05T16:10:00Z",
                    requested_by="ops@example.com",
                    data_classes=["ops"],
                    affected_surfaces=["semantic_catalog"],
                    risk_flags=["business_meaning_change"],
                    approval_posture="human_review_required_no_auto_mutation",
                )
            ]
        )

    monkeypatch.setattr(
        agent_runtime_router.AgentRuntimeService,
        "list_approval_requests",
        _fake_list_approval_requests,
    )

    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.get("/agent-runtime/approvals?status=pending&limit=500")

    assert res.status_code == 200
    body = res.json()
    assert body["runtime"] == "agent_runtime"
    assert body["approvals"][0]["id"] == approval_id
    assert body["approvals"][0]["status"] == "pending"
    assert body["approvals"][0]["target_kind"] == "semantic_catalog_mapping_proposal"
    assert captured == {
        "tenant_id": TenantId(tenant_id),
        "status": "pending",
        "limit": 100,
    }
    assert "sk-" not in res.text
    assert "raw_provider_payload" not in res.text


def test_agent_runtime_create_approval_request_wires_service(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    captured: dict[str, Any] = {}

    async def _fake_create_approval_request(self, principal, payload):
        captured["tenant_id"] = principal.require_tenant()
        captured["payload"] = payload
        return AgentRuntimeApprovalRequestOut(
            id=str(uuid.uuid4()),
            agent_name=payload.agent_name,
            tool_id=payload.tool_id,
            target_kind=payload.target_kind,
            target_ref=payload.target_ref,
            title=payload.title,
            reason=payload.reason,
            evidence_summary=payload.evidence_summary,
            requested_action=payload.requested_action,
            status="pending",
            requested_at="2026-06-05T16:10:00Z",
            requested_by=principal.email,
            data_classes=payload.data_classes,
            affected_surfaces=payload.affected_surfaces,
            risk_flags=payload.risk_flags,
            approval_posture=payload.approval_posture,
        )

    monkeypatch.setattr(
        agent_runtime_router.AgentRuntimeService,
        "create_approval_request",
        _fake_create_approval_request,
    )

    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.post(
        "/agent-runtime/approvals",
        json={
            "agent_name": "Data Intelligence Mapping Helper",
            "tool_id": "data_intelligence_semantic_mapping_proposal",
            "target_kind": "semantic_catalog_mapping_proposal",
            "target_ref": "lead-source-google-ads",
            "title": "Review mapping candidate",
            "reason": "Repeated source values need human review.",
            "evidence_summary": "Aggregate coverage only.",
            "requested_action": "Create Semantic Catalog review draft.",
            "data_classes": ["ops"],
            "affected_surfaces": ["semantic_catalog"],
            "risk_flags": ["business_meaning_change"],
        },
    )

    assert res.status_code == 200
    assert res.json()["status"] == "pending"
    assert captured["tenant_id"] == TenantId(tenant_id)
    assert isinstance(captured["payload"], AgentRuntimeApprovalRequestCreateIn)
    assert "sk-" not in res.text


def test_agent_runtime_decide_approval_request_wires_service(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    approval_id = uuid.uuid4()
    captured: dict[str, Any] = {}

    async def _fake_decide_approval_request(
        self,
        principal,
        approval_id_arg,
        payload,
    ):
        captured["tenant_id"] = principal.require_tenant()
        captured["approval_id"] = approval_id_arg
        captured["payload"] = payload
        return AgentRuntimeApprovalRequestOut(
            id=str(approval_id_arg),
            agent_name="Data Intelligence Mapping Helper",
            tool_id="data_intelligence_semantic_mapping_proposal",
            target_kind="semantic_catalog_mapping_proposal",
            target_ref="lead-source-google-ads",
            title="Review mapping candidate",
            reason="Repeated source values need human review.",
            evidence_summary="Aggregate coverage only.",
            requested_action="Create Semantic Catalog review draft.",
            status="approved",
            requested_at="2026-06-05T16:10:00Z",
            requested_by="ops@example.com",
            decided_at="2026-06-05T16:15:00Z",
            decided_by=principal.email,
            data_classes=["ops"],
            affected_surfaces=["semantic_catalog"],
            risk_flags=["business_meaning_change"],
            approval_posture="human_review_required_no_auto_mutation",
            decision_summary=payload.decision_summary,
        )

    monkeypatch.setattr(
        agent_runtime_router.AgentRuntimeService,
        "decide_approval_request",
        _fake_decide_approval_request,
    )

    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.post(
        f"/agent-runtime/approvals/{approval_id}/decision",
        json={
            "decision": "approve",
            "decision_summary": "Approved for downstream review workflow.",
        },
    )

    assert res.status_code == 200
    assert res.json()["status"] == "approved"
    assert captured["tenant_id"] == TenantId(tenant_id)
    assert captured["approval_id"] == approval_id
    assert isinstance(captured["payload"], AgentRuntimeApprovalDecisionIn)
    assert "sk-" not in res.text
