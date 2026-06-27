"""Bounce detection — poll every active mailbox for NDR messages.

Per ENG-134 + ADR-0004 §"Tracking" decision #3. The send-side
providers (Gmail, Microsoft Graph) DO NOT push bounce notifications
into our system (Gmail's push API requires Pub/Sub plumbing; Graph
change-notifications similarly require subscriptions). For Stage 1
we poll each connected mailbox every 15 minutes, scan the last 24h
for delivery-status notifications (DSNs / NDRs), match them back to
the original ``outreach.send`` row by ``Message-ID`` (via the
``In-Reply-To`` header on the NDR), mark the send as ``bounced``,
and add the recipient to ``outreach.suppression`` with reason
``bounce_hard``.

Why ``Message-ID`` matching:

  - Both Gmail and Outlook reproduce the bounced message's
    ``Message-ID`` in the NDR's ``In-Reply-To`` / ``References``
    headers (RFC 3464 §3.4).
  - We already persist the Gmail-returned ``id`` on ``send.message_id``
    via ENG-132's success path. For Microsoft Graph (which does not
    return an id on send), the column may be null — those sends
    cannot be matched and the NDR is logged at INFO + skipped.

Audit:

  - One ``outreach.email.bounced`` row per matched NDR. ``extra``
    carries ``send_id``, ``credential_id``, ``match_strategy``
    (``in_reply_to`` | ``failed_recipients``) — no PII, no body,
    no email plaintext (we use ``recipient_hash`` for correlation).
  - One ``outreach.suppression.add`` row per added suppression
    (written by ``SuppressionService.add_suppression`` itself).
  - No audit row for unmatched NDRs — they are common (older sends
    pre-dating the worker, bounces from a different system, etc.).

Idempotency: the worker re-runs every 15 min. If an NDR was
already processed, the matched send row is already ``bounced`` and
the suppression row already exists; both writes short-circuit (the
send-status update is a no-op, the suppression insert returns the
existing row).

Provider notes:

  - **Gmail:** queried with ``q=from:mailer-daemon@* newer_than:1d``.
    The ``mailer-daemon@*`` wildcard catches the deterministic Gmail
    bounce sender (``mailer-daemon@googlemail.com``) and forwarders.
    Newer NDRs have an ``X-Failed-Recipients`` header listing the
    bounced address explicitly.
  - **Microsoft Graph:** filtered with
    ``startsWith(from/emailAddress/address, 'postmaster@')`` — the
    canonical Microsoft NDR sender. NDR bodies + headers expose the
    bounced recipient via Diagnostic Reports; we extract the
    original ``Message-ID`` from ``internetMessageHeaders``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.service import AuditService
from packages.core.logging import get_logger
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.integrations.google_workspace.client import GoogleWorkspaceClient
from packages.integrations.google_workspace.exceptions import (
    GoogleAPIError,
    GoogleOAuthError,
)
from packages.integrations.microsoft_365.client import MicrosoftClient
from packages.integrations.microsoft_365.exceptions import (
    MicrosoftAPIError,
    MicrosoftOAuthError,
)
from packages.outreach.models import SendStatus
from packages.outreach.repository import SendRepository
from packages.outreach.send_service import _hash_email
from packages.outreach.service import (
    AUDIT_EMAIL_BOUNCED,
    SuppressionService,
)
from packages.tenant.credential_service import IntegrationCredentialService

log = get_logger("worker.bounce_poll")


# Provider kinds we know how to poll.
_GMAIL = "google_workspace"
_GRAPH = "microsoft_365"

# Bounded so a single tick stays under the arq job timeout. NDRs
# trickle in over hours; 100 per mailbox per tick is plenty.
_GMAIL_PAGE_SIZE = 100
_GRAPH_PAGE_SIZE = 50

# Gmail query — last 24h, bounce-canonical From addresses.
_GMAIL_QUERY = "from:mailer-daemon@* newer_than:1d"
# Graph filter template — we substitute ``receivedDateTime`` 24h ago
# at call time so a freshly-connected mailbox does not pull every
# historical NDR.
_GRAPH_FILTER_TEMPLATE = (
    "startsWith(from/emailAddress/address, 'postmaster@') "
    "and receivedDateTime ge {since_iso}"
)


def _system_principal(tenant_id: TenantId) -> Principal:
    """Synthesised principal for worker-side audit + service calls."""
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
        context={"source": "worker.bounce_poll"},
    )


async def poll_bounces(ctx: dict) -> dict[str, int]:
    """One bounce-poll pass across every active mailbox credential.

    Scheduled every 15 minutes via the arq cron config. The summary
    is returned for arq's keep_result so operators can see how many
    matches occurred per tick during incident response.
    """
    _ = ctx
    summary: dict[str, int] = {
        "candidates": 0,
        "matched": 0,
        "unmatched": 0,
        "errors": 0,
        "credentials_polled": 0,
    }

    # We import the tenant service lazily so the worker cold-start
    # stays light when bounce polling is disabled (e.g. in a test
    # harness that has no tenant rows).
    from packages.tenant.service import TenantService

    async with async_session() as session:
        tenant_rows = await TenantService(session).list_tenants()
        tenant_ids = [TenantId(t.id) for t in tenant_rows]

    if not tenant_ids:
        log.info("bounce_poll.no_tenants")
        return summary

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0)
    ) as http:
        for tenant_id in tenant_ids:
            tenant_summary = await _poll_one_tenant(
                tenant_id=tenant_id, http=http
            )
            for k, v in tenant_summary.items():
                summary[k] = summary.get(k, 0) + v

    log.info("bounce_poll.tick", summary=summary)
    return summary


async def _poll_one_tenant(
    *, tenant_id: TenantId, http: httpx.AsyncClient
) -> dict[str, int]:
    """Poll every active mailbox credential under ``tenant_id``."""
    out: dict[str, int] = {
        "candidates": 0,
        "matched": 0,
        "unmatched": 0,
        "errors": 0,
        "credentials_polled": 0,
    }

    async with async_session() as session:
        credentials = IntegrationCredentialService(session)
        rows = await credentials.list_for_tenant(tenant_id)
    active = [
        r
        for r in rows
        if r.provider_kind in {_GMAIL, _GRAPH} and r.status == "active"
    ]
    if not active:
        return out

    principal = _system_principal(tenant_id)

    for credential_row in active:
        out["credentials_polled"] += 1
        try:
            if credential_row.provider_kind == _GMAIL:
                per_cred = await _poll_gmail(
                    tenant_id=tenant_id,
                    credential_id=credential_row.id,
                    principal=principal,
                    http=http,
                )
            else:
                per_cred = await _poll_graph(
                    tenant_id=tenant_id,
                    credential_id=credential_row.id,
                    principal=principal,
                    http=http,
                )
        except (
            GoogleAPIError,
            GoogleOAuthError,
            MicrosoftAPIError,
            MicrosoftOAuthError,
        ) as exc:
            # Provider-side issues should not crash the worker — log
            # at WARNING, increment ``errors``, and continue with the
            # next credential.
            log.warning(
                "bounce_poll.provider_error",
                tenant_id=str(tenant_id),
                credential_id=str(credential_row.id),
                provider_kind=credential_row.provider_kind,
                error_type=type(exc).__name__,
            )
            out["errors"] += 1
            continue
        for k, v in per_cred.items():
            out[k] = out.get(k, 0) + v
    return out


# --- Gmail polling --------------------------------------------------------


async def _poll_gmail(
    *,
    tenant_id: TenantId,
    credential_id: UUID,
    principal: Principal,
    http: httpx.AsyncClient,
) -> dict[str, int]:
    """List + fetch + match NDRs in one Gmail mailbox."""
    out = {"candidates": 0, "matched": 0, "unmatched": 0}

    async with async_session() as session:
        client = await GoogleWorkspaceClient.from_credential(
            credential_id, session=session, principal=principal, http=http
        )
        try:
            listed = await client.get_messages_list(
                query=_GMAIL_QUERY, max_results=_GMAIL_PAGE_SIZE
            )
        finally:
            await client.close()

    messages = listed.get("messages") or []
    if not isinstance(messages, list):
        return out
    out["candidates"] = len(messages)

    for entry in messages:
        if not isinstance(entry, dict):
            continue
        msg_id = entry.get("id")
        if not isinstance(msg_id, str) or not msg_id:
            continue

        async with async_session() as session:
            inner_client = await GoogleWorkspaceClient.from_credential(
                credential_id,
                session=session,
                principal=principal,
                http=http,
            )
            try:
                metadata = await inner_client.get_message(
                    msg_id,
                    format_="metadata",
                    metadata_headers=[
                        "In-Reply-To",
                        "References",
                        "X-Failed-Recipients",
                        "Subject",
                        "From",
                    ],
                )
            finally:
                await inner_client.close()

            headers = _gmail_headers(metadata)
            in_reply_to = _extract_in_reply_to_gmail(headers)
            failed_rcpts = _extract_failed_recipients_gmail(headers)

            matched = await _try_match_and_record(
                session=session,
                tenant_id=tenant_id,
                credential_id=credential_id,
                principal=principal,
                in_reply_to=in_reply_to,
                failed_recipients=failed_rcpts,
            )
            if matched:
                out["matched"] += 1
            else:
                out["unmatched"] += 1
                log.info(
                    "bounce_poll.gmail.unmatched",
                    tenant_id=str(tenant_id),
                    credential_id=str(credential_id),
                    has_in_reply_to=bool(in_reply_to),
                    has_failed_recipients=bool(failed_rcpts),
                )

    return out


def _gmail_headers(metadata: dict[str, Any]) -> dict[str, str]:
    """Flatten Gmail's ``payload.headers`` array into a name → value map.

    Header names are case-insensitive; we lowercase the keys so the
    caller does not have to match Gmail's exact casing.
    """
    payload = metadata.get("payload") if isinstance(metadata, dict) else None
    if not isinstance(payload, dict):
        return {}
    header_list = payload.get("headers")
    if not isinstance(header_list, list):
        return {}
    out: dict[str, str] = {}
    for entry in header_list:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        value = entry.get("value")
        if isinstance(name, str) and isinstance(value, str):
            out[name.strip().lower()] = value
    return out


def _extract_in_reply_to_gmail(headers: dict[str, str]) -> str | None:
    """Return the ``In-Reply-To`` value (Message-ID with angle brackets)."""
    raw = headers.get("in-reply-to")
    if not raw:
        # Fall back to References — RFC 3464 NDRs typically include
        # both; In-Reply-To is the canonical "this references that".
        raw = headers.get("references")
    if not isinstance(raw, str):
        return None
    return raw.strip() or None


def _extract_failed_recipients_gmail(headers: dict[str, str]) -> list[str]:
    """Return the addresses in the ``X-Failed-Recipients`` header."""
    raw = headers.get("x-failed-recipients")
    if not isinstance(raw, str):
        return []
    return [piece.strip() for piece in raw.split(",") if piece.strip()]


# --- Graph polling -------------------------------------------------------


async def _poll_graph(
    *,
    tenant_id: TenantId,
    credential_id: UUID,
    principal: Principal,
    http: httpx.AsyncClient,
) -> dict[str, int]:
    """List + fetch + match NDRs in one Microsoft 365 mailbox."""
    out = {"candidates": 0, "matched": 0, "unmatched": 0}

    since_dt = datetime.now(UTC).replace(microsecond=0) - timedelta(days=1)
    since_iso = since_dt.isoformat().replace("+00:00", "Z")
    filter_query = _GRAPH_FILTER_TEMPLATE.format(since_iso=since_iso)

    async with async_session() as session:
        client = await MicrosoftClient.from_credential(
            credential_id, session=session, principal=principal, http=http
        )
        try:
            listed = await client.list_messages(
                filter_query=filter_query,
                select=[
                    "id",
                    "subject",
                    "from",
                    "internetMessageHeaders",
                    "internetMessageId",
                ],
                top=_GRAPH_PAGE_SIZE,
            )
        finally:
            await client.close()

    rows = listed.get("value") or []
    if not isinstance(rows, list):
        return out
    out["candidates"] = len(rows)

    for row in rows:
        if not isinstance(row, dict):
            continue
        headers = _graph_headers(row)
        in_reply_to = _extract_in_reply_to_graph(headers)

        async with async_session() as session:
            matched = await _try_match_and_record(
                session=session,
                tenant_id=tenant_id,
                credential_id=credential_id,
                principal=principal,
                in_reply_to=in_reply_to,
                failed_recipients=[],
            )
            if matched:
                out["matched"] += 1
            else:
                out["unmatched"] += 1
                log.info(
                    "bounce_poll.graph.unmatched",
                    tenant_id=str(tenant_id),
                    credential_id=str(credential_id),
                    has_in_reply_to=bool(in_reply_to),
                )
    return out


def _graph_headers(message: dict[str, Any]) -> dict[str, str]:
    """Flatten Graph's ``internetMessageHeaders`` list into name → value."""
    header_list = message.get("internetMessageHeaders")
    if not isinstance(header_list, list):
        return {}
    out: dict[str, str] = {}
    for entry in header_list:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        value = entry.get("value")
        if isinstance(name, str) and isinstance(value, str):
            out[name.strip().lower()] = value
    return out


def _extract_in_reply_to_graph(headers: dict[str, str]) -> str | None:
    raw = headers.get("in-reply-to") or headers.get("references")
    if not isinstance(raw, str):
        return None
    return raw.strip() or None


# --- Match + record ------------------------------------------------------


_MESSAGE_ID_PATTERN = re.compile(r"<([^<>\s]+)>")


def _normalise_message_id(value: str) -> str:
    """Strip angle brackets / whitespace; tolerate ``References`` chains.

    ``In-Reply-To`` is typically ``<id@host>``. ``References`` may be a
    space-separated list — we pick the first one (the original).
    """
    if not value:
        return ""
    match = _MESSAGE_ID_PATTERN.search(value)
    if match:
        return match.group(1).strip()
    return value.strip()


async def _try_match_and_record(
    *,
    session: AsyncSession,
    tenant_id: TenantId,
    credential_id: UUID,
    principal: Principal,
    in_reply_to: str | None,
    failed_recipients: Iterable[str],
) -> bool:
    """Match an NDR back to a send row and record the bounce.

    Returns True if a match was found (and the bounce recorded).
    Returns False otherwise — the caller logs the unmatched case at
    INFO without an audit row (NDRs for pre-tracking sends are common).
    """
    if not in_reply_to:
        return False

    original_id = _normalise_message_id(in_reply_to)
    if not original_id:
        return False

    send_repo = SendRepository(session)
    suppression = SuppressionService(session)
    audit = AuditService(session)

    send = await send_repo.find_by_message_id(tenant_id, original_id)
    if send is None:
        # Defence in depth — try the global lookup (a Graph mailbox
        # might have stored a wrapped variant of the id). We still
        # require ``tenant_id`` matches the send row before recording.
        send = await send_repo.find_by_message_id_global(original_id)
        if send is None or send.tenant_id != tenant_id:
            return False

    # Idempotent: if the send is already bounced, do not re-record.
    if send.status != SendStatus.BOUNCED.value:
        send.status = SendStatus.BOUNCED.value
        send.error_text = "bounce_hard"

    # Decide which recipient address to suppress. Prefer the failed-
    # recipients header value (more reliable on Gmail); fall back to
    # the send row's recorded address.
    suppress_target: str | None = None
    for candidate in failed_recipients:
        if "@" in candidate:
            suppress_target = candidate
            break
    if suppress_target is None:
        suppress_target = send.recipient_email

    await suppression.add_suppression(
        tenant_id,
        suppress_target,
        reason="bounce_hard",
        principal=principal,
        source_send_id=send.id,
    )

    match_strategy = "failed_recipients" if failed_recipients else "in_reply_to"

    await audit.record(
        principal=principal,
        action=AUDIT_EMAIL_BOUNCED,
        resource="outreach.send",
        extra={
            "tenant_id": str(tenant_id),
            "send_id": str(send.id),
            "credential_id": str(credential_id),
            "match_strategy": match_strategy,
            "recipient_hash": _hash_email(send.recipient_email),
        },
    )
    return True


__all__ = ["poll_bounces"]
