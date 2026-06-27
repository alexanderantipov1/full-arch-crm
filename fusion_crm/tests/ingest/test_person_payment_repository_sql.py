"""SQL-shape tests for per-person payment summary repository methods (ENG-306).

The full live-DB integration runs against Postgres; the test suite has no
ingest-schema Postgres fixture so we lock in the contract at the query-
construction layer. Regressions here would mean tenant scoping is lost,
the source/event-type filter slips, or the latest-per-patient dedup
breaks.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from packages.core.types import TenantId
from packages.ingest.repository import IngestRepository


def _stub_session_capturing() -> tuple[MagicMock, dict[str, Any]]:
    captured: dict[str, Any] = {}
    session = MagicMock()

    async def fake_execute(stmt: Any) -> MagicMock:
        captured["stmt"] = stmt
        result = MagicMock()
        result.all.return_value = []
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
async def test_latest_payment_summary_by_patient_filters_payment_summary_snapshot() -> None:
    session, captured = _stub_session_capturing()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    await repo.latest_payment_summary_by_patient(tenant_id, ["PT-1", "PT-2"])

    sql = _compile_sql(captured["stmt"])
    assert "tenant_id" in sql, "tenant scoping must be in the SQL"
    assert "carestack" in sql, "source filter must be in the SQL"
    assert "payment_summary.snapshot" in sql, (
        "event_type filter must scope to payment-summary snapshots"
    )
    assert "PT-1" in sql, "the patient id allow-list must reach the SQL"
    assert "PT-2" in sql


@pytest.mark.asyncio
async def test_latest_payment_summary_by_patient_uses_latest_per_external_id() -> None:
    session, captured = _stub_session_capturing()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    await repo.latest_payment_summary_by_patient(tenant_id, ["PT-1"])

    sql = _compile_sql(captured["stmt"]).lower()
    assert "max(" in sql, "latest-per-patient requires MAX(received_at)"
    assert "external_id" in sql
    assert "group by" in sql


@pytest.mark.asyncio
async def test_latest_payment_summary_by_patient_short_circuits_on_empty_input() -> None:
    """An empty patient-id list must not run a SQL query.

    The route calls this for every PM Payments page; an empty page (or a
    page where no person has a CareStack link) must NOT pay the DB cost.
    """
    captured: dict[str, Any] = {}
    session = MagicMock()

    async def fake_execute(stmt: Any) -> Any:
        captured["stmt"] = stmt
        return MagicMock()

    session.execute = fake_execute
    repo = IngestRepository(session)

    result = await repo.latest_payment_summary_by_patient(
        TenantId(uuid.uuid4()), []
    )

    assert result == {}
    assert "stmt" not in captured


@pytest.mark.asyncio
async def test_sum_accounting_totals_uses_signed_debit_credit() -> None:
    """``transactionType='credit'`` must subtract from the running total.

    Without this, an Adjustments column with a refund credit would render
    as a positive number — the operator would read it as an extra charge.
    """
    session, captured = _stub_session_capturing()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    await repo.sum_accounting_totals_by_patient(
        tenant_id,
        ["PT-1"],
        transaction_codes=("PATIENTADJUSTMENT", "FEEUPDATION"),
    )

    sql = _compile_sql(captured["stmt"]).lower()
    assert "case" in sql, "signed sum requires a CASE WHEN"
    assert "credit" in sql, "credit branch must appear"
    assert "tenant_id" in sql


@pytest.mark.asyncio
async def test_sum_accounting_totals_dedups_by_external_id() -> None:
    """The accounting feed has ~15 % duplicates by design — we want the LATEST
    per ``external_id`` only.
    """
    session, captured = _stub_session_capturing()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    await repo.sum_accounting_totals_by_patient(
        tenant_id,
        ["PT-1"],
        transaction_codes=("PROCEDURECOMPLETED",),
    )

    # ENG-412: dedup is now DISTINCT ON (external_id) ORDER BY received_at
    # DESC (narrow by patientId first, then keep the latest row per
    # external_id) instead of a max(received_at) GROUP BY join — same
    # "latest per external_id" result, but index-friendly.
    sql = _compile_sql(captured["stmt"]).lower()
    assert "distinct on (" in sql
    assert "external_id" in sql
    assert "received_at desc" in sql
    assert "accounting_transaction.upsert" in sql


@pytest.mark.asyncio
async def test_sum_accounting_totals_short_circuits_on_empty_inputs() -> None:
    captured: dict[str, Any] = {}
    session = MagicMock()

    async def fake_execute(stmt: Any) -> Any:
        captured["stmt"] = stmt
        return MagicMock()

    session.execute = fake_execute
    repo = IngestRepository(session)

    by_no_patients = await repo.sum_accounting_totals_by_patient(
        TenantId(uuid.uuid4()), [], transaction_codes=("PROCEDURECOMPLETED",)
    )
    by_no_codes = await repo.sum_accounting_totals_by_patient(
        TenantId(uuid.uuid4()), ["PT-1"], transaction_codes=()
    )

    assert by_no_patients == {}
    assert by_no_codes == {}
    assert "stmt" not in captured
