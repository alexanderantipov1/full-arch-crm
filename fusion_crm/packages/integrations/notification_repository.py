"""Notification repositories — data access only (ENG-436, Block C).

Mirrors ``packages.outreach.repository.OutboundQueueRepository``: the
``NotificationOutboxRepository`` carries the locked-pull query used by
the ``apps.worker.jobs.notification_dispatch`` dispatcher (``SELECT ...
FOR UPDATE SKIP LOCKED`` so multiple workers drain in parallel), and the
``NotificationRuleRepository`` is plain CRUD for the rule table.

Every per-tenant method takes ``tenant_id`` first and filters on it via
:func:`for_tenant`. Repositories never commit — the worker boundary does.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.db.tenant_scope import for_tenant

from .models import NotificationEmitted, NotificationOutbox, NotificationRule

# A locked row whose ``locked_at`` is older than this lease is considered
# STALE — its worker presumably crashed between locking and reaching a
# terminal state — and is reclaimed by the next drain. Without this, a crash
# after the lock-commit but before ``mark_sent`` / ``mark_failed`` would
# strand the row in ``status='locked'`` forever.
LOCK_LEASE_SECONDS = 300


class NotificationRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, rule: NotificationRule) -> NotificationRule:
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def get_for_tenant(
        self, tenant_id: TenantId, rule_id: UUID
    ) -> NotificationRule | None:
        stmt = for_tenant(select(NotificationRule), tenant_id, NotificationRule).where(
            NotificationRule.id == rule_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_by_event_and_channel(
        self, tenant_id: TenantId, event_type: str, channel: str
    ) -> NotificationRule | None:
        """Locate a rule by its idempotency key ``(event_type, channel)``."""
        stmt = (
            for_tenant(select(NotificationRule), tenant_id, NotificationRule)
            .where(NotificationRule.event_type == event_type)
            .where(NotificationRule.channel == channel)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_enabled_for_event(
        self, tenant_id: TenantId, event_type: str
    ) -> list[NotificationRule]:
        stmt = (
            for_tenant(select(NotificationRule), tenant_id, NotificationRule)
            .where(NotificationRule.event_type == event_type)
            .where(NotificationRule.enabled.is_(True))
            .order_by(NotificationRule.created_at.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_for_tenant(
        self,
        tenant_id: TenantId,
        *,
        event_type: str | None = None,
        limit: int = 200,
    ) -> list[NotificationRule]:
        stmt = (
            for_tenant(select(NotificationRule), tenant_id, NotificationRule)
            .order_by(NotificationRule.created_at.asc())
            .limit(limit)
        )
        if event_type is not None:
            stmt = stmt.where(NotificationRule.event_type == event_type)
        return list((await self._session.execute(stmt)).scalars().all())

    async def delete(self, rule: NotificationRule) -> None:
        """Remove a rule. The caller boundary owns the commit."""
        await self._session.delete(rule)
        await self._session.flush()


class NotificationOutboxRepository:
    """Worker-facing helpers for the notification outbox.

    Lifecycle mirrors the email outbound queue: ``add`` / ``get`` for
    enqueue + point read, and ``lock_batch`` for the dispatcher's
    ``FOR UPDATE SKIP LOCKED`` claim. ``lock_batch`` mutates + flushes
    rows to ``status='locked'`` so the caller can commit and release the
    row lock before doing network work.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, row: NotificationOutbox) -> NotificationOutbox:
        self._session.add(row)
        await self._session.flush()
        return row

    async def get(self, row_id: UUID) -> NotificationOutbox | None:
        return await self._session.get(NotificationOutbox, row_id)

    async def lock_batch(
        self,
        *,
        worker_id: str,
        batch_size: int,
        now: datetime,
    ) -> list[NotificationOutbox]:
        """Atomically take the next ``batch_size`` due rows.

        Two kinds of rows are claimed:

        * ``status='pending'`` rows whose ``scheduled_for <= now`` (the
          normal path), and
        * ``status='locked'`` rows whose ``locked_at`` is older than
          :data:`LOCK_LEASE_SECONDS` — STALE locks left by a crashed worker
          that locked the row but never reached ``mark_sent`` /
          ``mark_failed``. Reclaiming them re-locks the row under THIS worker.

        The ``status='locked'`` write + flush happens INSIDE the
        ``FOR UPDATE SKIP LOCKED`` row lock; once flushed, the caller
        commits and the rows are observable to other workers as
        ``locked`` (which they skip). ``now`` is parameterised so tests
        can fix a deterministic clock.

        AT-LEAST-ONCE (V1): the only durable side effect is the eventual
        provider ``post()``. A row that was already posted by the crashed
        worker but never marked ``sent`` will be reclaimed and posted a
        SECOND time — we accept at-least-once delivery for V1. To shrink the
        window, ``_process_one`` should mark the row terminal in the same
        commit as (or before) the post wherever feasible; a fully
        exactly-once design would need a pre-post provider idempotency key,
        which Mattermost does not offer today.
        """
        lease_cutoff = now - timedelta(seconds=LOCK_LEASE_SECONDS)
        stmt = (
            select(NotificationOutbox)
            .where(
                or_(
                    and_(
                        NotificationOutbox.status == "pending",
                        NotificationOutbox.scheduled_for <= now,
                    ),
                    and_(
                        NotificationOutbox.status == "locked",
                        NotificationOutbox.locked_at < lease_cutoff,
                    ),
                )
            )
            .order_by(NotificationOutbox.scheduled_for.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        for row in rows:
            row.status = "locked"
            row.locked_by = worker_id
            row.locked_at = now
        if rows:
            await self._session.flush()
        return rows

    async def mark_sent(
        self,
        row: NotificationOutbox,
        *,
        provider_message_id: str | None,
        now: datetime,
    ) -> None:
        """Terminal success — record the provider message id + sent time."""
        row.status = "sent"
        row.sent_at = now
        row.locked_by = None
        row.locked_at = None
        row.last_error = None
        if provider_message_id is not None:
            meta = dict(row.payload or {})
            meta["provider_message_id"] = provider_message_id
            row.payload = meta
        await self._session.flush()

    async def mark_failed(
        self, row: NotificationOutbox, *, last_error: str, now: datetime
    ) -> None:
        """Terminal failure — preserve attempt count + error reason."""
        row.status = "failed"
        row.last_error = last_error[:8000] if last_error else None
        row.attempts = (row.attempts or 0) + 1
        row.locked_by = None
        row.locked_at = None
        _ = now
        await self._session.flush()


class NotificationEmittedRepository:
    """Data access for the durable idempotency ledger (ENG-455).

    The single meaningful operation is :meth:`claim`, an atomic
    "insert-if-absent" against the ``(tenant_id, event_type, dedupe_key)``
    UNIQUE constraint. Like every repo here it NEVER commits — the caller
    boundary owns the unit of work, which is what makes the ledger claim and
    the outbox enqueue land (or roll back) together.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim(
        self, tenant_id: TenantId, event_type: str, dedupe_key: str
    ) -> bool:
        """Atomically record (tenant, event, key); report whether WE inserted.

        Uses ``INSERT ... ON CONFLICT (tenant_id, event_type, dedupe_key)
        DO NOTHING RETURNING id``. The returning row is present ONLY when
        this statement performed the insert, so:

        * ``True``  — first claim for this triple (caller may proceed to emit).
        * ``False`` — a prior claim already exists (caller must skip; emitting
          again would duplicate the notification).

        The row is flushed (not committed) so the same transaction can read it
        back if needed and so the boundary commits it atomically with the
        outbox row. Concurrency: two overlapping transactions both attempting
        the same triple are serialised by the UNIQUE index — the loser's
        ``DO NOTHING`` returns no row (``False``) once the winner commits, or
        blocks until the winner's transaction resolves.
        """
        stmt = (
            pg_insert(NotificationEmitted)
            .values(
                tenant_id=tenant_id,
                event_type=event_type,
                dedupe_key=dedupe_key,
            )
            .on_conflict_do_nothing(
                constraint="uq_notification_emitted_tenant_event_key",
            )
            .returning(NotificationEmitted.id)
        )
        inserted_id = (await self._session.execute(stmt)).scalar_one_or_none()
        if inserted_id is not None:
            await self._session.flush()
        return inserted_id is not None


__all__ = [
    "LOCK_LEASE_SECONDS",
    "NotificationEmittedRepository",
    "NotificationOutboxRepository",
    "NotificationRuleRepository",
]
