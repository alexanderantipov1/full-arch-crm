"""Tests for ``packages.outreach.rate_limiter.RateLimiter``.

A small in-memory fake Redis stands in for the real client. The
fake supports the subset of commands the limiter uses: ``get``,
``incr``, ``expire`` (with ``nx`` kwarg), ``ttl``.

Coverage (ENG-132 spec):

- Under cap → allowed, counter incremented.
- At cap → denied with retry_after.
- Two-window check (Microsoft 365 daily + per-minute): tripping
  EITHER window denies.
- Tenant override is honoured.
- Redis errors map to ``RateLimiterUnavailable``.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from packages.outreach.rate_limiter import (
    RateLimiter,
    RateLimiterUnavailable,
    parse_tenant_override,
)


class FakeRedis:
    """Minimal in-memory shim for the limiter.

    ``expire`` honours ``nx`` (no-op when a TTL is already set). The
    fake does not advance time — we just track stored counters and
    TTLs as the limiter writes them.
    """

    def __init__(self, *, raise_on: set[str] | None = None) -> None:
        self._values: dict[str, int] = {}
        self._ttls: dict[str, int] = {}
        self._raise_on = raise_on or set()

    async def get(self, key: str) -> Any:
        if "get" in self._raise_on:
            raise RuntimeError("boom")
        value = self._values.get(key)
        return None if value is None else str(value).encode()

    async def incr(self, key: str) -> int:
        if "incr" in self._raise_on:
            raise RuntimeError("boom")
        self._values[key] = self._values.get(key, 0) + 1
        return self._values[key]

    async def expire(
        self, key: str, seconds: int, nx: bool = False
    ) -> bool:
        if "expire" in self._raise_on:
            raise RuntimeError("boom")
        if nx and key in self._ttls:
            return False
        self._ttls[key] = seconds
        return True

    async def ttl(self, key: str) -> int:
        if "ttl" in self._raise_on:
            raise RuntimeError("boom")
        return self._ttls.get(key, -1)

    # Helpers for the test (not used by the limiter).
    def seed(self, key: str, value: int, ttl: int = 60) -> None:
        self._values[key] = value
        self._ttls[key] = ttl


@pytest.fixture
def redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def credential_id() -> uuid.UUID:
    return uuid.uuid4()


async def test_under_cap_allowed_and_increments(
    redis: FakeRedis, credential_id: uuid.UUID
) -> None:
    limiter = RateLimiter(redis)
    decision = await limiter.check_and_consume(credential_id, "google_workspace")
    assert decision.allowed is True
    # The Workspace single-window cap is 2 000/day; one consume yields 1.
    key = f"outreach:rl:{credential_id}:86400"
    assert redis._values[key] == 1


async def test_at_cap_denied(
    redis: FakeRedis, credential_id: uuid.UUID
) -> None:
    limiter = RateLimiter(redis)
    # Seed the bucket at the cap.
    key = f"outreach:rl:{credential_id}:86400"
    redis.seed(key, 2_000, ttl=3_600)

    decision = await limiter.check_and_consume(credential_id, "google_workspace")
    assert decision.allowed is False
    assert decision.retry_after_seconds == 3_600
    assert decision.window_seconds == 86_400
    assert decision.cap == 2_000


async def test_two_windows_per_minute_trips(
    redis: FakeRedis, credential_id: uuid.UUID
) -> None:
    """MS Graph has BOTH 10 000/day AND 30/minute. Tripping the minute
    window must deny even when the daily window is far from cap.
    """
    limiter = RateLimiter(redis)
    minute_key = f"outreach:rl:{credential_id}:60"
    redis.seed(minute_key, 30, ttl=30)

    decision = await limiter.check_and_consume(credential_id, "microsoft_365")
    assert decision.allowed is False
    assert decision.window_seconds == 60
    assert decision.retry_after_seconds == 30


async def test_tenant_override_replaces_defaults(
    redis: FakeRedis, credential_id: uuid.UUID
) -> None:
    overrides = {"google_workspace": [(60, 5)]}
    limiter = RateLimiter(redis, limits_by_provider=overrides)

    # Consume 5 — allowed.
    for _ in range(5):
        decision = await limiter.check_and_consume(
            credential_id, "google_workspace"
        )
        assert decision.allowed is True

    # 6th — denied.
    decision = await limiter.check_and_consume(credential_id, "google_workspace")
    assert decision.allowed is False
    assert decision.window_seconds == 60


async def test_unknown_provider_is_allowed_pass_through(
    redis: FakeRedis, credential_id: uuid.UUID
) -> None:
    limiter = RateLimiter(redis)
    decision = await limiter.check_and_consume(credential_id, "salesforce")
    assert decision.allowed is True


async def test_redis_error_raises_unavailable(
    credential_id: uuid.UUID,
) -> None:
    redis = FakeRedis(raise_on={"get"})
    limiter = RateLimiter(redis)
    with pytest.raises(RateLimiterUnavailable):
        await limiter.check_and_consume(credential_id, "google_workspace")


def test_parse_tenant_override_accepts_list_of_pairs() -> None:
    parsed = parse_tenant_override(
        [[60, 30], [86400, 5000]],
        provider_kind="google_workspace",
    )
    assert parsed == [(60, 30), (86400, 5000)]


def test_parse_tenant_override_accepts_windows_dict() -> None:
    parsed = parse_tenant_override(
        {"windows": [[60, 30]]},
        provider_kind="google_workspace",
    )
    assert parsed == [(60, 30)]


def test_parse_tenant_override_rejects_garbage() -> None:
    from packages.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        parse_tenant_override("nope", provider_kind="google_workspace")
    with pytest.raises(ValidationError):
        parse_tenant_override(
            [["x", 30]], provider_kind="google_workspace"
        )
    with pytest.raises(ValidationError):
        parse_tenant_override([[-1, 30]], provider_kind="google_workspace")
