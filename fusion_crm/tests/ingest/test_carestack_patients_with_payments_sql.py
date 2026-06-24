"""SQL-shape tests for ``list_carestack_patients_with_payment_activity`` (ENG-307).

The resolver feeds the ``--only-with-payments`` path of
``infra/scripts/backfill_payment_summary.py``: under prod we have 55,677
linked CareStack patients but only ~1803 with payment activity, and the
``list_source_links_for_dashboard`` order-by-first_seen_at fallback misses
most of the active set under ``--max-patients 2000``. These tests lock in
the contract at the query-construction layer (the test suite has no
ingest-schema Postgres fixture) so regressions in tenant scoping, the
event-type filter, the transactionCode allow-list, or the source_link
join cannot ship silently.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from packages.core.types import TenantId
from packages.ingest.repository import IngestRepository

_PAYMENT_CODES = (
    "PATIENTPAYMENTS",
    "INSURANCEPAYMENTS",
    "PATPAYMENTAPPLIED",
    "INSPAYMENTAPPLIED",
    "PATIENTPAYMENTSDELETE",
    "REFUND",
    "PATIENTREFUND",
    "INSURANCEREFUND",
)


def _stub_session_capturing() -> tuple[MagicMock, dict[str, Any]]:
    captured: dict[str, Any] = {}
    session = MagicMock()

    async def fake_execute(stmt: Any) -> MagicMock:
        captured["stmt"] = stmt
        result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = []
        result.scalars.return_value = scalars
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
async def test_returns_only_patients_with_payment_events() -> None:
    """The SQL must restrict the patient_id pool to raw_events whose
    ``transactionCode`` is in the payment allow-list. Without this, all
    accounting rows (charges, adjustments, fee updates) would inflate the
    result and the filter would be meaningless.
    """
    session, captured = _stub_session_capturing()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    await repo.list_carestack_patients_with_payment_activity(
        tenant_id, payment_codes=_PAYMENT_CODES, limit=2000
    )

    sql = _compile_sql(captured["stmt"])
    assert "accounting_transaction.upsert" in sql, (
        "must filter on the accounting raw-event type"
    )
    assert "transactionCode" in sql, "must filter on the transactionCode JSON key"
    for code in _PAYMENT_CODES:
        assert code in sql, f"payment code {code!r} must appear in the SQL allow-list"
    # Sanity: a non-payment code must NOT appear in the SQL.
    assert "PROCEDURECOMPLETED" not in sql


@pytest.mark.asyncio
async def test_query_dedups_patient_ids_via_distinct_or_in_subquery() -> None:
    """Repeated payment rows on the same patient must not double-count.

    The two-step shape (subquery on raw_event → SELECT source_link WHERE
    source_id IN <subquery>) gives natural dedup via ``IN`` semantics, and
    a ``DISTINCT`` on the patient_id projection makes the intent
    self-documenting in the compiled SQL.
    """
    session, captured = _stub_session_capturing()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    await repo.list_carestack_patients_with_payment_activity(
        tenant_id, payment_codes=_PAYMENT_CODES, limit=2000
    )

    sql = _compile_sql(captured["stmt"]).lower()
    assert "distinct" in sql, "patient_id projection must dedup"
    assert "patientid" in sql, "patientId JSON key must appear in the projection"


@pytest.mark.asyncio
async def test_query_is_tenant_scoped_on_both_raw_event_and_source_link() -> None:
    """Both the raw-event filter and the source_link select must include
    ``tenant_id``. A leak on either side would surface another tenant's
    patient_ids in the resolved list.
    """
    session, captured = _stub_session_capturing()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    await repo.list_carestack_patients_with_payment_activity(
        tenant_id, payment_codes=_PAYMENT_CODES, limit=2000
    )

    sql = _compile_sql(captured["stmt"])
    # ``tenant_id = '<uuid>'`` should appear at least twice (raw_event scope
    # AND source_link scope).
    assert sql.count("tenant_id") >= 2
    assert str(tenant_id) in sql, "the tenant uuid must reach the SQL"


@pytest.mark.asyncio
async def test_query_targets_carestack_patient_source_links_and_honors_limit() -> None:
    """Result rows must be CS patient source_links, ordered newest first,
    and capped by ``limit`` — same envelope as the default
    ``list_source_links_for_dashboard`` resolver so the caller's
    extraction loop is unchanged.
    """
    session, captured = _stub_session_capturing()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    await repo.list_carestack_patients_with_payment_activity(
        tenant_id, payment_codes=_PAYMENT_CODES, limit=3
    )

    sql = _compile_sql(captured["stmt"]).lower()
    assert "source_link" in sql
    assert "'carestack'" in sql
    assert "'patient'" in sql
    assert "order by" in sql
    assert "first_seen_at" in sql
    assert "limit 3" in sql


@pytest.mark.asyncio
async def test_short_circuits_when_no_payment_codes_provided() -> None:
    """Empty ``payment_codes`` must not run a SQL query.

    Defensive shape: a caller that hands us an empty allow-list (e.g. the
    accounting service's payment-code set drifted to empty during a
    refactor) should short-circuit cleanly rather than emit a SQL with
    ``IN ()`` that returns zero rows but still pays the DB round-trip.
    Mirrors ``sum_accounting_totals_by_patient``'s short-circuit
    behaviour.
    """
    captured: dict[str, Any] = {}
    session = MagicMock()

    async def fake_execute(stmt: Any) -> Any:
        captured["stmt"] = stmt
        return MagicMock()

    session.execute = fake_execute
    repo = IngestRepository(session)

    result = await repo.list_carestack_patients_with_payment_activity(
        TenantId(uuid.uuid4()), payment_codes=(), limit=2000
    )

    assert result == []
    assert "stmt" not in captured
