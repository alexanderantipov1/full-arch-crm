"""Outreach repositories — strictly data access.

Per ``packages/CLAUDE.md`` these are private to ``packages.outreach``.
Cross-package callers go through ``TemplateService`` /
``CampaignService`` / ``SuppressionService`` / ``SendService``.

Every method takes ``tenant_id`` first and uses it as a hard filter.
Repositories must NEVER read or write a row without the tenant filter
in place — there is no "admin" cross-tenant path here; that lives at
the audit + ops-tooling level.

The ``OutboundQueueRepository`` carries the locked-pull queries used
by the ``apps.worker.jobs.email_send`` dispatcher; per ADR-0004
decision #1 we pull with ``SELECT ... FOR UPDATE SKIP LOCKED`` so
multiple workers can drain in parallel without conflicting on the
same row.

ENG-134 (2026-05-11) extensions:

- ``SendRepository.find_by_message_id`` — used by the bounce poller
  to match an inbound NDR back to the original send.
- ``SendRepository.find_by_message_id_global`` — same lookup without
  the tenant filter, for the fallback path (the caller then verifies
  ``send.tenant_id`` before recording the bounce).
- ``SendRepository.get_global`` — used by the open-tracking pixel
  route, which has no tenant context on the wire (the HMAC token is
  the only auth). The route reads the tenant from the returned row.
- ``SuppressionRepository.list_for_tenant`` — paginated read for the
  operator settings UI (ENG-135).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Campaign,
    OutboundQueue,
    OutboundQueueStatus,
    Send,
    Suppression,
    Template,
)


class TemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_tenant(
        self, tenant_id: UUID, template_id: UUID
    ) -> Template | None:
        stmt = (
            select(Template)
            .where(Template.id == template_id)
            .where(Template.tenant_id == tenant_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_by_name(
        self, tenant_id: UUID, name: str
    ) -> Template | None:
        stmt = (
            select(Template)
            .where(Template.tenant_id == tenant_id)
            .where(Template.name == name)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Template]:
        stmt = (
            select(Template)
            .where(Template.tenant_id == tenant_id)
            .order_by(Template.updated_at.desc())
            .limit(limit)
        )
        if status is not None:
            stmt = stmt.where(Template.status == status)
        return list((await self._session.execute(stmt)).scalars().all())

    async def add(self, template: Template) -> Template:
        self._session.add(template)
        await self._session.flush()
        return template


class CampaignRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_tenant(
        self, tenant_id: UUID, campaign_id: UUID
    ) -> Campaign | None:
        stmt = (
            select(Campaign)
            .where(Campaign.id == campaign_id)
            .where(Campaign.tenant_id == tenant_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Campaign]:
        stmt = (
            select(Campaign)
            .where(Campaign.tenant_id == tenant_id)
            .order_by(Campaign.created_at.desc())
            .limit(limit)
        )
        if status is not None:
            stmt = stmt.where(Campaign.status == status)
        return list((await self._session.execute(stmt)).scalars().all())

    async def add(self, campaign: Campaign) -> Campaign:
        self._session.add(campaign)
        await self._session.flush()
        return campaign


class SendRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_campaign(
        self, tenant_id: UUID, campaign_id: UUID, *, limit: int = 1000
    ) -> list[Send]:
        stmt = (
            select(Send)
            .where(Send.tenant_id == tenant_id)
            .where(Send.campaign_id == campaign_id)
            .order_by(Send.created_at.asc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_for_tenant(
        self, tenant_id: UUID, send_id: UUID
    ) -> Send | None:
        stmt = (
            select(Send)
            .where(Send.tenant_id == tenant_id)
            .where(Send.id == send_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_global(self, send_id: UUID) -> Send | None:
        """Lookup by ``send_id`` without a tenant filter.

        ENG-134 (open tracking): the recipient-facing pixel route does
        not carry a tenant context on the wire — the HMAC token IS
        the gate. We look the send up globally, then derive the
        tenant_id from the row itself for any downstream writes.
        """
        stmt = select(Send).where(Send.id == send_id).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_by_message_id(
        self, tenant_id: UUID, message_id: str
    ) -> Send | None:
        """Locate a send by the provider's ``Message-ID`` header value.

        Used by the bounce poller (ENG-134) to match an NDR back to
        the original send. The tenant filter narrows so two tenants
        cannot collide if a provider ever recycles ids.
        """
        if not message_id:
            return None
        stmt = (
            select(Send)
            .where(Send.tenant_id == tenant_id)
            .where(Send.message_id == message_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_by_message_id_global(self, message_id: str) -> Send | None:
        """Locate a send by ``message_id`` without a tenant filter.

        The bounce poller iterates active mailbox credentials grouped
        by tenant; the message-id space is technically global so we
        keep a no-tenant fallback when the bounced NDR cannot be
        pre-bound to a tenant. The caller MUST verify
        ``send.tenant_id`` against the expected one before writing.
        """
        if not message_id:
            return None
        stmt = select(Send).where(Send.message_id == message_id).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add(self, send: Send) -> Send:
        self._session.add(send)
        await self._session.flush()
        return send


class SuppressionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self, tenant_id: UUID, recipient_email_normalised: str
    ) -> Suppression | None:
        stmt = (
            select(Suppression)
            .where(Suppression.tenant_id == tenant_id)
            .where(
                Suppression.recipient_email_normalised == recipient_email_normalised
            )
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add(self, row: Suppression) -> Suppression:
        self._session.add(row)
        await self._session.flush()
        return row

    async def delete_for(
        self, tenant_id: UUID, recipient_email_normalised: str
    ) -> bool:
        existing = await self.get(tenant_id, recipient_email_normalised)
        if existing is None:
            return False
        await self._session.delete(existing)
        await self._session.flush()
        return True

    async def count_for_tenant(self, tenant_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Suppression)
            .where(Suppression.tenant_id == tenant_id)
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Suppression]:
        """Paginated list, newest first.

        Used by the operator settings UI (ENG-135) and the operator-
        triggered manual unsubscribe surface. Tenant filter is hard;
        no admin cross-tenant path exists here by design.
        """
        stmt = (
            select(Suppression)
            .where(Suppression.tenant_id == tenant_id)
            .order_by(Suppression.created_at.desc())
            .limit(max(1, limit))
            .offset(max(0, offset))
        )
        return list((await self._session.execute(stmt)).scalars().all())


class OutboundQueueRepository:
    """Worker-facing helpers for the outbound queue (ENG-132).

    Two distinct lifecycles are exposed:

    1. ``add`` / ``get`` — enqueue + point read (used by the send
       service when materialising a campaign).
    2. ``lock_batch`` — the dispatcher's ``SELECT ... FOR UPDATE SKIP
       LOCKED`` pull. The repository returns the rows already updated
       to ``status='locked'`` so the caller can ``COMMIT`` and start
       work outside the row lock. Per ADR-0004 decision #1.

    Note: ``lock_batch`` mutates and flushes; the caller is expected
    to ``commit`` before processing each row to release the row lock
    early. The dispatcher pattern is "lock → commit → work → commit
    again" rather than holding a row lock across the network call to
    Gmail / Graph.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, row: OutboundQueue) -> OutboundQueue:
        self._session.add(row)
        await self._session.flush()
        return row

    async def get(self, row_id: UUID) -> OutboundQueue | None:
        return await self._session.get(OutboundQueue, row_id)

    async def lock_batch(
        self,
        *,
        worker_id: str,
        batch_size: int,
        now: datetime,
    ) -> list[OutboundQueue]:
        """Atomically take the next ``batch_size`` pending rows.

        The ``status='locked'`` write + flush happens INSIDE the
        ``FOR UPDATE SKIP LOCKED`` row lock; once we flush, callers
        commit and the row is free to be observed by other workers
        (which see ``status='locked'`` and skip).

        ``now`` is parameterised so tests can fix a deterministic
        clock; production passes ``datetime.now(UTC)``.
        """
        stmt = (
            select(OutboundQueue)
            .where(OutboundQueue.status == OutboundQueueStatus.PENDING.value)
            .where(OutboundQueue.scheduled_for <= now)
            .order_by(
                OutboundQueue.priority.asc(),
                OutboundQueue.scheduled_for.asc(),
            )
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        for row in rows:
            row.status = OutboundQueueStatus.LOCKED.value
            row.locked_by = worker_id
            row.locked_at = now
        if rows:
            await self._session.flush()
        return rows

    async def mark_succeeded(
        self, row: OutboundQueue, *, now: datetime
    ) -> None:
        """Terminal success — clear lock fields, leave attempts intact.

        Counter / attempt history is preserved so operators can see
        retry shapes after the fact.
        """
        row.status = OutboundQueueStatus.SUCCEEDED.value
        row.locked_by = None
        row.locked_at = None
        row.last_error = None
        # ``updated_at`` is auto-touched by the TimestampMixin; ``now``
        # is provided so future schema additions (e.g. an explicit
        # ``finished_at`` column) can be populated deterministically.
        _ = now
        await self._session.flush()

    async def mark_failed(
        self, row: OutboundQueue, *, last_error: str, now: datetime
    ) -> None:
        """Terminal failure — preserve attempt count + error reason."""
        row.status = OutboundQueueStatus.FAILED.value
        row.last_error = last_error[:8000] if last_error else None
        row.locked_by = None
        row.locked_at = None
        _ = now
        await self._session.flush()

    async def reschedule(
        self,
        row: OutboundQueue,
        *,
        scheduled_for: datetime,
        last_error: str | None,
        bump_attempts: bool = True,
    ) -> None:
        """Return a row to ``pending`` with a future ``scheduled_for``.

        Used for rate-limit deferrals and retry-eligible failures.
        Increments ``attempts`` so the dispatcher can enforce a cap
        across the retry budget.
        """
        row.status = OutboundQueueStatus.PENDING.value
        row.scheduled_for = scheduled_for
        row.locked_by = None
        row.locked_at = None
        if last_error is not None:
            row.last_error = last_error[:8000]
        if bump_attempts:
            row.attempts = (row.attempts or 0) + 1
        await self._session.flush()


__all__ = [
    "CampaignRepository",
    "OutboundQueueRepository",
    "SendRepository",
    "SuppressionRepository",
    "TemplateRepository",
]
