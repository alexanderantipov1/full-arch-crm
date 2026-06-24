"""Tests for the worker dependency health check."""

from __future__ import annotations

import pytest

from apps.worker import health


async def _ok() -> None:
    return None


async def _fail() -> None:
    raise TimeoutError("timeout")


@pytest.mark.asyncio
async def test_run_checks_reports_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "check_postgres", _ok)
    monkeypatch.setattr(health, "check_redis", _ok)

    result = await health.run_checks()

    assert result == {
        "status": "ok",
        "checks": {"postgres": "ok", "redis": "ok"},
        "errors": {},
    }


@pytest.mark.asyncio
async def test_run_checks_reports_dependency_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(health, "check_postgres", _ok)
    monkeypatch.setattr(health, "check_redis", _fail)

    result = await health.run_checks()

    assert result == {
        "status": "failed",
        "checks": {"postgres": "ok", "redis": "failed"},
        "errors": {"redis": "TimeoutError"},
    }
