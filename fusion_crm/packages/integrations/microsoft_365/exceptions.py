"""Microsoft 365 integration exceptions.

Typed errors mapped by the FastAPI middleware to the standard JSON
envelope. Mirrors ``google_workspace.exceptions`` for parity.
"""

from __future__ import annotations

from packages.core.exceptions import AuthorizationError, IntegrationError


class MicrosoftOAuthError(IntegrationError):
    """OAuth-flow failure (token endpoint, JWKS fetch, id_token decode)."""

    code = "microsoft_oauth_error"
    http_status = 502


class MicrosoftAPIError(IntegrationError):
    """Microsoft Graph API failure after a successful OAuth grant.

    A bare 401 is NOT this error — the client refreshes once first.
    Only persistent or non-auth failures bubble up.
    """

    code = "microsoft_api_error"
    http_status = 502


class PersonalAccountBlocked(AuthorizationError):
    """The OAuth grant resolved to a non-BAA-eligible Microsoft account.

    Personal Outlook / Hotmail / Live / MSN mailboxes are MSAs sitting
    in Microsoft's special ``consumers`` tenant
    (``9188040d-6c67-4c5b-b112-36a304b66dad``). Sending PHI through
    them is a compliance violation. The compliance gate in
    ``oauth.exchange_code`` blocks the grant before any token reaches
    the credential store.
    """

    code = "personal_account_blocked"
    http_status = 403


__all__ = [
    "MicrosoftAPIError",
    "MicrosoftOAuthError",
    "PersonalAccountBlocked",
]
