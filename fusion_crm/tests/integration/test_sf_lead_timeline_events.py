"""DB-backed integration coverage for Salesforce Lead timeline events."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.ingest.sf_lead_service import SfLeadIngestService
from packages.interaction.models import Event
from packages.ops.models import Lead
from packages.tenant.models import Tenant


class _FakeSfClient:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records

    async def describe(self, _resource: str) -> dict[str, Any]:
        # Empty describe → dynamic projection falls back to static (ENG-427).
        return {"fields": []}

    async def describe_tooling_fields(self, _resource: str) -> list[dict[str, Any]]:
        return []

    async def soql(self, _query: str) -> dict[str, Any]:
        return {
            "records": self.records,
            "totalSize": len(self.records),
            "done": True,
        }


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


def _record(
    *,
    sf_id: str,
    email: str,
    status: str = "Open",
    source: str = "Web",
    last_modified: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "Id": sf_id,
        "FirstName": "Jane",
        "LastName": "Doe",
        "Email": email,
        "Phone": "+15551234567",
        "Company": "Acme",
        "LeadSource": source,
        "Status": status,
        "CreatedDate": "2026-05-07T20:00:00.000+0000",
        "Description": "free text must stay in raw_event only",
    }
    if last_modified is not None:
        record["LastModifiedDate"] = last_modified
    return record


async def _seed_tenant(session: AsyncSession, tenant_id: TenantId) -> None:
    session.add(
        Tenant(
            id=tenant_id,
            slug=f"eng-237-{uuid.uuid4().hex[:12]}",
            name="ENG-237 integration tenant",
            primary_email=f"eng-237-{uuid.uuid4().hex[:12]}@example.test",
        )
    )
    await session.flush()


async def _events_for_person(
    session: AsyncSession,
    tenant_id: TenantId,
    person_uid: uuid.UUID,
) -> list[Event]:
    result = await session.execute(
        select(Event)
        .where(Event.tenant_id == tenant_id)
        .where(Event.person_uid == person_uid)
        .order_by(Event.occurred_at.asc())
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_salesforce_lead_pull_emits_created_then_changed_events(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await _seed_tenant(db_session, tenant_id)

    suffix = uuid.uuid4().hex[:12]
    sf_id = f"00Q{suffix}"
    email = f"eng-237-{suffix}@example.test"
    client = _FakeSfClient([_record(sf_id=sf_id, email=email)])
    service = SfLeadIngestService(db_session, client)

    first_pull = await service.pull_recent(tenant_id, limit=1)

    assert len(first_pull) == 1
    person_uid = first_pull[0].person_uid
    events = await _events_for_person(db_session, tenant_id, person_uid)
    assert [event.kind for event in events] == ["lead_created"]
    created = events[0]
    lead = (
        await db_session.execute(
            select(Lead)
            .where(Lead.tenant_id == tenant_id)
            .where(Lead.person_uid == person_uid)
        )
    ).scalar_one()
    assert created.source_kind == "salesforce_lead"
    assert created.source_external_id == sf_id
    assert created.projection_ref_type == "ops_lead"
    assert created.projection_ref_id == lead.id
    assert created.data_class == "operational"
    assert created.review_status == "auto"
    assert created.payload == {
        "Status": "Open",
        "LeadSource": "Web",
        "Id": sf_id,
        "CreatedDate": "2026-05-07T20:00:00.000+0000",
    }

    await service.pull_recent(tenant_id, limit=1)

    events = await _events_for_person(db_session, tenant_id, person_uid)
    assert [event.kind for event in events] == ["lead_created"]

    client.records = [
        _record(
            sf_id=sf_id,
            email=email,
            status="Working - Contacted",
            last_modified="2026-05-08T21:00:00.000+0000",
        )
    ]

    await service.pull_recent(tenant_id, limit=1)

    events = await _events_for_person(db_session, tenant_id, person_uid)
    assert [event.kind for event in events] == ["lead_created", "lead_updated"]
    updated = events[1]
    assert updated.source_kind == "salesforce_lead"
    assert updated.source_external_id == sf_id
    assert updated.projection_ref_type == "ops_lead"
    assert updated.projection_ref_id == lead.id
    assert updated.data_class == "operational"
    assert updated.review_status == "auto"
    assert updated.payload == {
        "Status": "Working - Contacted",
        "LeadSource": "Web",
        "Id": sf_id,
        "CreatedDate": "2026-05-07T20:00:00.000+0000",
        "LastModifiedDate": "2026-05-08T21:00:00.000+0000",
    }

    forbidden = {
        "FirstName",
        "LastName",
        "Email",
        "Phone",
        "Company",
        "Description",
    }
    for event in events:
        assert set(event.payload).isdisjoint(forbidden)
        assert "Jane" not in event.summary
        assert email not in event.summary
        assert "+15551234567" not in event.summary
        assert "free text" not in event.summary
