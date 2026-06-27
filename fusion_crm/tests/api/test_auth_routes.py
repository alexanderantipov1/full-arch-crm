"""HTTP-level tests for staff auth routes."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.routers import auth as auth_router


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router.router)
    return app


def test_login_sets_local_staff_session_cookie_in_non_production(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        auth_router,
        "get_settings",
        lambda: SimpleNamespace(is_production=False),
    )

    client = TestClient(_build_app())
    res = client.post(
        "/auth/login",
        json={"email": "demo@example.com", "password": "local"},
    )

    assert res.status_code == 200
    assert res.json()["session"]["email"] == "demo@example.com"
    cookie = res.headers["set-cookie"]
    assert "staff_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Max-Age=28800" in cookie


def test_login_does_not_set_staff_session_cookie_in_production(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        auth_router,
        "get_settings",
        lambda: SimpleNamespace(is_production=True),
    )

    client = TestClient(_build_app())
    res = client.post(
        "/auth/login",
        json={"email": "demo@example.com", "password": "local"},
    )

    assert res.status_code == 200
    assert "set-cookie" not in res.headers
