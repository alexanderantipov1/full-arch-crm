"""Salesforce OAuth Web Server Flow with PKCE — server-side.

Mirrors ``apps/web/lib/sf/oauth.ts``. We use S256 PKCE because the
Connected App requires it; without it SF rejects the auth request with
the misleading ``invalid_client_id`` error.

Credential resolution (ENG-125 / ENG-147): SF client config
(``client_id``, ``client_secret``, ``callback_url``, ``domain``) is
read DB-first via ``IntegrationCredentialService.read_for(tenant,
"salesforce", "api_key")``, with env-fallback on any failure. Refreshed
or freshly-issued OAuth tokens are persisted under the
``(salesforce, oauth_token)`` row in the same table; the SF client
(``packages.integrations.salesforce.client``) picks them up.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from packages.core.config import get_settings
from packages.core.exceptions import IntegrationError
from packages.core.logging import get_logger
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)

log = get_logger("integrations.salesforce.oauth")

_DEFAULT_DOMAIN = "login.salesforce.com"
_DEFAULT_SCOPE = "api refresh_token offline_access"


@dataclass(frozen=True)
class SfClientConfig:
    """The four values needed to drive the SF OAuth round-trip."""

    client_id: str
    client_secret: str
    callback_url: str
    domain: str


def _b64url(raw: bytes) -> str:
    """Strip-padding url-safe Base64, matching the SF PKCE spec."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def generate_pkce_pair() -> tuple[str, str]:
    """Return ``(verifier, challenge)`` — S256, RFC 7636 compliant."""
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def _as_str(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


async def load_client_config(
    cred_svc: IntegrationCredentialService,
    tenant_id: TenantId,
) -> SfClientConfig:
    """Resolve SF client config — DB-first, env-fallback.

    Raises :class:`IntegrationError` (code ``sf_oauth_unconfigured``)
    when neither source provides ``client_id`` + ``client_secret``;
    that is the irreducible minimum to start the flow.
    """
    payload: dict[str, Any] | None
    try:
        payload = await cred_svc.read_for(
            tenant_id, "salesforce", "api_key"
        )
    except NoCredentialError:
        payload = None

    settings = get_settings()
    client_id = (
        _as_str(payload.get("client_id") if payload else None)
        or settings.salesforce_client_id
    )
    client_secret_raw = payload.get("client_secret") if payload else None
    client_secret = _as_str(client_secret_raw)
    if not client_secret and settings.salesforce_client_secret is not None:
        client_secret = settings.salesforce_client_secret.get_secret_value()

    # ``callback_url`` and ``domain`` use **env-first** resolution because
    # the seed migration captured these from the local-dev environment
    # at first bootstrap (``apps/web/.sf-tokens.json`` / dev callback
    # URL). On production the operator sets ``SALESFORCE_CALLBACK_URL``
    # on the Cloud Run service to the public host
    # (``https://fusioncrm.app/api/integrations/salesforce/callback``)
    # and that value must win — otherwise SF redirects post-consent
    # back to localhost. The DB row stays as a usable fallback for
    # local dev and for environments where the env override is absent.
    callback_url = (
        settings.salesforce_callback_url
        or _as_str(payload.get("callback_url") if payload else None)
    )
    domain = (
        settings.salesforce_domain
        or _as_str(payload.get("domain") if payload else None)
        or _DEFAULT_DOMAIN
    )

    if not client_id or not client_secret:
        raise IntegrationError(
            "salesforce client config missing — seed (salesforce, api_key) "
            "in tenant.integration_credential or set SALESFORCE_CLIENT_ID + "
            "SALESFORCE_CLIENT_SECRET in env",
            details={"have_client_id": bool(client_id)},
        )
    if not callback_url:
        raise IntegrationError(
            "salesforce callback_url missing — seed callback_url in DB or "
            "set SALESFORCE_CALLBACK_URL env",
        )
    return SfClientConfig(
        client_id=client_id,
        client_secret=client_secret,
        callback_url=callback_url,
        domain=domain,
    )


def build_authorize_url(
    cfg: SfClientConfig,
    challenge: str,
    *,
    state: str | None = None,
) -> str:
    """Construct the SF authorize URL the operator's browser opens.

    ``prompt=consent`` is required for refresh_token issuance on a
    *re-connect*. When the operator already authorized the Connected
    App (e.g. an earlier connect that has since seen its refresh_token
    invalidated), Salesforce silently skips the consent screen and
    issues an access_token *without* a refresh_token. The persistence
    layer then has no token to refresh against, the next request
    fails ``invalid_grant``, the operator clicks Connect again — and
    the loop repeats forever. ``prompt=consent`` makes SF re-issue a
    refresh_token every time the user re-consents.
    """
    params: dict[str, str] = {
        "client_id": cfg.client_id,
        "redirect_uri": cfg.callback_url,
        "response_type": "code",
        "scope": _DEFAULT_SCOPE,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "consent",
    }
    if state:
        params["state"] = state
    return f"https://{cfg.domain}/services/oauth2/authorize?{urlencode(params)}"


async def exchange_code(
    cfg: SfClientConfig,
    *,
    code: str,
    verifier: str,
) -> dict[str, Any]:
    """POST ``authorization_code`` grant; return the JSON token payload.

    Raises :class:`IntegrationError` on non-2xx from SF.
    """
    body = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": cfg.client_id,
        "client_secret": cfg.client_secret,
        "redirect_uri": cfg.callback_url,
        "code_verifier": verifier,
    }
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0)
    ) as client:
        response = await client.post(
            f"https://{cfg.domain}/services/oauth2/token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if response.status_code >= 400:
        raise IntegrationError(
            f"salesforce token exchange failed: {response.status_code}",
            details={
                "status": response.status_code,
                "body": response.text[:500],
            },
        )
    return response.json()  # type: ignore[no-any-return]


async def persist_oauth_token(
    cred_svc: IntegrationCredentialService,
    tenant_id: TenantId,
    principal: Principal,
    *,
    token_response: dict[str, Any],
) -> None:
    """Write the OAuth token payload to ``tenant.integration_credential``.

    The SF token-exchange / refresh response carries ``access_token``,
    ``refresh_token`` (only on initial issue), ``instance_url`` and
    ``issued_at``. Store exactly those four — they map 1:1 onto the
    payload shape that ``SfClient.from_credential`` expects.
    """
    access_token = _as_str(token_response.get("access_token"))
    instance_url = _as_str(token_response.get("instance_url"))
    if not access_token or not instance_url:
        raise IntegrationError(
            "salesforce token response missing required fields",
            details={
                "have_access": bool(access_token),
                "have_instance_url": bool(instance_url),
            },
        )
    refresh_token = _as_str(token_response.get("refresh_token"))
    if not refresh_token:
        # Fail loud rather than silently storing an access_token-only
        # payload — that path leads to a permanent reconnect loop
        # (next refresh has no refresh_token to use → invalid_grant →
        # operator clicks Connect → repeat). If we ever land here
        # with `prompt=consent` in the authorize URL, the Connected
        # App probably lost the `refresh_token` OAuth scope or the
        # refresh-token policy is set to "Immediately expire".
        raise IntegrationError(
            "Salesforce did not return a refresh_token. "
            "Check the Connected App OAuth scopes (must include "
            "`refresh_token` / `offline_access`) and the refresh-token "
            "policy in Salesforce Setup → App Manager → Connected App "
            "→ Manage → Edit Policies. Then disconnect Salesforce in "
            "Settings → Integrations and connect again.",
            details={
                "have_access": True,
                "have_refresh_token": False,
                "action": "fix_connected_app_then_reconnect",
            },
        )
    payload: dict[str, object] = {
        "access_token": access_token,
        "instance_url": instance_url,
        "refresh_token": refresh_token,
    }
    issued_at = _as_str(token_response.get("issued_at"))
    if issued_at:
        payload["issued_at"] = issued_at

    await cred_svc.upsert(
        tenant_id,
        "salesforce",
        "oauth_token",
        payload,
        principal=principal,
        display_name="Salesforce OAuth tokens (operator-initiated)",
    )
    log.info(
        "sf.oauth.token_persisted",
        tenant_id=str(tenant_id),
        has_refresh=True,
    )
