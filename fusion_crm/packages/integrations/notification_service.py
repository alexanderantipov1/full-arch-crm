"""NotificationService — public surface for the messenger layer (ENG-436).

Enqueue chat messages onto the transactional outbox and manage the
notification rules that map workspace events to channels. The dispatcher
(``apps.worker.jobs.notification_dispatch``) drains the outbox and sends
via a :class:`ChatProvider`.

Services never commit — the caller boundary (worker job / API dependency)
owns the unit of work. Every state-change writes an ``audit.access_log``
row at the service layer so call sites do not need to remember.

Audit actions:

* ``integrations.notification.enqueued`` — ``enqueue``
* ``integrations.notification.rule.create`` — ``upsert_rule`` (insert)
* ``integrations.notification.rule.update`` — ``upsert_rule`` (update)
* ``integrations.notification.rule.delete`` — ``delete_rule``
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.service import AuditService
from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.logging import get_logger
from packages.core.security import Principal
from packages.core.types import TenantId

from .chat.base import ChatProvider
from .models import NotificationOutbox, NotificationRule
from .notification_repository import (
    NotificationOutboxRepository,
    NotificationRuleRepository,
)
from .notification_schemas import (
    NotificationOutboxIn,
    NotificationRuleIn,
    NotificationRulePatch,
)

log = get_logger("integrations.notification")

AUDIT_NOTIFICATION_ENQUEUED = "integrations.notification.enqueued"
AUDIT_NOTIFICATION_RULE_CREATE = "integrations.notification.rule.create"
AUDIT_NOTIFICATION_RULE_UPDATE = "integrations.notification.rule.update"
AUDIT_NOTIFICATION_RULE_DELETE = "integrations.notification.rule.delete"


class ChannelResolutionError(ValidationError):
    """Raised when a channel NAME cannot be resolved to a provider channel id.

    Surfaced by the admin API when an operator references a channel the bot
    cannot see (wrong name, bot not in the team, or provider unreachable).
    """

    code = "channel_resolution_failed"


class NotificationService:
    """Public surface for notification rules + the dispatch outbox."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._outbox = NotificationOutboxRepository(session)
        self._rules = NotificationRuleRepository(session)
        self._audit = AuditService(session)

    async def enqueue(
        self,
        tenant_id: TenantId,
        payload: NotificationOutboxIn,
        *,
        principal: Principal,
    ) -> NotificationOutbox:
        """Materialise one outbox row for the dispatcher to drain."""
        row = NotificationOutbox(
            tenant_id=tenant_id,
            event_type=payload.event_type,
            rule_id=payload.rule_id,
            channel=payload.channel,
            provider_kind=payload.provider_kind,
            payload=dict(payload.payload),
        )
        if payload.scheduled_for is not None:
            row.scheduled_for = payload.scheduled_for
        await self._outbox.add(row)
        await self._audit.record(
            principal=principal,
            action=AUDIT_NOTIFICATION_ENQUEUED,
            resource="integrations.notification_outbox",
            extra={
                "tenant_id": str(tenant_id),
                "outbox_id": str(row.id),
                "event_type": row.event_type,
                "provider_kind": row.provider_kind,
                "rule_id": str(row.rule_id) if row.rule_id else None,
            },
        )
        return row

    async def upsert_rule(
        self,
        tenant_id: TenantId,
        payload: NotificationRuleIn,
        *,
        principal: Principal,
    ) -> NotificationRule:
        """Insert or update a rule, idempotent on ``(event_type, channel)``."""
        existing = await self._rules.find_by_event_and_channel(
            tenant_id, payload.event_type, payload.channel
        )
        if existing is None:
            rule = NotificationRule(
                tenant_id=tenant_id,
                event_type=payload.event_type,
                channel=payload.channel,
                conditions=[dict(c) for c in payload.conditions],
                template=dict(payload.template),
                provider_kind=payload.provider_kind,
                enabled=payload.enabled,
                description=payload.description,
            )
            await self._rules.add(rule)
            action = AUDIT_NOTIFICATION_RULE_CREATE
        else:
            existing.conditions = [dict(c) for c in payload.conditions]
            existing.template = dict(payload.template)
            existing.provider_kind = payload.provider_kind
            existing.enabled = payload.enabled
            existing.description = payload.description
            rule = existing
            action = AUDIT_NOTIFICATION_RULE_UPDATE

        await self._audit.record(
            principal=principal,
            action=action,
            resource="integrations.notification_rule",
            extra={
                "tenant_id": str(tenant_id),
                "rule_id": str(rule.id),
                "event_type": rule.event_type,
                "provider_kind": rule.provider_kind,
                "enabled": rule.enabled,
            },
        )
        return rule

    async def create_rule(
        self,
        tenant_id: TenantId,
        payload: NotificationRuleIn,
        *,
        principal: Principal,
        provider: ChatProvider,
    ) -> NotificationRule:
        """Create/upsert a rule, resolving a channel NAME to an id first.

        ``payload.channel`` may be a channel NAME or an already-resolved id;
        ``provider.resolve_channel_id`` normalises it so the stored
        ``notification_rule.channel`` is ALWAYS a provider channel id. Reuses
        :meth:`upsert_rule` for the persistence + audit so create and update
        share one idempotent path.
        """
        channel_id = await self._resolve_channel(payload.channel, provider=provider)
        resolved = payload.model_copy(update={"channel": channel_id})
        return await self.upsert_rule(tenant_id, resolved, principal=principal)

    async def update_rule(
        self,
        tenant_id: TenantId,
        rule_id: UUID,
        patch: NotificationRulePatch,
        *,
        principal: Principal,
        provider: ChatProvider,
    ) -> NotificationRule:
        """Apply a partial update to an existing rule and audit it.

        Only the fields present in ``patch`` are changed. A supplied
        ``channel`` is resolved from a NAME to an id before storage. Writes
        one ``rule.update`` audit row. Raises ``NotFoundError`` when the rule
        does not exist for the tenant.
        """
        rule = await self.get_rule(tenant_id, rule_id)

        data = patch.model_dump(exclude_unset=True)
        if "channel" in data and data["channel"] is not None:
            data["channel"] = await self._resolve_channel(
                data["channel"], provider=provider
            )

        for field, value in data.items():
            if value is None and field in {"event_type", "channel"}:
                # Identity fields cannot be cleared; skip a stray null.
                continue
            setattr(rule, field, value)

        await self._rules.add(rule)
        await self._audit.record(
            principal=principal,
            action=AUDIT_NOTIFICATION_RULE_UPDATE,
            resource="integrations.notification_rule",
            extra={
                "tenant_id": str(tenant_id),
                "rule_id": str(rule.id),
                "event_type": rule.event_type,
                "provider_kind": rule.provider_kind,
                "enabled": rule.enabled,
            },
        )
        return rule

    async def _resolve_channel(
        self, channel: str, *, provider: ChatProvider
    ) -> str:
        """Resolve a channel NAME/id to a provider channel id.

        Raises :class:`ChannelResolutionError` when the provider cannot map
        the name (returns ``None``).
        """
        resolved = await provider.resolve_channel_id(channel)
        if not resolved:
            raise ChannelResolutionError(
                "could not resolve channel to a provider channel id",
                details={"channel": channel},
            )
        return resolved

    async def list_rules(
        self, tenant_id: TenantId, event_type: str | None = None
    ) -> list[NotificationRule]:
        return await self._rules.list_for_tenant(tenant_id, event_type=event_type)

    async def get_rule(self, tenant_id: TenantId, rule_id: UUID) -> NotificationRule:
        """Return one tenant-scoped rule or raise ``NotFoundError``."""
        rule = await self._rules.get_for_tenant(tenant_id, rule_id)
        if rule is None:
            raise NotFoundError(
                "notification rule not found",
                details={"tenant_id": str(tenant_id), "rule_id": str(rule_id)},
            )
        return rule

    async def delete_rule(
        self,
        tenant_id: TenantId,
        rule_id: UUID,
        *,
        principal: Principal,
    ) -> None:
        """Delete a tenant-scoped rule, writing one audit row.

        Raises ``NotFoundError`` when the rule does not exist for the tenant.
        """
        rule = await self.get_rule(tenant_id, rule_id)
        event_type = rule.event_type
        provider_kind = rule.provider_kind
        await self._rules.delete(rule)
        await self._audit.record(
            principal=principal,
            action=AUDIT_NOTIFICATION_RULE_DELETE,
            resource="integrations.notification_rule",
            extra={
                "tenant_id": str(tenant_id),
                "rule_id": str(rule_id),
                "event_type": event_type,
                "provider_kind": provider_kind,
            },
        )


__all__ = [
    "AUDIT_NOTIFICATION_ENQUEUED",
    "AUDIT_NOTIFICATION_RULE_CREATE",
    "AUDIT_NOTIFICATION_RULE_DELETE",
    "AUDIT_NOTIFICATION_RULE_UPDATE",
    "ChannelResolutionError",
    "NotificationService",
]
