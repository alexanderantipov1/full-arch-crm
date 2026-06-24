"""Unit tests for the Salesforce OAuth helpers.

Covers two specific bugs that produced a reconnect loop in production:

1. `build_authorize_url` did not request `prompt=consent`. Salesforce
   only re-issues a refresh_token when the user re-consents, so a
   re-connect by an already-authorized operator got an access_token
   with no refresh_token — and the next refresh failed
   `invalid_grant`, prompting another Connect click, repeat forever.

2. `persist_oauth_token` silently stored an access_token-only payload
   when the token response did not contain a refresh_token. Combined
   with bug #1 this is what produced the loop in prod.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest

from packages.core.exceptions import IntegrationError
from packages.core.types import TenantId
from packages.integrations.salesforce.oauth import (
    SfClientConfig,
    build_authorize_url,
    persist_oauth_token,
)


def _cfg() -> SfClientConfig:
    return SfClientConfig(
        client_id="sf-client-id",
        client_secret="sf-client-secret",
        callback_url="https://fusioncrm.app/api/integrations/salesforce/callback",
        domain="login.salesforce.com",
    )


def test_authorize_url_requests_prompt_consent() -> None:
    """The Connect flow MUST request `prompt=consent` so Salesforce
    re-issues a refresh_token on every re-consent. Without this, a
    re-connect by an already-authorized operator only receives an
    access_token, and the next refresh fails `invalid_grant` —
    the reconnect loop bug we saw in prod."""
    url = build_authorize_url(_cfg(), challenge="ch-abc", state="st-xyz")
    qs = parse_qs(urlsplit(url).query)
    assert qs.get("prompt") == ["consent"], (
        f"authorize URL must request prompt=consent; got query={qs}"
    )
    # Sanity-check the rest of the contract — these are not regressions
    # we expect, but if any of these drift, refresh_token issuance also
    # silently breaks even with prompt=consent.
    assert "refresh_token" in qs.get("scope", [""])[0]
    assert "offline_access" in qs.get("scope", [""])[0]
    assert qs.get("response_type") == ["code"]
    assert qs.get("code_challenge_method") == ["S256"]


async def test_persist_oauth_token_rejects_response_without_refresh_token() -> None:
    """The persistence layer MUST fail loud (IntegrationError) when
    Salesforce returns an access_token without a refresh_token —
    silently storing an access_token-only row leads to a permanent
    reconnect loop. The error message must steer the operator to
    fix the Connected App config, not just retry."""
    cred_svc = AsyncMock()
    tenant_id = TenantId(uuid4())
    principal = object()  # only passed through to svc; not introspected here

    token_response_no_refresh = {
        "access_token": "at-fresh",
        "instance_url": "https://example.my.salesforce.com",
        # Note: NO `refresh_token` key — this is what SF returns when
        # the user is already consented and prompt=consent was missing.
    }
    with pytest.raises(IntegrationError) as ei:
        await persist_oauth_token(
            cred_svc,
            tenant_id,
            principal,  # type: ignore[arg-type]
            token_response=token_response_no_refresh,
        )
    # Message must be actionable, not just a status code.
    msg = ei.value.message.lower()
    assert "refresh_token" in msg
    assert "connected app" in msg
    assert "reconnect" in msg or "connect again" in msg
    assert ei.value.details["have_refresh_token"] is False
    assert ei.value.details["action"] == "fix_connected_app_then_reconnect"

    # cred_svc.upsert MUST NOT have been called — we refuse to persist
    # an access_token-only payload that would break the next refresh.
    cred_svc.upsert.assert_not_called()


async def test_persist_oauth_token_stores_full_payload_when_refresh_token_present() -> None:
    cred_svc = AsyncMock()
    tenant_id = TenantId(uuid4())
    principal = object()
    token_response = {
        "access_token": "at-fresh",
        "instance_url": "https://example.my.salesforce.com",
        "refresh_token": "rt-fresh",
        "issued_at": "1729000000000",
    }
    await persist_oauth_token(
        cred_svc,
        tenant_id,
        principal,  # type: ignore[arg-type]
        token_response=token_response,
    )
    cred_svc.upsert.assert_awaited_once()
    args = cred_svc.upsert.await_args
    payload = args.args[3] if len(args.args) >= 4 else args.kwargs.get("payload")
    # Verify the persisted payload — refresh_token must be present.
    assert payload["access_token"] == "at-fresh"
    assert payload["refresh_token"] == "rt-fresh"
    assert payload["instance_url"] == "https://example.my.salesforce.com"
    assert payload["issued_at"] == "1729000000000"
