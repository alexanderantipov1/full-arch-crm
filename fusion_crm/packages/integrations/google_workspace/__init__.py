"""Google Workspace integration — OAuth + Gmail send (ENG-131).

Public surface:

    GoogleOAuthClient   — authorize URL + code exchange + refresh + id_token
    GoogleWorkspaceClient — Gmail API client (``send_message``, ``get_profile``)
    GoogleOAuthError, GoogleAPIError, PersonalAccountBlocked — typed errors

Compliance gate (per ADR-0004 §"HIPAA compliance gate"):

  Personal ``@gmail.com`` accounts are NOT BAA-eligible. The
  ``exchange_code`` flow inspects the returned ``id_token`` and
  rejects any grant whose decoded ``hd`` claim (Workspace domain) is
  empty. A second belt-and-braces check rejects emails whose host is
  one of the well-known consumer domains. Both raise
  ``PersonalAccountBlocked`` so the API can surface a 403 with an
  operator-readable message.

Token storage:

  ``GoogleWorkspaceClient.from_credential(credential_id)`` reads the
  decrypted payload via ``IntegrationCredentialService.read_by_id``
  and auto-refreshes on 401. There is intentionally no ``from_env``
  factory — every call site must go through the tenant credential
  store (multi-mailbox routing depends on it).
"""

from .client import GoogleWorkspaceClient
from .exceptions import GoogleAPIError, GoogleOAuthError, PersonalAccountBlocked
from .oauth import GoogleOAuthClient, GoogleTokens

__all__ = [
    "GoogleAPIError",
    "GoogleOAuthClient",
    "GoogleOAuthError",
    "GoogleTokens",
    "GoogleWorkspaceClient",
    "PersonalAccountBlocked",
]
