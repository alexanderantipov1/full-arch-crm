"""Tests for ``GmailSendAdapter`` (ENG-132).

Translates Gmail API responses + ``GoogleAPIError`` /
``GoogleOAuthError`` into the adapter error taxonomy.
External traffic is stubbed with ``respx``.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from packages.integrations.google_workspace.client import (
    GMAIL_API_BASE,
    SEND_PATH,
    GoogleWorkspaceClient,
)
from packages.integrations.google_workspace.send import (
    GmailSendAdapter,
    PermanentError,
    RateLimitError,
    TransientError,
)


def _client(http: httpx.AsyncClient) -> GoogleWorkspaceClient:
    # We bypass the oauth client because the adapter never refreshes —
    # it surfaces the underlying status to the dispatcher.
    return GoogleWorkspaceClient(
        access_token="ya29.test",  # noqa: S106 — fixture
        expires_at=None,
        oauth_client=None,  # type: ignore[arg-type]
        on_refresh=None,
        refresh_token=None,
        http=http,
    )


async def test_send_returns_message_id_on_200() -> None:
    async with httpx.AsyncClient() as http, respx.mock(
        assert_all_called=True
    ) as rx:
        rx.post(f"{GMAIL_API_BASE}{SEND_PATH}").mock(
            return_value=httpx.Response(
                200, json={"id": "msg-1", "threadId": "thr-1"}
            )
        )
        adapter = GmailSendAdapter(_client(http))
        result = await adapter.send(b"RFC822 test bytes\r\n")
        assert result.message_id == "msg-1"
        assert result.thread_id == "thr-1"
        assert result.provider == "google_workspace"


async def test_send_raises_rate_limit_on_429() -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.post(f"{GMAIL_API_BASE}{SEND_PATH}").mock(
            return_value=httpx.Response(
                429, json={"error": {"message": "quotaExceeded"}}
            )
        )
        adapter = GmailSendAdapter(_client(http))
        with pytest.raises(RateLimitError) as exc_info:
            await adapter.send(b"RFC822")
        assert exc_info.value.status_code == 429
        assert exc_info.value.provider == "google_workspace"


async def test_send_raises_transient_on_5xx() -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.post(f"{GMAIL_API_BASE}{SEND_PATH}").mock(
            return_value=httpx.Response(503, json={"error": "unavailable"})
        )
        adapter = GmailSendAdapter(_client(http))
        with pytest.raises(TransientError) as exc_info:
            await adapter.send(b"RFC822")
        assert exc_info.value.status_code == 503


async def test_send_raises_permanent_on_400() -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.post(f"{GMAIL_API_BASE}{SEND_PATH}").mock(
            return_value=httpx.Response(400, json={"error": "bad request"})
        )
        adapter = GmailSendAdapter(_client(http))
        with pytest.raises(PermanentError) as exc_info:
            await adapter.send(b"RFC822")
        assert exc_info.value.status_code == 400
