"""DB-backed tests for CareStack invoice-ref resolution (ENG-303).

``IngestRepository.get_carestack_invoice_refs`` powers the PM Payments page's
Invoice column: given the ``invoiceId`` carried on a payment event, it resolves
the human ``invoiceNumber`` + the invoice date from the latest captured invoice
raw row — reading only those two non-PII scalars. These tests seed invoice
raw_events on a fresh tenant (rolled back on teardown) and assert resolution,
latest-per-id selection, and graceful handling of unknown ids.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.ingest.models import RawEvent
from packages.ingest.repository import IngestRepository
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session

_BASE = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


async def _seed_invoice_raw(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    external_id: str,
    invoice_number: str,
    payment_date: str,
    received_at: datetime,
) -> RawEvent:
    raw = RawEvent(
        tenant_id=tenant_id,
        source="carestack",
        event_type="carestack.invoice.upsert",
        external_id=external_id,
        received_at=received_at,
        payload={
            "invoiceId": int(external_id),
            "invoiceNumber": invoice_number,
            "paymentDate": payment_date,
            "amount": 300.0,
        },
    )
    session.add(raw)
    await session.flush()
    return raw


async def test_resolves_number_and_date_from_latest_raw(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="inv-refs")
    # Same invoice id pulled twice — the later pull (newer received_at) wins.
    await _seed_invoice_raw(
        db_session, tenant_id, external_id="2424603", invoice_number="10498-OLD",
        payment_date="2026-05-28T00:00:00", received_at=_BASE,
    )
    await _seed_invoice_raw(
        db_session, tenant_id, external_id="2424603", invoice_number="10498",
        payment_date="2026-05-28T00:00:00", received_at=_BASE + timedelta(hours=2),
    )
    await _seed_invoice_raw(
        db_session, tenant_id, external_id="2424605", invoice_number="10499",
        payment_date="2026-04-15T09:30:00", received_at=_BASE,
    )
    repo = IngestRepository(db_session)

    refs = await repo.get_carestack_invoice_refs(
        tenant_id, ["2424603", "2424605", "9999999"]
    )
    assert refs["2424603"] == {
        "invoice_number": "10498",  # latest pull won
        "invoice_date": "2026-05-28",  # date prefix only
    }
    assert refs["2424605"] == {
        "invoice_number": "10499",
        "invoice_date": "2026-04-15",
    }
    # Unknown invoice id is simply absent (renders without invoice info).
    assert "9999999" not in refs


async def test_empty_ids_returns_empty_map(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="inv-refs-empty")
    repo = IngestRepository(db_session)
    assert await repo.get_carestack_invoice_refs(tenant_id, []) == {}
