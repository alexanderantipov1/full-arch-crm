"""HTTP contract tests for the enrichment annotation routes (ENG-439, Block F).

Handler-level coverage: the service is mocked and the principal is overridden,
so these assert the thin wiring (DTO ↔ service ↔ DTO, status codes, tenant
resolution) without a DB. Live persistence + tenant isolation lives in
``tests/enrichment/test_record_annotation_integration.py``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import (
    get_enrichment_service,
    get_principal_with_tenant,
)
from apps.api.middleware import platform_error_handler
from apps.api.routers import enrichment as enrichment_router
from packages.core.exceptions import PlatformError
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.enrichment.models import RecordAnnotation

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_ACTOR_ID = uuid.uuid4()


def _principal() -> Principal:
    return Principal(
        id=_ACTOR_ID,
        email="staff@example.com",
        tenant_id=_TENANT_ID,
        roles=frozenset({Role.ADMIN}),
    )


def _annotation(
    *,
    subject_type: str = "person",
    subject_id: uuid.UUID | None = None,
    key: str = "consult_notes",
) -> RecordAnnotation:
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    row = RecordAnnotation(
        tenant_id=uuid.UUID(str(_TENANT_ID)),
        subject_type=subject_type,
        subject_id=subject_id or uuid.uuid4(),
        key=key,
        value={"text": "Prefers morning slots"},
        source="ui",
        note=None,
        author_actor_id=None,
    )
    row.id = uuid.uuid4()
    row.created_at = now
    row.updated_at = now
    return row


def _build_app(svc: object) -> FastAPI:
    app = FastAPI()
    app.include_router(enrichment_router.router)
    app.add_exception_handler(PlatformError, platform_error_handler)  # type: ignore[arg-type]
    app.dependency_overrides[get_enrichment_service] = lambda: svc
    app.dependency_overrides[get_principal_with_tenant] = _principal
    return app


def test_create_annotation_returns_201_and_calls_service() -> None:
    subject_id = uuid.uuid4()
    row = _annotation(subject_id=subject_id)
    svc = MagicMock()
    svc.add_annotation = AsyncMock(return_value=row)
    client = TestClient(_build_app(svc))

    res = client.post(
        "/enrichment/annotations",
        json={
            "subject_type": "person",
            "subject_id": str(subject_id),
            "key": "consult_notes",
            "value": {"text": "Prefers morning slots"},
            "source": "ui",
        },
    )

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["id"] == str(row.id)
    assert body["subject_id"] == str(subject_id)
    assert body["key"] == "consult_notes"
    assert body["source"] == "ui"

    svc.add_annotation.assert_awaited_once()
    args = svc.add_annotation.await_args.args
    assert args[0] == _TENANT_ID
    assert svc.add_annotation.await_args.kwargs["principal"] == _principal()


def test_create_annotation_rejects_bad_source_at_dto() -> None:
    svc = MagicMock()
    svc.add_annotation = AsyncMock()
    client = TestClient(_build_app(svc))

    res = client.post(
        "/enrichment/annotations",
        json={
            "subject_type": "person",
            "subject_id": str(uuid.uuid4()),
            "key": "x",
            "value": {},
            "source": "webhook",
        },
    )

    assert res.status_code == 422
    svc.add_annotation.assert_not_awaited()


def test_list_annotations_returns_items_and_calls_service() -> None:
    subject_id = uuid.uuid4()
    rows = [_annotation(subject_id=subject_id, key="consult_notes")]
    svc = MagicMock()
    svc.list_for_subject = AsyncMock(return_value=rows)
    client = TestClient(_build_app(svc))

    res = client.get(
        "/enrichment/annotations",
        params={"subject_type": "person", "subject_id": str(subject_id)},
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["subject_id"] == str(subject_id)
    svc.list_for_subject.assert_awaited_once_with(_TENANT_ID, "person", subject_id)
