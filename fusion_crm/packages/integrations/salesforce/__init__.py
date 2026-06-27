"""Salesforce integration — SOQL client + token reader.

Public surface:
    SfClient        — async REST client; ``soql(query)`` + auto-refresh on 401
    SfTokens        — frozen dataclass holding OAuth tokens
    read_dev_tokens — Phase 1 token reader (apps/web/.sf-tokens.json)
    SfNotConnectedError, SfApiError — typed exceptions
"""

from .client import SfClient
from .exceptions import SfApiError, SfNotConnectedError
from .tokens import SfTokens, read_dev_tokens

__all__ = [
    "SfApiError",
    "SfClient",
    "SfNotConnectedError",
    "SfTokens",
    "read_dev_tokens",
]
