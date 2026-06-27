"""Integration tests for the ENG-381 raw_event duplicate cleanup script.

Real-PostgreSQL tests (per root testing policy) covering the keep-rules:

* newest row per (tenant, event_type, external_id, stamp) survives;
* rows with distinct provider stamps are NOT duplicates;
* stamp-less feeds dedupe by payload content;
* rows referenced by ``interaction.event.source_event_id`` or
  ``ingest.normalized_person_hint.raw_event_id`` are never deleted.
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.conftest import TENANT_SCHEMA_AVAILABLE, TwoTenantContext

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "scripts"
    / "cleanup_raw_event_duplicates.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "cleanup_raw_event_duplicates", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("cleanup_raw_event_duplicates", module)
    spec.loader.exec_module(module)
    return module


def _raw_event(
    tenant_id: uuid.UUID,
    *,
    event_type: str,
    external_id: str,
    payload: Mapping[str, object],
    received_at: datetime,
):
    from packages.ingest.models import RawEvent

    return RawEvent(
        tenant_id=tenant_id,
        source="salesforce",
        event_type=event_type,
        external_id=external_id,
        received_at=received_at,
        payload=payload,
    )


@pytest.mark.asyncio
@pytest.mark.skipif(
    not TENANT_SCHEMA_AVAILABLE, reason="tenant schema not available"
)
async def test_cleanup_keeps_newest_and_referenced_rows(
    two_tenant_db: TwoTenantContext,
) -> None:
    session = two_tenant_db.session
    assert session is not None
    tenant_id = two_tenant_db.tenant_a_id
    module = _load_script()

    base = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    event_type = "salesforce.opportunity.upsert"
    payload = {"Id": "006TEST", "LastModifiedDate": "2026-06-01T10:00:00Z"}

    # Three byte-identical captures of the same provider version + one
    # row carrying a NEWER provider stamp (a real change — must stay).
    dup_old_1 = _raw_event(
        tenant_id,
        event_type=event_type,
        external_id="006TEST",
        payload=payload,
        received_at=base,
    )
    dup_old_2 = _raw_event(
        tenant_id,
        event_type=event_type,
        external_id="006TEST",
        payload=payload,
        received_at=base + timedelta(minutes=1),
    )
    dup_newest = _raw_event(
        tenant_id,
        event_type=event_type,
        external_id="006TEST",
        payload=payload,
        received_at=base + timedelta(minutes=2),
    )
    changed = _raw_event(
        tenant_id,
        event_type=event_type,
        external_id="006TEST",
        payload={"Id": "006TEST", "LastModifiedDate": "2026-06-02T10:00:00Z"},
        received_at=base + timedelta(minutes=3),
    )
    session.add_all([dup_old_1, dup_old_2, dup_newest, changed])
    await session.flush()

    # Pin dup_old_1 with a timeline-event reference: it is a duplicate
    # but the FK keep-rule must protect it.
    from packages.interaction.models import Event

    session.add(
        Event(
            tenant_id=tenant_id,
            person_uid=two_tenant_db.seeded_ids["identity_person"]["tenant_a"],
            kind="opportunity_created",
            source_provider="salesforce",
            source_event_id=dup_old_1.id,
            occurred_at=base,
            summary="test pin",
            payload={},
            data_class="operational",
            review_status="auto",
        )
    )
    await session.flush()

    ids = set(
        await module.find_duplicate_ids(
            session, event_type=event_type, stamp_key="LastModifiedDate"
        )
    )

    # Membership assertions (the suite may run against a DB that holds
    # other rows of this event type): dup_old_2 is deletable; dup_newest
    # is the group's newest, `changed` has a different stamp, and
    # dup_old_1 is pinned by the timeline-event reference.
    assert dup_old_2.id in ids
    assert dup_newest.id not in ids
    assert changed.id not in ids
    assert dup_old_1.id not in ids


@pytest.mark.asyncio
@pytest.mark.skipif(
    not TENANT_SCHEMA_AVAILABLE, reason="tenant schema not available"
)
async def test_cleanup_stampless_feed_dedupes_by_content(
    two_tenant_db: TwoTenantContext,
) -> None:
    session = two_tenant_db.session
    assert session is not None
    tenant_id = two_tenant_db.tenant_a_id
    module = _load_script()

    base = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    event_type = "carestack.payment_summary.snapshot"
    same_balance = {"balanceDuePatient": 100.0}

    snap_1 = _raw_event(
        tenant_id,
        event_type=event_type,
        external_id="777",
        payload=same_balance,
        received_at=base,
    )
    snap_2 = _raw_event(
        tenant_id,
        event_type=event_type,
        external_id="777",
        payload=dict(same_balance),
        received_at=base + timedelta(hours=1),
    )
    snap_changed = _raw_event(
        tenant_id,
        event_type=event_type,
        external_id="777",
        payload={"balanceDuePatient": 50.0},
        received_at=base + timedelta(hours=2),
    )
    session.add_all([snap_1, snap_2, snap_changed])
    await session.flush()

    ids = set(
        await module.find_duplicate_ids(
            session, event_type=event_type, stamp_key=None
        )
    )

    # Identical content → older row deletable; the changed balance and
    # the newest identical row stay. Membership assertions so rows from
    # the surrounding database do not affect the test.
    assert snap_1.id in ids
    assert snap_2.id not in ids
    assert snap_changed.id not in ids


@pytest.mark.asyncio
@pytest.mark.skipif(
    not TENANT_SCHEMA_AVAILABLE, reason="tenant schema not available"
)
async def test_cleanup_apply_deletes_only_candidates(
    two_tenant_db: TwoTenantContext,
) -> None:
    session = two_tenant_db.session
    assert session is not None
    tenant_id = two_tenant_db.tenant_a_id
    module = _load_script()

    from sqlalchemy import func, select

    from packages.ingest.models import RawEvent

    base = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    event_type = "salesforce.case.upsert"
    payload = {"Id": "500TEST", "LastModifiedDate": "2026-06-01T10:00:00Z"}
    rows = [
        _raw_event(
            tenant_id,
            event_type=event_type,
            external_id="500TEST",
            payload=payload,
            received_at=base + timedelta(minutes=offset),
        )
        for offset in range(3)
    ]
    session.add_all(rows)
    await session.flush()

    # ``commit`` deliberately omitted: the fixture transaction owns the
    # unit of work, so the suite stays hermetic (rollback on teardown).
    counts = await module.cleanup_duplicates(
        session,
        event_types={event_type: "LastModifiedDate"},
        apply=True,
        batch_size=1,
    )

    assert counts[event_type] >= 2
    remaining = (
        await session.execute(
            select(func.count())
            .select_from(RawEvent)
            .where(
                RawEvent.tenant_id == tenant_id,
                RawEvent.event_type == event_type,
                RawEvent.external_id == "500TEST",
            )
        )
    ).scalar_one()
    assert remaining == 1
