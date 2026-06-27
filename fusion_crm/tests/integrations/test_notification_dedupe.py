"""Integration tests for the dedupe core (ENG-455, Block A).

Exercises the guarantees that make new-entity notifications reliable against
the REAL local Postgres:

* the ledger ``claim`` is idempotent (first True, second False);
* ``emit`` with the same ``dedupe_key`` twice enqueues exactly ONE row;
* ``emit`` honours the historical ``notifications_cutoff_at``;
* ``emit`` is a no-op when ``notifications_enabled`` is False.

Skips cleanly when no local DB is reachable, mirroring
``test_notification_emit.py``.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

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

DEDUPE_EVENT = "lead.created"
DEDUPE_CHANNEL = "leads"


def _principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
    )


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
def settings():  # type: ignore[no-untyped-def]
    """The live cached Settings (used to toggle the ENG-455 flags per test)."""
    from packages.core.config import get_settings

    return get_settings()


@pytest.fixture(autouse=True)
def _enable_notifications(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default each test to ENABLED + no cutoff; individual tests override."""
    if not _IMPORT_OK:
        return
    from packages.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "notifications_enabled", True, raising=False)
    monkeypatch.setattr(s, "notifications_cutoff_at", None, raising=False)


@pytest.fixture
async def tenant_id() -> AsyncIterator[TenantId]:
    if not await _db_reachable():
        pytest.skip("local Postgres not reachable (127.0.0.1:5434)")

    from sqlalchemy import text

    tid = uuid.uuid4()
    slug = f"eng455-test-{tid.hex[:12]}"
    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO tenant.tenant (id, slug, name, timezone, locale, status, "
                "created_at, updated_at) VALUES (:id, :slug, :name, 'UTC', 'en-US', "
                "'active', now(), now())"
            ),
            {"id": tid, "slug": slug, "name": "ENG-455 Test"},
        )

    try:
        yield TenantId(tid)
    finally:
        async with async_session() as session:
            for tbl in (
                "integrations.notification_outbox",
                "integrations.notification_emitted",
                "integrations.notification_rule",
                "audit.access_log",
            ):
                await session.execute(
                    text(f"DELETE FROM {tbl} WHERE tenant_id = :id"), {"id": tid}
                )
            await session.execute(
                text("DELETE FROM tenant.tenant WHERE id = :id"), {"id": tid}
            )


async def _seed_default_rule(tenant_id: TenantId) -> None:
    from packages.integrations.notification_schemas import NotificationRuleIn
    from packages.integrations.notification_service import NotificationService

    async with async_session() as session:
        await NotificationService(session).upsert_rule(
            tenant_id,
            NotificationRuleIn(
                event_type=DEDUPE_EVENT,
                channel=DEDUPE_CHANNEL,
                conditions=[],  # unconditional
                template={"text": "New lead {{person_uid}}"},
            ),
            principal=_principal(tenant_id),
        )
        await session.commit()


# --- 1. ledger claim is idempotent --------------------------------------


async def test_claim_is_idempotent(tenant_id: TenantId) -> None:
    from packages.integrations.notification_repository import (
        NotificationEmittedRepository,
    )

    key = f"lead-{uuid.uuid4().hex}"
    async with async_session() as session:
        repo = NotificationEmittedRepository(session)
        first = await repo.claim(tenant_id, DEDUPE_EVENT, key)
        second = await repo.claim(tenant_id, DEDUPE_EVENT, key)
        assert first is True
        assert second is False
        await session.commit()

    # A different key (or event type) is independent → claims True.
    async with async_session() as session:
        repo = NotificationEmittedRepository(session)
        assert await repo.claim(tenant_id, DEDUPE_EVENT, f"other-{key}") is True
        assert await repo.claim(tenant_id, "ownership.changed", key) is True
        await session.commit()


async def test_claim_survives_across_sessions(tenant_id: TenantId) -> None:
    """A committed claim in one session blocks a claim in a later session."""
    from packages.integrations.notification_repository import (
        NotificationEmittedRepository,
    )

    key = f"lead-{uuid.uuid4().hex}"
    async with async_session() as session:
        assert (
            await NotificationEmittedRepository(session).claim(
                tenant_id, DEDUPE_EVENT, key
            )
            is True
        )
        await session.commit()

    async with async_session() as session:
        assert (
            await NotificationEmittedRepository(session).claim(
                tenant_id, DEDUPE_EVENT, key
            )
            is False
        )
        await session.commit()


# --- 2. emit with same dedupe_key twice → exactly ONE outbox row --------


async def test_emit_dedupe_key_enqueues_once(tenant_id: TenantId) -> None:
    from sqlalchemy import text

    from packages.integrations.chat.event_service import NotificationEventService

    await _seed_default_rule(tenant_id)
    key = f"lead-{uuid.uuid4().hex}"
    context: dict[str, object] = {"owner_role": "agent"}

    async with async_session() as session:
        svc = NotificationEventService(session)
        rows1 = await svc.emit(
            tenant_id,
            DEDUPE_EVENT,
            context,
            principal=_principal(tenant_id),
            person_uid=uuid.uuid4(),
            dedupe_key=key,
        )
        await session.commit()
    assert len(rows1) == 1

    async with async_session() as session:
        svc = NotificationEventService(session)
        rows2 = await svc.emit(
            tenant_id,
            DEDUPE_EVENT,
            context,
            principal=_principal(tenant_id),
            person_uid=uuid.uuid4(),
            dedupe_key=key,
        )
        await session.commit()
    assert rows2 == []  # idempotent skip on the second emit

    async with async_session() as session:
        total = await session.scalar(
            text(
                "SELECT count(*) FROM integrations.notification_outbox "
                "WHERE tenant_id = :id AND event_type = :et"
            ),
            {"id": tenant_id, "et": DEDUPE_EVENT},
        )
    assert total == 1


async def test_no_matching_rule_does_not_burn_dedupe_key(
    tenant_id: TenantId,
) -> None:
    """A no-rule / no-match emit must NOT claim the ledger, so a later real
    notification (once a matching rule exists) STILL fires.

    Regression for the claim-before-rules ordering bug (Codex review of PR
    #163): the dedupe claim must be taken AFTER we know >=1 row will enqueue,
    otherwise an emit with no matching rule permanently suppresses the entity.
    """
    from sqlalchemy import text

    from packages.integrations.chat.event_service import NotificationEventService

    key = f"lead-{uuid.uuid4().hex}"
    context: dict[str, object] = {"owner_role": "agent"}

    # 1) No rule seeded yet → enqueue nothing AND claim nothing.
    async with async_session() as session:
        rows = await NotificationEventService(session).emit(
            tenant_id,
            DEDUPE_EVENT,
            context,
            principal=_principal(tenant_id),
            person_uid=uuid.uuid4(),
            dedupe_key=key,
        )
        await session.commit()
    assert rows == []

    async with async_session() as session:
        claimed = await session.scalar(
            text(
                "SELECT count(*) FROM integrations.notification_emitted "
                "WHERE tenant_id = :id AND dedupe_key = :k"
            ),
            {"id": tenant_id, "k": key},
        )
    assert claimed == 0  # ledger NOT burned by the no-match emit

    # 2) Now a matching rule exists → the SAME dedupe_key STILL notifies once.
    await _seed_default_rule(tenant_id)
    async with async_session() as session:
        rows = await NotificationEventService(session).emit(
            tenant_id,
            DEDUPE_EVENT,
            context,
            principal=_principal(tenant_id),
            person_uid=uuid.uuid4(),
            dedupe_key=key,
        )
        await session.commit()
    assert len(rows) == 1  # would be 0 under the pre-fix bug (key already burned)


# --- 3. emit honours the historical cutoff ------------------------------


async def test_emit_suppresses_pre_cutoff_entity(
    tenant_id: TenantId, settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import text

    from packages.integrations.chat.event_service import NotificationEventService

    await _seed_default_rule(tenant_id)
    cutoff = datetime(2026, 1, 1, tzinfo=UTC)
    monkeypatch.setattr(settings, "notifications_cutoff_at", cutoff, raising=False)

    # Entity created BEFORE the cutoff → zero rows.
    async with async_session() as session:
        rows_old = await NotificationEventService(session).emit(
            tenant_id,
            DEDUPE_EVENT,
            {},
            principal=_principal(tenant_id),
            person_uid=uuid.uuid4(),
            source_created_at=cutoff - timedelta(days=1),
        )
        await session.commit()
    assert rows_old == []

    # Entity created AT/AFTER the cutoff → one row.
    async with async_session() as session:
        rows_new = await NotificationEventService(session).emit(
            tenant_id,
            DEDUPE_EVENT,
            {},
            principal=_principal(tenant_id),
            person_uid=uuid.uuid4(),
            source_created_at=cutoff + timedelta(days=1),
        )
        await session.commit()
    assert len(rows_new) == 1

    async with async_session() as session:
        total = await session.scalar(
            text(
                "SELECT count(*) FROM integrations.notification_outbox "
                "WHERE tenant_id = :id"
            ),
            {"id": tenant_id},
        )
    assert total == 1


# --- 4. emit is a no-op when notifications are disabled -----------------


async def test_emit_noop_when_disabled(
    tenant_id: TenantId, settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import text

    from packages.integrations.chat.event_service import NotificationEventService

    await _seed_default_rule(tenant_id)
    monkeypatch.setattr(settings, "notifications_enabled", False, raising=False)

    async with async_session() as session:
        rows = await NotificationEventService(session).emit(
            tenant_id,
            DEDUPE_EVENT,
            {},
            principal=_principal(tenant_id),
            person_uid=uuid.uuid4(),
            dedupe_key=f"lead-{uuid.uuid4().hex}",
        )
        await session.commit()
    assert rows == []

    async with async_session() as session:
        outbox = await session.scalar(
            text(
                "SELECT count(*) FROM integrations.notification_outbox "
                "WHERE tenant_id = :id"
            ),
            {"id": tenant_id},
        )
        # Disabled returns BEFORE the ledger claim — nothing recorded either.
        emitted = await session.scalar(
            text(
                "SELECT count(*) FROM integrations.notification_emitted "
                "WHERE tenant_id = :id"
            ),
            {"id": tenant_id},
        )
    assert outbox == 0
    assert emitted == 0


async def test_emit_enabled_emits(tenant_id: TenantId) -> None:
    """Control: with the (autouse) enabled flag, a plain emit produces a row."""
    from packages.integrations.chat.event_service import NotificationEventService

    await _seed_default_rule(tenant_id)
    async with async_session() as session:
        rows = await NotificationEventService(session).emit(
            tenant_id,
            DEDUPE_EVENT,
            {},
            principal=_principal(tenant_id),
            person_uid=uuid.uuid4(),
        )
        await session.commit()
    assert len(rows) == 1


# --- 5. existing behaviour unchanged: no dedupe_key, enabled → emits ----


async def test_emit_without_dedupe_key_unchanged(tenant_id: TenantId) -> None:
    from packages.integrations.chat.event_service import NotificationEventService

    await _seed_default_rule(tenant_id)
    async with async_session() as session:
        svc = NotificationEventService(session)
        # Two emits with NO dedupe_key both enqueue (legacy behaviour: emit
        # is not deduped unless a key is supplied).
        rows1 = await svc.emit(
            tenant_id,
            DEDUPE_EVENT,
            {},
            principal=_principal(tenant_id),
            person_uid=uuid.uuid4(),
        )
        rows2 = await svc.emit(
            tenant_id,
            DEDUPE_EVENT,
            {},
            principal=_principal(tenant_id),
            person_uid=uuid.uuid4(),
        )
        await session.commit()
    assert len(rows1) == 1
    assert len(rows2) == 1
