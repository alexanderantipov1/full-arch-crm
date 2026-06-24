"""Signed inbound Mattermost callbacks (ENG-438, Block E).

PUBLIC, UNAUTHENTICATED endpoints — they are called by the Mattermost server,
not by our staff frontend, so they do NOT depend on ``get_principal``. The
shared Mattermost TOKEN IS the authentication: every request is verified by
constant-time-comparing its presented token against the tenant's stored
``mattermost`` / ``webhook_secret`` credential. This mirrors the
unauthenticated outreach tracking routes (the token is the auth).

Two handlers:

* ``POST /integrations/chat/mattermost/webhook`` — outgoing webhooks
  (thread replies / channel messages). Body is form-encoded OR JSON.
* ``POST /integrations/chat/mattermost/action`` — interactive message
  button actions. Body is JSON; the token rides in ``context.token``.

Both are THIN (invariant #5): read body → parse → verify token (resolve
tenant) → capture verbatim into ``ingest.raw_event`` → return 200 fast
(Mattermost expects < 3s). Deep domain mapping happens off the hot path in
``apps.worker.jobs.chat_inbound_map``.

SECURITY — fail closed:

* Missing or non-matching token → 401, NOTHING captured.
* The token is NEVER logged (no log line in this module includes it).
* An empty / URL-verification ping (no token, no ids) returns 200 without
  capture and without requiring a token.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db
from packages.core.exceptions import PlatformError
from packages.core.logging import get_logger
from packages.ingest.schemas import RawEventIn
from packages.ingest.service import IngestService
from packages.integrations.chat.inbound import (
    INBOUND_SOURCE,
    ParsedInbound,
    is_health_check,
    parse_action,
    parse_webhook,
    redact_auth_tokens,
    resolve_tenant_from_token,
)
from packages.tenant.credential_service import IntegrationCredentialService

router = APIRouter(prefix="/integrations/chat/mattermost", tags=["chat-inbound"])

log = get_logger("api.chat_inbound")


class InboundUnauthorizedError(PlatformError):
    """Presented Mattermost token did not match any active tenant secret.

    A single opaque 401 for every reject path (missing token, wrong token,
    no credential configured) so a caller cannot distinguish the cases.
    """

    code = "unauthorized"
    http_status = 401


async def _read_body(request: Request) -> dict[str, Any]:
    """Decode the inbound body as a dict, accepting JSON or form-encoded.

    Mattermost outgoing webhooks default to ``application/x-www-form-urlencoded``;
    interactive actions and some webhook configs send JSON. We branch on the
    content type and fall back to a tolerant parse so a missing/odd header
    never crashes the handler (it would just resolve to no token → 401).
    """
    content_type = request.headers.get("content-type", "")
    raw = await request.body()
    if not raw:
        return {}

    if "application/json" in content_type:
        try:
            parsed = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in (
        content_type
    ):
        form = await request.form()
        return {key: value for key, value in form.items() if isinstance(value, str)}

    # Unknown content type: try JSON, then fall through to empty (→ 401).
    try:
        parsed = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


async def _verify_and_capture(
    parsed: ParsedInbound,
    db: AsyncSession,
) -> dict[str, Any]:
    """Resolve tenant from the token then capture the verbatim body.

    Raises :class:`InboundUnauthorizedError` (→ 401) when the token does not
    match any active tenant secret — fail closed, nothing captured. On
    success captures one ``ingest.raw_event`` row and returns a minimal
    200 body.
    """
    credentials = IntegrationCredentialService(db)
    tenant_id = await resolve_tenant_from_token(credentials, parsed.token)
    if tenant_id is None:
        # No log of the token. Opaque 401 for every reject path.
        log.warning(
            "chat_inbound.rejected",
            event_type=parsed.event_type,
            reason="token_unrecognised",
        )
        raise InboundUnauthorizedError("invalid inbound token")

    ingest = IngestService(db)
    # The verbatim body is the forensic copy — but the live Mattermost shared
    # TOKEN must never be persisted (it is the same secret the next request
    # presents). Redact ONLY the auth token(s) from a COPY; everything else is
    # captured verbatim.
    await ingest.capture(
        tenant_id,
        RawEventIn(
            source=INBOUND_SOURCE,
            event_type=parsed.event_type,
            external_id=parsed.external_id,
            received_at=datetime.now(UTC),
            payload=redact_auth_tokens(parsed.payload),
        ),
    )
    log.info(
        "chat_inbound.captured",
        tenant_id=str(tenant_id),
        event_type=parsed.event_type,
        has_external_id=parsed.external_id is not None,
    )
    # Mattermost accepts an empty 200 (or an optional ``{"text": ...}``).
    # Keep it minimal — the response posts nothing back to the channel.
    return {}


@router.post("/webhook", include_in_schema=False)
async def mattermost_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Mattermost OUTGOING webhook (thread reply / channel message)."""
    body = await _read_body(request)
    if is_health_check(body):
        return {}
    return await _verify_and_capture(parse_webhook(body), db)


@router.post("/action", include_in_schema=False)
async def mattermost_action(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Mattermost interactive message button action."""
    body = await _read_body(request)
    if is_health_check(body):
        return {}
    return await _verify_and_capture(parse_action(body), db)


__all__ = ["router"]
