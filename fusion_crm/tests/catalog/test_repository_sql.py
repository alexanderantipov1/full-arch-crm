"""SQL-shape tests for ``CatalogRepository`` (ENG-420).

The full live-DB integration runs against Postgres; this file pins
the query-construction contract without a live database so an
autogenerate-style edit catches drift.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from packages.catalog.repository import CatalogRepository


def _stub_session_capturing() -> tuple[MagicMock, dict[str, Any]]:
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


def _compile_sql_no_literals(stmt: Any) -> str:
    """JSONB values can't render as literals; compile without
    literal_binds and assert on rendered structure."""
    compiled = stmt.compile(dialect=postgresql.dialect())
    return str(compiled)


# ---------------------------------------------------------------- upsert


@pytest.mark.asyncio
async def test_upsert_short_circuits_on_empty_input() -> None:
    """Empty input must NOT run a SQL query."""
    captured: dict[str, Any] = {}
    session = MagicMock()

    async def fake_execute(stmt: Any) -> Any:
        captured["stmt"] = stmt
        return MagicMock()

    session.execute = fake_execute
    repo = CatalogRepository(session)

    written = await repo.upsert_procedure_codes([])
    assert written == 0
    assert "stmt" not in captured


@pytest.mark.asyncio
async def test_upsert_uses_on_conflict_do_update_keyed_on_business_key() -> None:
    """The upsert must use ``ON CONFLICT (carestack_code_id) DO UPDATE``
    so a re-run on the same catalog is a no-op."""
    session, captured = _stub_session_capturing()
    repo = CatalogRepository(session)

    written = await repo.upsert_procedure_codes(
        [
            {
                "id": 117408,
                "code": "D7240",
                "description": "Removal of impacted tooth — completely bony",
                "codeTypeId": 1,
                "cdtCategoryId": 10,
            },
        ]
    )

    assert written == 1
    sql = _compile_sql_no_literals(captured["stmt"]).upper()
    assert "INSERT INTO CATALOG.PROCEDURE_CODE" in sql
    assert "ON CONFLICT" in sql
    assert "CARESTACK_CODE_ID" in sql
    assert "DO UPDATE SET" in sql


@pytest.mark.asyncio
async def test_upsert_dedupes_by_carestack_code_id_in_one_statement() -> None:
    """Postgres ON CONFLICT can fire only once per key per statement.
    Duplicates from the input list must be deduped before the SQL runs."""
    session, captured = _stub_session_capturing()
    repo = CatalogRepository(session)

    written = await repo.upsert_procedure_codes(
        [
            {"id": 1, "code": "D0120", "description": "Periodic exam"},
            {"id": 1, "code": "D0120", "description": "Periodic exam (dupe)"},
            {"id": 2, "code": "D0150", "description": "Comprehensive exam"},
        ]
    )

    assert written == 2


@pytest.mark.asyncio
async def test_upsert_skips_rows_missing_code() -> None:
    """``code`` is NOT NULL — a row without a code string must be dropped
    silently rather than crashing the whole batch."""
    session, captured = _stub_session_capturing()
    repo = CatalogRepository(session)

    written = await repo.upsert_procedure_codes(
        [
            {"id": 1, "code": "D0120"},
            {"id": 2},  # missing code
            {"id": 3, "code": ""},  # blank code
            {"id": 4, "code": "  "},  # whitespace-only
        ]
    )
    assert written == 1


@pytest.mark.asyncio
async def test_upsert_skips_non_integer_ids() -> None:
    session, _ = _stub_session_capturing()
    repo = CatalogRepository(session)

    written = await repo.upsert_procedure_codes(
        [
            {"id": "not-an-int", "code": "D0120"},
            {"id": None, "code": "D0150"},
            {"id": 117408, "code": "D7240"},
        ]
    )
    assert written == 1


# ---------------------------------------------------------------- resolve


@pytest.mark.asyncio
async def test_resolve_empty_input_returns_empty_dict() -> None:
    """Empty input must not run SQL."""
    captured: dict[str, Any] = {}
    session = MagicMock()

    async def fake_execute(stmt: Any) -> Any:
        captured["stmt"] = stmt
        return MagicMock()

    session.execute = fake_execute
    repo = CatalogRepository(session)
    out = await repo.resolve_procedure_codes([])
    assert out == {}
    assert "stmt" not in captured


@pytest.mark.asyncio
async def test_resolve_runs_select_against_catalog_table() -> None:
    captured: dict[str, Any] = {}
    session = MagicMock()

    async def fake_execute(stmt: Any) -> MagicMock:
        captured["stmt"] = stmt
        result = MagicMock()
        result.all.return_value = [
            (117408, "D7240", "Removal of impacted tooth"),
            (1, "D0120", "Periodic exam"),
        ]
        return result

    session.execute = fake_execute
    repo = CatalogRepository(session)

    out = await repo.resolve_procedure_codes([117408, 1, 999_999])

    assert out == {
        117408: ("D7240", "Removal of impacted tooth"),
        1: ("D0120", "Periodic exam"),
    }
    sql = str(
        captured["stmt"].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).upper()
    assert "FROM CATALOG.PROCEDURE_CODE" in sql
    assert "CARESTACK_CODE_ID" in sql
    assert "WHERE" in sql
    assert "IN (" in sql


@pytest.mark.asyncio
async def test_resolve_dedupes_and_filters_invalid_ids() -> None:
    captured: dict[str, Any] = {}
    session = MagicMock()

    async def fake_execute(stmt: Any) -> MagicMock:
        captured["stmt"] = stmt
        result = MagicMock()
        result.all.return_value = []
        return result

    session.execute = fake_execute
    repo = CatalogRepository(session)
    out = await repo.resolve_procedure_codes(
        [117408, 117408, "not-int", None, 1]  # type: ignore[list-item]
    )
    assert out == {}
    sql = str(
        captured["stmt"].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    # Both unique ids appear; dupes do not.
    assert sql.count("117408") == 1
