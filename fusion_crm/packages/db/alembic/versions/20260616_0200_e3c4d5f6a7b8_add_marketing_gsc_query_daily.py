"""Add marketing.gsc_query_daily (Search Console daily query rows).

Revision ID: e3c4d5f6a7b8
Revises: d2b3c4e5f6a7
Create Date: 2026-06-16 02:00:00.000000+00:00

Additive only — adds ``marketing.gsc_query_daily`` for read-only Google Search
Console organic-search rows (one per site × day × query). Idempotent on
``(tenant_id, site_url, metric_date, query_hash)`` — ``query_hash`` (sha256)
keys the unique constraint because search queries can exceed the btree index
size limit; the verbatim query stays in ``query`` (TEXT). Mirrors
:class:`packages.marketing.models.GscQueryDaily`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e3c4d5f6a7b8"
down_revision: str | None = "d2b3c4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gsc_query_daily",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("site_url", sa.String(length=512), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "clicks", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "impressions", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "ctr",
            sa.Numeric(precision=8, scale=6),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Numeric(precision=8, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("raw_event_id", sa.UUID(), nullable=True),
        sa.Column(
            "extra",
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
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_gsc_query_daily_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gsc_query_daily")),
        sa.UniqueConstraint(
            "tenant_id",
            "site_url",
            "metric_date",
            "query_hash",
            name="uq_gsc_query_daily_natural",
        ),
        schema="marketing",
    )
    op.create_index(
        "ix_gsc_query_daily_tenant_id",
        "gsc_query_daily",
        ["tenant_id"],
        schema="marketing",
    )
    op.create_index(
        "ix_gsc_query_daily_tenant_site_date",
        "gsc_query_daily",
        ["tenant_id", "site_url", "metric_date"],
        schema="marketing",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_gsc_query_daily_tenant_site_date",
        table_name="gsc_query_daily",
        schema="marketing",
    )
    op.drop_index(
        "ix_gsc_query_daily_tenant_id",
        table_name="gsc_query_daily",
        schema="marketing",
    )
    op.drop_table("gsc_query_daily", schema="marketing")
