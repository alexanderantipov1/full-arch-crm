"""HTTP-level tests for the operator-OAuth routes (ENG-131).

We mount a minimal FastAPI app with the integrations_oauth router,
override the DB-session and principal dependencies, and stub the
Google / Microsoft OAuth client classes so no real network calls
fire. The credential-service write path is exercised against an
in-memory ``IntegrationCredentialService`` mock so we can assert
the upsert is called with the right arguments.

What we cover:

  - ``/integrations/{provider}/connect/start`` returns a JSON body
    containing ``authorize_url`` with the required OAuth params.
  - The callback route blocks personal accounts with a 403 and the
    operator-readable message from ``PersonalAccountBlocked``.
  - The callback route redirects to the settings UI on success and
    invokes ``IntegrationCredentialService.upsert`` with the
    correct ``provider_kind``, ``mailbox_email``, and the
    ``location_id`` carried through state.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import (
    get_db,
    get_principal_with_tenant,
)
from apps.api.middleware import RequestContextMiddleware, platform_error_handler
from apps.api.routers import integrations_oauth as oauth_router
from packages.core.config import get_settings
from packages.core.exceptions import PlatformError
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.integrations._oauth_state import mint_state
from packages.integrations.google_workspace import (
    GoogleOAuthClient,
    GoogleTokens,
)
from packages.integrations.google_workspace import (
    PersonalAccountBlocked as GooglePersonalAccountBlocked,
)

# ----------------------------------------------------------------- fixtures


@pytest.fixture(autouse=True)
def _settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x@y/z")
    monkeypatch.setenv("REDIS_URL", "redis://x:6379/0")
    monkeypatch.setenv("INTERNAL_CREDENTIAL_TOKEN", "test-token-please-rotate-32chars")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client-id-x")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "client-secret-x")
    monkeypatch.setenv("MICROSOFT_OAUTH_CLIENT_ID", "ms-client-id")
    monkeypatch.setenv("MICROSOFT_OAUTH_CLIENT_SECRET", "ms-client-secret")
    monkeypatch.setenv("OAUTH_REDIRECT_BASE_URL", "http://127.0.0.1:8001")
    monkeypatch.setenv("WEB_APP_BASE_URL", "https://fusioncrm.app")
    get_settings.cache_clear()


def _principal(tenant_id: uuid.UUID) -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="ops@example.com",
        tenant_id=TenantId(tenant_id),
        roles=frozenset({Role.ADMIN}),
    )


def _build_app(
    *,
    tenant_id: uuid.UUID,
    db_session: Any,
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    # Same FastAPI typing quirk as the SF route tests.
    app.add_exception_handler(PlatformError, platform_error_handler)  # type: ignore[arg-type]
    app.include_router(oauth_router.router)

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_principal_with_tenant] = lambda: _principal(tenant_id)

    return app


# ----------------------------------------------------------------- start


def test_start_returns_authorize_url_google() -> None:
    tenant_id = uuid.uuid4()
    app = _build_app(tenant_id=tenant_id, db_session=MagicMock())
    client = TestClient(app)

    res = client.get("/integrations/google_workspace/connect/start")
    assert res.status_code == 200
    body = res.json()
    assert "authorize_url" in body
    url = body["authorize_url"]
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=client-id-x" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "state=" in url
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8001%2Fintegrations%2Fgoogle_workspace%2Fcallback" in url


def test_start_returns_authorize_url_microsoft() -> None:
    tenant_id = uuid.uuid4()
    app = _build_app(tenant_id=tenant_id, db_session=MagicMock())
    client = TestClient(app)

    res = client.get("/integrations/microsoft_365/connect/start")
    assert res.status_code == 200
    body = res.json()
    url = body["authorize_url"]
    assert url.startswith("https://login.microsoftonline.com/common/oauth2/v2.0/authorize?")
    assert "client_id=ms-client-id" in url
    assert "Mail.Send" in url
    assert "offline_access" in url


def test_start_unknown_provider_404() -> None:
    """An unknown provider is rejected at the path-pattern level."""
    tenant_id = uuid.uuid4()
    app = _build_app(tenant_id=tenant_id, db_session=MagicMock())
    client = TestClient(app)

    res = client.get("/integrations/madeup/connect/start")
    assert res.status_code == 422  # FastAPI rejects pattern mismatch


# ----------------------------------------------------------------- callback (block)


def test_callback_personal_gmail_returns_403_with_message() -> None:
    """A personal Gmail callback ends in 403 + operator-readable text."""
    tenant_id = uuid.uuid4()
    db_session = MagicMock()
    app = _build_app(tenant_id=tenant_id, db_session=db_session)
    client = TestClient(app)

    state = mint_state(tenant_id=tenant_id, provider="google_workspace")

    # Stub the OAuth client so we never make a real HTTP call. The
    # exchange raises PersonalAccountBlocked from inside the gate.
    fake_oauth = MagicMock()
    fake_oauth.exchange_code = AsyncMock(
        side_effect=GooglePersonalAccountBlocked(
            "Personal Gmail accounts (@gmail.com) are not BAA-eligible. "
            "Use a Google Workspace account.",
        )
    )
    fake_oauth.close = AsyncMock()

    with patch.object(GoogleOAuthClient, "from_settings", return_value=fake_oauth):
        res = client.get(
            f"/integrations/google_workspace/callback?code=abc&state={state}",
            follow_redirects=False,
        )
    assert res.status_code == 403
    body = res.json()
    assert body["error"]["code"] == "personal_account_blocked"
    assert "Workspace" in body["error"]["message"]


def test_callback_state_tampered_returns_422() -> None:
    tenant_id = uuid.uuid4()
    app = _build_app(tenant_id=tenant_id, db_session=MagicMock())
    client = TestClient(app)

    state = mint_state(tenant_id=tenant_id, provider="google_workspace")
    head, _ = state.rsplit(".", 1)
    tampered = f"{head}.deadbeef"
    res = client.get(
        f"/integrations/google_workspace/callback?code=abc&state={tampered}",
        follow_redirects=False,
    )
    assert res.status_code == 422
    body = res.json()
    assert body["error"]["code"] == "oauth_state_invalid"


def test_callback_missing_code_returns_422() -> None:
    tenant_id = uuid.uuid4()
    app = _build_app(tenant_id=tenant_id, db_session=MagicMock())
    client = TestClient(app)

    state = mint_state(tenant_id=tenant_id, provider="google_workspace")
    res = client.get(
        f"/integrations/google_workspace/callback?state={state}",
        follow_redirects=False,
    )
    assert res.status_code == 422


def test_callback_state_provider_mismatch_returns_422() -> None:
    """A state minted for Google cannot drive a Microsoft callback."""
    tenant_id = uuid.uuid4()
    app = _build_app(tenant_id=tenant_id, db_session=MagicMock())
    client = TestClient(app)

    state = mint_state(tenant_id=tenant_id, provider="google_workspace")
    res = client.get(
        f"/integrations/microsoft_365/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert res.status_code == 422
    body = res.json()
    # Either oauth_state_invalid (if the provider mismatch is caught
    # by verify_state's allowed-providers check, which it isn't here
    # since both google_workspace and microsoft_365 are allowed) OR
    # validation_error from the route's explicit cross-check.
    assert body["error"]["code"] in {"oauth_state_invalid", "validation_error"}


# ----------------------------------------------------------------- callback (success)


def test_callback_workspace_persists_and_redirects() -> None:
    """Happy path: state OK, gate passes, credential persisted, 302 issued."""
    tenant_id = uuid.uuid4()
    location_id = uuid.uuid4()

    db_session = MagicMock()
    app = _build_app(tenant_id=tenant_id, db_session=db_session)
    client = TestClient(app)

    state = mint_state(
        tenant_id=tenant_id,
        provider="google_workspace",
        location_id=location_id,
        display_name="Front desk",
    )

    fake_tokens = GoogleTokens(
        access_token="ya29.access",  # noqa: S106 — fixture
        refresh_token="1//refresh",  # noqa: S106 — fixture
        id_token="ey.fake.id_token",  # noqa: S106 — fixture
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        scope="openid",
        token_type="Bearer",  # noqa: S106 — OAuth scheme name
    )
    fake_claims = {
        "email": "info@galleriaoms.com",
        "email_verified": True,
        "hd": "galleriaoms.com",
        "sub": "1138",
    }

    fake_oauth = MagicMock()
    fake_oauth.exchange_code = AsyncMock(return_value=(fake_tokens, fake_claims))
    fake_oauth.close = AsyncMock()

    captured: dict[str, Any] = {}

    async def _capture_upsert(
        self: Any,  # noqa: ARG001
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        captured["args"] = args
        captured["kwargs"] = kwargs
        out = MagicMock()
        out.id = uuid.uuid4()
        out.provider_kind = kwargs.get("provider_kind")
        out.credential_kind = kwargs.get("credential_kind")
        out.is_default = False
        return out

    with patch.object(
        GoogleOAuthClient, "from_settings", return_value=fake_oauth
    ), patch(
        "packages.tenant.credential_service.IntegrationCredentialService.upsert",
        new=_capture_upsert,
    ):
        res = client.get(
            f"/integrations/google_workspace/callback?code=auth-code&state={state}",
            follow_redirects=False,
        )

    assert res.status_code == 302
    location = res.headers["location"]
    assert location.startswith("https://fusioncrm.app/settings/tenant?")
    assert "connected=google_workspace" in location
    assert "mailbox=info%40galleriaoms.com" in location or "mailbox=info@galleriaoms.com" in location
    assert "127.0.0.1" not in location

    # The credential service was invoked with the right arguments.
    kwargs = captured["kwargs"]
    assert kwargs["provider_kind"] == "google_workspace"
    assert kwargs["credential_kind"] == "oauth_token"
    assert kwargs["mailbox_email"] == "info@galleriaoms.com"
    assert kwargs["location_id"] == location_id
    assert kwargs["display_name"] == "Front desk"
    payload = kwargs["payload"]
    assert payload["access_token"] == "ya29.access"  # noqa: S105 — fixture
    assert payload["refresh_token"] == "1//refresh"  # noqa: S105 — fixture
    assert payload["mailbox_email"] == "info@galleriaoms.com"
    assert payload["hd"] == "galleriaoms.com"


def test_callback_provider_returned_error_redirects_to_settings() -> None:
    """When Google itself returns an error param, we surface it via redirect."""
    tenant_id = uuid.uuid4()
    app = _build_app(tenant_id=tenant_id, db_session=MagicMock())
    client = TestClient(app)
    res = client.get(
        "/integrations/google_workspace/callback?error=access_denied",
        follow_redirects=False,
    )
    assert res.status_code == 302
    location = res.headers["location"]
    assert location.startswith("https://fusioncrm.app/settings/tenant?")
    assert "oauth_error=access_denied" in location
    assert "127.0.0.1" not in location
