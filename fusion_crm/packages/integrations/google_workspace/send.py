"""GmailSendAdapter — protocol-shaped wrapper over ``GoogleWorkspaceClient``.

Per ENG-132 the outreach send pipeline calls adapters via a small
protocol so neither side knows about the other's internals. The
adapter:

  - takes RFC 5322 bytes (built by ``packages.outreach.email_builder``)
  - asks the Gmail client to ``send_message``
  - converts provider-specific errors into a typed error taxonomy
    (``RateLimitError``, ``TransientError``, ``PermanentError``) the
    dispatcher worker understands

We deliberately keep the adapter narrow — no template rendering, no
suppression checks, no rate-limit gate. Those are owned by the
outreach service / dispatcher. The adapter exists so the outreach
domain does not depend on the Gmail API surface directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from packages.core.logging import get_logger

from .client import GoogleWorkspaceClient
from .exceptions import GoogleAPIError, GoogleOAuthError

log = get_logger("integrations.google_workspace.send")


# --- Send-result envelope (provider-agnostic) ----------------------------


@dataclass(frozen=True, slots=True)
class SendResult:
    """Outcome of one successful send.

    ``message_id`` and ``thread_id`` are provider-issued identifiers
    when available. Gmail returns both; Microsoft Graph's
    ``/me/sendMail`` returns neither — adapters surface ``None`` there
    and the dispatcher persists what it has.
    """

    message_id: str | None
    thread_id: str | None
    provider: str


# --- Error taxonomy ------------------------------------------------------


class SendAdapterError(Exception):
    """Base for adapter-translated send failures."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        status_code: int | None = None,
        retry_after_seconds: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.details = details or {}


class RateLimitError(SendAdapterError):
    """Provider returned 429 / quota exceeded.

    The dispatcher backs off and reschedules; persistent 429 over the
    retry budget is converted to a ``failed`` queue row.
    """


class TransientError(SendAdapterError):
    """Provider returned 5xx or another retry-eligible failure.

    Retries with exponential backoff up to the per-job cap.
    """


class PermanentError(SendAdapterError):
    """Provider returned a non-retriable 4xx (other than 429).

    The send is marked ``failed`` immediately. Examples: malformed
    message, recipient address rejected, mailbox scope revoked.
    """


class SendAdapter(Protocol):
    """Minimum surface the outreach dispatcher depends on.

    Implementations live in each integration subpackage. The
    dispatcher resolves which adapter to call by ``provider_kind`` on
    the credential row.
    """

    async def send(self, rfc822_bytes: bytes) -> SendResult: ...


# --- GmailSendAdapter ----------------------------------------------------


class GmailSendAdapter:
    """Adapter over ``GoogleWorkspaceClient.send_message``.

    Translates ``GoogleAPIError`` / ``GoogleOAuthError`` (which carry
    HTTP status + body fragments) into the adapter error taxonomy.
    The dispatcher decides what to do with each class — the adapter
    is intentionally policy-free.
    """

    provider = "google_workspace"

    def __init__(self, client: GoogleWorkspaceClient) -> None:
        self._client = client

    async def send(self, rfc822_bytes: bytes) -> SendResult:
        try:
            body = await self._client.send_message(rfc822_bytes)
        except GoogleOAuthError as exc:
            # Refresh-after-401 already attempted inside the client;
            # this surface means the grant itself is gone. Treat as
            # permanent so the operator UI prompts for reconnect.
            raise PermanentError(
                "gmail OAuth grant revoked or refresh failed",
                provider=self.provider,
                status_code=exc.details.get("status") if isinstance(exc.details, dict) else None,
                details={"reason": "oauth_invalid"},
            ) from exc
        except GoogleAPIError as exc:
            status = (
                exc.details.get("status")
                if isinstance(exc.details, dict)
                else None
            )
            raise self._translate_status(status, exc) from exc

        message_id = body.get("message_id") if isinstance(body, dict) else None
        thread_id = body.get("thread_id") if isinstance(body, dict) else None
        log.info(
            "outreach.send.gmail_ok",
            has_message_id=message_id is not None,
            has_thread_id=thread_id is not None,
        )
        return SendResult(
            message_id=message_id if isinstance(message_id, str) else None,
            thread_id=thread_id if isinstance(thread_id, str) else None,
            provider=self.provider,
        )

    def _translate_status(
        self, status: object, exc: GoogleAPIError
    ) -> SendAdapterError:
        """Map a Gmail HTTP status into the adapter taxonomy."""
        status_int: int | None
        if isinstance(status, int):
            status_int = status
        elif isinstance(status, str) and status.isdigit():
            status_int = int(status)
        else:
            status_int = None

        if status_int == 429:
            return RateLimitError(
                "gmail rate limit hit",
                provider=self.provider,
                status_code=status_int,
                details=dict(exc.details) if isinstance(exc.details, dict) else {},
            )
        if status_int is not None and 500 <= status_int < 600:
            return TransientError(
                "gmail server error",
                provider=self.provider,
                status_code=status_int,
                details=dict(exc.details) if isinstance(exc.details, dict) else {},
            )
        return PermanentError(
            "gmail API rejected the send",
            provider=self.provider,
            status_code=status_int,
            details=dict(exc.details) if isinstance(exc.details, dict) else {},
        )


__all__ = [
    "GmailSendAdapter",
    "PermanentError",
    "RateLimitError",
    "SendAdapter",
    "SendAdapterError",
    "SendResult",
    "TransientError",
]
