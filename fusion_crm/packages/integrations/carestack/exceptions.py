"""CareStack integration exceptions.

These are domain-typed errors. The API middleware translates them into
the standard JSON envelope via the ``PlatformError`` machinery — never
raise raw ``HTTPException`` from the client or from services that
consume it.
"""

from __future__ import annotations

from packages.core.exceptions import IntegrationError


class CareStackNotConnectedError(IntegrationError):
    """CareStack is not reachable with the current credentials.

    Raised when:
      * required env vars are missing / empty
      * the password-grant token endpoint returns 4xx
      * a 401 from the API is followed by a re-grant that also fails

    The API translates this to HTTP 409 so the operator UI can prompt
    the user to (re-)enter credentials, rather than treating it as a
    5xx outage.
    """

    code = "carestack_not_connected"
    http_status = 409


class CareStackApiError(IntegrationError):
    """Non-401 CareStack API failure (4xx other than 401, or 5xx).

    A bare 401 alone is NOT this error — the client re-grants once
    first. Only persistent or non-auth failures bubble up as
    ``CareStackApiError``.
    """

    code = "carestack_api_error"
    http_status = 502
