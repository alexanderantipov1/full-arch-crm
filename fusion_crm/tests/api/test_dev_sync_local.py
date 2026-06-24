"""HTTP-level tests for the ENG-330 local-dev sync router.

We never touch real providers: ``run_local_sync`` is stubbed at the dev
router module. We assert:

- production gating: every route 404s when ``is_production`` is true,
- ``POST`` returns ``started`` (202) then ``already_running`` (200)
  while a drain is in flight,
- ``GET`` reflects running / last_summary state.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.middleware import RequestContextMiddleware, platform_error_handler
from apps.api.routers import dev as dev_router
from packages.core.exceptions import PlatformError


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(PlatformError, platform_error_handler)  # type: ignore[arg-type]
    app.include_router(dev_router.router)
    return app


def _set_env(monkeypatch: pytest.MonkeyPatch, *, production: bool) -> None:
    monkeypatch.setattr(
        dev_router,
        "get_settings",
        lambda: SimpleNamespace(is_production=production),
    )


@pytest.fixture(autouse=True)
def _reset_state() -> Any:
    # Each test starts from a clean module-level drain state.
    dev_router._state.task = None
    dev_router._state.last_summary = None
    dev_router._state.last_finished_at = None
    yield
    dev_router._state.task = None


def test_post_404_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch, production=True)
    app = _build_app()
    with TestClient(app) as client:
        res = client.post("/dev/sync-local")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


def test_get_404_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch, production=True)
    app = _build_app()
    with TestClient(app) as client:
        res = client.get("/dev/sync-local")
    assert res.status_code == 404


def test_post_starts_and_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch, production=False)

    summary = {"total_imported": 3, "elapsed_seconds": 0.0, "caught_up": True}

    async def _fast_sync(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return summary

    monkeypatch.setattr(dev_router, "run_local_sync", _fast_sync)

    app = _build_app()
    with TestClient(app) as client:
        first = client.post("/dev/sync-local")
        assert first.status_code == 202
        assert first.json() == {"status": "started"}

        # The drain returns immediately; poll GET until the done-callback
        # has stored the summary and cleared the running flag.
        body: dict[str, Any] = {}
        for _ in range(50):
            body = client.get("/dev/sync-local").json()
            if not body["running"]:
                break
        assert body["running"] is False
        assert body["last_summary"] == summary
        assert body["last_finished_at"] is not None


def test_post_already_running_short_circuits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch, production=False)

    started = 0

    async def _sync(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"total_imported": 0, "elapsed_seconds": 0.0, "caught_up": True}

    def _counting_ensure_future(coro: Any) -> Any:
        nonlocal started
        started += 1
        # Close the coroutine we are not going to schedule to avoid a
        # "never awaited" warning, and return a fake un-done task so the
        # module treats the drain as in-flight.
        coro.close()
        return SimpleNamespace(done=lambda: False, add_done_callback=lambda _cb: None)

    monkeypatch.setattr(dev_router, "run_local_sync", _sync)
    monkeypatch.setattr(dev_router.asyncio, "ensure_future", _counting_ensure_future)

    app = _build_app()
    with TestClient(app) as client:
        first = client.post("/dev/sync-local")
        assert first.json() == {"status": "started"}
        # The seeded fake task reports done()==False, so the next POST is
        # short-circuited and run_local_sync is NOT scheduled again.
        second = client.post("/dev/sync-local")
        assert second.status_code == 200
        assert second.json() == {"status": "already_running"}
        # GET reflects the in-flight drain.
        assert client.get("/dev/sync-local").json()["running"] is True

    assert started == 1


def test_post_forwards_deep_and_since(monkeypatch: pytest.MonkeyPatch) -> None:
    """ENG-351: a body ``{deep: true, since: ...}`` forwards into
    ``run_local_sync(deep=..., since=...)``."""
    _set_env(monkeypatch, production=False)

    captured: dict[str, Any] = {}

    async def _sync(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"total_imported": 0, "deep": True, "since": "2026-06-01"}

    monkeypatch.setattr(dev_router, "run_local_sync", _sync)

    app = _build_app()
    with TestClient(app) as client:
        res = client.post(
            "/dev/sync-local", json={"deep": True, "since": "2026-06-01"}
        )
        assert res.status_code == 202
        body: dict[str, Any] = {}
        for _ in range(50):
            body = client.get("/dev/sync-local").json()
            if not body["running"]:
                break
        assert body["running"] is False

    assert captured == {"deep": True, "since": "2026-06-01"}


def test_post_empty_body_runs_fast_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """No body → fast mode: ``deep=False``, ``since=None``."""
    _set_env(monkeypatch, production=False)

    captured: dict[str, Any] = {}

    async def _sync(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"total_imported": 0, "deep": False, "since": None}

    monkeypatch.setattr(dev_router, "run_local_sync", _sync)

    app = _build_app()
    with TestClient(app) as client:
        res = client.post("/dev/sync-local")
        assert res.status_code == 202
        body: dict[str, Any] = {}
        for _ in range(50):
            body = client.get("/dev/sync-local").json()
            if not body["running"]:
                break
        assert body["running"] is False

    assert captured == {"deep": False, "since": None}


def test_get_initial_state_not_running(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch, production=False)
    app = _build_app()
    with TestClient(app) as client:
        res = client.get("/dev/sync-local")
    assert res.status_code == 200
    assert res.json() == {
        "running": False,
        "last_summary": None,
        "last_finished_at": None,
    }
