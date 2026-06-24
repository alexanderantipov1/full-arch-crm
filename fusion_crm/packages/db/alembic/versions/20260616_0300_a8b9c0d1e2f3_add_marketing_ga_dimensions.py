"""Add GA4 dimension tables + engagement columns (ENG-478).

Revision ID: a8b9c0d1e2f3
Revises: e3c4d5f6a7b8
Create Date: 2026-06-16 03:00:00.000000+00:00

Additive only. Adds two ``marketing`` projection tables for the GA4 dimension
splits — ``ga_channel_daily`` (date × acquisition channel) and
``ga_page_daily`` (date × landing page) — and five NULLABLE engagement columns
to the existing ``ga_metric_daily`` rollup (``engaged_sessions`` /
``engagement_rate`` / ``avg_session_duration`` / ``bounce_rate`` /
``event_count``). No backfill: pre-ENG-478 ``ga_metric_daily`` rows keep NULL
engagement (UI renders "—"); the next pull populates them. Mirrors
:class:`packages.marketing.models.GaChannelDaily` / ``GaPageDaily`` and the
extended ``GaMetricDaily``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a8b9c0d1e2f3"
down_revision: str | None = "e3c4d5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- additive engagement columns on the existing ga_metric_daily rollup ---
    op.add_column(
        "ga_metric_daily",
        sa.Column("engaged_sessions", sa.BigInteger(), nullable=True),
        schema="marketing",
    )
    op.add_column(
        "ga_metric_daily",
        sa.Column(
            "engagement_rate", sa.Numeric(precision=8, scale=6), nullable=True
        ),
        schema="marketing",
    )
    op.add_column(
        "ga_metric_daily",
        sa.Column(
            "avg_session_duration", sa.Numeric(precision=12, scale=4), nullable=True
        ),
        schema="marketing",
    )
    op.add_column(
        "ga_metric_daily",
        sa.Column("bounce_rate", sa.Numeric(precision=8, scale=6), nullable=True),
        schema="marketing",
    )
    op.add_column(
        "ga_metric_daily",
        sa.Column("event_count", sa.BigInteger(), nullable=True),
        schema="marketing",
    )

    # --- marketing.ga_channel_daily (date × sessionDefaultChannelGroup) ---
    op.create_table(
        "ga_channel_daily",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("property_id", sa.String(length=64), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("channel", sa.String(length=128), nullable=False),
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
            name=op.f("fk_ga_channel_daily_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ga_channel_daily")),
        sa.UniqueConstraint(
            "tenant_id",
            "property_id",
            "metric_date",
            "channel",
            name="uq_ga_channel_daily_natural",
        ),
        schema="marketing",
    )
    op.create_index(
        "ix_ga_channel_daily_tenant_id",
        "ga_channel_daily",
        ["tenant_id"],
        schema="marketing",
    )
    op.create_index(
        "ix_ga_channel_daily_tenant_property_date",
        "ga_channel_daily",
        ["tenant_id", "property_id", "metric_date"],
        schema="marketing",
    )

    # --- marketing.ga_page_daily (date × landingPage) ---
    op.create_table(
        "ga_page_daily",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("property_id", sa.String(length=64), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("page_path", sa.Text(), nullable=False),
        sa.Column("page_hash", sa.String(length=64), nullable=False),
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
            name=op.f("fk_ga_page_daily_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ga_page_daily")),
        sa.UniqueConstraint(
            "tenant_id",
            "property_id",
            "metric_date",
            "page_hash",
            name="uq_ga_page_daily_natural",
        ),
        schema="marketing",
    )
    op.create_index(
        "ix_ga_page_daily_tenant_id",
        "ga_page_daily",
        ["tenant_id"],
        schema="marketing",
    )
    op.create_index(
        "ix_ga_page_daily_tenant_property_date",
        "ga_page_daily",
        ["tenant_id", "property_id", "metric_date"],
        schema="marketing",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ga_page_daily_tenant_property_date",
        table_name="ga_page_daily",
        schema="marketing",
    )
    op.drop_index(
        "ix_ga_page_daily_tenant_id",
        table_name="ga_page_daily",
        schema="marketing",
    )
    op.drop_table("ga_page_daily", schema="marketing")

    op.drop_index(
        "ix_ga_channel_daily_tenant_property_date",
        table_name="ga_channel_daily",
        schema="marketing",
    )
    op.drop_index(
        "ix_ga_channel_daily_tenant_id",
        table_name="ga_channel_daily",
        schema="marketing",
    )
    op.drop_table("ga_channel_daily", schema="marketing")

    op.drop_column("ga_metric_daily", "event_count", schema="marketing")
    op.drop_column("ga_metric_daily", "bounce_rate", schema="marketing")
    op.drop_column("ga_metric_daily", "avg_session_duration", schema="marketing")
    op.drop_column("ga_metric_daily", "engagement_rate", schema="marketing")
    op.drop_column("ga_metric_daily", "engaged_sessions", schema="marketing")
