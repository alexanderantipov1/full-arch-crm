"""Meta (Facebook) Ads provider plumbing — read-only Graph client (v21.0).

Public surface: :class:`MetaAdsClient` and the typed exceptions. See
``packages/integrations/meta_ads/CLAUDE.md``.
"""

from __future__ import annotations

from .client import MetaAdsClient
from .exceptions import MetaAdsApiError, MetaAdsNotConnectedError

__all__ = [
    "MetaAdsApiError",
    "MetaAdsClient",
    "MetaAdsNotConnectedError",
]
