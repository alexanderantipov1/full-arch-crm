"""Model-level smoke tests for ``ingest.normalized_person_hint`` (ENG-185).

These tests verify the SQLAlchemy metadata is shaped correctly so Alembic
autogenerate stays clean. DB-level enforcement (unique constraint
collisions, FK behavior) lands alongside the live Postgres integration
suite.
"""

from __future__ import annotations

from sqlalchemy import Table, UniqueConstraint

from packages.ingest.models import SCHEMA, NormalizedPersonHint

_HINT_TBL: Table = NormalizedPersonHint.__table__  # type: ignore[assignment]


def test_normalized_person_hint_table_metadata() -> None:
    assert NormalizedPersonHint.__tablename__ == "normalized_person_hint"
    assert _HINT_TBL.schema == SCHEMA

    cols = {c.name for c in _HINT_TBL.columns}
    expected = {
        "id",
        "tenant_id",
        "raw_event_id",
        "source_system",
        "source_instance",
        "source_kind",
        "source_id",
        "observed_at",
        "given_name",
        "family_name",
        "display_name",
        "email_normalized",
        "phone_normalized",
        "person_uid",
        "source_link_id",
        "payload_sha256",
        "hint_hash",
        "quality_flags",
        "meta",
        "created_at",
        "updated_at",
    }
    assert expected == cols, f"unexpected columns: {cols ^ expected}"


def test_normalized_person_hint_nullability() -> None:
    """Match the P2 shape: identifiers and pointers nullable, hash NOT NULL."""
    cols = {c.name: c for c in _HINT_TBL.columns}

    # Required
    for required in (
        "id",
        "tenant_id",
        "raw_event_id",
        "source_system",
        "source_instance",
        "source_kind",
        "observed_at",
        "hint_hash",
        "quality_flags",
        "meta",
        "created_at",
        "updated_at",
    ):
        assert not cols[required].nullable, f"{required} must be NOT NULL"

    # Nullable identifiers and pointers
    for nullable in (
        "source_id",
        "given_name",
        "family_name",
        "display_name",
        "email_normalized",
        "phone_normalized",
        "person_uid",
        "source_link_id",
        "payload_sha256",
    ):
        assert cols[nullable].nullable, f"{nullable} must be nullable"


def test_normalized_person_hint_unique_tenant_raw_event() -> None:
    """One hint per raw event per tenant for this slice."""
    uniques = [
        c
        for c in _HINT_TBL.constraints
        if isinstance(c, UniqueConstraint)
    ]
    names = {c.name for c in uniques}
    assert "uq_normalized_person_hint_tenant_raw_event" in names

    uq = next(
        c for c in uniques if c.name == "uq_normalized_person_hint_tenant_raw_event"
    )
    assert [c.name for c in uq.columns] == ["tenant_id", "raw_event_id"]


def test_normalized_person_hint_indexes_present() -> None:
    """Match-policy lookups need indexed access on email/phone/person_uid."""
    names = {idx.name for idx in _HINT_TBL.indexes}
    assert "ix_normalized_person_hint_tenant_id" in names
    assert "ix_normalized_person_hint_source" in names
    assert "ix_normalized_person_hint_email" in names
    assert "ix_normalized_person_hint_phone" in names
    assert "ix_normalized_person_hint_person_uid" in names


def test_normalized_person_hint_source_index_columns() -> None:
    source_idx = next(
        idx
        for idx in _HINT_TBL.indexes
        if idx.name == "ix_normalized_person_hint_source"
    )
    assert [c.name for c in source_idx.columns] == [
        "tenant_id",
        "source_system",
        "source_instance",
        "source_kind",
        "source_id",
    ]


def test_normalized_person_hint_email_index_is_tenant_scoped() -> None:
    email_idx = next(
        idx
        for idx in _HINT_TBL.indexes
        if idx.name == "ix_normalized_person_hint_email"
    )
    assert [c.name for c in email_idx.columns] == ["tenant_id", "email_normalized"]


def test_normalized_person_hint_phone_index_is_tenant_scoped() -> None:
    phone_idx = next(
        idx
        for idx in _HINT_TBL.indexes
        if idx.name == "ix_normalized_person_hint_phone"
    )
    assert [c.name for c in phone_idx.columns] == ["tenant_id", "phone_normalized"]


def test_normalized_person_hint_person_uid_is_plain_uuid_no_fk() -> None:
    """``person_uid`` must NOT carry a Python-side FK to identity.person.

    The ingest layer keeps ``person_uid`` as a bare UUID pointer so an
    identity row can be removed (compliance / merge) without cascading
    into the hint forensic trail.
    """
    person_uid_col = _HINT_TBL.c.person_uid
    assert person_uid_col.foreign_keys == set()

    source_link_col = _HINT_TBL.c.source_link_id
    assert source_link_col.foreign_keys == set()


def test_normalized_person_hint_raw_event_fk_present() -> None:
    """``raw_event_id`` IS a DB-level FK — both rows live inside ``ingest``."""
    raw_event_col = _HINT_TBL.c.raw_event_id
    fks = list(raw_event_col.foreign_keys)
    assert len(fks) == 1
    target = fks[0].target_fullname
    assert target == "ingest.raw_event.id"
