"""HTTP tests for the CareStack Patient import route."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import (
    get_carestack_appointment_ingest_service,
    get_carestack_client_factory,
    get_carestack_patient_ingest_service,
    get_integration_service,
    get_location_service,
    get_principal_with_tenant,
)
from apps.api.middleware import RequestContextMiddleware, platform_error_handler
from apps.api.routers import carestack as carestack_router
from packages.core.exceptions import PlatformError
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.ingest.schemas import (
    CareStackAppointmentImportOut,
    CareStackPatientImportOut,
)
from packages.integrations.carestack.exceptions import CareStackNotConnectedError
from packages.tenant.schemas import ImportSummary

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_SYNC_RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000239")


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


def _build_app(svc: MagicMock, integration_svc: MagicMock | None = None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(PlatformError, platform_error_handler)  # type: ignore[arg-type]
    app.include_router(carestack_router.router)
    app.dependency_overrides[get_carestack_patient_ingest_service] = lambda: svc
    app.dependency_overrides[get_principal_with_tenant] = _principal
    app.dependency_overrides[get_integration_service] = (
        lambda: integration_svc or _integration_service()
    )
    return app


def _build_pull_app(
    *,
    location_svc: MagicMock,
    patient_svc: MagicMock,
    appointment_svc: MagicMock,
    client_factory: object,
    integration_svc: MagicMock | None = None,
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(PlatformError, platform_error_handler)  # type: ignore[arg-type]
    app.include_router(carestack_router.router)
    app.dependency_overrides[get_location_service] = lambda: location_svc
    app.dependency_overrides[get_carestack_patient_ingest_service] = (
        lambda: patient_svc
    )
    app.dependency_overrides[get_carestack_appointment_ingest_service] = (
        lambda: appointment_svc
    )
    app.dependency_overrides[get_carestack_client_factory] = lambda: client_factory
    app.dependency_overrides[get_principal_with_tenant] = _principal
    app.dependency_overrides[get_integration_service] = (
        lambda: integration_svc or _integration_service()
    )
    return app


def test_import_patients_returns_summary() -> None:
    svc = MagicMock()
    svc.import_recent_patients = AsyncMock(
        return_value=CareStackPatientImportOut(
            imported_count=2,
            skipped_count=1,
            page_count=1,
            next_continue_token=None,
        )
    )
    client = TestClient(_build_app(svc))

    res = client.post("/integrations/carestack/import-patients?days=14&pageSize=50&maxPages=2")

    assert res.status_code == 200
    assert res.json() == {
        "imported_count": 2,
        "unchanged_count": 0,
        "skipped_count": 1,
        "page_count": 1,
        "next_continue_token": None,
        "sync_run_id": str(_SYNC_RUN_ID),
    }
    svc.import_recent_patients.assert_awaited_once_with(
        _TENANT_ID,
        days=14,
        page_size=50,
        max_pages=2,
    )


def test_import_patients_translates_not_connected_to_envelope() -> None:
    svc = MagicMock()
    svc.import_recent_patients = AsyncMock(
        side_effect=CareStackNotConnectedError(
            "carestack not connected",
            details={"missing": ["account_id"]},
        )
    )
    client = TestClient(_build_app(svc))

    res = client.post("/integrations/carestack/import-patients")

    assert res.status_code == 502
    body = res.json()
    assert body["error"]["code"] == "integration_error"
    assert body["error"]["details"] == {"missing": ["account_id"]}


def test_pull_runs_locations_before_patients_and_appointments() -> None:
    calls: list[str] = []
    fake_client = MagicMock()
    fake_client.close = AsyncMock()

    async def _factory() -> MagicMock:
        return fake_client

    location_svc = MagicMock()

    async def _locations(*_args: object, **_kwargs: object) -> ImportSummary:
        calls.append("locations")
        return ImportSummary(total_seen=2, created=1, updated=1)

    location_svc.import_locations_from_carestack = AsyncMock(side_effect=_locations)

    patient_svc = MagicMock()

    async def _patients(*_args: object, **_kwargs: object) -> CareStackPatientImportOut:
        calls.append("patients")
        return CareStackPatientImportOut(
            imported_count=3,
            skipped_count=0,
            page_count=1,
            next_continue_token=None,
        )

    patient_svc.import_recent_patients = AsyncMock(side_effect=_patients)

    appointment_svc = MagicMock()

    async def _appointments(
        *_args: object, **_kwargs: object
    ) -> CareStackAppointmentImportOut:
        calls.append("appointments")
        return CareStackAppointmentImportOut(
            imported_count=5,
            skipped_count=0,
            page_count=1,
            next_continue_token=None,
        )

    appointment_svc.import_recent_appointments = AsyncMock(
        side_effect=_appointments
    )

    client = TestClient(
        _build_pull_app(
            location_svc=location_svc,
            patient_svc=patient_svc,
            appointment_svc=appointment_svc,
            client_factory=_factory,
        )
    )

    res = client.post("/integrations/carestack/pull?days=7&pageSize=50&maxPages=2")

    assert res.status_code == 200
    assert calls == ["locations", "patients", "appointments"]
    assert res.json() == {
        "locations": {
            "total_seen": 2,
            "created": 1,
            "updated": 1,
            "deactivated": 0,
        },
        "patients": {
            "imported_count": 3,
            "unchanged_count": 0,
            "skipped_count": 0,
            "page_count": 1,
            "next_continue_token": None,
            "sync_run_id": None,
        },
        "appointments": {
            "imported_count": 5,
            "unchanged_count": 0,
            "skipped_count": 0,
            "page_count": 1,
            "next_continue_token": None,
            "sync_run_id": None,
        },
        "sync_run_id": str(_SYNC_RUN_ID),
    }
    location_svc.import_locations_from_carestack.assert_awaited_once()
    patient_svc.import_recent_patients.assert_awaited_once_with(
        _TENANT_ID,
        days=7,
        page_size=50,
        max_pages=2,
    )
    appointment_svc.import_recent_appointments.assert_awaited_once_with(
        _TENANT_ID,
        days=7,
        page_size=50,
        max_pages=2,
    )
    fake_client.close.assert_awaited_once()
