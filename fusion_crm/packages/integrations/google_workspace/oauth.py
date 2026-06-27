"""Google OAuth 2.0 client — authorize URL + code exchange + ID-token decode.

Implements the operator-account OAuth flow per ADR-0004:

  1. ``auth_url`` — operator-initiated. Builds Google's authorize URL
     with the scopes ENG-131..132 needs (gmail.send, userinfo.email,
     openid). ``access_type=offline`` + ``prompt=consent`` so we
     receive a refresh_token (no refresh = no autonomous worker).
  2. ``exchange_code`` — callback handler. Trades the auth code for
     access + refresh + id_token. Decodes the id_token, runs the
     **HIPAA compliance gate** (rejects personal Gmail), returns the
     verified token bundle to the API.
  3. ``refresh`` — long-lived refresh-token call.
  4. ``decode_id_token`` — verifies the JWT against Google's JWKS
     (cached) and returns claims.

The compliance gate is mandatory at every callback. Personal Gmail
accounts (``hd`` claim absent or hosted in a consumer domain) are
blocked with ``PersonalAccountBlocked``. There is no operator-toggled
opt-out — disabling the gate would require disabling HIPAA mode at
the tenant level (out of scope for ENG-131).

Hard rules:

  - The gate runs BEFORE any token is handed to the credential store.
    A blocked grant never persists tokens.
  - ID-token signature verification uses ``cryptography``-backed
    PyJWT — we do NOT trust the unverified payload.
  - Google's ``client_secret`` is read once via ``Settings`` and
    pulled out of ``SecretStr`` only at the moment of the HTTPS POST.
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

from .exceptions import GoogleOAuthError, PersonalAccountBlocked

log = get_logger("integrations.google_workspace.oauth")

# Google OAuth 2.0 endpoints (stable, documented at
# developers.google.com/identity/protocols/oauth2/web-server).
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 — public OAuth endpoint URL
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ID_TOKEN_ISSUERS = frozenset({"https://accounts.google.com", "accounts.google.com"})

# Scopes per ADR-0004 §5 — Stage 1 send-only. Inbound scopes
# (``gmail.readonly``) are deferred; adding them later requires
# operator re-consent so we deliberately do not request them now.
DEFAULT_SCOPES: tuple[str, ...] = (
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
)

# Personal mail hosts. A mailbox whose verified email ends in any of
# these is rejected even if the ``hd`` claim somehow slips through —
# defence in depth per ENG-131 §"Compliance gate".
PERSONAL_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        # Microsoft consumer hosts are excluded by the matching gate
        # in the microsoft_365 package — kept out of this set on
        # purpose so a misuse there raises GoogleOAuthError, not
        # PersonalAccountBlocked-with-confusing-message.
    }
)

_DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=10.0)


@dataclass(frozen=True, slots=True)
class GoogleTokens:
    """Bundle returned from ``exchange_code`` and ``refresh``.

    ``access_token`` is short-lived (~1h). ``refresh_token`` is
    long-lived but only present on the first exchange when
    ``access_type=offline`` + ``prompt=consent`` were both set.
    ``expires_at`` is computed at the call site so that downstream
    refresh checks do not need to reason about clock skew across
    components.
    """

    access_token: str
    refresh_token: str | None
    id_token: str | None
    expires_at: datetime
    scope: str | None
    token_type: str


class GoogleOAuthClient:
    """Stateless wrapper around Google's OAuth 2.0 web-server flow.

    One instance per request is cheap; tests inject a custom
    ``httpx.AsyncClient`` to avoid real network traffic, and a
    ``PyJWKClient`` (or a stub thereof) to control ID-token verification.
    """

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
        # Lazily constructed by ``decode_id_token`` when not injected.
        self._jwk_client = jwk_client

    @classmethod
    def from_settings(
        cls,
        *,
        http: httpx.AsyncClient | None = None,
        jwk_client: PyJWKClient | None = None,
    ) -> GoogleOAuthClient:
        """Build from ``Settings``. Raises ``GoogleOAuthError`` if creds missing."""
        settings = get_settings()
        if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
            raise GoogleOAuthError(
                "google oauth client credentials missing in environment",
                details={
                    "missing_env": [
                        e
                        for e, v in (
                            ("GOOGLE_OAUTH_CLIENT_ID", settings.google_oauth_client_id),
                            (
                                "GOOGLE_OAUTH_CLIENT_SECRET",
                                settings.google_oauth_client_secret,
                            ),
                        )
                        if not v
                    ],
                },
            )
        return cls(
            client_id=settings.google_oauth_client_id,
            client_secret=settings.google_oauth_client_secret.get_secret_value(),
            http=http,
            jwk_client=jwk_client,
        )

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> GoogleOAuthClient:
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
        """Build the Google authorize URL the operator gets redirected to.

        ``access_type=offline`` requests a refresh_token. ``prompt=consent``
        forces the consent screen even on a re-auth — this is what guarantees
        Google issues a fresh refresh_token (without ``prompt=consent`` a
        re-auth omits the refresh_token unless the operator already revoked
        the previous grant). ``include_granted_scopes=true`` lets a future
        scope upgrade (e.g. ``gmail.readonly`` for inbound) reuse this grant.
        """
        params: dict[str, str] = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
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
    ) -> tuple[GoogleTokens, dict[str, Any]]:
        """Exchange the authz code for tokens; run the compliance gate.

        Returns a 2-tuple ``(tokens, claims)`` so the caller can
        immediately read ``claims["email"]`` for the credential row's
        ``mailbox_email`` column. Raises ``PersonalAccountBlocked`` when
        the resolved account is not BAA-eligible.
        """
        body = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri": redirect_uri,
        }
        response = await self._http.post(
            TOKEN_URL,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code >= 400:
            log.warning(
                "google.oauth.exchange.error",
                status=response.status_code,
            )
            raise GoogleOAuthError(
                "google token exchange failed",
                details={"status": response.status_code},
            )

        payload = response.json()
        if not isinstance(payload, dict):
            raise GoogleOAuthError("google token response is not a JSON object")

        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise GoogleOAuthError("google token response missing access_token")

        id_token = payload.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise GoogleOAuthError("google token response missing id_token")

        refresh_token = payload.get("refresh_token")
        if refresh_token is not None and not isinstance(refresh_token, str):
            raise GoogleOAuthError("google token response refresh_token has wrong type")

        expires_in_raw = payload.get("expires_in", 3600)
        try:
            expires_in = int(expires_in_raw)
        except (TypeError, ValueError) as exc:
            raise GoogleOAuthError("google token response expires_in invalid") from exc

        # --- Compliance gate runs HERE, before tokens ever leave this module.
        claims = self.decode_id_token(id_token)
        _enforce_workspace_only(claims)

        log.info(
            "google.oauth.exchange.ok",
            # Domain only — never log the email itself.
            mailbox_domain=str(claims.get("hd") or ""),
        )

        tokens = GoogleTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            id_token=id_token,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
            scope=payload.get("scope"),
            token_type=payload.get("token_type", "Bearer"),
        )
        return tokens, claims

    # ---------------------------------------------------------------- refresh

    async def refresh(self, *, refresh_token: str) -> GoogleTokens:
        """Trade a refresh_token for a fresh access_token.

        Google's response on refresh does NOT include a new
        refresh_token (the existing one keeps working until revoked).
        We propagate the original refresh_token through into the
        returned bundle so downstream callers can persist it back.
        """
        body = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        response = await self._http.post(
            TOKEN_URL,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code >= 400:
            raise GoogleOAuthError(
                "google token refresh failed",
                details={"status": response.status_code},
            )
        payload = response.json()
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise GoogleOAuthError("google refresh response missing access_token")
        try:
            expires_in = int(payload.get("expires_in", 3600))
        except (TypeError, ValueError) as exc:
            raise GoogleOAuthError("google refresh response expires_in invalid") from exc
        return GoogleTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            id_token=payload.get("id_token"),
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
            scope=payload.get("scope"),
            token_type=payload.get("token_type", "Bearer"),
        )

    # ---------------------------------------------------------------- id_token

    def decode_id_token(self, id_token: str) -> dict[str, Any]:
        """Verify the JWT signature against Google's JWKS; return claims.

        The JWKS client is cached at the instance level so a single
        ``GoogleOAuthClient`` does not re-fetch the keys on every
        verification. Tests inject a stub ``PyJWKClient`` so they do
        not hit ``googleapis.com``.

        ``audience = client_id`` and ``issuer in ID_TOKEN_ISSUERS`` are
        both verified — without these checks an attacker could replay
        an id_token issued for a different OAuth client.
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
                issuer=list(ID_TOKEN_ISSUERS),
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.InvalidTokenError as exc:
            raise GoogleOAuthError(
                "google id_token verification failed",
                details={"reason": exc.__class__.__name__},
            ) from exc
        if not isinstance(decoded, dict):
            raise GoogleOAuthError("google id_token claims are not an object")
        return decoded


# ---------------------------------------------------------------- compliance gate


def _enforce_workspace_only(claims: dict[str, Any]) -> None:
    """Reject personal Gmail accounts.

    The decision is a function of the ID-token claims:

      - ``hd`` claim non-empty AND not in ``PERSONAL_EMAIL_DOMAINS`` → pass.
      - ``hd`` claim missing / empty → block (personal Gmail).
      - email host in ``PERSONAL_EMAIL_DOMAINS`` → block (defence in depth).
      - ``email_verified`` is not strictly true → block (we cannot
        confidently route mail through an unverified account).

    Per ENG-131, the rejection message names the actionable fix
    (use a Workspace account) so the operator does not have to guess
    why the connect button bounced them out.
    """
    blocked_msg = (
        "Personal Gmail accounts (@gmail.com) are not BAA-eligible. "
        "Use a Google Workspace account."
    )

    hd = claims.get("hd")
    email = claims.get("email")
    email_verified = claims.get("email_verified")

    if not isinstance(email, str) or not email:
        raise GoogleOAuthError("google id_token missing email claim")
    if email_verified is not True:
        raise PersonalAccountBlocked(
            blocked_msg,
            details={"reason": "email_not_verified"},
        )

    # ``hd`` (hosted domain) is the canonical Workspace marker. A truly
    # personal @gmail.com grant returns no ``hd`` claim at all.
    if not isinstance(hd, str) or not hd.strip():
        raise PersonalAccountBlocked(
            blocked_msg,
            details={"reason": "no_hosted_domain"},
        )

    # Belt-and-braces: even if ``hd`` is present, refuse if the email
    # host itself is a known personal domain.
    email_host = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
    if email_host in PERSONAL_EMAIL_DOMAINS:
        raise PersonalAccountBlocked(
            blocked_msg,
            details={"reason": "personal_email_host"},
        )
    if hd.strip().lower() in PERSONAL_EMAIL_DOMAINS:
        raise PersonalAccountBlocked(
            blocked_msg,
            details={"reason": "personal_hosted_domain"},
        )


__all__ = [
    "AUTHORIZE_URL",
    "DEFAULT_SCOPES",
    "GoogleOAuthClient",
    "GoogleTokens",
    "JWKS_URL",
    "PERSONAL_EMAIL_DOMAINS",
    "TOKEN_URL",
]
