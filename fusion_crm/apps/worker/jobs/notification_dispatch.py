"""Notification dispatcher — drain ``integrations.notification_outbox``.

Per ENG-436 (Block C). Mirrors the email dispatcher
(``apps.worker.jobs.email_send.drain_outbound_queue``): pulls pending
rows with ``SELECT ... FOR UPDATE SKIP LOCKED``, resolves a
:class:`ChatProvider` for the row's ``provider_kind``, posts the rendered
``payload`` to the target channel, and records the terminal outcome.

Job lifecycle for one outbox row:

1. Lock the row (``status='locked'``, ``locked_by``, ``locked_at``)
   inside the ``FOR UPDATE SKIP LOCKED`` lock, then COMMIT so the row
   lock releases and the row is observable to other workers as
   ``locked`` (which they skip).
2. Process each row in its own session: resolve the provider via
   ``resolve_chat_provider``.
   - On ``NotImplementedError`` (Block B adapter not yet wired) or any
     provider error / ``ok=False`` result → ``mark_failed`` with the
     error message.
   - On ``ok=True`` → ``mark_sent`` with the provider message id.
3. Commit and audit each outcome (``notification.dispatch.sent`` /
   ``notification.dispatch.failed``) under a synthesised SYSTEM
   principal — the drain runs outside any user request.

Idempotency: a row is only processed while ``status == 'locked'``; a
row already ``sent`` / ``failed`` is skipped on a second drain pass.

Stale-lock reclaim (AT-LEAST-ONCE): ``lock_batch`` also reclaims rows stuck
in ``status='locked'`` whose ``locked_at`` is older than
``LOCK_LEASE_SECONDS`` — these are rows whose worker crashed after locking
but before reaching a terminal state. Reclaiming guarantees forward
progress, but a row that the crashed worker had ALREADY posted (yet never
marked ``sent``) will be posted again on reclaim. We accept at-least-once
delivery for V1; Mattermost offers no pre-post idempotency key for a true
exactly-once. To keep the duplicate window small, the terminal mark and the
post live in the same per-row session/commit below.
"""

from __future__ import annotations

import os
import socket
from datetime import UTC, datetime
from uuid import UUID

from packages.audit.service import AuditService
from packages.core.logging import get_logger
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.integrations.chat.base import ChatMessage, ChatProvider
from packages.integrations.chat.resolver import resolve_chat_provider
from packages.integrations.notification_repository import (
    NotificationOutboxRepository,
)

log = get_logger("worker.notification_dispatch")

# Conservative batch — the drain is poll-driven and cheap when empty.
BATCH_SIZE = 25

AUDIT_DISPATCH_SENT = "notification.dispatch.sent"
AUDIT_DISPATCH_FAILED = "notification.dispatch.failed"


def _system_principal(tenant_id: TenantId | None) -> Principal:
    """A synthesised principal for worker-side audit rows."""
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
        context={"source": "worker.notification_dispatch"},
    )


def _worker_id() -> str:
    host = socket.gethostname() or "unknown"
    return f"{host}/{os.getpid()}"


async def drain_notification_outbox(ctx: dict) -> dict:
    """One drain pass over ``integrations.notification_outbox``.

    Scheduled every ~10 s via the arq cron config (offset from the email
    dispatcher). Each call drains at most ``BATCH_SIZE`` rows and returns
    a summary.
    """
    _ = ctx
    summary: dict[str, int] = {"sent": 0, "failed": 0, "skipped": 0}
    now = datetime.now(UTC)
    worker_id = _worker_id()

    # Lock + commit pass — release the row lock fast so other workers can
    # drain in parallel.
    locked: list[UUID] = []
    async with async_session() as session:
        repo = NotificationOutboxRepository(session)
        rows = await repo.lock_batch(
            worker_id=worker_id, batch_size=BATCH_SIZE, now=now
        )
        locked = [row.id for row in rows]

    if not locked:
        return summary

    for outbox_id in locked:
        outcome = await _process_one(outbox_id=outbox_id)
        summary[outcome] = summary.get(outcome, 0) + 1

    log.info(
        "notification.dispatcher.tick", summary=summary, worker_id=worker_id
    )
    return summary


async def _process_one(*, outbox_id: UUID) -> str:
    """Drive one locked outbox row to a terminal state.

    Returns ``"sent" | "failed" | "skipped"``.
    """
    async with async_session() as session:
        repo = NotificationOutboxRepository(session)
        audit = AuditService(session)

        row = await repo.get(outbox_id)
        if row is None or row.status != "locked":
            # Already terminal or claimed by another worker — idempotent skip.
            return "skipped"

        tenant_id = TenantId(row.tenant_id)
        principal = _system_principal(tenant_id)

        # --- Resolve the provider --------------------------------------
        try:
            provider: ChatProvider = await resolve_chat_provider(
                tenant_id, row.provider_kind, session
            )
        except NotImplementedError as exc:
            await repo.mark_failed(
                row, last_error=str(exc), now=datetime.now(UTC)
            )
            await _audit_failed(audit, principal, row, reason=str(exc))
            return "failed"
        except Exception as exc:  # noqa: BLE001 — resolver failure → fail row
            await repo.mark_failed(
                row,
                last_error=f"provider resolve error: {type(exc).__name__}",
                now=datetime.now(UTC),
            )
            await _audit_failed(audit, principal, row, reason="resolve_error")
            return "failed"

        # --- Resolve the channel ---------------------------------------
        # ENG-458: the outbox stores an environment-independent reference —
        # a bare ``scheduls`` or a team-qualified ``el-dorado/scheduls`` — which
        # the provider resolves to a concrete channel id (the bot belongs to
        # several teams, so a name alone is ambiguous). A failed resolution is a
        # failed row: never post to a fallback / wrong channel.
        channel_id = await provider.resolve_channel_id(row.channel)
        if channel_id is None:
            await repo.mark_failed(
                row,
                last_error=f"channel resolution failed: {row.channel}",
                now=datetime.now(UTC),
            )
            await _audit_failed(audit, principal, row, reason="channel_unresolved")
            return "failed"

        # --- Build + post the message ----------------------------------
        payload = dict(row.payload or {})
        text_raw = payload.get("text")
        text = text_raw if isinstance(text_raw, str) else ""
        blocks_raw = payload.get("blocks")
        blocks = blocks_raw if isinstance(blocks_raw, list) else None
        message = ChatMessage(channel=channel_id, text=text, blocks=blocks)

        try:
            result = await provider.post(message)
        except Exception as exc:  # noqa: BLE001 — provider error → fail row
            await repo.mark_failed(
                row,
                last_error=f"provider post error: {type(exc).__name__}",
                now=datetime.now(UTC),
            )
            await _audit_failed(audit, principal, row, reason="post_exception")
            return "failed"

        if not result.ok:
            await repo.mark_failed(
                row,
                last_error=result.error or "provider returned not ok",
                now=datetime.now(UTC),
            )
            await _audit_failed(audit, principal, row, reason="provider_not_ok")
            return "failed"

        # --- Terminal success ------------------------------------------
        await repo.mark_sent(
            row,
            provider_message_id=result.provider_message_id,
            now=datetime.now(UTC),
        )
        await audit.record(
            principal=principal,
            action=AUDIT_DISPATCH_SENT,
            resource="integrations.notification_outbox",
            extra={
                "tenant_id": str(tenant_id),
                "outbox_id": str(row.id),
                "event_type": row.event_type,
                "provider_kind": row.provider_kind,
                "has_provider_message_id": result.provider_message_id is not None,
            },
        )
        return "sent"


async def _audit_failed(
    audit: AuditService,
    principal: Principal,
    row: object,
    *,
    reason: str,
) -> None:
    await audit.record(
        principal=principal,
        action=AUDIT_DISPATCH_FAILED,
        resource="integrations.notification_outbox",
        extra={
            "tenant_id": str(getattr(row, "tenant_id", "")),
            "outbox_id": str(getattr(row, "id", "")),
            "event_type": getattr(row, "event_type", None),
            "provider_kind": getattr(row, "provider_kind", None),
            "reason": reason,
        },
    )


__all__ = ["drain_notification_outbox"]
