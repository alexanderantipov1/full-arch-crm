"""Integration tests for the consultation.scheduled emit (ENG-457, Block C).

Exercises the FULL real path against local Postgres: the ingest-boundary
helper ``emit_consultation_scheduled_notification`` →
``NotificationEventService.emit`` → durable dedupe ledger → seeded
``#scheduls`` rule → de-identified outbox row.

Covered scenarios (per the ENG-457 spec):

1. A newly-created consultation emits exactly ONE outbox row to the
   ``#scheduls`` channel id.
2. Re-emit of the SAME consultation id emits nothing (durable dedupe).
3. The backfill path (notifier=None) emits nothing.
4. An updated (``was_created=False``) consultation emits nothing.
5. A pre-cutoff consultation is suppressed by the historical-cutoff guard.

Notifications default OFF, so the fixture flips ``notifications_enabled`` on
the cached settings (reverted by ``monkeypatch``) exactly like the legacy
emit test.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.ops.models import ConsultationKind, ConsultationStatus
from packages.ops.schemas import ConsultationOut, ConsultationUpsertResult

try:  # noqa: SIM105
    from packages.db.session import async_session

    _IMPORT_OK = True
except Exception:  # noqa: BLE001 — environment not configured for a DB
    _IMPORT_OK = False

pytestmark = pytest.mark.skipif(
    not _IMPORT_OK, reason="DATABASE_URL / Settings not configured for a live DB"
)

_PROVIDER_CREATED_AT = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
_SCHEDULED_AT = datetime(2026, 6, 12, 14, 0, tzinfo=UTC)


def _principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
    )


def _upsert_result(
    *,
    consultation_id: uuid.UUID,
    person_uid: uuid.UUID,
    was_created: bool = True,
    provider_created_at: datetime | None = _PROVIDER_CREATED_AT,
    location_id: uuid.UUID | None = None,
) -> ConsultationUpsertResult:
    return ConsultationUpsertResult(
        consultation=ConsultationOut(
            id=consultation_id,
            person_uid=person_uid,
            source_provider="salesforce",
            source_instance="salesforce-main",
            external_id="00U5j000001abcd",
            scheduled_at=_SCHEDULED_AT,
            duration_minutes=30,
            status=ConsultationStatus.SCHEDULED,
            consultation_kind=ConsultationKind.INITIAL,
            location_id=location_id,
            provider_clinician_name=None,
            raw_event_id=uuid.uuid4(),
            provider_created_at=provider_created_at,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        was_created=was_created,
        was_changed=was_created,
    )


@pytest.fixture(autouse=True)
def _notifications_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _IMPORT_OK:
        return
    from packages.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "notifications_enabled", True, raising=False)
    monkeypatch.setattr(settings, "notifications_cutoff_at", None, raising=False)


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
    slug = f"eng457-test-{tid.hex[:12]}"
    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO tenant.tenant (id, slug, name, timezone, locale, "
                "status, created_at, updated_at) VALUES (:id, :slug, :name, 'UTC', "
                "'en-US', 'active', now(), now())"
            ),
            {"id": tid, "slug": slug, "name": "ENG-457 Test"},
        )

    try:
        yield TenantId(tid)
    finally:
        async with async_session() as session:
            for table in (
                "integrations.notification_outbox",
                "integrations.notification_emitted",
                "integrations.notification_rule",
                "tenant.location",
                "audit.access_log",
            ):
                await session.execute(
                    text(f"DELETE FROM {table} WHERE tenant_id = :id"),
                    {"id": tid},
                )
            await session.execute(
                text("DELETE FROM tenant.tenant WHERE id = :id"), {"id": tid}
            )


async def _outbox_rows(tenant_id: TenantId, event_type: str) -> list[object]:
    from sqlalchemy import select

    from packages.integrations.models import NotificationOutbox

    async with async_session() as session:
        rows = (
            await session.execute(
                select(NotificationOutbox)
                .where(NotificationOutbox.tenant_id == tenant_id)
                .where(NotificationOutbox.event_type == event_type)
            )
        ).scalars().all()
        return list(rows)


# --- 1. new consultation → exactly one #scheduls row --------------------


async def test_new_consultation_emits_one_scheduls_row(tenant_id: TenantId) -> None:
    from packages.ingest.consultation_notify import (
        CONSULTATION_SCHEDULED_EVENT,
        emit_consultation_scheduled_notification,
    )
    from packages.integrations.chat.event_service import NotificationEventService
    from packages.integrations.chat.seeds import (
        SCHEDULS_CHANNEL,
        seed_all_notification_rules,
    )

    consultation_id = uuid.uuid4()
    person_uid = uuid.uuid4()

    async with async_session() as session:
        await seed_all_notification_rules(session, tenant_id)
        notifier = NotificationEventService(session)
        await emit_consultation_scheduled_notification(
            notifier,
            tenant_id,
            _upsert_result(consultation_id=consultation_id, person_uid=person_uid),
            source_provider="salesforce",
            principal=_principal(tenant_id),
        )
        await session.commit()

    rows = await _outbox_rows(tenant_id, CONSULTATION_SCHEDULED_EVENT)
    assert len(rows) == 1
    row = rows[0]
    # ENG-458: with no location the rule's bare channel name is enqueued as-is
    # (the dispatcher resolves it against the bot's default team at post time).
    assert row.channel == SCHEDULS_CHANNEL  # type: ignore[attr-defined]
    assert row.status == "pending"  # type: ignore[attr-defined]
    text = str(row.payload)  # type: ignore[attr-defined]
    assert "{{" not in text  # all placeholders substituted
    assert str(person_uid) in text  # opaque uid present + deep link
    # ENG-465b: the card title + readable scheduled time always render. The
    # Kind / Duration / Source clutter was dropped, so we no longer assert on
    # consultation_kind here.
    assert "Consultation scheduled" in text
    assert "2026" in text  # readable scheduled time present


# --- 1b. per-location routing → team-qualified #scheduls (ENG-458) ------


async def test_consultation_with_location_routes_to_team_scheduls(
    tenant_id: TenantId,
) -> None:
    import json

    from sqlalchemy import text

    from packages.ingest.consultation_notify import (
        CONSULTATION_SCHEDULED_EVENT,
        emit_consultation_scheduled_notification,
    )
    from packages.integrations.chat.event_service import NotificationEventService
    from packages.integrations.chat.seeds import seed_all_notification_rules

    location_id = uuid.uuid4()
    consultation_id = uuid.uuid4()
    person_uid = uuid.uuid4()

    async with async_session() as session:
        # A location mapped to the ``galleria`` Mattermost team.
        await session.execute(
            text(
                "INSERT INTO tenant.location (id, tenant_id, name, external_ref, "
                "is_active, created_at, updated_at) VALUES (:id, :tid, :name, "
                "CAST(:ext AS jsonb), true, now(), now())"
            ),
            {
                "id": location_id,
                "tid": tenant_id,
                "name": "Galleria Oral Surgery & Dental Implants",
                "ext": json.dumps(
                    {"carestack_location_id": 10029, "mattermost_team": "galleria"}
                ),
            },
        )
        await seed_all_notification_rules(session, tenant_id)
        notifier = NotificationEventService(session)
        await emit_consultation_scheduled_notification(
            notifier,
            tenant_id,
            _upsert_result(
                consultation_id=consultation_id,
                person_uid=person_uid,
                location_id=location_id,
            ),
            source_provider="salesforce",
            principal=_principal(tenant_id),
        )
        await session.commit()

    rows = await _outbox_rows(tenant_id, CONSULTATION_SCHEDULED_EVENT)
    assert len(rows) == 1
    # Routed to the consultation's clinic team, not a bare channel name.
    assert rows[0].channel == "galleria/scheduls"  # type: ignore[attr-defined]


async def test_explicit_mattermost_team_in_context_wins(tenant_id: TenantId) -> None:
    # An explicit ``mattermost_team`` in the emit context takes precedence over
    # any location lookup (the documented precedence rule).
    from packages.integrations.chat.event_service import NotificationEventService
    from packages.integrations.chat.events import EVENT_CONSULTATION_SCHEDULED
    from packages.integrations.chat.seeds import seed_all_notification_rules

    person_uid = uuid.uuid4()
    async with async_session() as session:
        await seed_all_notification_rules(session, tenant_id)
        notifier = NotificationEventService(session)
        await notifier.emit(
            tenant_id,
            EVENT_CONSULTATION_SCHEDULED,
            {
                "mattermost_team": "san-francisco",
                "name": "Test Patient",
                "scheduled_when": "Jun 12, 2026 2:00 PM UTC",
            },
            principal=_principal(tenant_id),
            person_uid=person_uid,
        )
        await session.commit()

    rows = await _outbox_rows(tenant_id, EVENT_CONSULTATION_SCHEDULED)
    assert len(rows) == 1
    assert rows[0].channel == "san-francisco/scheduls"  # type: ignore[attr-defined]


async def test_location_without_team_mapping_falls_back_to_bare_channel(
    tenant_id: TenantId,
) -> None:
    # A location that exists but carries no ``mattermost_team`` (not yet mapped
    # during rollout) routes to the bare channel name — the dispatcher then uses
    # the bot's default team. Must not crash or emit ``None/scheduls``.
    import json

    from sqlalchemy import text

    from packages.ingest.consultation_notify import (
        CONSULTATION_SCHEDULED_EVENT,
        emit_consultation_scheduled_notification,
    )
    from packages.integrations.chat.event_service import NotificationEventService
    from packages.integrations.chat.seeds import seed_all_notification_rules

    location_id = uuid.uuid4()
    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO tenant.location (id, tenant_id, name, external_ref, "
                "is_active, created_at, updated_at) VALUES (:id, :tid, :name, "
                "CAST(:ext AS jsonb), true, now(), now())"
            ),
            {
                "id": location_id,
                "tid": tenant_id,
                "name": "Unmapped Clinic",
                "ext": json.dumps({"carestack_location_id": 7777}),
            },
        )
        await seed_all_notification_rules(session, tenant_id)
        notifier = NotificationEventService(session)
        await emit_consultation_scheduled_notification(
            notifier,
            tenant_id,
            _upsert_result(
                consultation_id=uuid.uuid4(),
                person_uid=uuid.uuid4(),
                location_id=location_id,
            ),
            source_provider="salesforce",
            principal=_principal(tenant_id),
        )
        await session.commit()

    rows = await _outbox_rows(tenant_id, CONSULTATION_SCHEDULED_EVENT)
    assert len(rows) == 1
    assert rows[0].channel == "scheduls"  # type: ignore[attr-defined]


# --- 2. re-emit of same consultation → dedupe (no second row) -----------


async def test_reingest_same_consultation_emits_nothing(tenant_id: TenantId) -> None:
    from packages.ingest.consultation_notify import (
        CONSULTATION_SCHEDULED_EVENT,
        emit_consultation_scheduled_notification,
    )
    from packages.integrations.chat.event_service import NotificationEventService
    from packages.integrations.chat.seeds import seed_all_notification_rules

    consultation_id = uuid.uuid4()
    person_uid = uuid.uuid4()

    async with async_session() as session:
        await seed_all_notification_rules(session, tenant_id)
        notifier = NotificationEventService(session)
        result = _upsert_result(
            consultation_id=consultation_id, person_uid=person_uid
        )
        await emit_consultation_scheduled_notification(
            notifier,
            tenant_id,
            result,
            source_provider="salesforce",
            principal=_principal(tenant_id),
        )
        await session.commit()

    # Second pull of the SAME consultation id (created again, e.g. an
    # idempotency hiccup) must NOT enqueue a second row.
    async with async_session() as session:
        notifier = NotificationEventService(session)
        await emit_consultation_scheduled_notification(
            notifier,
            tenant_id,
            _upsert_result(consultation_id=consultation_id, person_uid=person_uid),
            source_provider="salesforce",
            principal=_principal(tenant_id),
        )
        await session.commit()

    rows = await _outbox_rows(tenant_id, CONSULTATION_SCHEDULED_EVENT)
    assert len(rows) == 1


# --- 3. backfill (notifier=None) → nothing ------------------------------


async def test_backfill_emits_nothing(tenant_id: TenantId) -> None:
    from packages.ingest.consultation_notify import (
        CONSULTATION_SCHEDULED_EVENT,
        emit_consultation_scheduled_notification,
    )
    from packages.integrations.chat.seeds import seed_all_notification_rules

    async with async_session() as session:
        await seed_all_notification_rules(session, tenant_id)
        # The backfill path passes notifier=None — boundary helper no-ops.
        await emit_consultation_scheduled_notification(
            None,
            tenant_id,
            _upsert_result(
                consultation_id=uuid.uuid4(), person_uid=uuid.uuid4()
            ),
            source_provider="salesforce",
            principal=_principal(tenant_id),
        )
        await session.commit()

    rows = await _outbox_rows(tenant_id, CONSULTATION_SCHEDULED_EVENT)
    assert rows == []


# --- 4. updated (not created) consultation → nothing --------------------


async def test_updated_consultation_emits_nothing(tenant_id: TenantId) -> None:
    from packages.ingest.consultation_notify import (
        CONSULTATION_SCHEDULED_EVENT,
        emit_consultation_scheduled_notification,
    )
    from packages.integrations.chat.event_service import NotificationEventService
    from packages.integrations.chat.seeds import seed_all_notification_rules

    async with async_session() as session:
        await seed_all_notification_rules(session, tenant_id)
        notifier = NotificationEventService(session)
        await emit_consultation_scheduled_notification(
            notifier,
            tenant_id,
            _upsert_result(
                consultation_id=uuid.uuid4(),
                person_uid=uuid.uuid4(),
                was_created=False,  # update, not a create
            ),
            source_provider="salesforce",
            principal=_principal(tenant_id),
        )
        await session.commit()

    rows = await _outbox_rows(tenant_id, CONSULTATION_SCHEDULED_EVENT)
    assert rows == []


# --- 4b. ENG-460: full mode carries the real name into the card ---------


async def test_full_mode_consultation_card_carries_name(
    tenant_id: TenantId, monkeypatch: pytest.MonkeyPatch
) -> None:
    from packages.core.config import get_settings
    from packages.ingest.consultation_notify import (
        CONSULTATION_SCHEDULED_EVENT,
        emit_consultation_scheduled_notification,
    )
    from packages.integrations.chat.event_service import NotificationEventService
    from packages.integrations.chat.seeds import seed_all_notification_rules

    monkeypatch.setattr(
        get_settings(), "messenger_phi_full", True, raising=False
    )
    async with async_session() as session:
        await seed_all_notification_rules(session, tenant_id)
        notifier = NotificationEventService(session)
        await emit_consultation_scheduled_notification(
            notifier,
            tenant_id,
            _upsert_result(consultation_id=uuid.uuid4(), person_uid=uuid.uuid4()),
            source_provider="carestack",
            principal=_principal(tenant_id),
            person_name="Ghausuddin Nezami",
        )
        await session.commit()

    rows = await _outbox_rows(tenant_id, CONSULTATION_SCHEDULED_EVENT)
    assert len(rows) == 1
    payload = rows[0].payload  # type: ignore[attr-defined]
    text = str(payload)
    assert "Ghausuddin Nezami" in text
    assert "[redacted]" not in text
    assert payload["blocks"][0]["text"] == "**Ghausuddin Nezami**"


# --- 5. pre-cutoff consultation → suppressed ----------------------------


async def test_pre_cutoff_consultation_emits_nothing(
    tenant_id: TenantId, monkeypatch: pytest.MonkeyPatch
) -> None:
    from packages.core.config import get_settings
    from packages.ingest.consultation_notify import (
        CONSULTATION_SCHEDULED_EVENT,
        emit_consultation_scheduled_notification,
    )
    from packages.integrations.chat.event_service import NotificationEventService
    from packages.integrations.chat.seeds import seed_all_notification_rules

    # Cutoff AFTER the consultation's provider_created_at → suppressed.
    cutoff = _PROVIDER_CREATED_AT + timedelta(days=1)
    monkeypatch.setattr(
        get_settings(), "notifications_cutoff_at", cutoff, raising=False
    )

    async with async_session() as session:
        await seed_all_notification_rules(session, tenant_id)
        notifier = NotificationEventService(session)
        await emit_consultation_scheduled_notification(
            notifier,
            tenant_id,
            _upsert_result(
                consultation_id=uuid.uuid4(), person_uid=uuid.uuid4()
            ),
            source_provider="salesforce",
            principal=_principal(tenant_id),
        )
        await session.commit()

    rows = await _outbox_rows(tenant_id, CONSULTATION_SCHEDULED_EVENT)
    assert rows == []
