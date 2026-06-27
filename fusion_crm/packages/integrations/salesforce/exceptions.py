"""Salesforce integration exceptions.

These are domain-typed errors. The API middleware translates them to JSON
envelopes via the standard ``PlatformError`` machinery — never raise raw
``HTTPException`` from the client or from services that consume it.
"""

from __future__ import annotations

from packages.core.exceptions import IntegrationError


class SfNotConnectedError(IntegrationError):
    """Salesforce is not reachable with the current credentials.

    Raised when:
      * the dev token file is missing / malformed
      * a 401 response is followed by a refresh that also fails
      * required client_id / client_secret are not configured

    The API translates this to HTTP 409 so the operator UI can prompt the user
    to (re-)connect Salesforce, rather than treating it as a 5xx outage.
    """

    code = "sf_not_connected"
    http_status = 409


class SfApiError(IntegrationError):
    """Non-401 Salesforce API failure (4xx other than 401, or 5xx).

    A bare 401 alone is NOT this error — the client refreshes once first.
    Only persistent or non-auth failures bubble up as ``SfApiError``.
    """

    code = "sf_api_error"
    http_status = 502
