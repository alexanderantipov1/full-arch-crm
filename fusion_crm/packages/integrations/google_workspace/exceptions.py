"""Google Workspace integration exceptions.

Typed errors mapped by the FastAPI middleware to the standard JSON
envelope. Never raise raw ``HTTPException`` from the OAuth or Gmail
clients — that bypasses the envelope and leaks detail.
"""

from __future__ import annotations

from packages.core.exceptions import AuthorizationError, IntegrationError


class GoogleOAuthError(IntegrationError):
    """OAuth-flow failure (token endpoint, JWKS fetch, id_token decode).

    Distinct from a Gmail API failure so the operator UI can surface
    "reconnect this mailbox" vs "Gmail API outage".
    """

    code = "google_oauth_error"
    http_status = 502


class GoogleAPIError(IntegrationError):
    """Gmail / Google API failure after a successful OAuth grant.

    Used for ``users.messages.send`` 4xx/5xx, ``users.getProfile``
    failures, and any other authenticated REST call. A 401 specifically
    triggers an automatic refresh-once retry inside the client; only a
    persistent failure surfaces as ``GoogleAPIError``.
    """

    code = "google_api_error"
    http_status = 502


class PersonalAccountBlocked(AuthorizationError):
    """The OAuth grant resolved to a non-BAA-eligible Google account.

    Personal ``@gmail.com`` / ``@googlemail.com`` mailboxes are not
    covered by Google's Workspace BAA — sending PHI through them is a
    compliance violation. The compliance gate in ``oauth.exchange_code``
    blocks the grant before any token reaches the credential store.

    The operator-facing message is short, specific, and actionable —
    the operator needs to know they have to use a Workspace-billed
    account, not a personal one.
    """

    code = "personal_account_blocked"
    # 403 — the request was authenticated by the user but the resolved
    # account is not allowed to be connected.
    http_status = 403


__all__ = [
    "GoogleAPIError",
    "GoogleOAuthError",
    "PersonalAccountBlocked",
]
