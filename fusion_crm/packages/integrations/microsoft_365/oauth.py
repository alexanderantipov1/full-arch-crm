"""Microsoft Identity Platform OAuth 2.0 client.

Mirrors ``google_workspace.oauth`` — authorize URL, code exchange,
refresh, ID-token verification — with Microsoft-specific endpoints
and a Microsoft-specific compliance gate (consumer-tenant `tid`
rejection).

Why ``/common/`` and not ``/<tenant>/``:

  Stage 1 cannot enumerate operator tenants ahead of time — every
  clinic has its own AD tenant. ``/common/`` lets a user from any
  tenant consent. Once the operator finishes consent, the returned
  ID-token's ``tid`` claim tells us which tenant they came from; the
  compliance gate runs on that. Single-tenant per-org consent
  (``/<tid>/``) is a Stage 2 ergonomic improvement, not a security
  requirement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient

from packages.core.config import get_settings
from packages.core.logging import get_logger

from .exceptions import MicrosoftOAuthError, PersonalAccountBlocked

log = get_logger("integrations.microsoft_365.oauth")

# Microsoft Identity Platform v2.0 endpoints. ``/common/`` lets users
# from any AD tenant consent; the resulting id_token carries ``tid``.
AUTHORIZE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"  # noqa: S105 — public OAuth endpoint URL
JWKS_URL = "https://login.microsoftonline.com/common/discovery/v2.0/keys"

# Microsoft's special "consumers" tenant id. Every personal MSA grants
# from it; rejecting this tid is the canonical signal that the operator
# tried to connect a personal account.
CONSUMER_TENANT_ID = "9188040d-6c67-4c5b-b112-36a304b66dad"

# Personal Microsoft mail hosts. A grant whose ``preferred_username``
# (or ``email``) ends in any of these is rejected as defence in depth
# even if the tid check somehow misses (e.g. a B2C-style fork).
PERSONAL_EMAIL_DOMAINS = frozenset(
    {
        "outlook.com",
        "hotmail.com",
        "live.com",
        "msn.com",
    }
)

# Scopes per ADR-0004 — Stage 1 send-only.
DEFAULT_SCOPES: tuple[str, ...] = (
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/User.Read",
    "offline_access",
    "openid",
    "email",
    "profile",
)

_DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=10.0)


@dataclass(frozen=True, slots=True)
class MicrosoftTokens:
    """Bundle returned from ``exchange_code`` and ``refresh``.

    ``refresh_token`` is only present on the first exchange (and only
    when ``offline_access`` was in the scope set). ``id_token`` is
    always present for OIDC scopes; we use it for the compliance gate
    and for resolving the operator's mailbox email.
    """

    access_token: str
    refresh_token: str | None
    id_token: str | None
    expires_at: datetime
    scope: str | None
    token_type: str


class MicrosoftOAuthClient:
    """Stateless wrapper around Microsoft's v2.0 web-server flow."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        http: httpx.AsyncClient | None = None,
        jwk_client: PyJWKClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = http if http is not None else httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
        self._owns_http = http is None
        self._jwk_client = jwk_client

    @classmethod
    def from_settings(
        cls,
        *,
        http: httpx.AsyncClient | None = None,
        jwk_client: PyJWKClient | None = None,
    ) -> MicrosoftOAuthClient:
        """Build from ``Settings``. Raises ``MicrosoftOAuthError`` if creds missing."""
        settings = get_settings()
        if not settings.microsoft_oauth_client_id or not settings.microsoft_oauth_client_secret:
            raise MicrosoftOAuthError(
                "microsoft oauth client credentials missing in environment",
                details={
                    "missing_env": [
                        e
                        for e, v in (
                            (
                                "MICROSOFT_OAUTH_CLIENT_ID",
                                settings.microsoft_oauth_client_id,
                            ),
                            (
                                "MICROSOFT_OAUTH_CLIENT_SECRET",
                                settings.microsoft_oauth_client_secret,
                            ),
                        )
                        if not v
                    ],
                },
            )
        return cls(
            client_id=settings.microsoft_oauth_client_id,
            client_secret=settings.microsoft_oauth_client_secret.get_secret_value(),
            http=http,
            jwk_client=jwk_client,
        )

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> MicrosoftOAuthClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ---------------------------------------------------------------- authorize

    def auth_url(
        self,
        *,
        state: str,
        redirect_uri: str,
        scopes: tuple[str, ...] = DEFAULT_SCOPES,
        login_hint: str | None = None,
    ) -> str:
        """Build the Microsoft authorize URL the operator gets redirected to.

        ``response_mode=query`` so the callback receives ``code`` /
        ``state`` as query params (matches our handler shape).
        ``prompt=consent`` is included by default so the operator
        sees the consent screen (and so we always get a refresh
        token from ``offline_access``).
        """
        params: dict[str, str] = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "response_mode": "query",
            "prompt": "consent",
            "state": state,
        }
        if login_hint:
            params["login_hint"] = login_hint
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    # ---------------------------------------------------------------- exchange

    async def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        scopes: tuple[str, ...] = DEFAULT_SCOPES,
    ) -> tuple[MicrosoftTokens, dict[str, Any]]:
        """Exchange the authz code for tokens; run the compliance gate.

        Returns ``(tokens, claims)`` so the caller can read
        ``claims["preferred_username"]`` (or ``email``) for the
        ``mailbox_email`` column.
        """
        body = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
        }
        response = await self._http.post(
            TOKEN_URL,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code >= 400:
            log.warning(
                "microsoft.oauth.exchange.error",
                status=response.status_code,
            )
            raise MicrosoftOAuthError(
                "microsoft token exchange failed",
                details={"status": response.status_code},
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise MicrosoftOAuthError("microsoft token response is not a JSON object")

        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise MicrosoftOAuthError("microsoft token response missing access_token")

        id_token = payload.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise MicrosoftOAuthError("microsoft token response missing id_token")

        refresh_token = payload.get("refresh_token")
        if refresh_token is not None and not isinstance(refresh_token, str):
            raise MicrosoftOAuthError("microsoft token response refresh_token wrong type")

        try:
            expires_in = int(payload.get("expires_in", 3600))
        except (TypeError, ValueError) as exc:
            raise MicrosoftOAuthError("microsoft token response expires_in invalid") from exc

        # Compliance gate runs HERE.
        claims = self.decode_id_token(id_token)
        _enforce_business_only(claims)

        log.info(
            "microsoft.oauth.exchange.ok",
            tid=str(claims.get("tid") or ""),
        )

        tokens = MicrosoftTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            id_token=id_token,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
            scope=payload.get("scope"),
            token_type=payload.get("token_type", "Bearer"),
        )
        return tokens, claims

    # ---------------------------------------------------------------- refresh

    async def refresh(
        self,
        *,
        refresh_token: str,
        scopes: tuple[str, ...] = DEFAULT_SCOPES,
    ) -> MicrosoftTokens:
        """Trade a refresh_token for a fresh access_token.

        Microsoft's response on refresh DOES include a new
        refresh_token (rolling refresh token model). We use the new
        one going forward; the old one is invalidated.
        """
        body = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": " ".join(scopes),
        }
        response = await self._http.post(
            TOKEN_URL,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code >= 400:
            raise MicrosoftOAuthError(
                "microsoft token refresh failed",
                details={"status": response.status_code},
            )
        payload = response.json()
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise MicrosoftOAuthError("microsoft refresh response missing access_token")
        try:
            expires_in = int(payload.get("expires_in", 3600))
        except (TypeError, ValueError) as exc:
            raise MicrosoftOAuthError("microsoft refresh response expires_in invalid") from exc
        new_refresh = payload.get("refresh_token") if isinstance(
            payload.get("refresh_token"), str
        ) else refresh_token
        return MicrosoftTokens(
            access_token=access_token,
            refresh_token=new_refresh,
            id_token=payload.get("id_token"),
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
            scope=payload.get("scope"),
            token_type=payload.get("token_type", "Bearer"),
        )

    # ---------------------------------------------------------------- id_token

    def decode_id_token(self, id_token: str) -> dict[str, Any]:
        """Verify the JWT signature against Microsoft's JWKS; return claims.

        ``audience = client_id`` is verified. The issuer is NOT pinned
        (Microsoft's issuer URL embeds the tenant id, which differs per
        consenting org) but the ``tid`` claim is then used by the
        compliance gate.
        """
        jwk_client = self._jwk_client
        if jwk_client is None:
            jwk_client = PyJWKClient(JWKS_URL)
            self._jwk_client = jwk_client
        try:
            signing_key = jwk_client.get_signing_key_from_jwt(id_token).key
            decoded = jwt.decode(
                id_token,
                signing_key,
                algorithms=["RS256"],
                audience=self._client_id,
                # No fixed issuer — Microsoft's issuer is per-tenant and
                # we cannot enumerate ahead of time. ``tid`` is checked
                # by the compliance gate.
                options={
                    "verify_iss": False,
                    "require": ["exp", "iat", "aud", "sub"],
                },
            )
        except jwt.InvalidTokenError as exc:
            raise MicrosoftOAuthError(
                "microsoft id_token verification failed",
                details={"reason": exc.__class__.__name__},
            ) from exc
        if not isinstance(decoded, dict):
            raise MicrosoftOAuthError("microsoft id_token claims are not an object")
        return decoded


# ---------------------------------------------------------------- compliance gate


def _enforce_business_only(claims: dict[str, Any]) -> None:
    """Reject personal MSA accounts (consumer-tenant `tid` or known hosts).

    The decision tree:

      - ``tid`` claim equals the consumer-tenant id → block.
      - email/preferred_username host in ``PERSONAL_EMAIL_DOMAINS`` → block.

    Per ENG-131, the rejection message names the actionable fix
    (use a Microsoft 365 Business / Enterprise account).
    """
    blocked_msg = (
        "Personal Outlook/Hotmail accounts are not BAA-eligible. "
        "Use a Microsoft 365 Business / Enterprise account."
    )

    tid = claims.get("tid")
    if isinstance(tid, str) and tid.strip().lower() == CONSUMER_TENANT_ID:
        raise PersonalAccountBlocked(
            blocked_msg,
            details={"reason": "consumer_tenant_id"},
        )

    email = claims.get("preferred_username") or claims.get("email")
    if not isinstance(email, str) or not email:
        # No email-shaped claim at all — refuse the grant: we cannot
        # route mail without a verified mailbox.
        raise MicrosoftOAuthError(
            "microsoft id_token missing preferred_username/email claim"
        )

    email_host = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
    if email_host in PERSONAL_EMAIL_DOMAINS:
        raise PersonalAccountBlocked(
            blocked_msg,
            details={"reason": "personal_email_host"},
        )


__all__ = [
    "AUTHORIZE_URL",
    "CONSUMER_TENANT_ID",
    "DEFAULT_SCOPES",
    "JWKS_URL",
    "MicrosoftOAuthClient",
    "MicrosoftTokens",
    "PERSONAL_EMAIL_DOMAINS",
    "TOKEN_URL",
]
