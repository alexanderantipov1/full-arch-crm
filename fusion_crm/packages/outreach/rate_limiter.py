"""Per-mailbox rate limiter — Redis sliding-window counter.

Per ADR-0004 §"Rate limit" and ENG-132 spec.

Each ``(credential_id, window_seconds)`` pair has a Redis counter
keyed ``outreach:rl:{credential_id}:{window_seconds}``. The limiter:

1. ``INCR`` the counter for every send attempt.
2. ``EXPIRE`` the key to ``window_seconds`` on first creation
   (set NX so the TTL is anchored to the first write of a new
   window, not extended on every hit).
3. If the new counter value exceeds the cap, the caller is told
   ``allowed=False`` and given a ``retry_after_seconds`` equal to
   the current TTL.

This is a fixed-window approximation (not a true sliding window),
which is appropriate at our Stage 1 scale and matches the burst
shape of operator-account mail sends. A true sliding window would
require a Redis Lua script (cheap but worth the complexity only
when we hit a real fairness problem).

Per-tenant overrides flow in as a constructor arg
(``limits_by_provider``); the service layer reads the
``outreach.rate_limits.<provider_kind>`` setting from
``tenant.setting`` and constructs the limiter once per drain pass.

Provider defaults (ADR-0004 §"Rate limit"):

- Gmail Workspace: 2 000 sends / day (the Workspace-account cap
  per Google's published limits — conservative; some accounts can
  push higher).
- Microsoft 365: 10 000 sends / day AND 30 sends / minute.

Hard rules:

- This limiter operates on ``credential_id`` (the mailbox), not on
  ``tenant_id``. Two tenants sharing a mailbox would share a
  bucket, but our credential scheme is one mailbox per tenant by
  construction (see `packages/tenant/CLAUDE.md` multi-mailbox
  notes), so this is the right grain.
- The counter is incremented BEFORE the network call. If the send
  later fails, we do NOT decrement — the cap models "API calls
  issued", not "messages successfully sent". Drift between the
  two is bounded by retry behaviour.
- Redis unavailability is fail-open: ``check_and_consume`` raises
  a ``RateLimiterUnavailable`` and the worker treats the row as
  pending with a short backoff (the durable queue is in Postgres
  per ADR-0004 decision #1, so a Redis blip cannot lose work).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from packages.core.exceptions import IntegrationError, ValidationError
from packages.core.logging import get_logger

log = get_logger("outreach.rate_limiter")

# Provider → list of (window_seconds, max_count). Multiple windows AND.
# Order is informational; the limiter checks every window before
# allowing a send.
RATE_LIMITS: dict[str, list[tuple[int, int]]] = {
    "google_workspace": [
        (86_400, 2_000),
    ],
    "microsoft_365": [
        (86_400, 10_000),
        (60, 30),
    ],
}

_REDIS_NAMESPACE = "outreach:rl"


class RateLimiterUnavailable(IntegrationError):
    """Redis itself is unreachable or returned an error.

    Distinct from the rate-limit ``denied`` path — denied is an
    expected outcome of policy; unavailable is an infrastructure
    failure the caller should retry quickly.
    """

    code = "rate_limiter_unavailable"
    http_status = 503


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    """Outcome of one ``check_and_consume`` call.

    ``allowed=True`` means the counter was incremented and the
    caller may proceed. ``allowed=False`` means the cap is reached;
    ``retry_after_seconds`` is the TTL on the offending window key
    (i.e. when the next window starts). The denied path does NOT
    increment the counter past the cap — once we know we're over,
    we leave the bucket alone so a brief surge doesn't extend the
    cooldown.
    """

    allowed: bool
    retry_after_seconds: int = 0
    window_seconds: int | None = None  # which window pushed us over
    counter_value: int | None = None
    cap: int | None = None


class RateLimiter:
    """Redis-backed sliding-window-ish rate limiter per credential.

    The Redis client is injected so unit tests can pass a fake. A
    real call site builds one via the worker's redis-pool helper.

    ``limits_by_provider`` defaults to ``RATE_LIMITS``; pass a
    superset / override dict when tenant settings carry a custom
    schedule. The dict shape is identical:
    ``{provider_kind: [(window_seconds, max_count), ...]}``.
    """

    def __init__(
        self,
        redis: Any,
        *,
        limits_by_provider: dict[str, list[tuple[int, int]]] | None = None,
    ) -> None:
        self._redis = redis
        self._limits = limits_by_provider if limits_by_provider is not None else RATE_LIMITS

    async def check_and_consume(
        self,
        credential_id: UUID,
        provider_kind: str,
    ) -> RateLimitDecision:
        """Try to consume one send against ``credential_id``.

        Returns ``RateLimitDecision(allowed=True)`` when the send may
        proceed (and the counter has been incremented), or
        ``RateLimitDecision(allowed=False, retry_after_seconds=N)``
        when any configured window is at its cap.

        Raises ``RateLimiterUnavailable`` on Redis errors — the caller
        (the dispatcher worker) treats this as "back off briefly,
        the queue row stays pending".
        """
        windows = self._limits.get(provider_kind)
        if not windows:
            # Unknown provider — no limits to enforce. The send service
            # filters callers to email-OAuth providers, so this branch
            # is defensive against future additions.
            return RateLimitDecision(allowed=True)

        # Phase 1: probe every window without incrementing. If any
        # window is at-or-over the cap, deny without consuming. This
        # is the right semantics — we do not want a deny call to push
        # the counter further past the cap.
        for window_seconds, cap in windows:
            key = self._key(credential_id, window_seconds)
            try:
                current_raw = await self._redis.get(key)
            except Exception as exc:  # noqa: BLE001 — Redis failure mode
                raise RateLimiterUnavailable(
                    "rate-limiter probe failed",
                    details={"key": key, "error": str(exc)},
                ) from exc
            current = _coerce_int(current_raw)
            if current >= cap:
                ttl = await self._safe_ttl(key, window_seconds)
                log.info(
                    "outreach.rate_limit.denied",
                    credential_id=str(credential_id),
                    provider_kind=provider_kind,
                    window_seconds=window_seconds,
                    counter=current,
                    cap=cap,
                    retry_after_seconds=ttl,
                )
                return RateLimitDecision(
                    allowed=False,
                    retry_after_seconds=ttl,
                    window_seconds=window_seconds,
                    counter_value=current,
                    cap=cap,
                )

        # Phase 2: every window is under cap. Increment each counter
        # and anchor its TTL. Anchoring is conditional (NX on EXPIRE)
        # so we do not extend a running window every hit.
        for window_seconds, cap in windows:
            key = self._key(credential_id, window_seconds)
            try:
                new_value = await self._redis.incr(key)
                # Set TTL only the first time the key was created.
                # Redis ``EXPIRE key seconds NX`` is the right verb;
                # older clients fall back to a TTL check + EXPIRE.
                try:
                    await self._redis.expire(key, window_seconds, nx=True)
                except TypeError:
                    # The installed redis-py may not expose ``nx``;
                    # fall back to TTL probe before setting.
                    ttl = await self._redis.ttl(key)
                    if ttl is None or int(ttl) < 0:
                        await self._redis.expire(key, window_seconds)
            except Exception as exc:  # noqa: BLE001
                raise RateLimiterUnavailable(
                    "rate-limiter consume failed",
                    details={"key": key, "error": str(exc)},
                ) from exc

            # If the increment pushed us over the cap (very unlikely
            # given the probe above, but possible under racing
            # workers), surface a deny so the caller can defer the
            # send. We accept that the counter is now cap+1; the
            # over-budget delta is bounded by worker concurrency.
            if int(new_value) > cap:
                ttl = await self._safe_ttl(key, window_seconds)
                log.info(
                    "outreach.rate_limit.race_denied",
                    credential_id=str(credential_id),
                    provider_kind=provider_kind,
                    window_seconds=window_seconds,
                    counter=int(new_value),
                    cap=cap,
                    retry_after_seconds=ttl,
                )
                return RateLimitDecision(
                    allowed=False,
                    retry_after_seconds=ttl,
                    window_seconds=window_seconds,
                    counter_value=int(new_value),
                    cap=cap,
                )

        return RateLimitDecision(allowed=True)

    @staticmethod
    def _key(credential_id: UUID, window_seconds: int) -> str:
        return f"{_REDIS_NAMESPACE}:{credential_id}:{window_seconds}"

    async def _safe_ttl(self, key: str, fallback: int) -> int:
        """Return the TTL of ``key`` in seconds, falling back if unset."""
        try:
            ttl = await self._redis.ttl(key)
        except Exception:  # noqa: BLE001
            return fallback
        ttl_int = cast(int, _coerce_int(ttl, default=fallback))
        if ttl_int < 0:
            return fallback
        return ttl_int


def parse_tenant_override(
    raw: object,
    *,
    provider_kind: str,
) -> list[tuple[int, int]]:
    """Validate a tenant.setting override into the limiter shape.

    The setting value is expected to be either:

    - a list of ``[window_seconds, max_count]`` pairs, OR
    - a dict with key ``windows`` carrying that list

    Anything else raises ``ValidationError`` (the operator UI should
    have caught it; defending here keeps a broken setting from taking
    out the worker).
    """
    if isinstance(raw, dict):
        raw = raw.get("windows", raw)
    if not isinstance(raw, list):
        raise ValidationError(
            "rate-limit override must be a list of [window_seconds, max_count] pairs",
            details={"provider_kind": provider_kind},
        )
    parsed: list[tuple[int, int]] = []
    for entry in raw:
        if (
            isinstance(entry, (list, tuple))
            and len(entry) == 2
            and isinstance(entry[0], int)
            and isinstance(entry[1], int)
            and entry[0] > 0
            and entry[1] > 0
        ):
            parsed.append((int(entry[0]), int(entry[1])))
            continue
        raise ValidationError(
            "rate-limit override entry must be [window_seconds, max_count] with positive ints",
            details={"provider_kind": provider_kind, "entry": str(entry)},
        )
    if not parsed:
        raise ValidationError(
            "rate-limit override resolved to an empty list",
            details={"provider_kind": provider_kind},
        )
    return parsed


def _coerce_int(value: object, *, default: int = 0) -> int:
    """Best-effort int coercion for Redis return values."""
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, bytes):
        try:
            return int(value.decode("ascii"))
        except (UnicodeDecodeError, ValueError):
            return default
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


__all__ = [
    "RATE_LIMITS",
    "RateLimitDecision",
    "RateLimiter",
    "RateLimiterUnavailable",
    "parse_tenant_override",
]
