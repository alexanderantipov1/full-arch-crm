"""Google Ads provider plumbing — read-only REST client (API v23).

Public surface: :class:`GoogleAdsClient` and the typed exceptions. See
``packages/integrations/google_ads/CLAUDE.md``.
"""

from __future__ import annotations

from .client import GoogleAdsClient, GoogleAdsToken
from .exceptions import GoogleAdsApiError, GoogleAdsNotConnectedError

__all__ = [
    "GoogleAdsApiError",
    "GoogleAdsClient",
    "GoogleAdsNotConnectedError",
    "GoogleAdsToken",
]
