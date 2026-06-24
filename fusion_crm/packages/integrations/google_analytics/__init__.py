"""Google Analytics 4 provider plumbing — read-only Data API client (v1beta).

Public surface: :class:`GoogleAnalyticsClient` and the typed exceptions. See
``packages/integrations/google_analytics/CLAUDE.md``.
"""

from __future__ import annotations

from .client import GoogleAnalyticsClient, GoogleToken
from .exceptions import GoogleAnalyticsApiError, GoogleAnalyticsNotConnectedError

__all__ = [
    "GoogleAnalyticsApiError",
    "GoogleAnalyticsClient",
    "GoogleAnalyticsNotConnectedError",
    "GoogleToken",
]
