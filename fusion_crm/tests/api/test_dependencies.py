"""Tests for shared FastAPI dependency wiring."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from apps.api import dependencies
from apps.api.dependencies import get_principal
from packages.core.security import Principal, Role


def _principal_app(*, state_principal: Principal | None = None) -> FastAPI:
    app = FastAPI()

    if state_principal is not None:

        @app.middleware("http")
        async def _set_principal(request: Request, call_next):
            request.state.principal = state_principal
            return await call_next(request)

    @app.get("/principal")
    def _read_principal(principal: Principal = Depends(get_principal)):
        return {
            "email": principal.email,
            "roles": sorted(str(role) for role in principal.roles),
            "auth_source": principal.context.get("auth_source"),
        }

    return app


def test_get_principal_defaults_to_anonymous_without_local_cookie(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: SimpleNamespace(is_production=False),
    )

    client = TestClient(_principal_app())
    res = client.get("/principal")

    assert res.status_code == 200
    assert res.json() == {
        "email": None,
        "roles": [Role.GUEST],
        "auth_source": None,
    }


def test_get_principal_uses_local_staff_session_cookie_in_non_production(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: SimpleNamespace(is_production=False),
    )

    client = TestClient(_principal_app())
    client.cookies.set("staff_session", "mock-session")
    res = client.get("/principal")

    assert res.status_code == 200
    assert res.json() == {
        "email": "demo@fusion-dental.local",
        "roles": [Role.ADMIN],
        "auth_source": "local_dev_staff_session",
    }


def test_get_principal_uses_iap_header_as_admin_principal() -> None:
    client = TestClient(_principal_app())
    res = client.get(
        "/principal",
        headers={
            "x-goog-authenticated-user-email": "accounts.google.com:eduard@example.com"
        },
    )

    assert res.status_code == 200
    assert res.json() == {
        "email": "eduard@example.com",
        "roles": [Role.ADMIN],
        "auth_source": "google_iap",
    }


def test_get_principal_ignores_local_staff_session_cookie_in_production(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: SimpleNamespace(is_production=True),
    )

    client = TestClient(_principal_app())
    client.cookies.set("staff_session", "mock-session")
    res = client.get("/principal")

    assert res.status_code == 200
    assert res.json() == {
        "email": None,
        "roles": [Role.GUEST],
        "auth_source": None,
    }


def test_get_principal_prefers_state_principal_over_iap_and_local_cookie(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: SimpleNamespace(is_production=False),
    )
    principal = Principal(
        id=uuid.uuid4(),
        email="iap@example.com",
        roles=frozenset({Role.SYSTEM}),
        context={"auth_source": "iap"},
    )

    client = TestClient(_principal_app(state_principal=principal))
    client.cookies.set("staff_session", "mock-session")
    res = client.get(
        "/principal",
        headers={
            "x-goog-authenticated-user-email": "accounts.google.com:eduard@example.com"
        },
    )

    assert res.status_code == 200
    assert res.json() == {
        "email": "iap@example.com",
        "roles": [Role.SYSTEM],
        "auth_source": "iap",
    }
