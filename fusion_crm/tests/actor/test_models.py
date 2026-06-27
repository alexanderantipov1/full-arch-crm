"""Smoke tests for actor models — class structure, columns, constraints.

DB-level tests (CHECK enforcement, UNIQUE collisions) land with the alembic
migration in FUS-32, since they need a real Postgres instance.
"""

from __future__ import annotations

from sqlalchemy import Table

from packages.actor.models import SCHEMA, Actor, ActorIdentifier

# SQLAlchemy 2.0 typing reports `__table__` as ``FromClause``; cast to
# the more specific ``Table`` so attribute access (constraints, indexes,
# foreign_keys) type-checks under mypy strict.
_ACTOR_TBL: Table = Actor.__table__  # type: ignore[assignment]
_ACTOR_IDENT_TBL: Table = ActorIdentifier.__table__  # type: ignore[assignment]


def test_actor_table_metadata() -> None:
    assert Actor.__tablename__ == "actor"
    assert _ACTOR_TBL.schema == SCHEMA

    cols = {c.name for c in _ACTOR_TBL.columns}
    expected = {
        "id",
        "created_at",
        "updated_at",
        "actor_type",
        "name",
        "role",
        "status",
        "email",
        "phone",
        "person_uid",
        "availability_status",
        "meta",
    }
    assert expected.issubset(cols), f"missing columns: {expected - cols}"


def test_actor_check_constraints_present() -> None:
    """Every enum-shaped column must have a CHECK constraint defined explicitly."""
    check_names = {
        c.name for c in _ACTOR_TBL.constraints
        if isinstance(c.name, str) and c.name.startswith("ck_")
    }
    assert "ck_actor_actor_type" in check_names
    assert "ck_actor_status" in check_names
    assert "ck_actor_availability_status" in check_names


def test_actor_check_actor_type_values() -> None:
    """All four values are in the CHECK from day one (per FUS-32 review decision)."""
    constraint = next(
        c for c in _ACTOR_TBL.constraints
        if getattr(c, "name", None) == "ck_actor_actor_type"
    )
    sql = str(constraint.sqltext) if hasattr(constraint, "sqltext") else ""
    for value in ("human", "ai", "system", "external_service"):
        assert value in sql, f"actor_type CHECK must include '{value}'"


def test_actor_indexes() -> None:
    index_names = {ix.name for ix in _ACTOR_TBL.indexes}
    for required in (
        "ix_actor_type",
        "ix_actor_role",
        "ix_actor_status",
        "ix_actor_person_uid",
    ):
        assert required in index_names, f"missing index: {required}"


def test_actor_identifier_table_metadata() -> None:
    assert ActorIdentifier.__tablename__ == "actor_identifier"
    assert _ACTOR_IDENT_TBL.schema == SCHEMA

    cols = {c.name for c in _ACTOR_IDENT_TBL.columns}
    expected = {"id", "created_at", "updated_at", "actor_id", "kind", "value"}
    assert expected.issubset(cols), f"missing columns: {expected - cols}"


def test_actor_identifier_unique_constraint() -> None:
    uq_names = {
        c.name for c in _ACTOR_IDENT_TBL.constraints
        if isinstance(c.name, str) and c.name.startswith("uq_")
    }
    assert "uq_actor_identifier_kind_value" in uq_names


def test_actor_identifier_fk_to_actor() -> None:
    fks = list(_ACTOR_IDENT_TBL.foreign_keys)
    assert any("actor.actor.id" in str(fk.target_fullname) for fk in fks), (
        "actor_identifier.actor_id must FK to actor.actor.id"
    )
