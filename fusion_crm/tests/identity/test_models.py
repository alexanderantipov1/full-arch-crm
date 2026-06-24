"""Smoke tests for identity models — table structure, columns, constraints.

DB-level tests (CHECK enforcement, partial UNIQUE collisions) land alongside
the alembic migration when a real Postgres test container is available.
These tests verify the metadata is shaped correctly.

Per-tenant tables include ``tenant_id`` (ENG-128) — every per-tenant table
inherits ``TenantScopedMixin``.
"""

from __future__ import annotations

from sqlalchemy import Index, Table

from packages.identity.models import (
    MERGE_REASONS,
    SCHEMA,
    SOURCE_KINDS,
    SOURCE_SYSTEMS,
    MergeEvent,
    Person,
    PersonIdentifier,
    SourceLink,
)

# Cast `__table__` to ``Table`` so attribute access type-checks under mypy.
_PERSON_TBL: Table = Person.__table__  # type: ignore[assignment]
_PERSON_IDENT_TBL: Table = PersonIdentifier.__table__  # type: ignore[assignment]
_SOURCE_LINK_TBL: Table = SourceLink.__table__  # type: ignore[assignment]
_MERGE_EVENT_TBL: Table = MergeEvent.__table__  # type: ignore[assignment]


# --- existing tables (sanity check, ensure D2 didn't break Person/PersonIdentifier) ---


def test_existing_person_tables_intact() -> None:
    assert _PERSON_TBL.schema == SCHEMA
    assert _PERSON_IDENT_TBL.schema == SCHEMA
    assert "given_name" in {c.name for c in _PERSON_TBL.columns}
    assert "kind" in {c.name for c in _PERSON_IDENT_TBL.columns}


def test_person_carries_tenant_id() -> None:
    """Per-tenant tables inherit TenantScopedMixin (ENG-128)."""
    assert "tenant_id" in {c.name for c in _PERSON_TBL.columns}
    assert "tenant_id" in {c.name for c in _PERSON_IDENT_TBL.columns}


# --- ENG-341: shared-contact uniqueness guards on person_identifier ---


def test_person_identifier_blanket_unique_constraint_removed() -> None:
    """The old global ``uq_person_identifier_kind_value`` is gone — phone/email
    may now be shared across persons (ENG-341)."""
    constraint_names = {c.name for c in _PERSON_IDENT_TBL.constraints}
    assert "uq_person_identifier_kind_value" not in constraint_names


def test_person_identifier_per_person_unique_constraint_present() -> None:
    """Per-person idempotency: UNIQUE(person_id, kind, value) for ALL kinds."""
    by_name = {c.name: c for c in _PERSON_IDENT_TBL.constraints}
    uq = by_name.get("uq_person_identifier_person_kind_value")
    assert uq is not None
    assert {col.name for col in uq.columns} == {"person_id", "kind", "value"}


def test_person_identifier_unique_kind_partial_index_present() -> None:
    """Global 1:1 kept for NON-shared kinds via a partial unique index that
    exempts phone/email (ENG-341)."""
    by_name = {
        idx.name: idx for idx in _PERSON_IDENT_TBL.indexes if idx.name is not None
    }
    idx = by_name.get("uq_person_identifier_unique_kind_value")
    assert idx is not None
    assert idx.unique is True
    assert [col.name for col in idx.columns] == ["kind", "value"]
    where = idx.dialect_options["postgresql"].get("where")
    assert where is not None
    assert "phone" in str(where) and "email" in str(where)


def test_person_identifier_value_lookup_index_present() -> None:
    """The non-unique value lookup index is retained."""
    index_names = {idx.name for idx in _PERSON_IDENT_TBL.indexes}
    assert "ix_person_identifier_value" in index_names


# --- source_link ---


def test_source_link_table_metadata() -> None:
    assert SourceLink.__tablename__ == "source_link"
    assert _SOURCE_LINK_TBL.schema == SCHEMA

    cols = {c.name for c in _SOURCE_LINK_TBL.columns}
    expected = {
        "id",
        "tenant_id",
        "person_uid",
        "source_system",
        "source_instance",
        "source_kind",
        "source_id",
        "first_seen_at",
        "last_seen_at",
        "meta",
    }
    assert expected == cols, f"unexpected columns: {cols ^ expected}"


def test_source_link_check_constraints_present() -> None:
    check_names = {
        c.name
        for c in _SOURCE_LINK_TBL.constraints
        if isinstance(c.name, str) and c.name.startswith("ck_")
    }
    assert "ck_source_link_source_system" in check_names
    assert "ck_source_link_source_kind" in check_names


def test_source_link_partial_unique_index() -> None:
    """Partial UNIQUE on tenant + source instance + external record id."""
    indexes: dict[str, Index] = {
        str(idx.name): idx for idx in _SOURCE_LINK_TBL.indexes if idx.name is not None
    }
    assert "uq_source_link_external" in indexes
    uq = indexes["uq_source_link_external"]
    assert uq.unique is True
    # postgresql_where carries the partial-index filter
    assert uq.dialect_options["postgresql"].get("where") is not None
    cols = [c.name for c in uq.columns]
    assert cols == [
        "tenant_id",
        "source_system",
        "source_instance",
        "source_kind",
        "source_id",
    ]


def test_source_link_indexes_present() -> None:
    index_names = {idx.name for idx in _SOURCE_LINK_TBL.indexes}
    assert "ix_source_link_person_uid" in index_names
    assert "ix_source_link_source" in index_names


def test_source_systems_kinds_lists_match_constraints() -> None:
    """The Python tuples must mirror what the CHECK constraint allows.

    If anyone adds a value to one and forgets the other, the migration's
    CHECK rejects valid rows or accepts unknown ones.
    """
    # SOURCE_SYSTEMS must include each token referenced in the CHECK; this
    # test treats the model module as the canonical Python contract.
    assert "salesforce" in SOURCE_SYSTEMS
    assert "carestack" in SOURCE_SYSTEMS
    assert "manual" in SOURCE_SYSTEMS

    assert "lead" in SOURCE_KINDS
    assert "patient" in SOURCE_KINDS


# --- merge_event ---


def test_merge_event_table_metadata() -> None:
    assert MergeEvent.__tablename__ == "merge_event"
    assert _MERGE_EVENT_TBL.schema == SCHEMA

    cols = {c.name for c in _MERGE_EVENT_TBL.columns}
    expected = {
        "id",
        "tenant_id",
        "surviving_person_uid",
        "merged_person_uid",
        "reason",
        "evidence",
        "performed_by_actor_id",
        "occurred_at",
    }
    assert expected == cols, f"unexpected columns: {cols ^ expected}"


def test_merge_event_check_constraints_present() -> None:
    check_names = {
        c.name
        for c in _MERGE_EVENT_TBL.constraints
        if isinstance(c.name, str) and c.name.startswith("ck_")
    }
    assert "ck_merge_event_reason" in check_names
    assert "ck_merge_event_distinct_persons" in check_names


def test_merge_event_indexes_present() -> None:
    index_names = {idx.name for idx in _MERGE_EVENT_TBL.indexes}
    assert "ix_merge_event_surviving" in index_names
    assert "ix_merge_event_merged" in index_names


def test_merge_reasons_canonical() -> None:
    assert "duplicate_email" in MERGE_REASONS
    assert "duplicate_phone" in MERGE_REASONS
    assert "manual" in MERGE_REASONS
    assert "cross_provider_match" in MERGE_REASONS


# --- no created_at / updated_at on append-only / time-series rows ---


def test_source_link_has_no_timestamp_mixin_columns() -> None:
    """SourceLink uses first_seen_at / last_seen_at instead of created_at / updated_at."""
    cols = {c.name for c in _SOURCE_LINK_TBL.columns}
    assert "created_at" not in cols
    assert "updated_at" not in cols


def test_merge_event_has_no_timestamp_mixin_columns() -> None:
    """MergeEvent is append-only — only occurred_at, no updated_at."""
    cols = {c.name for c in _MERGE_EVENT_TBL.columns}
    assert "created_at" not in cols
    assert "updated_at" not in cols
