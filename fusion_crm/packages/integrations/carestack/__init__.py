"""CareStack integration — password-grant client + read-only sync helpers.

Public surface (Phase 1):

    CareStackClient      — async REST client with password-grant token flow
    CareStackTokens      — frozen dataclass holding the issued access token
    CareStackNotConnectedError, CareStackApiError — typed exceptions

Provider-specific resource calls go through ``CareStackClient.get(...)``
and ``CareStackClient.list(...)``. The client mirrors the structure of
``apps/web/lib/cs/auth.ts`` + ``apps/web/lib/cs/client.ts`` — same env
vars, same token-grant ROPC flow, same 401 → re-issue retry policy.

Domain-level mapping (CareStack location → ``tenant.location``,
appointment → ``ops.*``, patient → ``identity.person``) is NOT done
here — services in the consumer domain are responsible for that.
"""

from .client import CareStackClient, CareStackTokens
from .exceptions import CareStackApiError, CareStackNotConnectedError

__all__ = [
    "CareStackApiError",
    "CareStackClient",
    "CareStackNotConnectedError",
    "CareStackTokens",
]
