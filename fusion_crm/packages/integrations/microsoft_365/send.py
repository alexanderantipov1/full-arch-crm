"""GraphSendAdapter — protocol-shaped wrapper over ``MicrosoftClient``.

Mirrors ``packages.integrations.google_workspace.send.GmailSendAdapter``
so the outreach dispatcher can treat both providers symmetrically.

Per ADR-0004 §"Trust" Microsoft's ``/me/sendMail`` returns 202 with no
body — there is no equivalent of Gmail's ``messageId`` / ``threadId``
to persist. The adapter surfaces ``message_id=None`` deterministically;
the send row still has a usable correlation point via the
``Message-ID`` header we wrote into the RFC 5322 envelope. Stage 2
work may fetch the corresponding message from Sent Items.

The adapter consumes RFC 5322 bytes for parity with the Gmail
adapter. The underlying client converts to the Graph JSON shape via
``_rfc822_to_graph_message`` (see ``client.py``). New code paths in
the outreach service can shortcut this by building Graph bodies
directly and passing them to ``MicrosoftClient.send_message`` — that
is the explicit Stage 2 path.
"""

from __future__ import annotations

from typing import Any

from packages.core.logging import get_logger

# Reuse the error taxonomy + SendResult defined by the sibling
# provider so the dispatcher can ``isinstance``-check against one set
# of names regardless of provider. The taxonomy lives in
# google_workspace.send for historical reasons (it was the first
# adapter implemented); both adapters import from there. Long-term we
# could lift this into ``packages.integrations.base`` — not worth the
# churn at two providers.
from ..google_workspace.send import (
    PermanentError,
    RateLimitError,
    SendAdapterError,
    SendResult,
    TransientError,
)
from .client import MicrosoftClient
from .exceptions import MicrosoftAPIError, MicrosoftOAuthError

log = get_logger("integrations.microsoft_365.send")


class GraphSendAdapter:
    """Adapter over ``MicrosoftClient.send_message``."""

    provider = "microsoft_365"

    def __init__(self, client: MicrosoftClient) -> None:
        self._client = client

    async def send(self, rfc822_bytes: bytes) -> SendResult:
        try:
            body = await self._client.send_message(rfc822_bytes=rfc822_bytes)
        except MicrosoftOAuthError as exc:
            status = (
                exc.details.get("status")
                if isinstance(exc.details, dict)
                else None
            )
            raise PermanentError(
                "microsoft 365 OAuth grant revoked or refresh failed",
                provider=self.provider,
                status_code=status if isinstance(status, int) else None,
                details={"reason": "oauth_invalid"},
            ) from exc
        except MicrosoftAPIError as exc:
            status = (
                exc.details.get("status")
                if isinstance(exc.details, dict)
                else None
            )
            raise self._translate_status(status, exc) from exc

        # Graph returns 202 with no body — the client normalises to
        # {message_id: None, thread_id: None, raw: {...}}.
        message_id = body.get("message_id") if isinstance(body, dict) else None
        thread_id = body.get("thread_id") if isinstance(body, dict) else None
        log.info(
            "outreach.send.graph_ok",
            has_message_id=message_id is not None,
            has_thread_id=thread_id is not None,
        )
        return SendResult(
            message_id=message_id if isinstance(message_id, str) else None,
            thread_id=thread_id if isinstance(thread_id, str) else None,
            provider=self.provider,
        )

    def _translate_status(
        self, status: object, exc: MicrosoftAPIError
    ) -> SendAdapterError:
        status_int: int | None
        if isinstance(status, int):
            status_int = status
        elif isinstance(status, str) and status.isdigit():
            status_int = int(status)
        else:
            status_int = None

        details = dict(exc.details) if isinstance(exc.details, dict) else {}

        if status_int == 429:
            return RateLimitError(
                "microsoft graph rate limit hit",
                provider=self.provider,
                status_code=status_int,
                details=details,
            )
        if status_int is not None and 500 <= status_int < 600:
            return TransientError(
                "microsoft graph server error",
                provider=self.provider,
                status_code=status_int,
                details=details,
            )
        return PermanentError(
            "microsoft graph rejected the send",
            provider=self.provider,
            status_code=status_int,
            details=details,
        )


__all__ = [
    "GraphSendAdapter",
    # Re-export the shared taxonomy so callers importing from this
    # subpackage do not need to know it lives next door.
    "PermanentError",
    "RateLimitError",
    "SendAdapterError",
    "SendResult",
    "TransientError",
]


# Defensive: silence linters about the unused ``Any`` import — it is
# kept for future Graph-message bodies threading through the adapter.
_ = Any
