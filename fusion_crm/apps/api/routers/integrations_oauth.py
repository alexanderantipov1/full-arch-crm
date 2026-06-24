"""Operator-account OAuth routes — Google Workspace + Microsoft 365.

Surfaces three endpoints per provider (``provider`` ∈
``{google_workspace, microsoft_365}``):

  - ``GET  /integrations/{provider}/connect/start`` — mints state +
    builds the provider's authorize URL; returns ``{authorize_url}``
    for the frontend to open in a popup.
  - ``GET  /integrations/{provider}/callback`` — verifies state,
    exchanges code, runs the HIPAA compliance gate, persists the
    credential, and 302-redirects back to the settings UI.
  - ``POST /integrations/{provider}/credentials/{credential_id}/refresh``
    — internal-use refresh; clients on a 401 can call this to bump
    the access_token. Idempotent.

Per ENG-131 + ADR-0004 §"OAuth flow" + §"HIPAA compliance gate":

  - The compliance gate is mandatory and lives inside the OAuth
    client's ``exchange_code`` — this router never sees a personal
    account's tokens.
  - State is HMAC-signed with ``Settings.internal_credential_token``;
    no in-server session is needed (the state IS the CSRF protection).
  - The callback never logs payload values. Audit rows name only
    ``provider``, ``mailbox_email`` (which is operator-known PII the
    operator just typed, not a clinical secret), and the success /
    failure outcome.

Routes adhere to the ``apps/api/CLAUDE.md`` thin-handler discipline:
DTO → service → return. The OAuth client classes own the heavy
lifting.
"""

from __future__ import annotations

from typing import Annotated, Any
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import (
    get_db,
    get_principal_with_tenant,
)
from packages.core.config import get_settings
from packages.core.exceptions import ValidationError
from packages.core.logging import get_logger
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.integrations._oauth_state import (
    ALLOWED_PROVIDERS,
    OAuthStatePayload,
    mint_state,
    verify_state,
)
from packages.integrations.google_workspace import (
    GoogleOAuthClient,
    GoogleTokens,
)
from packages.integrations.microsoft_365 import (
    MicrosoftOAuthClient,
    MicrosoftTokens,
)
from packages.tenant.credential_service import IntegrationCredentialService

router = APIRouter(prefix="/integrations", tags=["integrations-oauth"])

log = get_logger("api.integrations_oauth")


ProviderParam = Annotated[
    str,
    Path(
        description="Email-OAuth provider key",
        pattern="^(google_workspace|microsoft_365)$",
    ),
]


# ---------------------------------------------------------------- helpers


def _redirect_uri_for(provider: str) -> str:
    """Build the absolute callback URI from ``OAUTH_REDIRECT_BASE_URL``.

    The provider's OAuth app must have this exact URI registered as an
    authorised redirect — a mismatch fails the exchange step with a
    ``redirect_uri_mismatch`` error from the provider.
    """
    base = get_settings().oauth_redirect_base_url.rstrip("/")
    return f"{base}/integrations/{provider}/callback"


def _settings_redirect_url(params: dict[str, str]) -> str:
    """Build an absolute staff-settings redirect URL.

    Email-OAuth callbacks may execute on the API callback origin while the
    operator-facing settings UI lives on the web app. Always redirect back to
    ``WEB_APP_BASE_URL`` so a callback served on an internal/API host cannot
    leave the operator at ``127.0.0.1:8000/settings/tenant`` in production.
    """
    base = get_settings().web_app_base_url.rstrip("/")
    return f"{base}/settings/tenant?{urlencode(params)}"


def _validate_provider(provider: str) -> None:
    if provider not in ALLOWED_PROVIDERS:
        raise ValidationError(
            "unknown OAuth provider",
            details={"provider": provider, "allowed": sorted(ALLOWED_PROVIDERS)},
        )


# ---------------------------------------------------------------- start


@router.get("/{provider}/connect/start")
async def connect_start(
    provider: ProviderParam,
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    location_id: Annotated[UUID | None, Query()] = None,
    display_name: Annotated[str | None, Query(max_length=240)] = None,
) -> dict[str, Any]:
    """Mint a state token and return the provider's authorize URL.

    The frontend opens ``authorize_url`` in a popup; the operator
    consents inside the popup; the provider redirects them back to
    ``/integrations/{provider}/callback`` (this same API host), which
    handles the credential write and a final redirect into the
    settings UI.

    ``location_id`` and ``display_name`` are carried through the OAuth
    round-trip via the signed ``state`` payload — they end up on the
    persisted credential row when the callback fires.
    """
    _validate_provider(provider)
    tenant_id = principal.require_tenant()
    redirect_uri = _redirect_uri_for(provider)

    state = mint_state(
        tenant_id=tenant_id,
        provider=provider,
        location_id=location_id,
        display_name=display_name,
    )

    if provider == "google_workspace":
        client = GoogleOAuthClient.from_settings()
        try:
            authorize_url = client.auth_url(state=state, redirect_uri=redirect_uri)
        finally:
            await client.close()
    else:  # microsoft_365 — guarded by _validate_provider above
        ms_client = MicrosoftOAuthClient.from_settings()
        try:
            authorize_url = ms_client.auth_url(state=state, redirect_uri=redirect_uri)
        finally:
            await ms_client.close()

    log.info(
        "oauth.connect.start",
        provider=provider,
        tenant_id=str(tenant_id),
        has_location=location_id is not None,
    )
    return {"authorize_url": authorize_url}


# ---------------------------------------------------------------- callback


@router.get("/{provider}/callback")
async def connect_callback(
    provider: ProviderParam,
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    """Handle the provider's redirect-back; persist the credential.

    Failure modes mapped to the JSON envelope by the global handler:

      - missing ``code`` / ``state`` → 422 ``validation_error``
      - state tampered / expired → 422 ``oauth_state_invalid``
      - personal account → 403 ``personal_account_blocked``
      - exchange / id_token failure → 502 ``<provider>_oauth_error``

    On success, redirects to the settings UI with
    ``?connected=<provider>&mailbox=<email>`` query params.
    """
    _validate_provider(provider)

    if error:
        # Provider returned an error parameter (user denied, scope
        # mismatch, etc.). We do not try to recover — punt back to the
        # settings UI with a marker the frontend can surface.
        return RedirectResponse(
            url=_settings_redirect_url(
                {"oauth_error": error, "provider": provider}
            ),
            status_code=302,
        )

    if not code:
        raise ValidationError("missing code parameter")
    if not state:
        raise ValidationError("missing state parameter")

    state_payload = verify_state(state)
    if state_payload.provider != provider:
        # State was minted for a different provider. We do not allow
        # cross-provider replay (an attacker who knows a Google state
        # cannot use it to drive a Microsoft callback).
        raise ValidationError(
            "state provider mismatch",
            details={"state_provider": state_payload.provider, "path_provider": provider},
        )

    # Defence in depth: refuse if the request principal's tenant
    # somehow drifts from the state's tenant. In Phase 1 single-tenant
    # they are always equal; this guards Phase 2 multi-tenant from a
    # cross-tenant grant injection.
    request_tenant = principal.require_tenant()
    if state_payload.tenant_id != request_tenant:
        raise ValidationError("state tenant mismatch")

    redirect_uri = _redirect_uri_for(provider)

    if provider == "google_workspace":
        mailbox_email = await _exchange_and_persist_google(
            code=code,
            redirect_uri=redirect_uri,
            db=db,
            principal=principal,
            state_payload=state_payload,
        )
    else:
        mailbox_email = await _exchange_and_persist_microsoft(
            code=code,
            redirect_uri=redirect_uri,
            db=db,
            principal=principal,
            state_payload=state_payload,
        )

    log.info(
        "oauth.connect.success",
        provider=provider,
        tenant_id=str(request_tenant),
    )

    target = _settings_redirect_url(
        {"connected": provider, "mailbox": mailbox_email}
    )
    return RedirectResponse(url=target, status_code=302)


# ---------------------------------------------------------------- refresh


@router.post("/{provider}/credentials/{credential_id}/refresh")
async def refresh_credential(
    provider: ProviderParam,
    credential_id: Annotated[UUID, Path()],
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Refresh the access_token on the given credential row.

    Used by clients that hit a 401 outside of the auto-refresh paths
    on the OAuth client (e.g. an ad-hoc operator-triggered "test
    connection" button). The credential row is updated in place via
    ``IntegrationCredentialService.upsert``; audit row is written by
    that service.
    """
    _validate_provider(provider)
    tenant_id = principal.require_tenant()
    cred_svc = IntegrationCredentialService(db)
    payload = await cred_svc.read_by_id(credential_id, tenant_id=tenant_id)

    refresh_token = payload.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise ValidationError(
            "credential payload has no refresh_token",
            details={"credential_id": str(credential_id), "provider": provider},
        )

    if provider == "google_workspace":
        oauth = GoogleOAuthClient.from_settings()
        try:
            new_tokens = await oauth.refresh(refresh_token=refresh_token)
        finally:
            await oauth.close()
        await _persist_google_refresh(
            payload=payload,
            new_tokens=new_tokens,
            db=db,
            principal=principal,
        )
    else:
        ms_oauth = MicrosoftOAuthClient.from_settings()
        try:
            new_ms_tokens = await ms_oauth.refresh(refresh_token=refresh_token)
        finally:
            await ms_oauth.close()
        await _persist_microsoft_refresh(
            payload=payload,
            new_tokens=new_ms_tokens,
            db=db,
            principal=principal,
        )

    return {
        "ok": True,
        "credential_id": str(credential_id),
        "provider": provider,
    }


# ---------------------------------------------------------------- internals


async def _exchange_and_persist_google(
    *,
    code: str,
    redirect_uri: str,
    db: AsyncSession,
    principal: Principal,
    state_payload: OAuthStatePayload,
) -> str:
    """Run the Google exchange + persist + return the mailbox email."""
    oauth = GoogleOAuthClient.from_settings()
    try:
        tokens, claims = await oauth.exchange_code(code=code, redirect_uri=redirect_uri)
    finally:
        await oauth.close()

    mailbox_email = str(claims.get("email") or "")
    if not mailbox_email:
        raise ValidationError("google id_token missing email after gate")

    cred_svc = IntegrationCredentialService(db)
    await cred_svc.upsert(
        tenant_id=TenantId(state_payload.tenant_id),
        provider_kind="google_workspace",
        credential_kind="oauth_token",
        payload={
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "id_token": tokens.id_token,
            "expires_at": tokens.expires_at.timestamp(),
            "scope": tokens.scope,
            "token_type": tokens.token_type,
            "mailbox_email": mailbox_email,
            "hd": claims.get("hd"),
            "sub": claims.get("sub"),
        },
        principal=principal,
        mailbox_email=mailbox_email,
        location_id=state_payload.location_id,
        display_name=state_payload.display_name,
        expires_at=tokens.expires_at,
    )
    return mailbox_email


async def _exchange_and_persist_microsoft(
    *,
    code: str,
    redirect_uri: str,
    db: AsyncSession,
    principal: Principal,
    state_payload: OAuthStatePayload,
) -> str:
    """Run the Microsoft exchange + persist + return the mailbox email."""
    oauth = MicrosoftOAuthClient.from_settings()
    try:
        tokens, claims = await oauth.exchange_code(code=code, redirect_uri=redirect_uri)
    finally:
        await oauth.close()

    raw_email = claims.get("preferred_username") or claims.get("email")
    mailbox_email = str(raw_email or "")
    if not mailbox_email:
        raise ValidationError("microsoft id_token missing email after gate")

    cred_svc = IntegrationCredentialService(db)
    await cred_svc.upsert(
        tenant_id=TenantId(state_payload.tenant_id),
        provider_kind="microsoft_365",
        credential_kind="oauth_token",
        payload={
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "id_token": tokens.id_token,
            "expires_at": tokens.expires_at.timestamp(),
            "scope": tokens.scope,
            "token_type": tokens.token_type,
            "mailbox_email": mailbox_email,
            "tid": claims.get("tid"),
            "oid": claims.get("oid"),
        },
        principal=principal,
        mailbox_email=mailbox_email,
        location_id=state_payload.location_id,
        display_name=state_payload.display_name,
        expires_at=tokens.expires_at,
    )
    return mailbox_email


async def _persist_google_refresh(
    *,
    payload: dict[str, Any],
    new_tokens: GoogleTokens,
    db: AsyncSession,
    principal: Principal,
) -> None:
    cred_svc = IntegrationCredentialService(db)
    updated = dict(payload)
    updated["access_token"] = new_tokens.access_token
    updated["expires_at"] = new_tokens.expires_at.timestamp()
    if new_tokens.refresh_token is not None:
        updated["refresh_token"] = new_tokens.refresh_token
    mailbox_raw = payload.get("mailbox_email")
    mailbox = mailbox_raw if isinstance(mailbox_raw, str) else None
    await cred_svc.upsert(
        tenant_id=principal.require_tenant(),
        provider_kind="google_workspace",
        credential_kind="oauth_token",
        payload=updated,
        principal=principal,
        mailbox_email=mailbox,
        expires_at=new_tokens.expires_at,
    )


async def _persist_microsoft_refresh(
    *,
    payload: dict[str, Any],
    new_tokens: MicrosoftTokens,
    db: AsyncSession,
    principal: Principal,
) -> None:
    cred_svc = IntegrationCredentialService(db)
    updated = dict(payload)
    updated["access_token"] = new_tokens.access_token
    updated["expires_at"] = new_tokens.expires_at.timestamp()
    if new_tokens.refresh_token is not None:
        updated["refresh_token"] = new_tokens.refresh_token
    mailbox_raw = payload.get("mailbox_email")
    mailbox = mailbox_raw if isinstance(mailbox_raw, str) else None
    await cred_svc.upsert(
        tenant_id=principal.require_tenant(),
        provider_kind="microsoft_365",
        credential_kind="oauth_token",
        payload=updated,
        principal=principal,
        mailbox_email=mailbox,
        expires_at=new_tokens.expires_at,
    )
