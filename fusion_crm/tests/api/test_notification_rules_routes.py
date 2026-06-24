"""HTTP contract tests for the notification-rule admin routes (ENG-458).

Handler-level coverage: the service + chat provider are mocked and the
principal is overridden, so these assert the thin wiring (DTO ↔ service ↔
DTO, status codes, tenant resolution, channel-name pass-through) without a
DB. Live persistence + audit + real channel-id storage live in
``tests/integrations/test_notification_rule_admin_integration.py``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import (
    get_chat_provider,
    get_notification_service,
    get_principal_with_tenant,
)
from apps.api.middleware import platform_error_handler
from apps.api.routers import notification_rules as rules_router
from packages.core.exceptions import PlatformError
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.integrations.models import NotificationRule

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_ACTOR_ID = uuid.uuid4()
_RESOLVED_CHANNEL_ID = "abcdefghijklmnopqrstuvwxyz"  # 26-char MM id shape


def _principal() -> Principal:
    return Principal(
        id=_ACTOR_ID,
        email="staff@example.com",
        tenant_id=_TENANT_ID,
        roles=frozenset({Role.ADMIN}),
    )


def _rule(
    *,
    event_type: str = "lead.created",
    channel: str = _RESOLVED_CHANNEL_ID,
    enabled: bool = True,
) -> NotificationRule:
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    row = NotificationRule(
        tenant_id=uuid.UUID(str(_TENANT_ID)),
        event_type=event_type,
        channel=channel,
        conditions=[],
        template={"text": "{{ summary }}"},
        provider_kind="mattermost",
        enabled=enabled,
        description="route new leads",
    )
    row.id = uuid.uuid4()
    row.created_at = now
    row.updated_at = now
    return row


def _build_app(svc: object, provider: object) -> FastAPI:
    app = FastAPI()
    app.include_router(rules_router.router)
    app.add_exception_handler(PlatformError, platform_error_handler)  # type: ignore[arg-type]
    app.dependency_overrides[get_notification_service] = lambda: svc
    app.dependency_overrides[get_chat_provider] = lambda: provider
    app.dependency_overrides[get_principal_with_tenant] = _principal
    return app


def test_create_rule_returns_201_and_passes_channel_name_to_service() -> None:
    row = _rule()
    svc = MagicMock()
    svc.create_rule = AsyncMock(return_value=row)
    provider = MagicMock()
    client = TestClient(_build_app(svc, provider))

    res = client.post(
        "/integrations/chat/notification-rules",
        json={
            "event_type": "lead.created",
            "channel": "leads",  # NAME, not an id
            "conditions": [],
            "template": {"text": "{{ summary }}"},
            "description": "route new leads",
        },
    )

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["id"] == str(row.id)
    assert body["channel"] == _RESOLVED_CHANNEL_ID

    svc.create_rule.assert_awaited_once()
    args = svc.create_rule.await_args.args
    kwargs = svc.create_rule.await_args.kwargs
    assert args[0] == _TENANT_ID
    # The route hands the raw NAME to the service; resolution is the
    # service's job (it owns the provider it was given).
    assert args[1].channel == "leads"
    assert kwargs["principal"] == _principal()
    assert kwargs["provider"] is provider


def test_list_rules_returns_items_and_calls_service() -> None:
    rows = [_rule(event_type="lead.created"), _rule(event_type="ownership.changed")]
    svc = MagicMock()
    svc.list_rules = AsyncMock(return_value=rows)
    client = TestClient(_build_app(svc, MagicMock()))

    res = client.get("/integrations/chat/notification-rules")

    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["items"]) == 2
    svc.list_rules.assert_awaited_once_with(_TENANT_ID, event_type=None)


def test_patch_rule_toggles_enabled_and_calls_service() -> None:
    rule_id = uuid.uuid4()
    row = _rule(enabled=False)
    row.id = rule_id
    svc = MagicMock()
    svc.update_rule = AsyncMock(return_value=row)
    provider = MagicMock()
    client = TestClient(_build_app(svc, provider))

    res = client.patch(
        f"/integrations/chat/notification-rules/{rule_id}",
        json={"enabled": False},
    )

    assert res.status_code == 200, res.text
    assert res.json()["enabled"] is False

    svc.update_rule.assert_awaited_once()
    args = svc.update_rule.await_args.args
    kwargs = svc.update_rule.await_args.kwargs
    assert args[0] == _TENANT_ID
    assert args[1] == rule_id
    assert args[2].enabled is False
    assert kwargs["provider"] is provider


def test_delete_rule_returns_204_and_calls_service() -> None:
    rule_id = uuid.uuid4()
    svc = MagicMock()
    svc.delete_rule = AsyncMock(return_value=None)
    client = TestClient(_build_app(svc, MagicMock()))

    res = client.delete(f"/integrations/chat/notification-rules/{rule_id}")

    assert res.status_code == 204, res.text
    svc.delete_rule.assert_awaited_once()
    args = svc.delete_rule.await_args.args
    assert args[0] == _TENANT_ID
    assert args[1] == rule_id
    assert svc.delete_rule.await_args.kwargs["principal"] == _principal()
