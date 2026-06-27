"""Tests for the by-id procedure-code work-list enumeration (ENG-538).

The catalog by-id sync resolves the distinct ``procedureCodeId`` values
observed in captured ``carestack.treatment_procedure.upsert`` raw_events.
``catalog`` may not read ``ingest`` (import matrix), so the enumeration
lives in ``IngestRepository`` / ``IngestService`` and the boundary hands
the ids to ``CatalogService.sync_procedure_codes_by_id``.

The repository is exercised against a fake session (no live DB): we pin
the SQL shape (DISTINCT, event-type filter, tenant scope) and the Python
int-parsing / dedup / sort behaviour.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from packages.core.types import TenantId
from packages.ingest.repository import IngestRepository
from packages.ingest.service import IngestService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _session_returning(rows: list[tuple[Any]]) -> tuple[MagicMock, dict[str, Any]]:
    captured: dict[str, Any] = {}
    session = MagicMock()

    async def fake_execute(stmt: Any) -> MagicMock:
        captured["stmt"] = stmt
        result = MagicMock()
        result.all.return_value = rows
        return result

    session.execute = fake_execute
    return session, captured


@pytest.mark.asyncio
async def test_distinct_payload_int_values_parses_dedups_and_sorts() -> None:
    """Non-numeric / null values are dropped; ints are deduped + sorted."""
    rows = [("6111",), ("6100",), ("6100",), (None,), ("not-a-number",), ("228501",)]
    session, captured = _session_returning(rows)
    repo = IngestRepository(session)

    out = await repo.distinct_payload_int_values(
        _TENANT_ID,
        event_type="carestack.treatment_procedure.upsert",
        payload_key="procedureCodeId",
    )

    assert out == [6100, 6111, 228501]
    sql = str(
        captured["stmt"].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).upper()
    assert "DISTINCT" in sql
    assert "FROM INGEST.RAW_EVENT" in sql
    assert "PROCEDURECODEID" in sql
    assert "CARESTACK.TREATMENT_PROCEDURE.UPSERT" in sql


@pytest.mark.asyncio
async def test_service_enumerates_treatment_procedure_code_ids() -> None:
    """The service wrapper forwards the treatment event-type + payload key."""
    svc = IngestService(MagicMock())
    svc._repo.distinct_payload_int_values = AsyncMock(  # type: ignore[method-assign]
        return_value=[6100, 6111]
    )

    out = await svc.distinct_treatment_procedure_code_ids(_TENANT_ID)

    assert out == [6100, 6111]
    svc._repo.distinct_payload_int_values.assert_awaited_once_with(
        _TENANT_ID,
        event_type="carestack.treatment_procedure.upsert",
        payload_key="procedureCodeId",
    )
