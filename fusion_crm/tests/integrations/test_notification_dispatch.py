"""Integration tests for the notification messenger layer (ENG-436, Block C).

Exercises the full enqueue → drain → send pipeline against the REAL local
Postgres (the dispatcher's ``FOR UPDATE SKIP LOCKED`` claim and the
partial pending index cannot be faithfully reproduced with a mocked
session). The suite skips cleanly when no local DB is reachable so it
does not block environments without a database.

Covered scenarios (per the ENG-436 spec):

1. enqueue → drain with a FAKE ChatProvider → row goes pending → sent and
   the fake provider received the rendered message.
2. drain idempotency: a 'sent' row is not re-sent on a second pass.
3. provider failure → row marked 'failed' with last_error.
4. rule round-trip: upsert_rule + list_rules returns JSONB intact.
5. seed_default_notification_rules is idempotent.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest

from packages.core.security import Principal, Role
from packages.core.types import TenantId

# ``async_session`` builds the engine at import time from DATABASE_URL.
# If Settings cannot be constructed (no env) the import itself fails;
# guard so the suite skips rather than errors during collection.
try:  # noqa: SIM105
    from packages.db.session import async_session

    _IMPORT_OK = True
except Exception:  # noqa: BLE001 — environment not configured for a DB
    _IMPORT_OK = False

pytestmark = pytest.mark.skipif(
    not _IMPORT_OK, reason="DATABASE_URL / Settings not configured for a live DB"
)


def _principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
    )


class _FakeChatProvider:
    """Records every message it is asked to post."""

    def __init__(self, *, ok: bool = True, error: str | None = None) -> None:
        self.ok = ok
        self.error = error
        self.posted: list[object] = []

    async def post(self, message: object):  # noqa: ANN001 — ChatMessage
        from packages.integrations.chat.base import ChatPostResult

        self.posted.append(message)
        return ChatPostResult(
            ok=self.ok,
            provider_message_id="mm-123" if self.ok else None,
            error=self.error,
        )

    async def resolve_channel_id(self, channel: str) -> str | None:
        # ENG-458: the dispatcher resolves the channel before posting. The fake
        # echoes the reference back so existing channel assertions still hold.
        return channel


async def _db_reachable() -> bool:
    from sqlalchemy import text

    # The global engine in ``packages.db.session`` is created once at import
    # on whatever loop imported it. pytest-asyncio runs each test on a fresh
    # per-function loop, so asyncpg connections from a previous test's loop
    # are dead. Dispose first so this probe (and the test) opens a fresh
    # connection bound to the current loop.
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
    """Create a throwaway tenant row; drop it (and its rows) on teardown."""
    if not await _db_reachable():
        pytest.skip("local Postgres not reachable (127.0.0.1:5434)")

    from sqlalchemy import text

    tid = uuid.uuid4()
    slug = f"eng436-test-{tid.hex[:12]}"
    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO tenant.tenant (id, slug, name, timezone, locale, status, "
                "created_at, updated_at) VALUES (:id, :slug, :name, 'UTC', 'en-US', "
                "'active', now(), now())"
            ),
            {"id": tid, "slug": slug, "name": "ENG-436 Test"},
        )

    try:
        yield TenantId(tid)
    finally:
        async with async_session() as session:
            await session.execute(
                text(
                    "DELETE FROM integrations.notification_outbox WHERE tenant_id = :id"
                ),
                {"id": tid},
            )
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


# --- 1. enqueue → drain → sent ------------------------------------------


async def test_enqueue_drain_sends_via_provider(
    tenant_id: TenantId, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.worker.jobs import notification_dispatch
    from packages.integrations.notification_repository import (
        NotificationOutboxRepository,
    )
    from packages.integrations.notification_schemas import NotificationOutboxIn
    from packages.integrations.notification_service import NotificationService

    fake = _FakeChatProvider(ok=True)

    async def _resolver(tid, kind, session):  # noqa: ANN001
        return fake

    monkeypatch.setattr(notification_dispatch, "resolve_chat_provider", _resolver)

    async with async_session() as session:
        svc = NotificationService(session)
        row = await svc.enqueue(
            tenant_id,
            NotificationOutboxIn(
                event_type="lead.created",
                channel="leads",
                payload={"text": "New lead abc — https://x/leads/abc"},
            ),
            principal=_principal(tenant_id),
        )
        outbox_id = row.id
        assert row.status == "pending"

    summary = await notification_dispatch.drain_notification_outbox({})
    assert summary["sent"] == 1, summary
    assert len(fake.posted) == 1
    assert fake.posted[0].channel == "leads"
    assert fake.posted[0].text == "New lead abc — https://x/leads/abc"

    async with async_session() as session:
        repo = NotificationOutboxRepository(session)
        refreshed = await repo.get(outbox_id)
        assert refreshed is not None
        assert refreshed.status == "sent"
        assert refreshed.sent_at is not None
        assert refreshed.payload.get("provider_message_id") == "mm-123"


# --- 2. drain idempotency -----------------------------------------------


async def test_drain_does_not_resend_sent_row(
    tenant_id: TenantId, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.worker.jobs import notification_dispatch
    from packages.integrations.notification_schemas import NotificationOutboxIn
    from packages.integrations.notification_service import NotificationService

    fake = _FakeChatProvider(ok=True)

    async def _resolver(tid, kind, session):  # noqa: ANN001
        return fake

    monkeypatch.setattr(notification_dispatch, "resolve_chat_provider", _resolver)

    async with async_session() as session:
        svc = NotificationService(session)
        await svc.enqueue(
            tenant_id,
            NotificationOutboxIn(event_type="lead.created", channel="leads"),
            principal=_principal(tenant_id),
        )

    first = await notification_dispatch.drain_notification_outbox({})
    assert first["sent"] == 1
    second = await notification_dispatch.drain_notification_outbox({})
    # Nothing pending left → no rows claimed → no re-send.
    assert second["sent"] == 0
    assert len(fake.posted) == 1


# --- 3. provider failure path -------------------------------------------


async def test_provider_failure_marks_row_failed(
    tenant_id: TenantId, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.worker.jobs import notification_dispatch
    from packages.integrations.notification_repository import (
        NotificationOutboxRepository,
    )
    from packages.integrations.notification_schemas import NotificationOutboxIn
    from packages.integrations.notification_service import NotificationService

    fake = _FakeChatProvider(ok=False, error="channel not found")

    async def _resolver(tid, kind, session):  # noqa: ANN001
        return fake

    monkeypatch.setattr(notification_dispatch, "resolve_chat_provider", _resolver)

    async with async_session() as session:
        svc = NotificationService(session)
        row = await svc.enqueue(
            tenant_id,
            NotificationOutboxIn(event_type="lead.created", channel="missing"),
            principal=_principal(tenant_id),
        )
        outbox_id = row.id

    summary = await notification_dispatch.drain_notification_outbox({})
    assert summary["failed"] == 1, summary

    async with async_session() as session:
        repo = NotificationOutboxRepository(session)
        refreshed = await repo.get(outbox_id)
        assert refreshed is not None
        assert refreshed.status == "failed"
        assert refreshed.last_error == "channel not found"
        assert refreshed.attempts == 1


async def test_resolver_without_credential_marks_row_failed(
    tenant_id: TenantId,
) -> None:
    """Real resolver + no mattermost credential → row degrades to failed.

    Block B (ENG-435) replaced the ``NotImplementedError`` placeholder
    with a real Mattermost resolver. The throwaway tenant has no
    ``mattermost`` credential, so ``resolve_chat_provider`` raises
    ``NoCredentialError``; the dispatcher's broad resolver-error handler
    marks the row failed.
    """
    from apps.worker.jobs import notification_dispatch
    from packages.integrations.notification_repository import (
        NotificationOutboxRepository,
    )
    from packages.integrations.notification_schemas import NotificationOutboxIn
    from packages.integrations.notification_service import NotificationService

    async with async_session() as session:
        svc = NotificationService(session)
        row = await svc.enqueue(
            tenant_id,
            NotificationOutboxIn(
                event_type="lead.created",
                channel="leads",
                provider_kind="mattermost",
            ),
            principal=_principal(tenant_id),
        )
        outbox_id = row.id

    summary = await notification_dispatch.drain_notification_outbox({})
    assert summary["failed"] == 1, summary

    async with async_session() as session:
        repo = NotificationOutboxRepository(session)
        refreshed = await repo.get(outbox_id)
        assert refreshed is not None
        assert refreshed.status == "failed"
        # Broad resolver-error handler records a type-only message.
        assert refreshed.last_error == "provider resolve error: NoCredentialError"


# --- 3b. stale-lock reclaim ---------------------------------------------


async def test_stale_locked_row_is_reclaimed_and_driven_terminal(
    tenant_id: TenantId, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A row stuck in ``status='locked'`` past the lease is reclaimed.

    Simulates a worker that crashed after locking but before marking the
    row terminal: insert the row, then back-date ``locked_at`` beyond
    ``LOCK_LEASE_SECONDS``. The next drain must reclaim it and drive it to
    ``sent``. A freshly-locked row (recent ``locked_at``) is NOT reclaimed.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    from apps.worker.jobs import notification_dispatch
    from packages.integrations.notification_repository import (
        LOCK_LEASE_SECONDS,
        NotificationOutboxRepository,
    )
    from packages.integrations.notification_schemas import NotificationOutboxIn
    from packages.integrations.notification_service import NotificationService

    fake = _FakeChatProvider(ok=True)

    async def _resolver(tid, kind, session):  # noqa: ANN001
        return fake

    monkeypatch.setattr(notification_dispatch, "resolve_chat_provider", _resolver)

    # Enqueue a row, then force it into a STALE locked state directly in SQL.
    async with async_session() as session:
        svc = NotificationService(session)
        stale = await svc.enqueue(
            tenant_id,
            NotificationOutboxIn(event_type="lead.created", channel="leads"),
            principal=_principal(tenant_id),
        )
        stale_id = stale.id

    stale_locked_at = datetime.now(UTC) - timedelta(seconds=LOCK_LEASE_SECONDS + 60)
    async with async_session() as session:
        await session.execute(
            text(
                "UPDATE integrations.notification_outbox "
                "SET status='locked', locked_by='dead-worker', locked_at=:la "
                "WHERE id=:id"
            ),
            {"la": stale_locked_at, "id": stale_id},
        )
        await session.commit()

    summary = await notification_dispatch.drain_notification_outbox({})
    assert summary["sent"] == 1, summary

    async with async_session() as session:
        repo = NotificationOutboxRepository(session)
        refreshed = await repo.get(stale_id)
        assert refreshed is not None
        assert refreshed.status == "sent"


async def test_fresh_locked_row_is_not_reclaimed(
    tenant_id: TenantId, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A row locked recently (within the lease) is left alone by the drain."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    from apps.worker.jobs import notification_dispatch
    from packages.integrations.notification_repository import (
        NotificationOutboxRepository,
    )
    from packages.integrations.notification_schemas import NotificationOutboxIn
    from packages.integrations.notification_service import NotificationService

    fake = _FakeChatProvider(ok=True)

    async def _resolver(tid, kind, session):  # noqa: ANN001
        return fake

    monkeypatch.setattr(notification_dispatch, "resolve_chat_provider", _resolver)

    async with async_session() as session:
        svc = NotificationService(session)
        fresh = await svc.enqueue(
            tenant_id,
            NotificationOutboxIn(event_type="lead.created", channel="leads"),
            principal=_principal(tenant_id),
        )
        fresh_id = fresh.id

    # Locked 5 seconds ago — well within the lease, so it must be skipped.
    recent_locked_at = datetime.now(UTC) - timedelta(seconds=5)
    async with async_session() as session:
        await session.execute(
            text(
                "UPDATE integrations.notification_outbox "
                "SET status='locked', locked_by='live-worker', locked_at=:la "
                "WHERE id=:id"
            ),
            {"la": recent_locked_at, "id": fresh_id},
        )
        await session.commit()

    summary = await notification_dispatch.drain_notification_outbox({})
    assert summary["sent"] == 0, summary
    assert len(fake.posted) == 0

    async with async_session() as session:
        repo = NotificationOutboxRepository(session)
        refreshed = await repo.get(fresh_id)
        assert refreshed is not None
        # Untouched — still locked by the other (live) worker.
        assert refreshed.status == "locked"
        assert refreshed.locked_by == "live-worker"


# --- 4. rule round-trip --------------------------------------------------


async def test_rule_round_trip_preserves_jsonb(tenant_id: TenantId) -> None:
    from packages.integrations.notification_schemas import NotificationRuleIn
    from packages.integrations.notification_service import NotificationService

    conditions = [{"field": "phone", "op": "is_empty"}]
    template = {"text": "New lead {{person_uid}}", "blocks": [{"type": "section"}]}

    async with async_session() as session:
        svc = NotificationService(session)
        created = await svc.upsert_rule(
            tenant_id,
            NotificationRuleIn(
                event_type="lead.created",
                channel="leads",
                conditions=conditions,
                template=template,
                description="round trip",
            ),
            principal=_principal(tenant_id),
        )
        created_id = created.id

    async with async_session() as session:
        svc = NotificationService(session)
        rules = await svc.list_rules(tenant_id, event_type="lead.created")
        assert len(rules) == 1
        rule = rules[0]
        assert rule.id == created_id
        assert rule.conditions == conditions
        assert rule.template == template
        assert rule.enabled is True

    # Idempotent upsert on (event_type, channel) → still one rule, updated.
    async with async_session() as session:
        svc = NotificationService(session)
        await svc.upsert_rule(
            tenant_id,
            NotificationRuleIn(
                event_type="lead.created",
                channel="leads",
                conditions=[],
                template={"text": "changed"},
                enabled=False,
            ),
            principal=_principal(tenant_id),
        )

    async with async_session() as session:
        svc = NotificationService(session)
        rules = await svc.list_rules(tenant_id)
        assert len(rules) == 1
        assert rules[0].id == created_id
        assert rules[0].enabled is False
        assert rules[0].template == {"text": "changed"}


# --- 5. seed idempotency -------------------------------------------------


async def test_seed_default_rules_is_idempotent(tenant_id: TenantId) -> None:
    # ENG-437 Block D extended the seed from one rule to the full default
    # set (one per canonical event type + the phone-less field-control
    # rule). The flagship ``lead.created`` → ``leads`` rule is still
    # returned by ``seed_default_notification_rules`` for the Block C
    # return contract.
    from packages.integrations.chat.seeds import (
        _DEFAULT_RULES,
        seed_default_notification_rules,
    )
    from packages.integrations.notification_service import NotificationService

    expected_count = len(_DEFAULT_RULES)

    async with async_session() as session:
        r1 = await seed_default_notification_rules(session, tenant_id)
        first_id = r1.id

    async with async_session() as session:
        r2 = await seed_default_notification_rules(session, tenant_id)
        assert r2.id == first_id

    async with async_session() as session:
        svc = NotificationService(session)
        rules = await svc.list_rules(tenant_id)
        assert len(rules) == expected_count
        flagship = next(
            r for r in rules if r.event_type == "lead.created" and r.channel == "leads"
        )
        assert flagship.id == first_id
        # ENG-460: the flagship lead.created rule now carries the rich card.
        from packages.integrations.chat.seeds import LEAD_CREATED_RICH_TEMPLATE

        assert flagship.template == LEAD_CREATED_RICH_TEMPLATE
        assert flagship.template["blocks"][0]["text"] == "**{{name}}**"
