"""Integration tests for the notification-rule admin surface (ENG-458).

Exercises ``NotificationService`` create/get/update/delete against the REAL
local Postgres (same session/repo stack the dispatcher uses), with the chat
provider mocked so channel-name resolution is deterministic. Skips cleanly
when no local DB is reachable.

Covered:

1. CRUD round-trip — create (by channel NAME → resolved id), list, toggle
   ``enabled`` via update, delete.
2. The stored ``channel`` is ALWAYS the resolved id, never the name.
3. One audit row per mutation (create, update, delete).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.security import Principal, Role
from packages.core.types import TenantId

try:  # noqa: SIM105
    from packages.db.session import async_session

    _IMPORT_OK = True
except Exception:  # noqa: BLE001 — environment not configured for a DB
    _IMPORT_OK = False

pytestmark = pytest.mark.skipif(
    not _IMPORT_OK, reason="DATABASE_URL / Settings not configured for a live DB"
)

_RESOLVED_CHANNEL_ID = "abcdefghijklmnopqrstuvwxyz"  # 26-char MM id shape


def _principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="admin@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )


def _provider(resolved: str | None = _RESOLVED_CHANNEL_ID) -> MagicMock:
    provider = MagicMock()
    provider.resolve_channel_id = AsyncMock(return_value=resolved)
    return provider


async def _db_reachable() -> bool:
    from sqlalchemy import text

    from packages.db.session import engine

    try:
        await engine.dispose()
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 — DB down / unreachable
        return False


@pytest.fixture
async def tenant_id() -> AsyncIterator[TenantId]:
    if not await _db_reachable():
        pytest.skip("local Postgres not reachable (127.0.0.1:5434)")

    from sqlalchemy import text

    tid = uuid.uuid4()
    slug = f"eng458-test-{tid.hex[:12]}"
    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO tenant.tenant (id, slug, name, timezone, locale, status, "
                "created_at, updated_at) VALUES (:id, :slug, :name, 'UTC', 'en-US', "
                "'active', now(), now())"
            ),
            {"id": tid, "slug": slug, "name": "ENG-458 Test"},
        )
        await session.commit()

    try:
        yield TenantId(tid)
    finally:
        async with async_session() as session:
            await session.execute(
                text(
                    "DELETE FROM integrations.notification_rule WHERE tenant_id = :id"
                ),
                {"id": tid},
            )
            await session.execute(
                text("DELETE FROM audit.access_log WHERE tenant_id = :id"),
                {"id": tid},
            )
            await session.execute(
                text("DELETE FROM tenant.tenant WHERE id = :id"), {"id": tid}
            )
            await session.commit()


async def _count_audit(tenant_id: TenantId, action: str) -> int:
    from sqlalchemy import text

    async with async_session() as session:
        result = await session.execute(
            text(
                "SELECT count(*) FROM audit.access_log "
                "WHERE tenant_id = :id AND action = :action"
            ),
            {"id": uuid.UUID(str(tenant_id)), "action": action},
        )
        return int(result.scalar_one())


async def test_crud_round_trip_resolves_channel_and_audits(
    tenant_id: TenantId,
) -> None:
    from packages.integrations.notification_schemas import (
        NotificationRuleIn,
        NotificationRulePatch,
    )
    from packages.integrations.notification_service import (
        AUDIT_NOTIFICATION_RULE_CREATE,
        AUDIT_NOTIFICATION_RULE_DELETE,
        AUDIT_NOTIFICATION_RULE_UPDATE,
        NotificationService,
    )

    principal = _principal(tenant_id)
    provider = _provider()

    # --- create (by channel NAME) ---
    async with async_session() as session:
        svc = NotificationService(session)
        created = await svc.create_rule(
            tenant_id,
            NotificationRuleIn(
                event_type="lead.created",
                channel="leads",  # NAME, not an id
                template={"text": "{{ summary }}"},
                description="route new leads",
            ),
            principal=principal,
            provider=provider,
        )
        rule_id = created.id
        await session.commit()

    provider.resolve_channel_id.assert_awaited_once_with("leads")
    assert created.channel == _RESOLVED_CHANNEL_ID  # stored as id, not name
    assert await _count_audit(tenant_id, AUDIT_NOTIFICATION_RULE_CREATE) == 1

    # --- list ---
    async with async_session() as session:
        rows = await NotificationService(session).list_rules(tenant_id)
    assert [r.id for r in rows] == [rule_id]
    assert rows[0].channel == _RESOLVED_CHANNEL_ID

    # --- toggle enabled via update (no channel change) ---
    async with async_session() as session:
        svc = NotificationService(session)
        updated = await svc.update_rule(
            tenant_id,
            rule_id,
            NotificationRulePatch(enabled=False),
            principal=principal,
            provider=_provider(),  # not consulted: no channel in patch
        )
        assert updated.enabled is False
        await session.commit()
    assert await _count_audit(tenant_id, AUDIT_NOTIFICATION_RULE_UPDATE) == 1

    # --- delete ---
    async with async_session() as session:
        svc = NotificationService(session)
        await svc.delete_rule(tenant_id, rule_id, principal=principal)
        await session.commit()
    assert await _count_audit(tenant_id, AUDIT_NOTIFICATION_RULE_DELETE) == 1

    async with async_session() as session:
        remaining = await NotificationService(session).list_rules(tenant_id)
    assert remaining == []


async def test_get_rule_missing_raises_not_found(tenant_id: TenantId) -> None:
    from packages.core.exceptions import NotFoundError
    from packages.integrations.notification_service import NotificationService

    async with async_session() as session:
        svc = NotificationService(session)
        with pytest.raises(NotFoundError):
            await svc.get_rule(tenant_id, uuid.uuid4())


async def test_create_rule_with_unresolvable_channel_raises(
    tenant_id: TenantId,
) -> None:
    from packages.integrations.notification_schemas import NotificationRuleIn
    from packages.integrations.notification_service import (
        ChannelResolutionError,
        NotificationService,
    )

    principal = _principal(tenant_id)
    provider = _provider(resolved=None)  # provider cannot map the name

    async with async_session() as session:
        svc = NotificationService(session)
        with pytest.raises(ChannelResolutionError):
            await svc.create_rule(
                tenant_id,
                NotificationRuleIn(event_type="lead.created", channel="nope"),
                principal=principal,
                provider=provider,
            )
