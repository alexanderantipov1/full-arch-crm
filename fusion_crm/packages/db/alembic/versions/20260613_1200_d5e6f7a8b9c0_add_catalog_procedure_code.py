"""add catalog procedure_code

Revision ID: d5e6f7a8b9c0
Revises: e4f5a6b7c8d9
Create Date: 2026-06-13 12:00:00.000000

ENG-420 — CareStack procedure-code (CDT) catalog sync.

Adds the workspace-wide ``catalog`` schema and the
``catalog.procedure_code`` reference table. Tenant scoping is
intentionally omitted (CDT is a global ADA standard); see
``packages/catalog/CLAUDE.md`` for the rationale.

Primary key is the codebase-standard UUID (root ``CLAUDE.md``
invariant #8). The CareStack procedure-code id is stored on
``carestack_code_id`` (``BIGINT NOT NULL UNIQUE``) — the natural
business key the resolver looks up and the idempotent upsert keys on.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: str | Sequence[str] | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "catalog"


def upgrade() -> None:
    # Existing dev/test/prod databases predate the init-schemas.sql
    # ``catalog`` entry — init-schemas runs ONCE on a fresh data dir.
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))

    op.create_table(
        "procedure_code",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "carestack_code_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("code_type_id", sa.Integer(), nullable=True),
        sa.Column("cdt_category_id", sa.Integer(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_procedure_code")),
        sa.UniqueConstraint(
            "carestack_code_id",
            name="uq_procedure_code_carestack_code_id",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_procedure_code_carestack_code_id",
        "procedure_code",
        ["carestack_code_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_procedure_code_carestack_code_id",
        table_name="procedure_code",
        schema=SCHEMA,
    )
    op.drop_table("procedure_code", schema=SCHEMA)
    # ``procedure_code`` is the FIRST table in the ``catalog`` schema,
    # so the downgrade reverses the schema creation from ``upgrade``.
    # ``IF EXISTS`` keeps this idempotent — and safe if a later catalog
    # migration ever lands a second table that this downgrade outlives
    # (Postgres refuses to drop a non-empty schema without CASCADE).
    op.execute(sa.text(f"DROP SCHEMA IF EXISTS {SCHEMA}"))
