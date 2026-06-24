"""SQL-shape tests for ``IngestRepository.sum_latest_payment_summary_balances`` (ENG-266).

The full latest-snapshot-per-patient aggregation runs against Postgres;
the test suite currently has no live-DB fixture for the ``ingest`` schema
so we lock in the contract at the query-construction layer. A regression
here means the AR-risk count would silently lose tenant scoping,
latest-per-patient deduplication, the strict ``>`` threshold rule, or
its event-type filter.
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
        row = MagicMock()
        row._mapping = {
            "balance_due_patient": 0,
            "balance_due_insurance": 0,
            "patient_count": 0,
            "ar_risk_count": 0,
        }
        result.one.return_value = row
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
async def test_aggregate_sql_is_tenant_scoped_and_filters_event_type() -> None:
    session, captured = _stub_session_capturing()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    await repo.sum_latest_payment_summary_balances(
        tenant_id, ar_risk_threshold=500.0
    )

    sql = _compile_sql(captured["stmt"])
    assert "tenant_id" in sql, "tenant scoping must be in the SQL"
    assert "carestack" in sql, "source filter must be in the SQL"
    assert "payment_summary.snapshot" in sql, (
        "event_type filter must scope to payment-summary snapshots"
    )


@pytest.mark.asyncio
async def test_aggregate_sql_uses_latest_snapshot_per_external_id() -> None:
    session, captured = _stub_session_capturing()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    await repo.sum_latest_payment_summary_balances(
        tenant_id, ar_risk_threshold=500.0
    )

    sql = _compile_sql(captured["stmt"]).lower()
    assert "max(" in sql, "latest-per-patient requires MAX(received_at)"
    assert "external_id" in sql, (
        "latest-per-patient subquery must group by external_id"
    )
    assert "group by" in sql, "latest-per-patient must aggregate via GROUP BY"


@pytest.mark.asyncio
async def test_ar_risk_count_uses_strict_greater_than_threshold() -> None:
    """A patient exactly AT the threshold must NOT be counted; only
    strictly above. Compile the SQL with literal binds and assert the
    comparison operator is ``>`` (not ``>=``).
    """
    session, captured = _stub_session_capturing()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    await repo.sum_latest_payment_summary_balances(
        tenant_id, ar_risk_threshold=500.0
    )

    sql = _compile_sql(captured["stmt"])
    sql_lower = sql.lower()
    assert "case" in sql_lower, "AR-risk count must use a CASE WHEN"
    assert "500.0" in sql, "threshold value must be present in the SQL"
    assert "> 500.0" in sql, "AR-risk rule must be strictly greater than"
    assert ">= 500.0" not in sql, (
        "AR-risk rule must be exclusive at the threshold (no >=)"
    )


@pytest.mark.asyncio
async def test_aggregate_exposes_all_four_labels() -> None:
    session, captured = _stub_session_capturing()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    await repo.sum_latest_payment_summary_balances(
        tenant_id, ar_risk_threshold=500.0
    )

    sql = _compile_sql(captured["stmt"])
    for label in (
        "balance_due_patient",
        "balance_due_insurance",
        "patient_count",
        "ar_risk_count",
    ):
        assert label in sql, f"aggregate must expose '{label}' label"


@pytest.mark.asyncio
async def test_threshold_value_flows_into_sql() -> None:
    """Tuning the constant must change the SQL — otherwise the threshold
    is dead config. Pass a non-default value through the kwarg and assert
    it lands in the compiled query.
    """
    session, captured = _stub_session_capturing()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    await repo.sum_latest_payment_summary_balances(
        tenant_id, ar_risk_threshold=1234.56
    )

    sql = _compile_sql(captured["stmt"])
    assert "1234.56" in sql, "non-default threshold must reach the SQL"
    assert "> 1234.56" in sql
