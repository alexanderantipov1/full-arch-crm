"""Google Search Console provider plumbing — read-only Webmasters v3 client.

Public surface: :class:`GoogleSearchConsoleClient` and the typed exceptions.
See ``packages/integrations/google_search_console/CLAUDE.md``.
"""

from __future__ import annotations

from .client import GoogleSearchConsoleClient, GoogleToken
from .exceptions import (
    GoogleSearchConsoleApiError,
    GoogleSearchConsoleNotConnectedError,
)

__all__ = [
    "GoogleSearchConsoleApiError",
    "GoogleSearchConsoleClient",
    "GoogleSearchConsoleNotConnectedError",
    "GoogleToken",
]
