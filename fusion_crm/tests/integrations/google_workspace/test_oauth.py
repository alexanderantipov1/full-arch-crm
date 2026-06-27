"""Unit tests for the Google Workspace OAuth client (ENG-131).

External calls are stubbed via ``respx``. ID-token signature
verification is bypassed by monkeypatching ``decode_id_token`` —
the JWKS-fetch path is exercised by an integration smoke test outside
this file. What we DO verify here:

  - The compliance gate behaviour (personal Gmail blocked, Workspace
    account passes, both belt-and-braces checks fire).
  - The exchange-code flow consumes the ID-token claims correctly.
  - The state-CSRF helper round-trips and rejects tampering.

The state CSRF tests live here (rather than in a shared file) because
they need ``Settings.internal_credential_token`` to be set, and the
test fixture is cheap to spin up.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

import httpx
import pytest
import respx

from packages.core.config import get_settings
from packages.core.exceptions import ValidationError
from packages.integrations._oauth_state import (
    OAuthStateInvalid,
    mint_state,
    verify_state,
)
from packages.integrations.google_workspace import (
    GoogleOAuthClient,
    GoogleOAuthError,
    PersonalAccountBlocked,
)
from packages.integrations.google_workspace.oauth import (
    TOKEN_URL,
    _enforce_workspace_only,
)

# ----------------------------------------------------------------- fixtures


@pytest.fixture(autouse=True)
def _settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide minimal env so ``Settings`` builds + state HMAC works."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x@y/z")
    monkeypatch.setenv("REDIS_URL", "redis://x:6379/0")
    monkeypatch.setenv("INTERNAL_CREDENTIAL_TOKEN", "test-token-please-rotate-32chars")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client-id-x")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "client-secret-x")
    # Reset cached settings so the new env is picked up.
    get_settings.cache_clear()


def _client(http: httpx.AsyncClient) -> GoogleOAuthClient:
    return GoogleOAuthClient(
        client_id="client-id-x",
        client_secret="client-secret-x",  # noqa: S106 — fixture
        http=http,
    )


# ----------------------------------------------------------------- state CSRF


def test_state_csrf_roundtrip() -> None:
    tenant_id = uuid.uuid4()
    location_id = uuid.uuid4()
    token = mint_state(
        tenant_id=tenant_id,
        provider="google_workspace",
        location_id=location_id,
        display_name="Front desk",
    )
    payload = verify_state(token)
    assert payload.tenant_id == tenant_id
    assert payload.provider == "google_workspace"
    assert payload.location_id == location_id
    assert payload.display_name == "Front desk"


def test_state_csrf_rejects_tampered_signature() -> None:
    token = mint_state(tenant_id=uuid.uuid4(), provider="google_workspace")
    head, _ = token.rsplit(".", 1)
    tampered = f"{head}.deadbeef"
    with pytest.raises(OAuthStateInvalid):
        verify_state(tampered)


def test_state_csrf_rejects_unknown_provider() -> None:
    with pytest.raises(ValidationError):
        mint_state(tenant_id=uuid.uuid4(), provider="not-a-provider")


def test_state_csrf_rejects_expired() -> None:
    """A token with expires_at in the past is rejected."""
    token = mint_state(
        tenant_id=uuid.uuid4(),
        provider="google_workspace",
        ttl_seconds=-1,  # already expired
    )
    with pytest.raises(OAuthStateInvalid):
        verify_state(token)


# ----------------------------------------------------------------- gate (direct)


def test_personal_gmail_blocked_no_hd() -> None:
    """An id_token with no `hd` claim is rejected (canonical signal)."""
    claims: dict[str, Any] = {
        "email": "someone@gmail.com",
        "email_verified": True,
        "sub": "1138",
        # No `hd` at all.
    }
    with pytest.raises(PersonalAccountBlocked) as exc:
        _enforce_workspace_only(claims)
    assert "Workspace" in exc.value.message


def test_personal_gmail_blocked_email_host() -> None:
    """Belt-and-braces: even an `hd`-bearing claim is blocked if the
    email host is gmail.com (e.g. a misconfigured Workspace mapping)."""
    claims = {
        "email": "ceo@gmail.com",
        "email_verified": True,
        "hd": "drantipov.com",
        "sub": "1138",
    }
    with pytest.raises(PersonalAccountBlocked):
        _enforce_workspace_only(claims)


def test_workspace_account_passes() -> None:
    """A real Workspace claim flows through cleanly."""
    claims = {
        "email": "info@galleriaoms.com",
        "email_verified": True,
        "hd": "galleriaoms.com",
        "sub": "1138",
    }
    # Should not raise.
    _enforce_workspace_only(claims)


def test_unverified_email_blocked() -> None:
    claims = {
        "email": "info@galleriaoms.com",
        "email_verified": False,
        "hd": "galleriaoms.com",
        "sub": "1138",
    }
    with pytest.raises(PersonalAccountBlocked):
        _enforce_workspace_only(claims)


def test_missing_email_raises_oauth_error() -> None:
    claims = {"hd": "galleriaoms.com", "email_verified": True, "sub": "1138"}
    with pytest.raises(GoogleOAuthError):
        _enforce_workspace_only(claims)


# ----------------------------------------------------------------- auth_url


def test_auth_url_includes_required_params() -> None:
    """The authorize URL carries scopes, state, redirect_uri and the
    offline-access / consent prompt that ENG-131 requires."""
    client = GoogleOAuthClient(
        client_id="client-id-x",
        client_secret="client-secret-x",  # noqa: S106 — fixture
    )
    url = client.auth_url(state="abc.def", redirect_uri="https://x/cb")
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "state=abc.def" in url
    assert "redirect_uri=https" in url
    assert "gmail.send" in url
    assert "client-id-x" in url


# ----------------------------------------------------------------- exchange flow


@respx.mock
async def test_exchange_code_workspace_account_succeeds() -> None:
    """Happy path: token endpoint returns id_token, gate passes,
    bundle is returned with the verified claims."""
    workspace_claims = {
        "email": "info@galleriaoms.com",
        "email_verified": True,
        "hd": "galleriaoms.com",
        "sub": "1138-google-sub",
    }

    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "ya29.access",
                "refresh_token": "1//refresh",
                "id_token": "ey.fake.id_token",
                "expires_in": 3600,
                "scope": "openid",
                "token_type": "Bearer",
            },
        )
    )

    async with httpx.AsyncClient() as http:
        client = _client(http)
        # Bypass the JWKS network round-trip — replace the verifier
        # with a stub that returns our fixture claims.
        with patch.object(
            GoogleOAuthClient,
            "decode_id_token",
            return_value=workspace_claims,
        ):
            tokens, claims = await client.exchange_code(
                code="auth-code", redirect_uri="https://x/cb"
            )
    assert tokens.access_token == "ya29.access"  # noqa: S105 — test fixture
    assert tokens.refresh_token == "1//refresh"  # noqa: S105 — test fixture
    assert claims["hd"] == "galleriaoms.com"


@respx.mock
async def test_exchange_code_personal_gmail_blocked() -> None:
    """End-to-end: token endpoint OK, gate rejects, no bundle returned."""
    personal_claims = {
        "email": "someone@gmail.com",
        "email_verified": True,
        "sub": "1138-google-sub",
        # No `hd` — personal account.
    }
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "ya29.access",
                "refresh_token": "1//refresh",
                "id_token": "ey.fake.id_token",
                "expires_in": 3600,
            },
        )
    )

    async with httpx.AsyncClient() as http:
        client = _client(http)
        with patch.object(
            GoogleOAuthClient,
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
        with pytest.raises(GoogleOAuthError):
            await client.exchange_code(
                code="auth-code", redirect_uri="https://x/cb"
            )


@respx.mock
async def test_exchange_code_missing_id_token_raises() -> None:
    """Google's token response without `id_token` cannot pass the gate.

    Without an id_token there is no way to verify the resolved
    account's domain — refusing the grant is the only safe behaviour."""
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "ya29.access",
                "refresh_token": "1//refresh",
                "expires_in": 3600,
            },
        )
    )
    async with httpx.AsyncClient() as http:
        client = _client(http)
        with pytest.raises(GoogleOAuthError):
            await client.exchange_code(
                code="auth-code", redirect_uri="https://x/cb"
            )
