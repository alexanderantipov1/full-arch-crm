"""Model-level smoke tests for ``identity.match_candidate`` (ENG-182).

DB-level enforcement of CHECK constraints and partial-unique indexes
lands alongside the live Postgres integration suite. These tests verify
the metadata is shaped correctly so the Alembic autogenerate stays
clean.
"""

from __future__ import annotations

from sqlalchemy import Index, Table

from packages.identity.models import (
    MATCH_CANDIDATE_ACCEPTED_STATUSES,
    MATCH_CANDIDATE_STATUSES,
    SCHEMA,
    MatchCandidate,
    make_person_pair_key,
)

_MATCH_TBL: Table = MatchCandidate.__table__  # type: ignore[assignment]


def test_match_candidate_table_metadata() -> None:
    assert MatchCandidate.__tablename__ == "match_candidate"
    assert _MATCH_TBL.schema == SCHEMA

    cols = {c.name for c in _MATCH_TBL.columns}
    expected = {
        "id",
        "tenant_id",
        "hint_id",
        "source_person_uid",
        "candidate_person_uid",
        "accepted_person_uid",
        "merge_event_id",
        "status",
        "match_rule",
        "confidence",
        "evidence",
        "conflicts",
        "person_pair_key",
        "decided_at",
        "decided_by_actor_id",
        "superseded_by_match_id",
        "created_at",
        "updated_at",
    }
    assert expected == cols, f"unexpected columns: {cols ^ expected}"


def test_match_candidate_check_constraints_present() -> None:
    check_names = {
        c.name
        for c in _MATCH_TBL.constraints
        if isinstance(c.name, str) and c.name.startswith("ck_")
    }
    assert "ck_match_candidate_status" in check_names
    assert "ck_match_candidate_confidence_range" in check_names
    assert "ck_match_candidate_distinct_persons" in check_names
    assert "ck_match_candidate_accepted_status" in check_names


def test_match_candidate_indexes_present() -> None:
    index_names = {idx.name for idx in _MATCH_TBL.indexes}
    assert "ix_match_candidate_tenant_id" in index_names
    assert "ix_match_candidate_candidate" in index_names
    assert "ix_match_candidate_source_person" in index_names
    assert "ix_match_candidate_hint" in index_names
    assert "ix_match_candidate_status" in index_names


def test_match_candidate_partial_unique_indexes_carry_where() -> None:
    """Partial-unique guards must declare ``postgresql_where`` filters."""
    indexes: dict[str, Index] = {
        str(idx.name): idx for idx in _MATCH_TBL.indexes if idx.name is not None
    }

    open_pair = indexes["uq_match_candidate_open_pair"]
    assert open_pair.unique is True
    open_pair_where = open_pair.dialect_options["postgresql"].get("where")
    assert open_pair_where is not None
    assert "status = 'open'" in str(open_pair_where)
    assert "person_pair_key IS NOT NULL" in str(open_pair_where)
    assert [c.name for c in open_pair.columns] == ["tenant_id", "person_pair_key"]

    hint_guard = indexes["uq_match_candidate_hint_candidate_active"]
    assert hint_guard.unique is True
    hint_where = hint_guard.dialect_options["postgresql"].get("where")
    assert hint_where is not None
    assert "auto_accepted" in str(hint_where)
    assert "hint_id IS NOT NULL" in str(hint_where)
    assert [c.name for c in hint_guard.columns] == [
        "tenant_id",
        "hint_id",
        "candidate_person_uid",
    ]


def test_match_candidate_statuses_canonical() -> None:
    assert MATCH_CANDIDATE_STATUSES == (
        "open",
        "auto_accepted",
        "accepted",
        "rejected",
        "superseded",
    )
    assert MATCH_CANDIDATE_ACCEPTED_STATUSES == ("auto_accepted", "accepted")
    for accepted in MATCH_CANDIDATE_ACCEPTED_STATUSES:
        assert accepted in MATCH_CANDIDATE_STATUSES


def test_person_pair_key_is_sorted_and_stable() -> None:
    import uuid

    a = uuid.UUID("00000000-0000-0000-0000-000000000001")
    b = uuid.UUID("00000000-0000-0000-0000-000000000002")
    key_ab = make_person_pair_key(a, b)
    key_ba = make_person_pair_key(b, a)
    assert key_ab is not None
    assert key_ab == key_ba
    assert key_ab.startswith(str(a))
    assert key_ab.endswith(str(b))
    assert len(key_ab) == 73


def test_person_pair_key_none_when_either_missing() -> None:
    import uuid

    a = uuid.uuid4()
    assert make_person_pair_key(None, a) is None
    assert make_person_pair_key(a, None) is None
    assert make_person_pair_key(None, None) is None
