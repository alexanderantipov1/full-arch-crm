"""Tests for ``GraphSendAdapter`` (ENG-132).

Translates Graph API responses + ``MicrosoftAPIError`` /
``MicrosoftOAuthError`` into the adapter error taxonomy.
External traffic is stubbed with ``respx``.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from packages.integrations.microsoft_365.client import (
    GRAPH_API_BASE,
    SEND_MAIL_PATH,
    MicrosoftClient,
)
from packages.integrations.microsoft_365.send import (
    GraphSendAdapter,
    PermanentError,
    RateLimitError,
    TransientError,
)

# Minimal RFC 5322 payload — has the required headers so the client's
# internal ``_rfc822_to_graph_message`` produces a valid body.
_RFC822 = (
    b"From: info@galleriaoms.com\r\n"
    b"To: patient@example.com\r\n"
    b"Subject: Hello\r\n"
    b"Content-Type: text/plain; charset=utf-8\r\n"
    b"\r\n"
    b"Body"
)


def _client(http: httpx.AsyncClient) -> MicrosoftClient:
    return MicrosoftClient(
        access_token="ey.test",  # noqa: S106 — fixture
        expires_at=None,
        oauth_client=None,  # type: ignore[arg-type]
        on_refresh=None,
        refresh_token=None,
        http=http,
    )


async def test_send_returns_none_message_id_on_202() -> None:
    """Graph ``/me/sendMail`` returns 202 with empty body."""
    async with httpx.AsyncClient() as http, respx.mock(
        assert_all_called=True
    ) as rx:
        rx.post(f"{GRAPH_API_BASE}{SEND_MAIL_PATH}").mock(
            return_value=httpx.Response(202)
        )
        adapter = GraphSendAdapter(_client(http))
        result = await adapter.send(_RFC822)
        assert result.message_id is None
        assert result.thread_id is None
        assert result.provider == "microsoft_365"


async def test_send_raises_rate_limit_on_429() -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.post(f"{GRAPH_API_BASE}{SEND_MAIL_PATH}").mock(
            return_value=httpx.Response(429, json={"error": "throttled"})
        )
        adapter = GraphSendAdapter(_client(http))
        with pytest.raises(RateLimitError) as exc_info:
            await adapter.send(_RFC822)
        assert exc_info.value.status_code == 429
        assert exc_info.value.provider == "microsoft_365"


async def test_send_raises_transient_on_5xx() -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.post(f"{GRAPH_API_BASE}{SEND_MAIL_PATH}").mock(
            return_value=httpx.Response(503, json={"error": "unavailable"})
        )
        adapter = GraphSendAdapter(_client(http))
        with pytest.raises(TransientError) as exc_info:
            await adapter.send(_RFC822)
        assert exc_info.value.status_code == 503


async def test_send_raises_permanent_on_400() -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.post(f"{GRAPH_API_BASE}{SEND_MAIL_PATH}").mock(
            return_value=httpx.Response(400, json={"error": "bad request"})
        )
        adapter = GraphSendAdapter(_client(http))
        with pytest.raises(PermanentError) as exc_info:
            await adapter.send(_RFC822)
        assert exc_info.value.status_code == 400
