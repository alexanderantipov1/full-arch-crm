"""Smoke tests for ops models — D3 / ENG-4 additions.

DB-level tests (CHECK enforcement, UNIQUE collisions) land alongside the
alembic migration when a Postgres test container is wired in.

The expected column sets include ``tenant_id`` (ENG-128) — every per-tenant
table inherits ``TenantScopedMixin``.
"""

from __future__ import annotations

from sqlalchemy import Table

from packages.ops.models import (
    ACCOUNT_PROVIDERS,
    SCHEMA,
    Account,
    FollowupTask,
    Lead,
)

_LEAD_TBL: Table = Lead.__table__  # type: ignore[assignment]
_FOLLOWUP_TBL: Table = FollowupTask.__table__  # type: ignore[assignment]
_ACCOUNT_TBL: Table = Account.__table__  # type: ignore[assignment]


# --- existing tables remain intact ---


def test_lead_table_unaffected() -> None:
    """D3 must not have rewritten Lead's columns."""
    assert _LEAD_TBL.schema == SCHEMA
    cols = {c.name for c in _LEAD_TBL.columns}
    expected = {
        "id",
        "tenant_id",
        "created_at",
        "updated_at",
        "person_uid",
        "source",
        "status",
        "notes",
        "extra",
    }
    assert expected == cols


def test_followup_task_unaffected() -> None:
    assert _FOLLOWUP_TBL.schema == SCHEMA
    cols = {c.name for c in _FOLLOWUP_TBL.columns}
    assert {"id", "tenant_id", "person_uid", "title", "status"}.issubset(cols)


# --- account ---


def test_account_table_metadata() -> None:
    assert Account.__tablename__ == "account"
    assert _ACCOUNT_TBL.schema == SCHEMA

    cols = {c.name for c in _ACCOUNT_TBL.columns}
    expected = {
        "id",
        "tenant_id",
        "created_at",
        "updated_at",
        "provider",
        "source_id",
        "name",
        "raw",
    }
    assert expected == cols, f"unexpected columns: {cols ^ expected}"


def test_account_check_constraint_present() -> None:
    check_names = {
        c.name
        for c in _ACCOUNT_TBL.constraints
        if isinstance(c.name, str) and c.name.startswith("ck_")
    }
    assert "ck_account_provider" in check_names


def test_account_provider_source_unique() -> None:
    """Idempotency rests on a real UNIQUE constraint at the DB layer."""
    constraint_names = {
        c.name
        for c in _ACCOUNT_TBL.constraints
        if isinstance(c.name, str) and c.name.startswith("uq_")
    }
    assert "uq_account_provider_source" in constraint_names


def test_account_indexes_present() -> None:
    index_names = {idx.name for idx in _ACCOUNT_TBL.indexes}
    assert "ix_account_provider" in index_names


def test_account_providers_canonical() -> None:
    assert "salesforce" in ACCOUNT_PROVIDERS
    assert "hubspot" in ACCOUNT_PROVIDERS
    assert "carestack" in ACCOUNT_PROVIDERS
    assert "manual" in ACCOUNT_PROVIDERS
    assert "import" in ACCOUNT_PROVIDERS
