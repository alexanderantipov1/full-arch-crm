"""D3: ops.account (Phase 1 minimal view) — ENG-4

Revision ID: 4ba791c47185
Revises: 390b53c6f4a9
Create Date: 2026-05-05 23:18:00.000000+00:00

Chains after ENG-3 / D2 (a3b1c5d7e9f0) and ENG-2 / D1 (390b53c6f4a9),
which merged first.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "4ba791c47185"
down_revision: str | None = "390b53c6f4a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=240), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column(
            "raw",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider IN ('salesforce', 'hubspot', 'carestack', "
            "'manual', 'import')",
            name=op.f("ck_account_provider"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account")),
        sa.UniqueConstraint("provider", "source_id", name="uq_account_provider_source"),
        schema="ops",
    )
    op.create_index("ix_account_provider", "account", ["provider"], schema="ops")


def downgrade() -> None:
    op.drop_index("ix_account_provider", table_name="account", schema="ops")
    op.drop_table("account", schema="ops")
