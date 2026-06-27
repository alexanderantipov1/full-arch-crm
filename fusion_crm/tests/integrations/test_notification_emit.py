"""Integration tests for NotificationEventService.emit (ENG-437, Block D).

Exercises the rule engine against the REAL local Postgres (the emit flow
reads enabled rules and writes outbox rows through the same session/repo
stack the dispatcher uses). Skips cleanly when no local DB is reachable.

Covered scenarios (per the ENG-437 spec):

1. For each of the 4 canonical event types, a seeded matching rule
   produces a pending outbox row with a de-identified payload.
2. A non-matching condition produces NO row.
3. The field-control rule (phone is_empty) fires only when phone empty.
4. The de-identified payload contains person_uid + deep_link, never PII.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

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


def _principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
    )


@pytest.fixture(autouse=True)
def _notifications_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable the messenger engine for the legacy emit tests (ENG-455).

    ``Settings.notifications_enabled`` defaults to False so the wiring lands
    dark; these tests assert the ENABLED behaviour, so flip it on the cached
    settings object and clear any cutoff. Patching the live instance avoids
    re-reading ``.env`` and is reverted automatically by ``monkeypatch``.
    """
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
    slug = f"eng437-test-{tid.hex[:12]}"
    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO tenant.tenant (id, slug, name, timezone, locale, status, "
                "created_at, updated_at) VALUES (:id, :slug, :name, 'UTC', 'en-US', "
                "'active', now(), now())"
            ),
            {"id": tid, "slug": slug, "name": "ENG-437 Test"},
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


# --- 1. each canonical event type fires its seeded rule -----------------


@pytest.mark.parametrize(
    "event_type,channel",
    [
        ("lead.created", "leads"),
        ("opportunity.stage_changed", "opportunities"),
        ("ownership.changed", "ownership"),
        ("ingest.sync_failed", "ingest-alerts"),
    ],
)
async def test_emit_fires_seeded_rule_per_event_type(
    tenant_id: TenantId, event_type: str, channel: str
) -> None:
    from packages.integrations.chat.event_service import NotificationEventService
    from packages.integrations.chat.seeds import seed_all_notification_rules

    person_uid = uuid.uuid4()

    async with async_session() as session:
        await seed_all_notification_rules(session, tenant_id)
        svc = NotificationEventService(session)
        rows = await svc.emit(
            tenant_id,
            event_type,
            {
                "stage": "qualified",
                "owner_role": "agent",
                "provider": "salesforce",
                "object": "Lead",
                "sync_status": "failed",
            },
            principal=_principal(tenant_id),
            person_uid=person_uid,
        )
        # The unconditional default rule for this event must fire. (For
        # lead.created the phone-less field-control rule also fires since no
        # phone is supplied — assert the default channel is among them.)
        channels = {r.channel for r in rows}
        assert channel in channels, (event_type, channels)
        default_row = next(r for r in rows if r.channel == channel)
        assert default_row.status == "pending"
        assert default_row.event_type == event_type
        assert default_row.rule_id is not None
        # De-identified payload: all placeholders substituted, nothing left
        # dangling, and no stray PII (only allowlisted labels were passed).
        text = str(default_row.payload)
        assert "{{" not in text  # all placeholders substituted
        # Person-scoped events carry the opaque uid; the ingest alert is a
        # system event with no person, so its template omits person_uid.
        if event_type != "ingest.sync_failed":
            assert str(person_uid) in text


# --- 2. non-matching condition produces no row --------------------------


async def test_emit_skips_non_matching_condition(tenant_id: TenantId) -> None:
    from packages.integrations.chat.event_service import NotificationEventService
    from packages.integrations.notification_schemas import NotificationRuleIn
    from packages.integrations.notification_service import NotificationService

    async with async_session() as session:
        notif = NotificationService(session)
        await notif.upsert_rule(
            tenant_id,
            NotificationRuleIn(
                event_type="lead.created",
                channel="qualified-only",
                conditions=[{"field": "lead.Status", "op": "eq", "value": "qualified"}],
                template={"text": "Qualified lead {{person_uid}}"},
            ),
            principal=_principal(tenant_id),
        )
        svc = NotificationEventService(session)
        rows = await svc.emit(
            tenant_id,
            "lead.created",
            {"lead": {"Status": "new"}},  # not qualified → no match
            principal=_principal(tenant_id),
            person_uid=uuid.uuid4(),
        )
        assert rows == []


# --- 3. field-control phone rule fires only when phone empty ------------


async def test_field_control_phone_rule_fires_only_when_empty(
    tenant_id: TenantId,
) -> None:
    from packages.integrations.chat.event_service import NotificationEventService
    from packages.integrations.chat.seeds import (
        LEADS_MISSING_INFO_CHANNEL,
        seed_all_notification_rules,
    )

    async with async_session() as session:
        await seed_all_notification_rules(session, tenant_id)
        svc = NotificationEventService(session)

        # Phone present (has_phone=True) → the missing-info rule must NOT fire.
        rows_present = await svc.emit(
            tenant_id,
            "lead.created",
            {"has_phone": True},
            principal=_principal(tenant_id),
            person_uid=uuid.uuid4(),
        )
        present_channels = {r.channel for r in rows_present}
        assert LEADS_MISSING_INFO_CHANNEL not in present_channels
        assert "leads" in present_channels  # unconditional default still fires

        # Phone missing (has_phone=False) → the missing-info rule fires.
        rows_empty = await svc.emit(
            tenant_id,
            "lead.created",
            {"has_phone": False},
            principal=_principal(tenant_id),
            person_uid=uuid.uuid4(),
        )
        empty_channels = {r.channel for r in rows_empty}
        assert LEADS_MISSING_INFO_CHANNEL in empty_channels

        # Regression guard: the OLD bug fired the rule on EVERY lead because
        # ``lead.Phone`` was absent → ``is_empty`` matched. With the boolean
        # ``has_phone`` predicate, a context that omits it entirely must NOT
        # route to the missing-info channel (eq against None is False).
        rows_absent = await svc.emit(
            tenant_id,
            "lead.created",
            {"lead": {"source": "web"}},
            principal=_principal(tenant_id),
            person_uid=uuid.uuid4(),
        )
        absent_channels = {r.channel for r in rows_absent}
        assert LEADS_MISSING_INFO_CHANNEL not in absent_channels
        assert "leads" in absent_channels


# --- 4. guardrail: a phone in context never reaches the payload ---------
#        (de-identified fallback mode: Settings.messenger_phi_full=False)


async def test_emit_payload_never_contains_pii(
    tenant_id: TenantId, monkeypatch: pytest.MonkeyPatch
) -> None:
    from packages.core.config import get_settings
    from packages.integrations.chat.event_service import NotificationEventService
    from packages.integrations.notification_schemas import NotificationRuleIn
    from packages.integrations.notification_service import NotificationService

    # Pin de-identified mode: this test asserts the allowlist fallback still
    # redacts PII when the operator turns the PHI surface OFF (ENG-460).
    monkeypatch.setattr(
        get_settings(), "messenger_phi_full", False, raising=False
    )

    async with async_session() as session:
        notif = NotificationService(session)
        # A misconfigured template that tries to render PII vars.
        await notif.upsert_rule(
            tenant_id,
            NotificationRuleIn(
                event_type="lead.created",
                channel="leaky",
                conditions=[{"field": "lead.Phone", "op": "is_present"}],
                template={"text": "Call {{phone}} for {{first_name}} — {{person_uid}}"},
            ),
            principal=_principal(tenant_id),
        )
        svc = NotificationEventService(session)
        rows = await svc.emit(
            tenant_id,
            "lead.created",
            {
                "lead": {"Phone": "+15558675309"},
                "phone": "+15558675309",
                "first_name": "Jane",
            },
            principal=_principal(tenant_id),
            person_uid=uuid.uuid4(),
        )
        leaky = next(r for r in rows if r.channel == "leaky")
        text = str(leaky.payload)
        assert "5558675309" not in text
        assert "Jane" not in text
        assert "[redacted]" in text


# --- 5. no rules / disabled rule produces no rows -----------------------


async def test_emit_no_rules_returns_empty(tenant_id: TenantId) -> None:
    from packages.integrations.chat.event_service import NotificationEventService

    async with async_session() as session:
        svc = NotificationEventService(session)
        rows = await svc.emit(
            tenant_id,
            "lead.created",
            {},
            principal=_principal(tenant_id),
            person_uid=uuid.uuid4(),
        )
        assert rows == []


# --- 6. ENG-460: full-mode emit carries the real name + the rich card ---


async def test_emit_full_mode_renders_real_name_and_attachment(
    tenant_id: TenantId, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With ``messenger_phi_full`` on (the default), the seeded lead.created
    rich rule produces an outbox payload containing the REAL name + phone +
    source and the Mattermost attachment block — NOT ``[redacted]``."""
    from packages.core.config import get_settings
    from packages.integrations.chat.event_service import NotificationEventService
    from packages.integrations.chat.seeds import seed_all_notification_rules

    monkeypatch.setattr(
        get_settings(), "messenger_phi_full", True, raising=False
    )
    person_uid = uuid.uuid4()

    async with async_session() as session:
        await seed_all_notification_rules(session, tenant_id)
        svc = NotificationEventService(session)
        rows = await svc.emit(
            tenant_id,
            "lead.created",
            {
                "name": "Angel Bryant",
                "phone": "19254918047",
                "source": "Facebook",
                "has_phone": True,
            },
            principal=_principal(tenant_id),
            person_uid=person_uid,
        )
        default_row = next(r for r in rows if r.channel == "leads")
        payload = default_row.payload
        text = str(payload)
        assert "Angel Bryant" in text
        assert "19254918047" in text
        assert "Facebook" in text
        assert "[redacted]" not in text
        assert "{{" not in text
        # The rich attachment block is present and carries the name + link.
        blocks = payload["blocks"]
        assert blocks[0]["text"] == "**Angel Bryant**"
        assert str(person_uid) in blocks[0]["title_link"]
