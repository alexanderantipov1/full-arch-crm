"""Unit tests for the Microsoft 365 OAuth client (ENG-131).

Mirrors ``tests/integrations/google_workspace/test_oauth.py``. The
canonical M365 personal-account signal is a ``tid`` claim equal to
the consumer-tenant id; the email-host check is the second guard.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import httpx
import pytest
import respx

from packages.core.config import get_settings
from packages.integrations._oauth_state import (
    OAuthStateInvalid,
    mint_state,
    verify_state,
)
from packages.integrations.microsoft_365 import (
    MicrosoftOAuthClient,
    MicrosoftOAuthError,
    PersonalAccountBlocked,
)
from packages.integrations.microsoft_365.oauth import (
    CONSUMER_TENANT_ID,
    TOKEN_URL,
    _enforce_business_only,
)


@pytest.fixture(autouse=True)
def _settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x@y/z")
    monkeypatch.setenv("REDIS_URL", "redis://x:6379/0")
    monkeypatch.setenv("INTERNAL_CREDENTIAL_TOKEN", "test-token-please-rotate-32chars")
    monkeypatch.setenv("MICROSOFT_OAUTH_CLIENT_ID", "ms-client-id")
    monkeypatch.setenv("MICROSOFT_OAUTH_CLIENT_SECRET", "ms-client-secret")
    get_settings.cache_clear()


def _client(http: httpx.AsyncClient) -> MicrosoftOAuthClient:
    return MicrosoftOAuthClient(
        client_id="ms-client-id",
        client_secret="ms-client-secret",  # noqa: S106 — fixture
        http=http,
    )


# ----------------------------------------------------------------- state CSRF


def test_state_csrf_roundtrip_microsoft() -> None:
    tenant_id = uuid.uuid4()
    token = mint_state(tenant_id=tenant_id, provider="microsoft_365")
    payload = verify_state(token)
    assert payload.tenant_id == tenant_id
    assert payload.provider == "microsoft_365"


def test_state_csrf_cross_provider_replay_rejected_at_callsite() -> None:
    """A state minted for Google does not pass for Microsoft.

    The state itself verifies (it is a valid token), but the route
    handler compares ``state.provider`` against the path provider —
    the test for that check lives in the route tests; here we
    assert that the payload exposes the provider so the comparison
    can happen.
    """
    google_state = mint_state(
        tenant_id=uuid.uuid4(), provider="google_workspace"
    )
    payload = verify_state(google_state)
    assert payload.provider == "google_workspace"


def test_state_csrf_rejects_truncated() -> None:
    with pytest.raises(OAuthStateInvalid):
        verify_state("not-a-valid-state")


# ----------------------------------------------------------------- gate


def test_personal_msa_blocked_by_consumer_tid() -> None:
    """Microsoft's consumer-tenant tid is the canonical personal MSA marker."""
    claims = {
        "tid": CONSUMER_TENANT_ID,
        "preferred_username": "someone@outlook.com",
        "sub": "1138",
    }
    with pytest.raises(PersonalAccountBlocked) as exc:
        _enforce_business_only(claims)
    assert "Microsoft 365 Business" in exc.value.message


def test_personal_msa_blocked_by_email_host_outlook() -> None:
    """Even with a non-consumer tid, an @outlook.com username blocks."""
    claims = {
        "tid": "11111111-2222-3333-4444-555555555555",
        "preferred_username": "owner@outlook.com",
        "sub": "1138",
    }
    with pytest.raises(PersonalAccountBlocked):
        _enforce_business_only(claims)


def test_personal_msa_blocked_by_email_host_hotmail() -> None:
    claims = {
        "tid": "11111111-2222-3333-4444-555555555555",
        "preferred_username": "owner@hotmail.com",
        "sub": "1138",
    }
    with pytest.raises(PersonalAccountBlocked):
        _enforce_business_only(claims)


def test_business_account_passes() -> None:
    claims = {
        "tid": "11111111-2222-3333-4444-555555555555",
        "preferred_username": "info@galleriaoms.com",
        "sub": "1138",
        "oid": "abc",
    }
    # Should not raise.
    _enforce_business_only(claims)


def test_missing_email_raises_oauth_error() -> None:
    claims = {
        "tid": "11111111-2222-3333-4444-555555555555",
        "sub": "1138",
        # No preferred_username, no email.
    }
    with pytest.raises(MicrosoftOAuthError):
        _enforce_business_only(claims)


# ----------------------------------------------------------------- auth_url


def test_auth_url_includes_offline_access() -> None:
    client = MicrosoftOAuthClient(
        client_id="ms-client-id",
        client_secret="ms-client-secret",  # noqa: S106 — fixture
    )
    url = client.auth_url(state="abc.def", redirect_uri="https://x/cb")
    assert "offline_access" in url
    assert "Mail.Send" in url
    assert "state=abc.def" in url
    assert "ms-client-id" in url
    assert "response_mode=query" in url


# ----------------------------------------------------------------- exchange flow


@respx.mock
async def test_exchange_code_business_account_succeeds() -> None:
    business_claims = {
        "tid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "preferred_username": "info@galleriaoms.com",
        "sub": "ms-sub",
        "oid": "ms-oid",
    }
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "ms.access",
                "refresh_token": "M.R3_BAY.refresh",
                "id_token": "ey.fake.id_token",
                "expires_in": 3600,
                "scope": "https://graph.microsoft.com/Mail.Send offline_access",
                "token_type": "Bearer",
            },
        )
    )

    async with httpx.AsyncClient() as http:
        client = _client(http)
        with patch.object(
            MicrosoftOAuthClient,
            "decode_id_token",
            return_value=business_claims,
        ):
            tokens, claims = await client.exchange_code(
                code="auth-code", redirect_uri="https://x/cb"
            )
    assert tokens.access_token == "ms.access"  # noqa: S105 — test fixture
    assert claims["preferred_username"] == "info@galleriaoms.com"


@respx.mock
async def test_exchange_code_personal_msa_blocked() -> None:
    personal_claims = {
        "tid": CONSUMER_TENANT_ID,
        "preferred_username": "someone@outlook.com",
        "sub": "ms-sub",
    }
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "ms.access",
                "refresh_token": "M.R3_BAY.refresh",
                "id_token": "ey.fake.id_token",
                "expires_in": 3600,
            },
        )
    )

    async with httpx.AsyncClient() as http:
        client = _client(http)
        with patch.object(
            MicrosoftOAuthClient,
            "decode_id_token",
            return_value=personal_claims,
        ), pytest.raises(PersonalAccountBlocked):
            await client.exchange_code(
                code="auth-code", redirect_uri="https://x/cb"
            )


@respx.mock
async def test_exchange_code_token_endpoint_error_raises_oauth() -> None:
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(400, json={"error": "invalid_grant"})
    )
    async with httpx.AsyncClient() as http:
        client = _client(http)
        with pytest.raises(MicrosoftOAuthError):
            await client.exchange_code(
                code="auth-code", redirect_uri="https://x/cb"
            )


# ----------------------------------------------------------------- refresh


@respx.mock
async def test_refresh_uses_new_rolling_refresh_token() -> None:
    """Microsoft rolls refresh tokens — the response carries a new
    refresh_token which we surface so callers persist it."""
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "ms.access2",
                "refresh_token": "M.R3_BAY.refresh2",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        )
    )
    async with httpx.AsyncClient() as http:
        client = _client(http)
        new_tokens = await client.refresh(refresh_token="M.R3_BAY.refresh1")
    assert new_tokens.access_token == "ms.access2"  # noqa: S105 — test fixture
    assert new_tokens.refresh_token == "M.R3_BAY.refresh2"  # noqa: S105 — test fixture
