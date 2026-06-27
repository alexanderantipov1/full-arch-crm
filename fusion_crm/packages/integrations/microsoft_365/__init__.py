"""Microsoft 365 integration — OAuth + Graph sendMail (ENG-131).

Public surface (mirrors ``google_workspace`` for parity):

    MicrosoftOAuthClient — authorize URL + code exchange + refresh + id_token
    MicrosoftClient      — Graph API client (``send_message``, ``get_profile``)
    MicrosoftOAuthError, MicrosoftAPIError, PersonalAccountBlocked — errors

Compliance gate (per ADR-0004 §"HIPAA compliance gate"):

  Personal MSA accounts (``@outlook.com`` / ``@hotmail.com`` / etc.)
  are NOT BAA-eligible. The ``exchange_code`` flow inspects the
  returned ``id_token`` and rejects any grant whose ``tid`` claim is
  Microsoft's special "consumer" tenant id
  (``9188040d-6c67-4c5b-b112-36a304b66dad``) OR whose
  ``preferred_username`` host is one of the well-known consumer
  domains. Both raise ``PersonalAccountBlocked``.
"""

from .client import MicrosoftClient
from .exceptions import MicrosoftAPIError, MicrosoftOAuthError, PersonalAccountBlocked
from .oauth import MicrosoftOAuthClient, MicrosoftTokens

__all__ = [
    "MicrosoftAPIError",
    "MicrosoftClient",
    "MicrosoftOAuthClient",
    "MicrosoftOAuthError",
    "MicrosoftTokens",
    "PersonalAccountBlocked",
]
