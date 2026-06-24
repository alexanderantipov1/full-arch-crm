"""ENG-502 — secrets must never reach a log sink.

Two layers are exercised:

1. ``configure_logging`` clamps the ``httpx`` / ``httpcore`` stdlib loggers to
   WARNING so httpx's INFO ``HTTP Request: <method> <url> ...`` line — whose URL
   can carry an OAuth/access token in the query string — never emits.
2. ``redact_url`` masks secret-bearing query params for any URL we *do* choose
   to log.
"""

from __future__ import annotations

import logging

from packages.core.logging import configure_logging, redact_url


def test_redact_url_masks_secret_query_params() -> None:
    url = (
        "https://graph.facebook.com/v21.0/act_1/insights"
        "?after=CURSOR&access_token=EAAsecret123&limit=500"
    )
    out = redact_url(url)
    assert "EAAsecret123" not in out
    assert "access_token=%2A%2A%2A" in out or "access_token=***" in out
    # Non-secret params + path are preserved so the line stays useful.
    assert "after=CURSOR" in out
    assert "limit=500" in out
    assert "/act_1/insights" in out


def test_redact_url_masks_oauth_refresh_params() -> None:
    url = (
        "https://oauth2.googleapis.com/token"
        "?client_secret=abc&refresh_token=rt-xyz&code=authcode&grant_type=refresh_token"
    )
    out = redact_url(url)
    for secret in ("abc", "rt-xyz", "authcode"):
        assert secret not in out
    # grant_type is not a secret and survives.
    assert "grant_type=refresh_token" in out


def test_redact_url_no_query_is_passthrough() -> None:
    url = "https://googleads.googleapis.com/v23/customers/123/googleAds:search"
    assert redact_url(url) == url


def test_configure_logging_clamps_httpx_loggers() -> None:
    configure_logging()
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
    # The INFO request line is below the clamp, so it would be filtered.
    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)
    # Real errors still surface.
    assert logging.getLogger("httpx").isEnabledFor(logging.WARNING)
