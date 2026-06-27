"""HTTP tests for PHI-free ops person context routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import get_ops_service, get_principal_with_tenant
from apps.api.routers import ops as ops_router
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.ops.models import (
    ConsultationKind,
    ConsultationStatus,
    RelationshipKind,
    RelationshipStatus,
)
from packages.ops.schemas import ConsultationOut, PersonLocationProfileOut

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_PERSON_UID = uuid.uuid4()
_LOCATION_ID = uuid.uuid4()
_NOW = datetime(2026, 6, 1, 14, 0, tzinfo=UTC)


def _principal() -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="ops@example.com",
        tenant_id=_TENANT_ID,
        roles=frozenset({Role.STAFF}),
    )


def _build_app(svc: MagicMock) -> FastAPI:
    app = FastAPI()
    app.include_router(ops_router.router)
    app.dependency_overrides[get_ops_service] = lambda: svc
    app.dependency_overrides[get_principal_with_tenant] = _principal
    return app


def test_list_person_consultations_returns_ops_projection() -> None:
    svc = MagicMock()
    svc.list_consultations_for_person = AsyncMock(
        return_value=[
            ConsultationOut(
                id=uuid.uuid4(),
                person_uid=_PERSON_UID,
                source_provider="carestack",
                source_instance="carestack-main",
                external_id="7821",
                scheduled_at=_NOW,
                duration_minutes=30,
                status=ConsultationStatus.SCHEDULED,
                consultation_kind=ConsultationKind.OTHER,
                location_id=_LOCATION_ID,
                provider_clinician_name="Dr. Smith",
                raw_event_id=uuid.uuid4(),
                created_at=_NOW,
                updated_at=_NOW,
            )
        ]
    )
    client = TestClient(_build_app(svc))

    res = client.get(f"/ops/persons/{_PERSON_UID}/consultations")

    assert res.status_code == 200
    body = res.json()
    assert body[0]["person_uid"] == str(_PERSON_UID)
    assert body[0]["source_provider"] == "carestack"
    assert body[0]["status"] == "scheduled"
    assert body[0]["location_id"] == str(_LOCATION_ID)
    svc.list_consultations_for_person.assert_awaited_once_with(
        _TENANT_ID, _PERSON_UID
    )


def test_list_person_location_profiles_returns_relationship_evidence() -> None:
    svc = MagicMock()
    svc.list_person_location_profiles_for_person = AsyncMock(
        return_value=[
            PersonLocationProfileOut(
                id=uuid.uuid4(),
                person_uid=_PERSON_UID,
                location_id=_LOCATION_ID,
                relationship_kind=RelationshipKind.PROSPECT,
                relationship_status=RelationshipStatus.CONSULT_SCHEDULED,
                last_evidence_provider="carestack",
                last_evidence_source_instance="carestack-main",
                last_evidence_external_id="7821",
                last_evidence_at=_NOW,
                last_consultation_id=uuid.uuid4(),
                last_raw_event_id=uuid.uuid4(),
                created_at=_NOW,
                updated_at=_NOW,
            )
        ]
    )
    client = TestClient(_build_app(svc))

    res = client.get(f"/ops/persons/{_PERSON_UID}/location-profiles")

    assert res.status_code == 200
    body = res.json()
    assert body[0]["person_uid"] == str(_PERSON_UID)
    assert body[0]["location_id"] == str(_LOCATION_ID)
    assert body[0]["relationship_kind"] == "prospect"
    assert body[0]["relationship_status"] == "consult_scheduled"
    assert body[0]["last_evidence_provider"] == "carestack"
    svc.list_person_location_profiles_for_person.assert_awaited_once_with(
        _TENANT_ID, _PERSON_UID
    )
