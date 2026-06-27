"""Lock the ``catalog.procedure_code`` model shape (ENG-420).

The migration is a draft until the live alembic round-trip runs; these
tests pin the columns and constraints so an autogenerate diff would
catch a drift.
"""

from __future__ import annotations

import uuid

from sqlalchemy import UniqueConstraint

from packages.catalog.models import SCHEMA, ProcedureCode


def test_schema_is_catalog() -> None:
    assert SCHEMA == "catalog"
    assert ProcedureCode.__table__.schema == "catalog"


def test_table_name_is_procedure_code() -> None:
    assert ProcedureCode.__tablename__ == "procedure_code"


def test_primary_key_is_uuid_id_only() -> None:
    """Codebase invariant #8 — UUID primary keys everywhere. The
    procedure-code catalog is workspace-wide and uses a plain UUID PK;
    the CareStack-assigned id lives on a separate UNIQUE business-key
    column (see test_business_key_is_carestack_code_id_unique)."""
    pk_cols = [c.name for c in ProcedureCode.__table__.primary_key.columns]
    assert pk_cols == ["id"]


def test_id_is_uuid() -> None:
    """The PK column type is the codebase-standard UUID."""
    id_col = ProcedureCode.__table__.columns["id"]
    sql_type = id_col.type.compile().upper()
    assert "UUID" in sql_type


def test_no_tenant_id_column() -> None:
    """Workspace-wide reference data: ``tenant_id`` must NOT be present
    (see packages/catalog/CLAUDE.md for the rationale)."""
    column_names = {c.name for c in ProcedureCode.__table__.columns}
    assert "tenant_id" not in column_names


def test_required_columns_present() -> None:
    column_names = {c.name for c in ProcedureCode.__table__.columns}
    assert {
        "id",
        "carestack_code_id",
        "code",
        "description",
        "code_type_id",
        "cdt_category_id",
        "payload",
        "created_at",
        "updated_at",
    } <= column_names


def test_business_key_is_carestack_code_id() -> None:
    """The CareStack-assigned id is the business key, stored separately
    from the UUID PK so callers can keep using integer ids."""
    col = ProcedureCode.__table__.columns["carestack_code_id"]
    assert col.nullable is False
    sql_type = col.type.compile().upper()
    assert "BIGINT" in sql_type


def test_business_key_is_unique() -> None:
    """The idempotent upsert depends on ``ON CONFLICT (carestack_code_id)``
    — the UNIQUE constraint MUST exist or the upsert will silently
    insert duplicates."""
    uniques = [
        c
        for c in ProcedureCode.__table__.constraints
        if isinstance(c, UniqueConstraint)
    ]
    unique_col_lists = [
        [col.name for col in c.columns] for c in uniques
    ]
    assert ["carestack_code_id"] in unique_col_lists


def test_default_id_factory_is_uuid4() -> None:
    """Client-side UUID PK default follows the codebase mixin pattern
    (``UUIDPrimaryKeyMixin`` sets ``default=uuid.uuid4``). SQLAlchemy wraps
    it in a CallableColumnDefault invoked with an execution context."""
    default = ProcedureCode.__table__.columns["id"].default
    assert default is not None and default.is_callable
    assert isinstance(default.arg(None), uuid.UUID)


def test_code_is_not_null() -> None:
    assert ProcedureCode.__table__.columns["code"].nullable is False


def test_description_is_nullable() -> None:
    """CareStack occasionally returns rows with a code but no description.
    Don't reject them."""
    assert ProcedureCode.__table__.columns["description"].nullable is True


def test_code_type_and_category_are_nullable() -> None:
    assert ProcedureCode.__table__.columns["code_type_id"].nullable is True
    assert ProcedureCode.__table__.columns["cdt_category_id"].nullable is True
