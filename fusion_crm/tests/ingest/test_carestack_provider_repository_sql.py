"""SQL-shape tests for the CareStack provider repository methods (ENG-308).

The provider lookup feeds the person-card "Provider" line and the
multi-link expander; tenant scoping, on-conflict upsert behaviour, and
the empty-input short-circuit are the contract we lock in here. The
full live-DB integration runs against Postgres; the unit test suite has
no ingest-schema Postgres fixture so we lock in the contract at the
query-construction layer.
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
    """Reused from test_person_payment_repository_sql.py — captures the
    statement passed to ``session.execute`` so we can compile and inspect
    it without a live database."""
    captured: dict[str, Any] = {}
    session = MagicMock()

    async def fake_execute(stmt: Any) -> MagicMock:
        captured["stmt"] = stmt
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


def _compile_sql_no_literals(stmt: Any) -> str:
    """Compile without literal_binds — needed for JSONB-bearing INSERTs where
    SQLAlchemy can't render a Python dict as a SQL literal. We assert on
    the rendered placeholder structure (ON CONFLICT clauses, column names)
    rather than on bound values.
    """
    compiled = stmt.compile(dialect=postgresql.dialect())
    return str(compiled)


# ---------------------------------------------------------------- upsert_providers


@pytest.mark.asyncio
async def test_upsert_providers_short_circuits_on_empty_input() -> None:
    """An empty providers list must not run a SQL query."""
    captured: dict[str, Any] = {}
    session = MagicMock()

    async def fake_execute(stmt: Any) -> Any:
        captured["stmt"] = stmt
        return MagicMock()

    session.execute = fake_execute
    repo = IngestRepository(session)

    written = await repo.upsert_providers(TenantId(uuid.uuid4()), [])

    assert written == 0
    assert "stmt" not in captured


@pytest.mark.asyncio
async def test_upsert_providers_uses_on_conflict_do_update_keyed_on_tenant_and_id() -> None:
    """The upsert must use ``ON CONFLICT (tenant_id, provider_carestack_id)``
    so a re-import of the same provider row updates rather than duplicates.
    """
    session, captured = _stub_session_capturing()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    written = await repo.upsert_providers(
        tenant_id,
        [
            {
                "id": 17,
                "firstName": "Aram",
                "lastName": "Torosyan",
                "middleName": None,
                "shortName": "A.T.",
                "providerType": "Doctor",
                "isActive": True,
            }
        ],
    )

    assert written == 1
    sql = _compile_sql_no_literals(captured["stmt"]).lower()
    assert "on conflict" in sql
    assert "tenant_id" in sql
    assert "provider_carestack_id" in sql


@pytest.mark.asyncio
async def test_upsert_providers_dedups_input_rows_by_id() -> None:
    """The accounting feed has duplicate provider entries on some accounts.
    The repository must not pass duplicates to the same INSERT because the
    Postgres ON CONFLICT path can only fire once per command per key."""
    session, captured = _stub_session_capturing()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    written = await repo.upsert_providers(
        tenant_id,
        [
            {"id": 17, "firstName": "A", "lastName": "T"},
            {"id": 17, "firstName": "A", "lastName": "T"},
            {"id": 99, "firstName": "B", "lastName": "S"},
        ],
    )

    assert written == 2


# ---------------------------------------------------------------- lookup_provider_names


@pytest.mark.asyncio
async def test_lookup_provider_names_short_circuits_on_empty_input() -> None:
    captured: dict[str, Any] = {}
    session = MagicMock()

    async def fake_execute(stmt: Any) -> Any:
        captured["stmt"] = stmt
        return MagicMock()

    session.execute = fake_execute
    repo = IngestRepository(session)

    out = await repo.lookup_provider_names(TenantId(uuid.uuid4()), [])

    assert out == {}
    assert "stmt" not in captured


@pytest.mark.asyncio
async def test_lookup_provider_names_filters_by_tenant_and_ids() -> None:
    """The SELECT must carry tenant_id scoping and the requested id list."""
    session, captured = _stub_session_capturing()
    repo = IngestRepository(session)
    tenant_id = TenantId(uuid.uuid4())

    await repo.lookup_provider_names(tenant_id, [17, 99])

    sql = _compile_sql(captured["stmt"]).lower()
    assert "tenant_id" in sql, "tenant scoping must be in the SQL"
    assert "provider_carestack_id" in sql
    assert "17" in sql
    assert "99" in sql
