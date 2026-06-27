"""HTTP contract tests for the Messenger directory routes (ENG-564).

Handler-level coverage: the service is mocked and the principal overridden, so
these assert the thin wiring (path/query ↔ service ↔ DTO, status codes, tenant
resolution) and the three error envelopes the directory can surface:

* no credential configured → 404 ``no_credential`` (resolver propagation);
* invalid credential (e.g. bad admin_token) → 422 ``invalid_chat_credential``;
* token rejected / Mattermost unreachable → 502 ``integration_error``.

No Mattermost token is ever asserted in a response because none is ever
returned; the service strips everything to a token-free envelope.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import (
    get_messenger_directory_service,
    get_principal_with_tenant,
)
from apps.api.middleware import platform_error_handler
from apps.api.routers import messenger as messenger_router
from packages.core.exceptions import IntegrationError, PlatformError
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.integrations.chat.directory_schemas import (
    MessengerChannelOut,
    MessengerTeamOut,
)
from packages.integrations.chat.resolver import InvalidChatCredentialError
from packages.tenant.credential_service import NoCredentialError

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_ACTOR_ID = uuid.uuid4()


def _principal() -> Principal:
    return Principal(
        id=_ACTOR_ID,
        email="staff@example.com",
        tenant_id=_TENANT_ID,
        roles=frozenset({Role.ADMIN}),
    )


def _build_app(svc: object) -> FastAPI:
    app = FastAPI()
    app.include_router(messenger_router.router)
    app.add_exception_handler(PlatformError, platform_error_handler)  # type: ignore[arg-type]
    app.dependency_overrides[get_messenger_directory_service] = lambda: svc
    app.dependency_overrides[get_principal_with_tenant] = _principal
    return app


def test_list_teams_returns_items() -> None:
    svc = AsyncMock()
    svc.list_teams.return_value = [
        MessengerTeamOut(
            id="t1",
            name="marketing",
            display_name="Marketing",
            url="https://chat.example.com/marketing",
        ),
    ]
    client = TestClient(_build_app(svc))

    resp = client.get("/messenger/teams")

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["id"] == "t1"
    assert body[0]["url"] == "https://chat.example.com/marketing"
    svc.list_teams.assert_awaited_once_with(_TENANT_ID)


def test_list_channels_returns_items() -> None:
    svc = AsyncMock()
    svc.list_channels.return_value = [
        MessengerChannelOut(
            id="c1",
            name="leads",
            display_name="Leads",
            type="O",
            purpose="incoming",
        ),
    ]
    client = TestClient(_build_app(svc))

    resp = client.get("/messenger/teams/t1/channels")

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["type"] == "O"
    svc.list_channels.assert_awaited_once_with(_TENANT_ID, "t1")


def test_list_channels_empty_returns_200_empty() -> None:
    svc = AsyncMock()
    svc.list_channels.return_value = []
    client = TestClient(_build_app(svc))

    resp = client.get("/messenger/teams/t1/channels")

    assert resp.status_code == 200
    assert resp.json() == []


def test_no_credential_returns_404_envelope() -> None:
    svc = AsyncMock()
    svc.list_teams.side_effect = NoCredentialError(
        "no active mattermost credential",
        details={"provider_kind": "mattermost"},
    )
    client = TestClient(_build_app(svc))

    resp = client.get("/messenger/teams")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "no_credential"


def test_invalid_credential_returns_422_envelope() -> None:
    svc = AsyncMock()
    svc.list_teams.side_effect = InvalidChatCredentialError(
        "mattermost credential has invalid admin_token",
        details={"tenant_id": str(_TENANT_ID)},
    )
    client = TestClient(_build_app(svc))

    resp = client.get("/messenger/teams")

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_chat_credential"


def test_unreachable_returns_502_envelope_without_token() -> None:
    svc = AsyncMock()
    svc.list_teams.side_effect = IntegrationError(
        "Mattermost directory unavailable",
        details={"tenant_id": str(_TENANT_ID)},
    )
    client = TestClient(_build_app(svc))

    resp = client.get("/messenger/teams")

    assert resp.status_code == 502
    error = resp.json()["error"]
    assert error["code"] == "integration_error"
    assert error["message"] == "Mattermost directory unavailable"
    # The envelope carries no token / payload.
    assert "token" not in str(error).lower()
