"""Typed exceptions for the Google Search Console client."""

from __future__ import annotations

from packages.core.exceptions import IntegrationError


class GoogleSearchConsoleNotConnectedError(IntegrationError):
    """Credentials missing, OAuth refresh failed, or no verified site (→ 409)."""

    code = "google_search_console_not_connected"
    http_status = 409


class GoogleSearchConsoleApiError(IntegrationError):
    """A Search Console (Webmasters v3) call returned a non-2xx response."""

    code = "google_search_console_api_error"
    http_status = 502
