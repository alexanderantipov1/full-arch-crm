"""Unit tests for the Mattermost signed-inbound helper (ENG-438, Block E).

Covers token verification (constant-time), payload parsing, tenant
resolution by token match, the health-check fast path, and the security
invariant that the token is never logged.

No database: ``resolve_tenant_from_token`` is driven through a stub
credential service that returns ``(tenant_id, payload)`` rows.
"""

from __future__ import annotations

import inspect
import uuid

from packages.core.types import TenantId
from packages.integrations.chat import inbound as inbound_mod
from packages.integrations.chat.inbound import (
    EVENT_TYPE_ACTION,
    EVENT_TYPE_WEBHOOK,
    is_health_check,
    parse_action,
    parse_webhook,
    resolve_tenant_from_token,
    tokens_match,
)


class _StubCredentials:
    """Stand-in for IntegrationCredentialService cross-tenant read."""

    def __init__(self, rows: list[tuple[TenantId, dict[str, object]]]) -> None:
        self._rows = rows
        self.calls: list[tuple[str, str]] = []

    async def list_active_payloads_across_tenants(
        self, provider_kind: str, credential_kind: str
    ) -> list[tuple[TenantId, dict[str, object]]]:
        self.calls.append((provider_kind, credential_kind))
        return self._rows


def test_tokens_match_uses_constant_time(monkeypatch) -> None:
    # Assert the helper routes through hmac.compare_digest (constant-time).
    seen: dict[str, tuple[str, str]] = {}
    import hmac as hmac_mod

    real = hmac_mod.compare_digest

    def _spy(a, b):  # noqa: ANN001
        seen["args"] = (a, b)
        return real(a, b)

    monkeypatch.setattr(inbound_mod.hmac, "compare_digest", _spy)

    assert tokens_match("secret-token", "secret-token") is True
    assert seen["args"] == ("secret-token", "secret-token")
    assert tokens_match("secret-token", "other") is False


def test_tokens_match_fails_closed_on_empty() -> None:
    assert tokens_match("", "stored") is False
    assert tokens_match("presented", "") is False
    assert tokens_match("", "") is False


def test_parse_webhook_extracts_token_and_post_id() -> None:
    parsed = parse_webhook(
        {
            "token": "tok-abc",
            "channel_id": "chan1",
            "user_id": "user1",
            "post_id": "post1",
            "text": "hello",
        }
    )
    assert parsed.event_type == EVENT_TYPE_WEBHOOK
    assert parsed.token == "tok-abc"
    assert parsed.external_id == "post1"
    assert parsed.user_id == "user1"
    assert parsed.payload["text"] == "hello"


def test_parse_action_reads_token_from_context() -> None:
    parsed = parse_action(
        {
            "trigger_id": "trig1",
            "user_id": "user2",
            "context": {"token": "tok-ctx", "action": "approve"},
        }
    )
    assert parsed.event_type == EVENT_TYPE_ACTION
    assert parsed.token == "tok-ctx"
    assert parsed.external_id == "trig1"
    assert parsed.user_id == "user2"


def test_parse_action_user_id_falls_back_to_context() -> None:
    parsed = parse_action(
        {"trigger_id": "t", "context": {"token": "x", "user_id": "ctx-user"}}
    )
    assert parsed.user_id == "ctx-user"


def test_is_health_check_for_empty_body() -> None:
    assert is_health_check({}) is True


def test_is_health_check_false_when_token_present() -> None:
    assert is_health_check({"token": "tok"}) is False


def test_is_health_check_false_when_ids_present() -> None:
    assert is_health_check({"post_id": "p", "text": "hi"}) is False


async def test_resolve_tenant_matches_correct_token() -> None:
    tenant_a = TenantId(uuid.uuid4())
    tenant_b = TenantId(uuid.uuid4())
    creds = _StubCredentials(
        [
            (tenant_a, {"token": "token-a"}),
            (tenant_b, {"token": "token-b"}),
        ]
    )

    resolved = await resolve_tenant_from_token(creds, "token-b")
    assert resolved == tenant_b
    assert creds.calls == [("mattermost", "webhook_secret")]


async def test_resolve_tenant_ambiguous_shared_token_returns_none() -> None:
    # Two DISTINCT tenants storing the SAME token → ambiguous → fail closed.
    tenant_a = TenantId(uuid.uuid4())
    tenant_b = TenantId(uuid.uuid4())
    creds = _StubCredentials(
        [
            (tenant_a, {"token": "shared-token"}),
            (tenant_b, {"token": "shared-token"}),
        ]
    )
    assert await resolve_tenant_from_token(creds, "shared-token") is None


async def test_resolve_tenant_same_tenant_duplicate_rows_resolves() -> None:
    # Same tenant with two active credential rows carrying the same token is
    # NOT ambiguous (one distinct tenant) → resolve it.
    tenant_a = TenantId(uuid.uuid4())
    creds = _StubCredentials(
        [
            (tenant_a, {"token": "tok"}),
            (tenant_a, {"token": "tok"}),
        ]
    )
    assert await resolve_tenant_from_token(creds, "tok") == tenant_a


async def test_resolve_tenant_scans_all_credentials_no_early_return(
    monkeypatch,
) -> None:
    # Defence: assert EVERY credential is compared (no early return). The
    # match is in row 1, but rows 2 and 3 must still be scanned.
    tenant_a = TenantId(uuid.uuid4())
    tenant_b = TenantId(uuid.uuid4())
    tenant_c = TenantId(uuid.uuid4())
    creds = _StubCredentials(
        [
            (tenant_a, {"token": "token-a"}),
            (tenant_b, {"token": "token-b"}),
            (tenant_c, {"token": "token-c"}),
        ]
    )

    compared: list[tuple[str, str]] = []
    real = inbound_mod.tokens_match

    def _spy(presented, stored):  # noqa: ANN001
        compared.append((presented, stored))
        return real(presented, stored)

    monkeypatch.setattr(inbound_mod, "tokens_match", _spy)

    resolved = await resolve_tenant_from_token(creds, "token-a")
    assert resolved == tenant_a
    # All three stored tokens were compared — no short-circuit on first match.
    assert [stored for _, stored in compared] == ["token-a", "token-b", "token-c"]


async def test_resolve_tenant_returns_none_for_wrong_token() -> None:
    tenant_a = TenantId(uuid.uuid4())
    creds = _StubCredentials([(tenant_a, {"token": "token-a"})])
    assert await resolve_tenant_from_token(creds, "nope") is None


async def test_resolve_tenant_returns_none_for_absent_token() -> None:
    creds = _StubCredentials([(TenantId(uuid.uuid4()), {"token": "token-a"})])
    # No DB read attempted when the token is missing/empty.
    assert await resolve_tenant_from_token(creds, None) is None
    assert await resolve_tenant_from_token(creds, "") is None
    assert creds.calls == []


def test_verify_helper_does_not_log_token() -> None:
    # Security invariant: the verification + resolution source must never
    # pass the token to a logger. Assert no ``log`` call references the
    # token variable in the resolver/verify source.
    src = inspect.getsource(resolve_tenant_from_token)
    src += inspect.getsource(tokens_match)
    # No logger invocation at all in the verify/resolve path.
    assert "log." not in src
    assert "get_logger" not in src
    # The whole helper module never imports a logger — defence in depth.
    module_src = inspect.getsource(inbound_mod)
    assert "get_logger" not in module_src
    assert "log." not in module_src
