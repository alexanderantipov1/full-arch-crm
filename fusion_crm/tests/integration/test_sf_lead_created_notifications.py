"""DB-backed integration coverage for ingest-driven lead.created notifications.

ENG-456 (Block B of ENG-454): genuinely-new INGESTED Salesforce leads are
fanned out to the ``#leads`` channel exactly once, at the SF scheduled-pull
worker boundary (``apps.worker.jobs.ingest_scheduled``) — NOT inside the
``ingest`` / ``ops`` services, which the packages import matrix forbids from
depending on ``integrations``.

Each test drives the REAL ``SfLeadIngestService.pull_recent_for_sync`` against
the local Postgres with a fake SF client, then runs the SAME worker-boundary
helper the cron job uses (``_emit_lead_created_notifications``) over the
returned NON-PII ``notify_signals``. Everything runs in ONE session and is
rolled back at the end (no commit), so no manual cross-schema cleanup is
needed; the ledger ``claim`` is visible within the session via its flush, which
is all the dedupe guard needs.

Notifications default to OFF (``Settings.notifications_enabled``), so every
test flips the live cached settings ON (and clears any cutoff), mirroring the
ENG-437 / ENG-455 emit tests.

Scenarios:
  1. a newly-ingested lead emits exactly one outbox row;
  2. re-emitting the same lead signal emits nothing (ledger dedupe on the SF
     Lead Id);
  3. the backfill path (``pull_all_since``) produces zero notifications;
  4. an updated (not created) lead emits nothing.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.worker.jobs.ingest_scheduled import _emit_lead_created_notifications
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.ingest.sf_lead_service import SfLeadIngestService
from packages.integrations.chat.seeds import (
    DEFAULT_LEAD_CREATED_CHANNEL,
    seed_all_notification_rules,
)
from packages.integrations.models import NotificationEmitted, NotificationOutbox
from packages.tenant.models import Tenant


class _FakeSfClient:
    """Minimal SF client surface; records are mutable so a test can re-pull."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records

    async def describe(self, _resource: str) -> dict[str, Any]:
        return {"fields": []}

    async def describe_tooling_fields(self, _resource: str) -> list[dict[str, Any]]:
        return []

    async def soql(self, _query: str) -> dict[str, Any]:
        return {
            "records": self.records,
            "totalSize": len(self.records),
            "done": True,
        }


def _principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
    )


def _record(
    *,
    sf_id: str,
    email: str,
    status: str = "Open",
    source: str = "Web",
    phone: str | None = "+15551234567",
    created: str = "2026-05-07T20:00:00.000+0000",
    last_modified: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "Id": sf_id,
        "FirstName": "Jane",
        "LastName": "Doe",
        "Email": email,
        "Phone": phone,
        "Company": "Acme",
        "LeadSource": source,
        "Status": status,
        "CreatedDate": created,
        "Description": "free text must stay in raw_event only",
    }
    if last_modified is not None:
        record["LastModifiedDate"] = last_modified
    return record


@pytest.fixture(autouse=True)
def _enable_notifications(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flip the messenger engine ON + clear any cutoff for these tests.

    ``Settings.notifications_enabled`` defaults to False (the wiring lands
    dark); these tests assert the ENABLED behaviour.
    """
    from packages.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "notifications_enabled", True, raising=False)
    monkeypatch.setattr(settings, "notifications_cutoff_at", None, raising=False)
    # ENG-460: pin full PHI mode (the production default) so the assertions
    # below exercise the rich, real-name cards deterministically regardless of
    # any local ``.env`` MESSENGER_PHI_FULL override.
    monkeypatch.setattr(settings, "messenger_phi_full", True, raising=False)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    try:
        from packages.db.session import SessionFactory, engine
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"database settings unavailable: {exc}")

    session = SessionFactory()
    try:
        await session.execute(sa.text("SELECT 1"))
    except OperationalError as exc:  # pragma: no cover - environment dependent
        await session.close()
        pytest.skip(f"database unavailable: {exc}")

    try:
        yield session
    finally:
        await session.rollback()
        await session.close()
        await engine.dispose()


async def _seed_tenant(session: AsyncSession, tenant_id: TenantId) -> None:
    suffix = uuid.uuid4().hex[:12]
    session.add(
        Tenant(
            id=tenant_id,
            slug=f"eng-456-{suffix}",
            name="ENG-456 integration tenant",
            primary_email=f"eng-456-{suffix}@example.test",
        )
    )
    await session.flush()
    # The flagship ``lead.created → #leads`` rule (+ the field-control rule).
    await seed_all_notification_rules(session, tenant_id)
    await session.flush()


async def _outbox_rows(
    session: AsyncSession, tenant_id: TenantId
) -> list[NotificationOutbox]:
    result = await session.execute(
        select(NotificationOutbox).where(NotificationOutbox.tenant_id == tenant_id)
    )
    return list(result.scalars().all())


async def _emitted_rows(
    session: AsyncSession, tenant_id: TenantId
) -> list[NotificationEmitted]:
    result = await session.execute(
        select(NotificationEmitted).where(NotificationEmitted.tenant_id == tenant_id)
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_new_ingested_lead_emits_exactly_one_outbox_row(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await _seed_tenant(db_session, tenant_id)

    suffix = uuid.uuid4().hex[:12]
    sf_id = f"00Q{suffix}"
    email = f"eng-456-{suffix}@example.test"
    client = _FakeSfClient([_record(sf_id=sf_id, email=email)])
    service = SfLeadIngestService(db_session, client)

    summary = await service.pull_recent_for_sync(tenant_id, limit=50)

    # Exactly one genuinely-new lead → one NON-PII signal keyed by the SF id.
    assert len(summary.notify_signals) == 1
    signal = summary.notify_signals[0]
    assert signal.sf_lead_id == sf_id
    assert signal.source_created_at == datetime(2026, 5, 7, 20, 0, tzinfo=UTC)
    assert signal.has_phone is True
    assert signal.source == "Web"

    await _emit_lead_created_notifications(
        db_session, tenant_id, summary.notify_signals, principal=_principal(tenant_id)
    )

    rows = await _outbox_rows(db_session, tenant_id)
    # The default ``lead.created → #leads`` rule fires (phone present → the
    # missing-info rule does NOT).
    channels = {r.channel for r in rows}
    assert DEFAULT_LEAD_CREATED_CHANNEL in channels
    default_row = next(r for r in rows if r.channel == DEFAULT_LEAD_CREATED_CHANNEL)
    assert default_row.status == "pending"
    assert default_row.event_type == "lead.created"
    # ENG-460 full PHI card: the deep link (with the opaque uid), the real
    # resolved name, the normalised phone, and the source all render — and
    # no placeholder is left dangling.
    payload_text = str(default_row.payload)
    assert str(signal.person_uid) in payload_text  # deep_link carries the uid
    assert "{{" not in payload_text
    assert "Jane Doe" in payload_text  # resolved display name
    assert "15551234567" in payload_text  # normalised phone (digits only)
    assert "Web" in payload_text  # lead source
    # The rich Mattermost attachment block is present.
    block = default_row.payload["blocks"][0]
    assert block["text"] == "**Jane Doe**"
    # The ledger recorded the SF id as the dedupe key.
    emitted = await _emitted_rows(db_session, tenant_id)
    assert {e.dedupe_key for e in emitted} == {sf_id}


@pytest.mark.asyncio
async def test_re_emitting_same_lead_signal_is_a_noop(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await _seed_tenant(db_session, tenant_id)

    suffix = uuid.uuid4().hex[:12]
    sf_id = f"00Q{suffix}"
    email = f"eng-456-{suffix}@example.test"
    client = _FakeSfClient([_record(sf_id=sf_id, email=email)])
    service = SfLeadIngestService(db_session, client)

    summary = await service.pull_recent_for_sync(tenant_id, limit=50)
    assert len(summary.notify_signals) == 1

    # First fan-out → one row.
    await _emit_lead_created_notifications(
        db_session, tenant_id, summary.notify_signals, principal=_principal(tenant_id)
    )
    assert len(await _outbox_rows(db_session, tenant_id)) == 1

    # Re-emitting the SAME signal (a re-pull of the same SF Lead) is a no-op:
    # the ledger claim on ``dedupe_key == sf_lead_id`` loses on the second
    # attempt, so NO second outbox row is enqueued.
    await _emit_lead_created_notifications(
        db_session, tenant_id, summary.notify_signals, principal=_principal(tenant_id)
    )

    rows = await _outbox_rows(db_session, tenant_id)
    lead_rows = [r for r in rows if r.channel == DEFAULT_LEAD_CREATED_CHANNEL]
    assert len(lead_rows) == 1


@pytest.mark.asyncio
async def test_backfill_path_emits_nothing(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await _seed_tenant(db_session, tenant_id)

    suffix = uuid.uuid4().hex[:12]
    sf_id = f"00Q{suffix}"
    email = f"eng-456-{suffix}@example.test"
    client = _FakeSfClient([_record(sf_id=sf_id, email=email)])
    service = SfLeadIngestService(db_session, client)

    # The bulk/backfill entry point captures leads but returns a bare count and
    # carries NO notify signals — it never routes through the emitting
    # boundary, so a full historical backfill produces ZERO notifications.
    imported = await service.pull_all_since(tenant_id, datetime(2000, 1, 1, tzinfo=UTC))
    assert imported >= 1

    rows = await _outbox_rows(db_session, tenant_id)
    assert rows == []
    emitted = await _emitted_rows(db_session, tenant_id)
    assert emitted == []


@pytest.mark.asyncio
async def test_updated_lead_emits_nothing(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await _seed_tenant(db_session, tenant_id)

    suffix = uuid.uuid4().hex[:12]
    sf_id = f"00Q{suffix}"
    email = f"eng-456-{suffix}@example.test"
    client = _FakeSfClient([_record(sf_id=sf_id, email=email)])
    service = SfLeadIngestService(db_session, client)

    # First pull CREATES the lead → one signal → one outbox row.
    created = await service.pull_recent_for_sync(tenant_id, limit=50)
    assert len(created.notify_signals) == 1
    await _emit_lead_created_notifications(
        db_session, tenant_id, created.notify_signals, principal=_principal(tenant_id)
    )
    assert len(await _outbox_rows(db_session, tenant_id)) == 1

    # Re-pull with a CHANGED status + advanced LastModifiedDate → the upsert
    # reports ``was_changed`` (an UPDATE), NOT ``was_created`` → no signal.
    client.records = [
        _record(
            sf_id=sf_id,
            email=email,
            status="Working - Contacted",
            last_modified="2026-05-08T21:00:00.000+0000",
        )
    ]
    updated = await service.pull_recent_for_sync(tenant_id, limit=50)
    assert updated.notify_signals == ()
    await _emit_lead_created_notifications(
        db_session, tenant_id, updated.notify_signals, principal=_principal(tenant_id)
    )

    # Still exactly one lead.created outbox row from the original creation.
    rows = await _outbox_rows(db_session, tenant_id)
    lead_rows = [r for r in rows if r.channel == DEFAULT_LEAD_CREATED_CHANNEL]
    assert len(lead_rows) == 1
