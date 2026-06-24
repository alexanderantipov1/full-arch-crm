"""add ops opportunity table (ENG-414)

Revision ID: b1f2c3d4e5a6
Revises: e4f5a6b7c8d9
Create Date: 2026-06-13 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b1f2c3d4e5a6"
down_revision: str | Sequence[str] | None = "a6b7c8d9e0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "ops"


def upgrade() -> None:
    op.create_table(
        "opportunity",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_uid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_provider", sa.String(length=32), nullable=False),
        sa.Column("source_instance", sa.String(length=96), nullable=False),
        sa.Column("external_id", sa.String(length=240), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=True),
        sa.Column("stage", sa.String(length=64), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("close_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_provider IN ('salesforce')",
            name=op.f("ck_opportunity_source_provider"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_opportunity_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_opportunity")),
        sa.UniqueConstraint(
            "tenant_id",
            "source_provider",
            "source_instance",
            "external_id",
            name="uq_opportunity_source",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_opportunity_tenant_id",
        "opportunity",
        ["tenant_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_opportunity_person_uid",
        "opportunity",
        ["person_uid"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_opportunity_tenant_person_close",
        "opportunity",
        ["tenant_id", "person_uid", "close_date"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_opportunity_tenant_provider_created",
        "opportunity",
        ["tenant_id", "provider_created_at"],
        unique=False,
        schema=SCHEMA,
    )
    # GIN index on extra so the owner-name backfill and the PM dashboard
    # owner-filter can jsonb-path-lookup ``extra->>'owner_id'`` without
    # scanning the table.
    op.create_index(
        "ix_opportunity_extra_gin",
        "opportunity",
        ["extra"],
        unique=False,
        schema=SCHEMA,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_opportunity_extra_gin",
        table_name="opportunity",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_opportunity_tenant_provider_created",
        table_name="opportunity",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_opportunity_tenant_person_close",
        table_name="opportunity",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_opportunity_person_uid",
        table_name="opportunity",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_opportunity_tenant_id",
        table_name="opportunity",
        schema=SCHEMA,
    )
    op.drop_table("opportunity", schema=SCHEMA)
