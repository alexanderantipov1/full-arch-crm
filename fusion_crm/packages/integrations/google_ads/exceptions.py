"""Typed exceptions for the Google Ads client."""

from __future__ import annotations

from packages.core.exceptions import IntegrationError


class GoogleAdsNotConnectedError(IntegrationError):
    """Credentials are missing or the OAuth refresh failed.

    Translated by the API middleware to a 409 so the operator sees a
    reconnect-needed signal rather than a 500.
    """

    code = "google_ads_not_connected"
    http_status = 409


class GoogleAdsApiError(IntegrationError):
    """A Google Ads REST call returned a non-2xx response."""

    code = "google_ads_api_error"
    http_status = 502
