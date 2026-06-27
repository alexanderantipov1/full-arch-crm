"""Smoke tests for auth models — class structure, columns, constraints.

DB-level tests (CHECK enforcement, partial-unique collisions, FK cascades)
land with the alembic migration in FUS-32, since they need a real Postgres.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Table

from packages.auth.models import SCHEMA, ApiKey, Credential, Session

# SQLAlchemy 2.0 typing reports `__table__` as ``FromClause``; cast to
# ``Table`` so attribute access (constraints, indexes, FK) type-checks.
_CRED_TBL: Table = Credential.__table__  # type: ignore[assignment]
_SESS_TBL: Table = Session.__table__  # type: ignore[assignment]
_API_KEY_TBL: Table = ApiKey.__table__  # type: ignore[assignment]


# --- Credential ---


def test_credential_table_metadata() -> None:
    assert Credential.__tablename__ == "credential"
    assert _CRED_TBL.schema == SCHEMA
    cols = {c.name for c in _CRED_TBL.columns}
    expected = {
        "id",
        "tenant_id",
        "created_at",
        "updated_at",
        "subject_type",
        "subject_id",
        "credential_kind",
        "secret_hash",
        "meta",
        "status",
        "expires_at",
        "last_used_at",
    }
    assert expected.issubset(cols), f"missing: {expected - cols}"


def test_credential_check_subject_type_includes_portal_account() -> None:
    """Per FUS-32 review: portal_account is in the CHECK from M1 day one."""
    constraint = next(
        c for c in _CRED_TBL.constraints if getattr(c, "name", None) == "ck_credential_subject_type"
    )
    sql = str(constraint.sqltext) if hasattr(constraint, "sqltext") else ""
    assert "actor" in sql
    assert "portal_account" in sql


def test_credential_check_credential_kind_full_set() -> None:
    constraint = next(
        c
        for c in _CRED_TBL.constraints
        if getattr(c, "name", None) == "ck_credential_credential_kind"
    )
    sql = str(constraint.sqltext) if hasattr(constraint, "sqltext") else ""
    for kind in ("password", "mfa_totp", "oauth_external", "sso_subject", "webauthn"):
        assert kind in sql, f"credential_kind CHECK must include '{kind}'"


def test_credential_partial_unique_index() -> None:
    """Active-credential uniqueness is partial WHERE status='active'."""
    index_names = {ix.name for ix in _CRED_TBL.indexes}
    assert "uq_credential_subject_kind_active" in index_names

    idx = next(ix for ix in _CRED_TBL.indexes if ix.name == "uq_credential_subject_kind_active")
    assert idx.unique is True
    # The postgresql_where clause shows up in the dialect_options dict.
    pg_opts: dict[str, Any] = dict(idx.dialect_options.get("postgresql", {}))
    assert "where" in pg_opts


# --- Session ---


def test_session_table_metadata() -> None:
    assert Session.__tablename__ == "session"
    assert _SESS_TBL.schema == SCHEMA
    cols = {c.name for c in _SESS_TBL.columns}
    expected = {
        "id",
        "tenant_id",
        "created_at",
        "updated_at",
        "subject_type",
        "subject_id",
        "token_hash",
        "ip_address",
        "user_agent",
        "expires_at",
        "revoked_at",
        "last_seen_at",
        "meta",
    }
    assert expected.issubset(cols), f"missing: {expected - cols}"


def test_session_unique_token_hash() -> None:
    uq_names = {
        c.name
        for c in _SESS_TBL.constraints
        if isinstance(c.name, str) and c.name.startswith("uq_")
    }
    assert "uq_session_token_hash" in uq_names


def test_session_partial_indexes_use_postgresql_where() -> None:
    """Active-session indexes are partial WHERE revoked_at IS NULL."""
    by_name = {str(ix.name): ix for ix in _SESS_TBL.indexes if ix.name is not None}
    for required in ("ix_session_subject_active", "ix_session_expires"):
        assert required in by_name
        pg_opts: dict[str, Any] = dict(by_name[required].dialect_options.get("postgresql", {}))
        assert "where" in pg_opts, f"{required} must use postgresql_where"


# --- ApiKey ---


def test_api_key_table_metadata() -> None:
    assert ApiKey.__tablename__ == "api_key"
    assert _API_KEY_TBL.schema == SCHEMA
    cols = {c.name for c in _API_KEY_TBL.columns}
    expected = {
        "id",
        "tenant_id",
        "created_at",
        "updated_at",
        "name",
        "actor_id",
        "token_hash",
        "token_prefix",
        "scopes",
        "status",
        "expires_at",
        "last_used_at",
        "revoked_at",
        "created_by_actor_id",
        "meta",
    }
    assert expected.issubset(cols), f"missing: {expected - cols}"


def test_api_key_unique_token_hash() -> None:
    uq_names = {
        c.name
        for c in _API_KEY_TBL.constraints
        if isinstance(c.name, str) and c.name.startswith("uq_")
    }
    assert "uq_api_key_token_hash" in uq_names


def test_api_key_fk_to_actor() -> None:
    """`actor_id` and `created_by_actor_id` both FK actor.actor.id."""
    fks = list(_API_KEY_TBL.foreign_keys)
    targets = {str(fk.target_fullname) for fk in fks}
    actor_fks = {t for t in targets if "actor.actor.id" in t}
    # Two FKs both point to actor.actor.id (set has 1 unique target).
    assert len(actor_fks) == 1, f"expected actor.actor.id FK; got {targets}"
