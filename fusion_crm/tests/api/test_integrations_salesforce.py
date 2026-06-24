"""HTTP-level tests for the Salesforce integration routes (slice 1).

We mount the FastAPI app and stub ``SfLeadIngestService`` via
``app.dependency_overrides`` so the route tests don't touch the real DB or
the SF API. Service-level behaviour is covered by
``tests/ingest/test_sf_lead_service.py``.

ENG-128: ``get_principal_with_tenant`` is also overridden — the live
dependency reaches into the DB to resolve the bootstrap tenant slug,
which is not available in unit tests. We stub a synthetic principal
with a fixed tenant id and assert the route forwards it to the service.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api import dependencies as api_dependencies
from apps.api.dependencies import (
    get_db,
    get_integration_service,
    get_principal_with_tenant,
    get_salesforce_client,
    get_sf_lead_ingest_service,
    get_sf_task_ingest_service,
)
from apps.api.middleware import RequestContextMiddleware, platform_error_handler
from apps.api.routers import integrations as integrations_router
from packages.core.exceptions import PlatformError
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.ingest.schemas import SfLeadOut, SfTaskImportOut
from packages.integrations.salesforce.exceptions import SfNotConnectedError
from packages.tenant.credential_service import NoCredentialError

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_SYNC_RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000239")
_SF_LEAD_ID = "00Q000000000001"


def _principal() -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="oncall@fusiondentalimplants.com",
        tenant_id=_TENANT_ID,
        roles=frozenset({Role.STAFF}),
    )


def _integration_service() -> MagicMock:
    svc = MagicMock()
    svc.open_provider_sync_run = AsyncMock(return_value=SimpleNamespace(id=_SYNC_RUN_ID))
    svc.close_provider_sync_run = AsyncMock()
    return svc


def _build_app(
    svc: MagicMock,
    sf_client: MagicMock | None = None,
    integration_svc: MagicMock | None = None,
    task_svc: MagicMock | None = None,
) -> FastAPI:
    """Build a minimal FastAPI app with just the integrations router and the
    error-envelope middleware, with the SF service dependency overridden."""
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    # FastAPI / Starlette overload mismatch on PlatformError-typed handlers —
    # same baseline issue as apps/api/main.py.
    app.add_exception_handler(PlatformError, platform_error_handler)  # type: ignore[arg-type]
    app.include_router(integrations_router.router)
    app.dependency_overrides[get_sf_lead_ingest_service] = lambda: svc
    if task_svc is not None:
        app.dependency_overrides[get_sf_task_ingest_service] = lambda: task_svc
    app.dependency_overrides[get_principal_with_tenant] = _principal
    app.dependency_overrides[get_integration_service] = (
        lambda: integration_svc or _integration_service()
    )

    async def _db_override():
        yield MagicMock()

    app.dependency_overrides[get_db] = _db_override
    if sf_client is not None:
        app.dependency_overrides[get_salesforce_client] = lambda: sf_client
    return app


def _lead_dto(*, sf_id: str = "00Q1") -> SfLeadOut:
    return SfLeadOut(
        id=uuid.uuid4(),
        person_uid=uuid.uuid4(),
        sf_lead_id=sf_id,
        display_name="Jane Doe",
        email="jane@example.com",
        phone="+15551234567",
        company="Acme",
        lead_source="Web",
        lead_status="Open",
        is_reactivation=False,
        sf_created_at="2026-05-07T20:00:00.000+0000",
        created_at=datetime.now(UTC),
    )


def test_pull_recent_returns_items_and_count() -> None:
    svc = MagicMock()
    svc.pull_recent = AsyncMock(return_value=[_lead_dto(sf_id="00Q1"), _lead_dto(sf_id="00Q2")])
    client = TestClient(_build_app(svc))

    res = client.post("/integrations/salesforce/pull-recent?limit=2")

    assert res.status_code == 200
    body = res.json()
    assert body["pulled_count"] == 2
    assert body["sync_run_id"] == str(_SYNC_RUN_ID)
    assert len(body["items"]) == 2
    assert body["items"][0]["sf_lead_id"] == "00Q1"
    svc.pull_recent.assert_awaited_once_with(_TENANT_ID, 2)


def test_pull_recent_default_limit_is_5() -> None:
    svc = MagicMock()
    svc.pull_recent = AsyncMock(return_value=[])
    client = TestClient(_build_app(svc))

    res = client.post("/integrations/salesforce/pull-recent")

    assert res.status_code == 200
    svc.pull_recent.assert_awaited_once_with(_TENANT_ID, 5)


def test_pull_recent_closes_partial_when_service_reports_error() -> None:
    integration_svc = _integration_service()
    svc = MagicMock()
    svc.pull_recent = AsyncMock(side_effect=RuntimeError("provider timeout"))
    client = TestClient(_build_app(svc, integration_svc=integration_svc))

    with pytest.raises(RuntimeError):
        client.post("/integrations/salesforce/pull-recent")

    close_call = integration_svc.close_provider_sync_run.await_args
    assert close_call is not None
    assert close_call.kwargs["status"] == "failed"
    assert close_call.kwargs["records_failed"] == 1


@pytest.mark.parametrize("bad_limit", ["0", "-1", "51", "1000"])
def test_pull_recent_rejects_out_of_range_limit(bad_limit: str) -> None:
    svc = MagicMock()
    svc.pull_recent = AsyncMock()
    client = TestClient(_build_app(svc))

    res = client.post(f"/integrations/salesforce/pull-recent?limit={bad_limit}")

    assert res.status_code == 422
    svc.pull_recent.assert_not_called()


def test_pull_recent_translates_sf_not_connected_to_envelope() -> None:
    svc = MagicMock()
    svc.pull_recent = AsyncMock(side_effect=SfNotConnectedError("tokens missing"))
    client = TestClient(_build_app(svc))

    res = client.post("/integrations/salesforce/pull-recent")

    assert res.status_code == 409
    body = res.json()
    assert body["error"]["code"] == "sf_not_connected"
    assert "tokens missing" in body["error"]["message"]


def test_pull_recent_marks_oauth_expired_when_refresh_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expire_active_for = AsyncMock(return_value=1)

    class _CredentialService:
        def __init__(self, _db: object) -> None:
            pass

        async def expire_active_for(self, *args: object, **kwargs: object) -> int:
            return await expire_active_for(*args, **kwargs)

    monkeypatch.setattr(
        integrations_router,
        "IntegrationCredentialService",
        _CredentialService,
    )
    svc = MagicMock()
    svc.pull_recent = AsyncMock(
        side_effect=SfNotConnectedError(
            "Salesforce connection expired.",
            details={"action": "reconnect"},
        )
    )
    client = TestClient(_build_app(svc))

    res = client.post("/integrations/salesforce/pull-recent")

    assert res.status_code == 409
    assert res.json()["error"]["code"] == "sf_not_connected"
    expire_active_for.assert_awaited_once()
    call = expire_active_for.await_args
    assert call is not None
    args, kwargs = call
    assert args[:3] == (_TENANT_ID, "salesforce", "oauth_token")
    assert kwargs["principal"].tenant_id == _TENANT_ID


def test_recent_leads_returns_items() -> None:
    svc = MagicMock()
    svc.list_recent = AsyncMock(return_value=[_lead_dto()])
    client = TestClient(_build_app(svc))

    res = client.get("/integrations/salesforce/recent-leads?limit=3")

    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["sf_lead_id"] == "00Q1"
    svc.list_recent.assert_awaited_once_with(_TENANT_ID, 3)


def test_recent_leads_rejects_bad_limit() -> None:
    svc = MagicMock()
    svc.list_recent = AsyncMock()
    client = TestClient(_build_app(svc))

    res = client.get("/integrations/salesforce/recent-leads?limit=0")

    assert res.status_code == 422
    svc.list_recent.assert_not_called()


def test_import_tasks_runs_task_service_and_sync_journal() -> None:
    svc = MagicMock()
    task_svc = MagicMock()
    task_svc.import_recent_tasks = AsyncMock(
        return_value=SfTaskImportOut(
            imported_count=3,
            skipped_count=1,
            queried_count=4,
        )
    )
    integration_svc = _integration_service()
    client = TestClient(
        _build_app(svc, integration_svc=integration_svc, task_svc=task_svc)
    )

    res = client.post("/integrations/salesforce/import-tasks?days=7&limit=25")

    assert res.status_code == 200
    body = res.json()
    assert body["imported_count"] == 3
    assert body["skipped_count"] == 1
    assert body["queried_count"] == 4
    assert body["sync_run_id"] == str(_SYNC_RUN_ID)
    task_svc.import_recent_tasks.assert_awaited_once_with(_TENANT_ID, days=7, limit=25)
    close_call = integration_svc.close_provider_sync_run.await_args
    assert close_call is not None
    assert close_call.kwargs["object_scope"] == "task"
    assert close_call.kwargs["status"] == "partial"
    assert close_call.kwargs["records_total"] == 4
    assert close_call.kwargs["records_succeeded"] == 3
    assert close_call.kwargs["records_failed"] == 1


def test_lead_raw_uses_salesforce_client_dependency() -> None:
    svc = MagicMock()
    sf_client = MagicMock()
    sf_client.get_object = AsyncMock(
        return_value={"Id": _SF_LEAD_ID, "attributes": {"type": "Lead"}}
    )
    client = TestClient(_build_app(svc, sf_client=sf_client))

    res = client.get(f"/integrations/salesforce/lead/{_SF_LEAD_ID}/raw")

    assert res.status_code == 200
    assert res.json()["Id"] == _SF_LEAD_ID
    sf_client.get_object.assert_awaited_once_with("Lead", _SF_LEAD_ID)


def test_lead_raw_translates_sf_not_connected_to_envelope() -> None:
    svc = MagicMock()

    def _not_connected():
        raise SfNotConnectedError("Salesforce not connected — run OAuth flow first.")

    app = _build_app(svc)
    app.dependency_overrides[get_salesforce_client] = _not_connected
    client = TestClient(app)

    res = client.get(f"/integrations/salesforce/lead/{_SF_LEAD_ID}/raw")

    assert res.status_code == 409
    body = res.json()
    assert body["error"]["code"] == "sf_not_connected"
    assert "Salesforce not connected" in body["error"]["message"]


def test_lead_operational_summary_allowlists_safe_salesforce_fields() -> None:
    svc = MagicMock()
    sf_client = MagicMock()
    sf_client.get_object = AsyncMock(
        return_value={
            "Id": _SF_LEAD_ID,
            "Status": "Unqualified",
            "CreatedDate": "2025-10-01T07:00:57.000+0000",
            "Status_Last_Updated__c": "2026-04-27T20:26:33.000+0000",
            "LeadSource": None,
            "Hubspot_Lead_Source__c": "Zahn Implant Club Landing Built-In Form",
            "Record_Source_Detail__c": "Zahn Implant Club Landing Built-In Form",
            "Lead_Owner__c": "Call Center",
            "OwnerId": "00G-owner",
            "Assigned_Center__c": "Roseville",
            "Attempt_Count_c__c": "3",
            "Last_Call_Display__c": "Sofia",
            "Unqualified_Reason__c": "No Interest / Not Pursuing",
            "HS_Contact_ID__c": "40874168932",
            "Hubspot_Created_Date__c": "2024-07-20T15:09:00.000+0000",
            "Lead_Summary__c": (
                "free text must not render. "
                "Recording: https://storage.vapi.ai/call.wav"
            ),
            "Description": "PHI_MARKER must stay raw only",
            "raw_sensitive_field": "must not render",
        }
    )
    client = TestClient(_build_app(svc, sf_client=sf_client))

    res = client.get(
        f"/integrations/salesforce/lead/{_SF_LEAD_ID}/operational-summary"
    )

    assert res.status_code == 200
    body = res.json()
    assert body["sf_lead_id"] == _SF_LEAD_ID
    assert body["salesforce_status"] == "Unqualified"
    assert body["source"] == "Zahn Implant Club Landing Built-In Form"
    assert body["owner"] == "Call Center"
    assert body["assigned_center"] == "Roseville"
    assert body["attempt_count"] == 3
    assert body["call_recording_url"] == "https://storage.vapi.ai/call.wav"
    assert body["hubspot_contact_id"] == "40874168932"
    rendered = res.text
    assert "Description" not in rendered
    assert "PHI_MARKER" not in rendered
    assert "raw_sensitive_field" not in rendered
    assert "free text must not render" not in rendered
    sf_client.get_object.assert_awaited_once_with("Lead", _SF_LEAD_ID)


def test_lead_operational_tasks_parses_safe_sofia_call_metadata() -> None:
    svc = MagicMock()
    sf_client = MagicMock()
    sf_client.soql = AsyncMock(
        return_value={
            "records": [
                {
                    "Id": "00T000000000001",
                    "Subject": "Sofia AI Call - unqualified",
                    "Status": "Completed",
                    "ActivityDate": "2026-04-27",
                    "CreatedDate": "2026-04-27T20:26:32.000+0000",
                    "LastModifiedDate": "2026-04-27T20:26:33.000+0000",
                    "OwnerId": "005-owner",
                    "CallDurationInSeconds": None,
                    "CallObject": None,
                    "Description": (
                        "Agent: Sofia AI\n"
                        "Patient: Larry Jensen Unknown\n"
                        "Phone: +19169569183\n"
                        "Outcome: unqualified\n"
                        "Duration: 2 min\n\n"
                        "Call Recording: https://storage.vapi.ai/call.wav\n\n"
                        "Full Transcript:\n"
                        "AI: sensitive transcript must stay raw\n"
                    ),
                }
            ]
        }
    )
    client = TestClient(_build_app(svc, sf_client=sf_client))

    res = client.get(
        f"/integrations/salesforce/lead/{_SF_LEAD_ID}/operational-tasks"
    )

    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    task = body["items"][0]
    assert task["task_id"] == "00T000000000001"
    assert task["task_kind"] == "call"
    assert task["task_label"] == "Sofia AI Call"
    assert task["call_label"] == "Sofia AI Call"
    assert task["agent"] == "Sofia AI"
    assert task["outcome"] == "unqualified"
    assert task["duration_label"] == "2 min"
    assert task["duration_seconds"] == 120
    assert task["call_recording_url"] == "https://storage.vapi.ai/call.wav"
    rendered = res.text
    assert "Patient" not in rendered
    assert "Phone" not in rendered
    assert "transcript" not in rendered.lower()
    assert _SF_LEAD_ID in sf_client.soql.await_args.args[0]


def test_lead_operational_tasks_parses_new_lead_followup_metadata() -> None:
    svc = MagicMock()
    sf_client = MagicMock()
    sf_client.soql = AsyncMock(
        return_value={
            "records": [
                {
                    "Id": "00T000000000002",
                    "Subject": "NEW LEAD — CALL NOW: Lost Hills Ca",
                    "Status": "Open",
                    "ActivityDate": "2026-05-25",
                    "CreatedDate": "2026-05-25T21:23:21.000+0000",
                    "LastModifiedDate": "2026-05-25T21:23:21.000+0000",
                    "OwnerId": "005-owner",
                    "Description": (
                        "NEW LEAD JUST CAME IN — first one to call wins.\n"
                        "Patient: Lost Hills Ca\n"
                        "Phone: 661-214-0807\n"
                        "Source: Salesforce\n"
                        "BU: Fusion Dental Implants\n"
                        "Language: English\n"
                        "Created: 5/25/2026, 2:23:21 PM PT\n"
                    ),
                }
            ]
        }
    )
    client = TestClient(_build_app(svc, sf_client=sf_client))

    res = client.get(
        f"/integrations/salesforce/lead/{_SF_LEAD_ID}/operational-tasks"
    )

    assert res.status_code == 200
    task = res.json()["items"][0]
    assert task["task_kind"] == "followup"
    assert task["task_label"] == "New lead call-now task"
    assert task["source"] == "Salesforce"
    assert task["business_unit"] == "Fusion Dental Implants"
    assert task["language"] == "English"
    assert task["created_label"] == "5/25/2026, 2:23:21 PM PT"
    assert task["is_overdue"] is True
    rendered = res.text
    assert "Patient" not in rendered
    assert "661-214-0807" not in rendered
    assert "Lost Hills" not in rendered


async def test_salesforce_client_builder_requires_db_oauth_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing DB OAuth credentials should not fall back to stale dev files."""

    class _NoCredentialService:
        def __init__(self, _db: object) -> None:
            pass

        async def read_for(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            raise NoCredentialError(
                "missing",
                details={
                    "provider_kind": "salesforce",
                    "credential_kind": "oauth_token",
                },
            )

    from_dev_file = MagicMock()
    monkeypatch.setattr(
        api_dependencies,
        "IntegrationCredentialService",
        _NoCredentialService,
    )
    monkeypatch.setattr(
        api_dependencies.SfClient,
        "from_dev_file",
        from_dev_file,
    )

    with pytest.raises(SfNotConnectedError) as exc:
        await api_dependencies._build_salesforce_client(
            MagicMock(),
            _principal(),
        )

    assert exc.value.message == "Salesforce not connected — run the OAuth flow first."
    assert exc.value.details["provider_kind"] == "salesforce"
    assert exc.value.details["credential_kind"] == "oauth_token"
    from_dev_file.assert_not_called()
