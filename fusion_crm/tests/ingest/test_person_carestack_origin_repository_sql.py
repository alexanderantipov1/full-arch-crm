"""SQL-shape tests for the per-pid CareStack origin aggregator (ENG-308).

``person_carestack_origin_context`` is what powers the "First ingest" +
"Earliest activity" + "City, State" lines on the person card. The
contract we lock in at the query layer:

* Tenant scoping is in the SQL.
* The empty-input case short-circuits without a SELECT.
* The earliest/latest pulls from BOTH appointment ``createdOn`` and
  accounting ``TransactionDate`` (the two events that DO carry a
  CareStack-side activity timestamp).
* The payload reads target the right JSONB paths for city + state on
  the latest patient.upsert row.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from packages.core.types import TenantId
from packages.ingest.repository import IngestRepository


def _stub_session_capturing_many() -> tuple[MagicMock, list[Any]]:
    """Captures every statement passed to ``session.execute`` in order.

    The aggregator method may issue more than one SELECT (one per anchor
    type) — we want to be able to inspect each one independently.
    """
    captured: list[Any] = []
    session = MagicMock()

    async def fake_execute(stmt: Any) -> MagicMock:
        captured.append(stmt)
        result = MagicMock()
        result.all.return_value = []
        result.scalars.return_value = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    session.execute = fake_execute
    return session, captured


def _compile_sql(stmt: Any) -> str:
    compiled = stmt.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    )
    return str(compiled)


@pytest.mark.asyncio
async def test_person_carestack_origin_short_circuits_on_empty_input() -> None:
    captured: list[Any] = []
    session = MagicMock()

    async def fake_execute(stmt: Any) -> Any:
        captured.append(stmt)
        return MagicMock()

    session.execute = fake_execute
    repo = IngestRepository(session)

    out = await repo.person_carestack_origin_context(TenantId(uuid.uuid4()), [])

    assert out == {}
    assert captured == []


@pytest.mark.asyncio
async def test_person_carestack_origin_reads_appointment_created_on() -> None:
    """The earliest-activity computation MUST consult
    ``carestack.appointment.upsert`` raw_events and pluck
    ``payload->>'createdOn'``. Missing this would silently fall back to
    our ingest date which is the bug ENG-308 is fixing.
    """
    session, captured = _stub_session_capturing_many()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    await repo.person_carestack_origin_context(tenant_id, ["1461274"])

    compiled = "\n".join(_compile_sql(stmt).lower() for stmt in captured)
    assert "appointment.upsert" in compiled
    assert "createdon" in compiled, "appointment createdOn must reach the SQL"
    assert "tenant_id" in compiled
    assert "1461274" in compiled


@pytest.mark.asyncio
async def test_person_carestack_origin_reads_accounting_transaction_date() -> None:
    """For accounting raw_events, ``createdOn`` does NOT exist; the
    documented activity anchor is ``TransactionDate``. The aggregator must
    consult it — otherwise we miss the activity contribution from
    finance-only patients (no appointments).
    """
    session, captured = _stub_session_capturing_many()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    await repo.person_carestack_origin_context(tenant_id, ["1461274"])

    compiled = "\n".join(_compile_sql(stmt).lower() for stmt in captured)
    assert "accounting_transaction.upsert" in compiled
    assert "transactiondate" in compiled


@pytest.mark.asyncio
async def test_person_carestack_origin_reads_patient_payload_address_fields() -> None:
    """``city`` / ``state`` / ``addressLine1`` / ``addressLine2`` /
    ``zipCode`` all come from ``payload.addressDetail`` of the latest
    ``carestack.patient.upsert``.

    The pre-ENG-310 Safe-Harbor carve-out limited this query to
    city+state. ENG-310 broadened the read to populate the
    click-to-reveal Patient details panel per the 2026-06-01 PHI policy
    update; the full address is surfaced behind intentional access on
    the staff frontend. The aggregator pulls the broader set in a
    single SELECT so the route stays one round-trip.
    """
    session, captured = _stub_session_capturing_many()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    await repo.person_carestack_origin_context(tenant_id, ["1461274"])

    compiled = "\n".join(_compile_sql(stmt).lower() for stmt in captured)
    assert "patient.upsert" in compiled
    assert "addressdetail" in compiled
    assert "'city'" in compiled
    assert "'state'" in compiled
    # ENG-310: the patient details panel reads the full address fields.
    assert "'addressline1'" in compiled
    assert "'addressline2'" in compiled
    assert "'zipcode'" in compiled
