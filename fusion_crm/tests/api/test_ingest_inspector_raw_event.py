"""HTTP tests for the single-raw-event inspector sibling (ENG-271).

``GET /ingest/dev/inspector/raw-events/{event_id}`` mirrors the existing
list endpoint and is used by the PM Payments page row drilldown. The
underlying tenant filter on ``IngestRepository.get`` is the safety
boundary; one tenant must never read another tenant's raw event.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import get_ingest_service, get_principal_with_tenant
from apps.api.middleware import platform_error_handler
from apps.api.routers import ingest as ingest_router
from packages.core.exceptions import PlatformError
from packages.core.security import Principal, Role
from packages.core.types import TenantId

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _principal() -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="inspector@example.com",
        tenant_id=_TENANT_ID,
        roles=frozenset({Role.STAFF}),
    )


def _build_app(svc: MagicMock) -> FastAPI:
    app = FastAPI()
    app.include_router(ingest_router.router)
    app.add_exception_handler(PlatformError, platform_error_handler)  # type: ignore[arg-type]
    app.dependency_overrides[get_ingest_service] = lambda: svc
    app.dependency_overrides[get_principal_with_tenant] = _principal
    return app


def test_inspector_by_id_returns_verbatim_payload() -> None:
    event_id = uuid.uuid4()
    svc = MagicMock()
    svc.get_raw_event = AsyncMock(
        return_value=SimpleNamespace(
            id=event_id,
            source="carestack",
            event_type="carestack.accounting_transaction.upsert",
            external_id="CS-TX-9001",
            received_at=datetime(2026, 5, 22, 15, 30, tzinfo=UTC),
            payload={
                "id": "CS-TX-9001",
                "amount": 1850.0,
                "transactionType": "PATIENTCREDIT",
                "isReversed": False,
                "locationId": "22222222-0000-0000-0000-000000000001",
                "notes": "Crown final payment",
            },
        )
    )

    client = TestClient(_build_app(svc))
    res = client.get(f"/ingest/dev/inspector/raw-events/{event_id}")

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == str(event_id)
    assert body["provider"] == "carestack"
    assert body["external_id"] == "CS-TX-9001"
    assert body["kind"] == "carestack.accounting_transaction.upsert"
    # Verbatim payload survives unchanged — that's the drilldown contract.
    assert body["payload"]["amount"] == 1850.0
    assert body["payload"]["notes"] == "Crown final payment"
    # Tenant-scoped lookup with the principal's tenant id.
    svc.get_raw_event.assert_awaited_once_with(_TENANT_ID, event_id)


def test_inspector_by_id_returns_404_for_other_tenant_event() -> None:
    """When the repository's tenant filter excludes the row, service returns
    ``None`` and the route surfaces a 404 (PlatformError -> JSON envelope)."""
    event_id = uuid.uuid4()
    svc = MagicMock()
    svc.get_raw_event = AsyncMock(return_value=None)

    client = TestClient(_build_app(svc))
    res = client.get(f"/ingest/dev/inspector/raw-events/{event_id}")

    assert res.status_code == 404
    body = res.json()
    # PlatformError middleware ships a structured envelope. We don't assert
    # the exact code string here (middleware-owned) — only that the route
    # refuses to leak any payload from another tenant's row.
    assert "error" in body
    assert "payload" not in body
    svc.get_raw_event.assert_awaited_once_with(_TENANT_ID, event_id)
