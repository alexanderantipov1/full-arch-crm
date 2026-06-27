"""Coverage for the ENG-555 shared-contact-reuse alert scan (Layer D).

Unit tests (no DB):

* the event is in the canonical roster;
* the default seed routes to the leads channel with no extra condition;
* the card template is PHI-FREE (no name/phone/email placeholders);
* the rule → contact-kind mapping;
* the scan is a no-op when ``NOTIFICATIONS_CUTOFF_AT`` is unset.

Integration tests (real local Postgres, skipped when unreachable — mirrors
``tests/integrations/test_notification_dedupe.py``):

* a NEW reuse candidate (post-cutoff) → exactly one outbox row, carrying NO PHI;
* re-running the scan → no duplicate (dedupe ledger);
* a PRE-cutoff candidate → nothing;
* disabled notifications → nothing.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from apps.worker.jobs.shared_contact_reuse import (
    _RULE_TO_KIND,
    scan_shared_contact_reuse,
)
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.integrations.chat.events import (
    ALL_EVENT_TYPES,
    EVENT_SHARED_CONTACT_REUSE,
)
from packages.integrations.chat.seeds import (
    _DEFAULT_RULES,
    SHARED_CONTACT_REUSE_CHANNEL,
    SHARED_CONTACT_REUSE_TEMPLATE,
)

# --- Unit: taxonomy + seed + template (no DB) ---------------------------

# Placeholders that would leak PHI if they ever appeared in this card.
_PHI_PLACEHOLDERS = ("{{name}}", "{{phone}}", "{{email}}", "{{dob}}", "{{ssn}}")


def test_reuse_event_is_in_the_roster() -> None:
    assert EVENT_SHARED_CONTACT_REUSE in ALL_EVENT_TYPES


def test_default_seed_routes_reuse_to_leads_channel() -> None:
    rule = next(r for r in _DEFAULT_RULES if r[0] == EVENT_SHARED_CONTACT_REUSE)
    _event_type, channel, conditions, _template, _description = rule
    assert channel == SHARED_CONTACT_REUSE_CHANNEL == "leads"
    # The scanner already filters reuse rules + cutoff, so no extra condition
    # (a stray condition would silently suppress alerts).
    assert conditions == []


def test_reuse_template_is_phi_free() -> None:
    # Serialise the whole template and assert no PHI placeholder is present —
    # this card carries opaque uids + the contact KIND only, never the value.
    blob = repr(SHARED_CONTACT_REUSE_TEMPLATE)
    for ph in _PHI_PLACEHOLDERS:
        assert ph not in blob, f"PHI placeholder {ph} leaked into the reuse card"
    # It DOES surface the contact kind (the type, not the value) + deep links.
    assert "{{contact_kind}}" in blob
    assert "{{deep_link}}" in blob


def test_rule_to_kind_mapping() -> None:
    assert _RULE_TO_KIND["phone_only_ambiguous"] == "phone"
    assert _RULE_TO_KIND["email_only_ambiguous"] == "email"


async def test_scan_is_noop_without_cutoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """No NOTIFICATIONS_CUTOFF_AT → no-retro guard returns early (no DB hit)."""
    from packages.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "notifications_cutoff_at", None, raising=False)
    summary = await scan_shared_contact_reuse({})
    assert summary == {"tenants": 0, "emitted": 0, "failed": 0}


# --- Integration: real Postgres ----------------------------------------

try:  # noqa: SIM105
    from packages.db.session import async_session

    _IMPORT_OK = True
except Exception:  # noqa: BLE001 — environment not configured for a DB
    _IMPORT_OK = False


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


# A cutoff well after any pre-existing test data; our candidates are created
# relative to it so the no-retro filter is exercised deterministically.
_CUTOFF = datetime(2026, 6, 22, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _enable_notifications(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default each integration test to ENABLED + the fixed cutoff."""
    if not _IMPORT_OK:
        return
    from packages.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "notifications_enabled", True, raising=False)
    monkeypatch.setattr(s, "notifications_cutoff_at", _CUTOFF, raising=False)


@pytest.fixture
def settings():  # type: ignore[no-untyped-def]
    from packages.core.config import get_settings

    return get_settings()


@pytest.fixture
async def tenant_id() -> AsyncIterator[TenantId]:
    if not _IMPORT_OK or not await _db_reachable():
        pytest.skip("local Postgres not reachable")

    from sqlalchemy import text

    tid = uuid.uuid4()
    slug = f"eng555-test-{tid.hex[:12]}"
    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO tenant.tenant (id, slug, name, timezone, locale, "
                "status, created_at, updated_at) VALUES (:id, :slug, :name, 'UTC', "
                "'en-US', 'active', now(), now())"
            ),
            {"id": tid, "slug": slug, "name": "ENG-555 Test"},
        )

    try:
        yield TenantId(tid)
    finally:
        async with async_session() as session:
            for tbl in (
                "identity.match_candidate",
                "identity.person",
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


async def _seed_reuse_rule(tenant_id: TenantId) -> None:
    from packages.integrations.notification_schemas import NotificationRuleIn
    from packages.integrations.notification_service import NotificationService

    async with async_session() as session:
        await NotificationService(session).upsert_rule(
            tenant_id,
            NotificationRuleIn(
                event_type=EVENT_SHARED_CONTACT_REUSE,
                channel=SHARED_CONTACT_REUSE_CHANNEL,
                conditions=[],
                template=SHARED_CONTACT_REUSE_TEMPLATE,
            ),
            principal=_principal(tenant_id),
        )
        await session.commit()


async def _insert_person(tenant_id: TenantId, given_name: str) -> uuid.UUID:
    from sqlalchemy import text

    pid = uuid.uuid4()
    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO identity.person (id, tenant_id, given_name, "
                "created_at, updated_at) VALUES (:id, :tid, :gn, now(), now())"
            ),
            {"id": pid, "tid": tenant_id, "gn": given_name},
        )
        await session.commit()
    return pid


async def _insert_reuse_candidate(
    tenant_id: TenantId,
    *,
    incoming: uuid.UUID,
    existing: uuid.UUID,
    created_at: datetime,
    match_rule: str = "phone_only_ambiguous",
) -> uuid.UUID:
    from sqlalchemy import text

    cid = uuid.uuid4()
    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO identity.match_candidate "
                "(id, tenant_id, source_person_uid, candidate_person_uid, status, "
                "match_rule, confidence, evidence, conflicts, created_at, updated_at) "
                "VALUES (:id, :tid, :src, :cand, 'open', :rule, 0.5, '{}'::jsonb, "
                "'{}'::jsonb, :ts, :ts)"
            ),
            {
                "id": cid,
                "tid": tenant_id,
                "src": incoming,
                "cand": existing,
                "rule": match_rule,
                "ts": created_at,
            },
        )
        await session.commit()
    return cid


async def _outbox_payloads(tenant_id: TenantId) -> list[dict]:
    from sqlalchemy import text

    async with async_session() as session:
        rows = await session.execute(
            text(
                "SELECT payload FROM integrations.notification_outbox "
                "WHERE tenant_id = :id AND event_type = :et"
            ),
            {"id": tenant_id, "et": EVENT_SHARED_CONTACT_REUSE},
        )
        return [r[0] for r in rows.all()]


async def test_new_reuse_signal_enqueues_one_phi_free_alert(
    tenant_id: TenantId,
) -> None:
    await _seed_reuse_rule(tenant_id)
    # Names are deliberately distinctive so we can prove they DON'T leak.
    incoming = await _insert_person(tenant_id, "ReuseIncomingName")
    existing = await _insert_person(tenant_id, "ReuseExistingName")
    await _insert_reuse_candidate(
        tenant_id,
        incoming=incoming,
        existing=existing,
        created_at=_CUTOFF + timedelta(hours=1),
    )

    # NB: ``summary`` counts across ALL tenants in the shared dev DB, so every
    # correctness assertion is scoped to OUR tenant via the outbox.
    await scan_shared_contact_reuse({})

    payloads = await _outbox_payloads(tenant_id)
    assert len(payloads) == 1
    blob = repr(payloads[0])
    # No-PHI proof: the persons' names never appear in the rendered card.
    assert "ReuseIncomingName" not in blob
    assert "ReuseExistingName" not in blob
    # It DOES carry the opaque uids + the contact kind.
    assert str(incoming) in blob
    assert "phone" in blob


async def test_rerun_does_not_duplicate(tenant_id: TenantId) -> None:
    await _seed_reuse_rule(tenant_id)
    incoming = await _insert_person(tenant_id, "Inc")
    existing = await _insert_person(tenant_id, "Exi")
    await _insert_reuse_candidate(
        tenant_id,
        incoming=incoming,
        existing=existing,
        created_at=_CUTOFF + timedelta(hours=1),
    )

    await scan_shared_contact_reuse({})
    await scan_shared_contact_reuse({})  # idempotent re-run

    payloads = await _outbox_payloads(tenant_id)
    assert len(payloads) == 1  # dedupe ledger blocks the second emit


async def test_pre_cutoff_candidate_is_silent(tenant_id: TenantId) -> None:
    await _seed_reuse_rule(tenant_id)
    incoming = await _insert_person(tenant_id, "OldInc")
    existing = await _insert_person(tenant_id, "OldExi")
    # Created BEFORE the cutoff → must never be scanned/alerted (no retro-blast).
    await _insert_reuse_candidate(
        tenant_id,
        incoming=incoming,
        existing=existing,
        created_at=_CUTOFF - timedelta(days=1),
    )

    # Scoped to OUR tenant: a pre-cutoff candidate must produce no alert.
    await scan_shared_contact_reuse({})
    assert await _outbox_payloads(tenant_id) == []


async def test_disabled_notifications_emit_nothing(
    tenant_id: TenantId, settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed_reuse_rule(tenant_id)
    monkeypatch.setattr(settings, "notifications_enabled", False, raising=False)
    incoming = await _insert_person(tenant_id, "DInc")
    existing = await _insert_person(tenant_id, "DExi")
    await _insert_reuse_candidate(
        tenant_id,
        incoming=incoming,
        existing=existing,
        created_at=_CUTOFF + timedelta(hours=1),
    )

    summary = await scan_shared_contact_reuse({})
    assert await _outbox_payloads(tenant_id) == []
    # ENG-555 review (blocker 3): the summary must NOT overstate work when the
    # engine is dark. notifications_enabled is a global gate, so a disabled run
    # emits nothing for EVERY tenant — emitted must be exactly 0.
    assert summary["emitted"] == 0


async def test_scan_paginates_past_first_page(
    tenant_id: TenantId, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ENG-555 review (blocker 1): every post-cutoff candidate is alerted, even
    beyond one page — the bare limit alone starved rows past page 1 once the head
    rows were emitted. Shrink the page size and prove a 3rd candidate still wins
    an alert."""
    monkeypatch.setattr(
        "apps.worker.jobs.shared_contact_reuse._PAGE_SIZE", 2, raising=False
    )
    await _seed_reuse_rule(tenant_id)
    existing = await _insert_person(tenant_id, "PageExisting")
    cand_ids = []
    for hours in (1, 2, 3):  # 3 candidates, page size 2 → forces a 2nd page
        incoming = await _insert_person(tenant_id, f"PageInc{hours}")
        cand_ids.append(
            await _insert_reuse_candidate(
                tenant_id,
                incoming=incoming,
                existing=existing,
                created_at=_CUTOFF + timedelta(hours=hours),
            )
        )

    await scan_shared_contact_reuse({})

    # All three candidates must have produced an alert (one outbox row each),
    # proving the scan advanced past the first page rather than starving #3.
    assert len(await _outbox_payloads(tenant_id)) == 3
