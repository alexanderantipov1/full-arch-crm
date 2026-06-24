"""Notification-rule admin routes (ENG-458, Block D of ENG-454).

Make "route event X → channel Y" a configurable SETTING via a thin admin
API instead of seed code or raw SQL. An operator references a channel by
NAME; the handler resolves the name to a provider channel id (via the
tenant's :class:`ChatProvider`) BEFORE storing, so
``integrations.notification_rule.channel`` is ALWAYS a channel id.

Handlers stay thin (apps/api invariant #5): DTO/path → service → DTO. All
logic — channel resolution, persistence, audit, tenant scoping — lives in
:class:`packages.integrations.notification_service.NotificationService`.
Domain failures raise ``PlatformError`` subclasses; the middleware
translates them to the JSON envelope (no raw ``HTTPException``).

Staff endpoints (not public): they depend on the tenant-aware principal.

These POST/PATCH/DELETE handlers mutate notification routing rules. Like every
other endpoint today they run under the platform-wide ANONYMOUS auth stub —
which is the documented single-user posture (root ``CLAUDE.md`` "Data
visibility & access posture"): no per-endpoint authn/authz this phase, on any
environment, with one trusted operator. Endpoint authz arrives later as the
uniform access-control layer (not a per-route bolt-on here). Notifications also
ship DARK (``NOTIFICATIONS_ENABLED=false``) until the prod bring-up (ENG-442).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from apps.api.dependencies import (
    get_chat_provider,
    get_notification_service,
    get_principal_with_tenant,
)
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.integrations.chat.base import ChatProvider
from packages.integrations.notification_schemas import (
    NotificationRuleIn,
    NotificationRuleListOut,
    NotificationRuleOut,
    NotificationRulePatch,
)
from packages.integrations.notification_service import NotificationService

router = APIRouter(
    prefix="/integrations/chat/notification-rules",
    tags=["notification-rules"],
)

NotificationServiceDep = Annotated[
    NotificationService, Depends(get_notification_service)
]
ChatProviderDep = Annotated[ChatProvider, Depends(get_chat_provider)]
PrincipalDep = Annotated[Principal, Depends(get_principal_with_tenant)]


@router.get("", response_model=NotificationRuleListOut)
async def list_notification_rules(
    svc: NotificationServiceDep,
    principal: PrincipalDep,
    event_type: str | None = Query(default=None, min_length=1, max_length=128),
) -> NotificationRuleListOut:
    tenant_id: TenantId = principal.require_tenant()
    rows = await svc.list_rules(tenant_id, event_type=event_type)
    return NotificationRuleListOut(
        items=[NotificationRuleOut.model_validate(row) for row in rows]
    )


@router.post(
    "",
    response_model=NotificationRuleOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification_rule(
    body: NotificationRuleIn,
    svc: NotificationServiceDep,
    principal: PrincipalDep,
    provider: ChatProviderDep,
) -> NotificationRuleOut:
    tenant_id: TenantId = principal.require_tenant()
    rule = await svc.create_rule(
        tenant_id, body, principal=principal, provider=provider
    )
    return NotificationRuleOut.model_validate(rule)


@router.patch("/{rule_id}", response_model=NotificationRuleOut)
async def update_notification_rule(
    rule_id: UUID,
    body: NotificationRulePatch,
    svc: NotificationServiceDep,
    principal: PrincipalDep,
    provider: ChatProviderDep,
) -> NotificationRuleOut:
    tenant_id: TenantId = principal.require_tenant()
    rule = await svc.update_rule(
        tenant_id, rule_id, body, principal=principal, provider=provider
    )
    return NotificationRuleOut.model_validate(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification_rule(
    rule_id: UUID,
    svc: NotificationServiceDep,
    principal: PrincipalDep,
) -> None:
    tenant_id: TenantId = principal.require_tenant()
    await svc.delete_rule(tenant_id, rule_id, principal=principal)
