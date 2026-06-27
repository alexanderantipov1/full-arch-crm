"""Typed exceptions for the GA4 client."""

from __future__ import annotations

from packages.core.exceptions import IntegrationError


class GoogleAnalyticsNotConnectedError(IntegrationError):
    """Credentials missing or the OAuth refresh failed (→ 409)."""

    code = "google_analytics_not_connected"
    http_status = 409


class GoogleAnalyticsApiError(IntegrationError):
    """A GA4 Data API call returned a non-2xx response."""

    code = "google_analytics_api_error"
    http_status = 502
