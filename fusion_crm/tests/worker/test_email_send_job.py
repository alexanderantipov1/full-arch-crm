"""Smoke + unit tests for the outreach dispatcher (ENG-132).

The full ``drain_outbound_queue`` lifecycle is exercised by the
integration suite (which spins up a real PG + Redis). Here we cover
the deterministic helpers and the empty-queue happy path that
verifies the cron entry-point is wireable.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from apps.worker.jobs.email_send import (
    BATCH_SIZE,
    MAX_RATE_LIMIT_RETRIES,
    MAX_TRANSIENT_RETRIES,
    _backoff_seconds,
    _system_principal,
    _worker_id,
    drain_outbound_queue,
)
from packages.core.security import Role
from packages.core.types import TenantId


def test_worker_id_is_stable_within_process() -> None:
    """``_worker_id`` returns a host/pid string that is stable for
    one process and present on every queue row's ``locked_by``."""
    wid_a = _worker_id()
    wid_b = _worker_id()
    assert wid_a == wid_b
    assert "/" in wid_a  # host/pid


def test_backoff_seconds_grows_with_attempts_and_caps() -> None:
    """Exponential growth, jitter within ±20%, capped at 1h."""
    # attempt 0 → ~30s base
    s0 = _backoff_seconds(0)
    assert 20 <= s0 <= 40  # 30s ±20%

    # attempt 5 → would be 30 * 32 = 960s without cap → 960 ±20%
    s5 = _backoff_seconds(5)
    assert s5 > s0

    # attempt 99 → cap kicks in (3600s)
    s99 = _backoff_seconds(99)
    assert 3600 * 0.8 <= s99 <= 3600 * 1.2


def test_system_principal_carries_role_system() -> None:
    """The worker writes audit under a SYSTEM principal — required so
    audit rows do not slip in under ANONYMOUS (which has no tenant)."""
    tenant_id = TenantId(uuid.uuid4())
    principal = _system_principal(tenant_id)
    assert principal.tenant_id == tenant_id
    assert Role.SYSTEM in principal.roles
    assert principal.email is None


def test_retry_caps_are_set() -> None:
    """Sanity: the rate-limit / transient caps are non-zero."""
    assert MAX_RATE_LIMIT_RETRIES >= 1
    assert MAX_TRANSIENT_RETRIES >= 1
    assert BATCH_SIZE >= 1


@pytest.mark.asyncio
async def test_drain_outbound_queue_empty_returns_zero_summary() -> None:
    """Smoke: drain with an empty queue returns the zero summary
    without opening a Redis connection or touching HTTP."""

    # Patch ``async_session`` to yield a context manager whose
    # ``OutboundQueueRepository.lock_batch`` returns an empty list.
    class _FakeSession:
        async def __aenter__(self) -> _FakeSession:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    def _fake_session_factory() -> _FakeSession:
        return _FakeSession()

    with patch("apps.worker.jobs.email_send.async_session", _fake_session_factory), patch(
        "apps.worker.jobs.email_send.OutboundQueueRepository"
    ) as repo_cls:
        repo_cls.return_value = repo_cls
        repo_cls.lock_batch = AsyncMock(return_value=[])

        summary = await drain_outbound_queue({})
        assert summary == {
            "sent": 0,
            "failed": 0,
            "deferred": 0,
            "suppressed": 0,
        }
