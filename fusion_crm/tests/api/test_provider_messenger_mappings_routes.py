"""HTTP contract tests for the provider → Mattermost username routes (ENG-546).

Handler-level coverage: the service is mocked and the principal overridden, so
these assert the thin wiring (path/body ↔ service ↔ DTO, status codes, tenant
resolution, error envelope) without a DB. Live persistence + the re-map
invariant live in ``tests/actor/test_provider_messenger_mapping.py``.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import get_actor_service, get_principal_with_tenant
from apps.api.middleware import platform_error_handler
from apps.api.routers import provider_messenger_mappings as mappings_router
from packages.actor.schemas import ProviderMessengerMappingOut
from packages.core.exceptions import NotFoundError, PlatformError, ValidationError
from packages.core.security import Principal, Role
from packages.core.types import TenantId

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_ACTOR_ID = uuid.uuid4()


def _principal() -> Principal:
    return Principal(
        id=_ACTOR_ID,
        email="staff@example.com",
        tenant_id=_TENANT_ID,
        roles=frozenset({Role.ADMIN}),
    )


def _mapping(
    *,
    carestack_provider_id: str = "1",
    username: str | None = "drantipov",
) -> ProviderMessengerMappingOut:
    return ProviderMessengerMappingOut(
        actor_id=uuid.uuid4(),
        actor_name="Dr Antipov",
        carestack_provider_id=carestack_provider_id,
        mattermost_username=username,
    )


def _build_app(svc: object) -> FastAPI:
    app = FastAPI()
    app.include_router(mappings_router.router)
    app.add_exception_handler(PlatformError, platform_error_handler)  # type: ignore[arg-type]
    app.dependency_overrides[get_actor_service] = lambda: svc
    app.dependency_overrides[get_principal_with_tenant] = _principal
    return app


def test_list_returns_items() -> None:
    svc = AsyncMock()
    svc.list_provider_messenger_mappings.return_value = [
        _mapping(carestack_provider_id="1", username="drantipov"),
        _mapping(carestack_provider_id="2", username=None),
    ]
    client = TestClient(_build_app(svc))

    resp = client.get("/actor/provider-messenger-mappings")

    assert resp.status_code == 200
    body = resp.json()
    assert [i["carestack_provider_id"] for i in body["items"]] == ["1", "2"]
    assert body["items"][1]["mattermost_username"] is None
    svc.list_provider_messenger_mappings.assert_awaited_once_with(_TENANT_ID)


def test_put_sets_username_strips_at_via_service() -> None:
    svc = AsyncMock()
    svc.set_provider_messenger_username.return_value = _mapping(username="drantipov")
    client = TestClient(_build_app(svc))

    resp = client.put(
        "/actor/provider-messenger-mappings/1",
        json={"mattermost_username": "@drantipov"},
    )

    assert resp.status_code == 200
    assert resp.json()["mattermost_username"] == "drantipov"
    svc.set_provider_messenger_username.assert_awaited_once_with(
        _TENANT_ID, "1", "@drantipov"
    )


def test_put_unknown_provider_returns_404_envelope() -> None:
    svc = AsyncMock()
    svc.set_provider_messenger_username.side_effect = NotFoundError(
        "no provider actor for carestack_provider_id",
        details={"carestack_provider_id": "999"},
    )
    client = TestClient(_build_app(svc))

    resp = client.put(
        "/actor/provider-messenger-mappings/999",
        json={"mattermost_username": "ghost"},
    )

    assert resp.status_code == 404
    error = resp.json()["error"]
    assert error["code"] == "not_found"
    assert error["details"]["carestack_provider_id"] == "999"


def test_put_conflicting_username_returns_validation_envelope() -> None:
    """A duplicate-handle conflict from the service must surface as a clean 4xx
    error envelope, not a 500."""
    svc = AsyncMock()
    svc.set_provider_messenger_username.side_effect = ValidationError(
        "identifier already attached to a different actor",
        details={
            "kind": "mattermost_username",
            "value": "drantipov",
            "existing_actor_id": str(uuid.uuid4()),
            "requested_actor_id": str(uuid.uuid4()),
        },
    )
    client = TestClient(_build_app(svc))

    resp = client.put(
        "/actor/provider-messenger-mappings/2",
        json={"mattermost_username": "drantipov"},
    )

    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"]
    assert error["details"]["value"] == "drantipov"
