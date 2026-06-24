"""Auth class hierarchy + provider client Protocol.

Three concrete auth classes cover our target providers:

- ``PKCEOAuth``         — Salesforce (3-legged with PKCE; refresh token; scope list)
- ``StandardOAuth2``    — HubSpot (3-legged with client_secret; refresh token)
- ``PasswordGrantAuth`` — CareStack (ROPC; no refresh — re-issue with same creds)

Each shares the ``BaseAuth`` Protocol. Provider subpackages
(``packages/integrations/<provider>/auth.py``) inherit from the appropriate
class and supply provider-specific endpoints + scopes.

``BaseProviderClient`` is the resource-oriented Protocol that all provider
HTTP clients implement, so sync code (``sync.py::pull/push``) talks to a
single shape regardless of provider.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@dataclass(slots=True, frozen=True)
class AuthExchangeResult:
    """Result of an OAuth code exchange or password-grant token issuance."""

    access_token: str
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    scopes: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class BaseAuth(Protocol):
    """Common surface for every provider's authentication implementation.

    Methods that don't apply to a given grant type return ``None`` rather than
    raising — keeps call-sites uniform (``if (url := auth.build_authorize_url())``).
    """

    provider: str

    def build_authorize_url(self, *, state: str, code_challenge: str | None = None) -> str | None:
        """Return the URL to redirect the user to. None for non-redirect flows."""
        ...

    async def exchange(self, **kwargs: Any) -> AuthExchangeResult:
        """Exchange code/credentials for an access token."""
        ...

    async def refresh(self, refresh_token: str) -> AuthExchangeResult | None:
        """Refresh an access token. None if the grant type doesn't issue refresh tokens."""
        ...

    async def revoke(self, token: str) -> None:
        """Revoke a token. Best-effort; raises only on protocol error."""
        ...


class PKCEOAuth:
    """Authorization Code with PKCE.

    Used by Salesforce. ``code_verifier`` is generated client-side,
    ``code_challenge = base64url(sha256(code_verifier))``. The verifier MUST
    be persisted in Redis (keyed by ``state``) between authorize-redirect and
    callback-exchange.

    Subclass per provider to set ``provider``, ``authorize_endpoint``,
    ``token_endpoint``, ``revoke_endpoint``, ``default_scopes``.
    """

    provider: str = "abstract"
    authorize_endpoint: str = ""
    token_endpoint: str = ""
    revoke_endpoint: str | None = None
    default_scopes: tuple[str, ...] = ()

    def __init__(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        client_secret: str | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def build_authorize_url(self, *, state: str, code_challenge: str | None = None) -> str:
        # Provider subclass formats the URL with provider-specific query params.
        raise NotImplementedError("subclass must implement build_authorize_url")

    async def exchange(
        self,
        *,
        code: str,
        code_verifier: str,
        **_: Any,
    ) -> AuthExchangeResult:
        raise NotImplementedError("subclass must implement exchange")

    async def refresh(self, refresh_token: str) -> AuthExchangeResult | None:
        raise NotImplementedError("subclass must implement refresh")

    async def revoke(self, token: str) -> None:
        raise NotImplementedError("subclass must implement revoke")


class StandardOAuth2:
    """Authorization Code with client_secret (no PKCE).

    Used by HubSpot. Less ceremony than PKCE but requires a backend
    that can keep the client_secret confidential.
    """

    provider: str = "abstract"
    authorize_endpoint: str = ""
    token_endpoint: str = ""
    revoke_endpoint: str | None = None
    default_scopes: tuple[str, ...] = ()

    def __init__(self, *, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def build_authorize_url(self, *, state: str, code_challenge: str | None = None) -> str:
        raise NotImplementedError("subclass must implement build_authorize_url")

    async def exchange(self, *, code: str, **_: Any) -> AuthExchangeResult:
        raise NotImplementedError("subclass must implement exchange")

    async def refresh(self, refresh_token: str) -> AuthExchangeResult | None:
        raise NotImplementedError("subclass must implement refresh")

    async def revoke(self, token: str) -> None:
        raise NotImplementedError("subclass must implement revoke")


class PasswordGrantAuth:
    """Resource Owner Password Credentials.

    Used by CareStack. No refresh token — when the access token expires,
    re-issue by calling ``exchange`` again with the same credentials.

    Credentials (vendor_username + account_password) live encrypted on
    ``IntegrationAccount.meta``; this class reads them to issue tokens.
    ``build_authorize_url`` returns ``None`` because there's no redirect flow.
    """

    provider: str = "abstract"
    token_endpoint: str = ""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret

    def build_authorize_url(self, *, state: str, code_challenge: str | None = None) -> None:
        return None

    async def exchange(
        self,
        *,
        username: str,
        password: str,
        **_: Any,
    ) -> AuthExchangeResult:
        raise NotImplementedError("subclass must implement exchange")

    async def refresh(self, refresh_token: str) -> AuthExchangeResult | None:
        return None

    async def revoke(self, token: str) -> None:
        # Most ROPC providers don't expose a revoke endpoint; subclass overrides
        # if applicable.
        return None


@runtime_checkable
class BaseProviderClient(Protocol):
    """Resource-oriented HTTP client. All providers implement this surface.

    ``resource`` is the provider's own resource name (``Lead``, ``Contact``,
    ``patients``, ``appointments``, ``contacts``). Implementations translate
    verbs onto provider-specific endpoints (SOQL+sObject for SF; Sync APIs for
    CareStack; CRM v3 for HubSpot).

    Sync pipelines (``sync.py::pull/push``) consume this Protocol and never
    see provider HTTP details.
    """

    provider: str

    async def list(  # noqa: A003  (shadow built-in OK on Protocol method)
        self,
        resource: str,
        *,
        since: datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        ...

    async def get(self, resource: str, external_id: str) -> dict[str, Any]:
        ...

    async def create(self, resource: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    async def update(
        self,
        resource: str,
        external_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    async def describe(self, resource: str) -> dict[str, Any]:
        ...
