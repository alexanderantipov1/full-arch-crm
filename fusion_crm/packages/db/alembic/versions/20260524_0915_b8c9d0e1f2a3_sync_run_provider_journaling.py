"""ENG-239: provider sync-run journaling contract.

Revision ID: b8c9d0e1f2a3
Revises: f3a4b5c6d7e8
Create Date: 2026-05-24 09:15:00.000000+00:00

Scheduled and manual provider pulls now write real ``integrations.sync_run``
rows. This revision admits the inbound lifecycle vocabulary used by that
journal and scopes the legacy integration_account uniqueness by tenant.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a9b8c7d6e5f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SYNC_DIRECTIONS: tuple[str, ...] = (
    "inbound",
    "pull",
    "push",
    "cdc",
    "webhook",
)
LEGACY_SYNC_DIRECTIONS: tuple[str, ...] = ("pull", "push", "cdc", "webhook")

SYNC_STATUSES: tuple[str, ...] = (
    "running",
    "succeeded",
    "success",
    "failed",
    "partial",
    "skipped_credential",
)
LEGACY_SYNC_STATUSES: tuple[str, ...] = (
    "running",
    "success",
    "failed",
    "partial",
)


def _check_clause(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_sync_run_direction"),
        "sync_run",
        schema="integrations",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_sync_run_status"),
        "sync_run",
        schema="integrations",
        type_="check",
    )
    op.alter_column(
        "sync_run",
        "status",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=False,
        existing_server_default=sa.text("'running'"),
        schema="integrations",
    )
    op.create_check_constraint(
        op.f("ck_sync_run_direction"),
        "sync_run",
        _check_clause("direction", SYNC_DIRECTIONS),
        schema="integrations",
    )
    op.create_check_constraint(
        op.f("ck_sync_run_status"),
        "sync_run",
        _check_clause("status", SYNC_STATUSES),
        schema="integrations",
    )

    op.drop_constraint(
        "uq_integration_account_provider_company",
        "integration_account",
        schema="integrations",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_integration_account_tenant_provider_company",
        "integration_account",
        ["tenant_id", "provider", "company_uid"],
        schema="integrations",
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_integration_account_tenant_provider_company",
        "integration_account",
        schema="integrations",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_integration_account_provider_company",
        "integration_account",
        ["provider", "company_uid"],
        schema="integrations",
    )

    op.drop_constraint(
        op.f("ck_sync_run_status"),
        "sync_run",
        schema="integrations",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_sync_run_direction"),
        "sync_run",
        schema="integrations",
        type_="check",
    )
    op.alter_column(
        "sync_run",
        "status",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=False,
        existing_server_default=sa.text("'running'"),
        schema="integrations",
    )
    op.create_check_constraint(
        op.f("ck_sync_run_status"),
        "sync_run",
        _check_clause("status", LEGACY_SYNC_STATUSES),
        schema="integrations",
    )
    op.create_check_constraint(
        op.f("ck_sync_run_direction"),
        "sync_run",
        _check_clause("direction", LEGACY_SYNC_DIRECTIONS),
        schema="integrations",
    )
