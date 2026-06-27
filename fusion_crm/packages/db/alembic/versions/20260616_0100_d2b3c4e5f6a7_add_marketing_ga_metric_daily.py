"""Add marketing.ga_metric_daily (GA4 daily property metrics).

Revision ID: d2b3c4e5f6a7
Revises: c1a2b3d4e5f6
Create Date: 2026-06-16 01:00:00.000000+00:00

Additive only — adds ``marketing.ga_metric_daily`` to the existing
``marketing`` schema for read-only GA4 daily web-traffic metrics
(sessions / users / pageviews / conversions). Idempotent on
``(tenant_id, property_id, metric_date)``. Mirrors
:class:`packages.marketing.models.GaMetricDaily`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d2b3c4e5f6a7"
down_revision: str | None = "c1a2b3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ga_metric_daily",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("property_id", sa.String(length=64), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column(
            "sessions", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "total_users", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "new_users", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "screen_page_views",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "conversions",
            sa.Numeric(precision=14, scale=2),
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
            name=op.f("fk_ga_metric_daily_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ga_metric_daily")),
        sa.UniqueConstraint(
            "tenant_id",
            "property_id",
            "metric_date",
            name="uq_ga_metric_daily_natural",
        ),
        schema="marketing",
    )
    op.create_index(
        "ix_ga_metric_daily_tenant_id",
        "ga_metric_daily",
        ["tenant_id"],
        schema="marketing",
    )
    op.create_index(
        "ix_ga_metric_daily_tenant_property_date",
        "ga_metric_daily",
        ["tenant_id", "property_id", "metric_date"],
        schema="marketing",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ga_metric_daily_tenant_property_date",
        table_name="ga_metric_daily",
        schema="marketing",
    )
    op.drop_index(
        "ix_ga_metric_daily_tenant_id",
        table_name="ga_metric_daily",
        schema="marketing",
    )
    op.drop_table("ga_metric_daily", schema="marketing")
