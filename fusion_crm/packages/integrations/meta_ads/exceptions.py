"""Typed exceptions for the Meta Ads client."""

from __future__ import annotations

from packages.core.exceptions import IntegrationError


class MetaAdsNotConnectedError(IntegrationError):
    """Credentials are missing or the access token is invalid/expired.

    Translated by the API middleware to a 409 so the operator sees a
    reconnect-needed signal rather than a 500.
    """

    code = "meta_ads_not_connected"
    http_status = 409


class MetaAdsApiError(IntegrationError):
    """A Meta Graph API call returned an error envelope or non-2xx."""

    code = "meta_ads_api_error"
    http_status = 502
