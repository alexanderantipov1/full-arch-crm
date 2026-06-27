"""Add marketing schema: ad_campaign + ad_metric_daily (ad-spend ingest).

Revision ID: c1a2b3d4e5f6
Revises: e7d6c5b4a3f2
Create Date: 2026-06-15 08:00:00.000000+00:00

Additive only — creates the ``marketing`` schema (user-approved 2026-06-15)
and its two Phase-1 tables holding aggregate, non-PHI ad-spend data pulled
read-only from Google/Meta/TikTok ads:

* ``marketing.ad_campaign`` — one row per platform campaign, idempotent on
  ``(tenant_id, provider, external_id)``.
* ``marketing.ad_metric_daily`` — daily spend/impressions/clicks/conversions,
  idempotent on ``(tenant_id, provider, campaign_external_id, metric_date)``.

The schema is created with ``CREATE SCHEMA IF NOT EXISTS marketing`` so
existing databases (which do not re-run ``init-schemas.sql``) get it; fresh
databases also get it from ``infra/docker/init-schemas.sql``.

Constraints/indexes mirror :mod:`packages.marketing.models`. The ``provider``
CHECK constraints stay in lock-step with ``AD_PROVIDERS`` in that module.
``tenant_id`` FKs ``tenant.tenant.id`` via the shared mixin.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1a2b3d4e5f6"
down_revision: str | None = "e7d6c5b4a3f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROVIDER_SQL = "provider IN ('google_ads', 'meta_ads', 'tiktok_ads')"


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS marketing")

    op.create_table(
        "ad_campaign",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=240), nullable=False),
        sa.Column("name", sa.String(length=480), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("objective", sa.String(length=128), nullable=True),
        sa.Column("account_id", sa.String(length=128), nullable=True),
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
        sa.CheckConstraint(_PROVIDER_SQL, name=op.f("ck_ad_campaign_provider")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_ad_campaign_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ad_campaign")),
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "external_id",
            name="uq_ad_campaign_natural",
        ),
        schema="marketing",
    )
    op.create_index(
        "ix_ad_campaign_tenant_id",
        "ad_campaign",
        ["tenant_id"],
        schema="marketing",
    )
    op.create_index(
        "ix_ad_campaign_tenant_provider",
        "ad_campaign",
        ["tenant_id", "provider"],
        schema="marketing",
    )

    op.create_table(
        "ad_metric_daily",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("campaign_external_id", sa.String(length=240), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column(
            "spend",
            sa.Numeric(precision=14, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "impressions",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "clicks",
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
        sa.Column("currency", sa.String(length=8), nullable=True),
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
        sa.CheckConstraint(_PROVIDER_SQL, name=op.f("ck_ad_metric_daily_provider")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_ad_metric_daily_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ad_metric_daily")),
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "campaign_external_id",
            "metric_date",
            name="uq_ad_metric_daily_natural",
        ),
        schema="marketing",
    )
    op.create_index(
        "ix_ad_metric_daily_tenant_id",
        "ad_metric_daily",
        ["tenant_id"],
        schema="marketing",
    )
    op.create_index(
        "ix_ad_metric_daily_tenant_provider_date",
        "ad_metric_daily",
        ["tenant_id", "provider", "metric_date"],
        schema="marketing",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ad_metric_daily_tenant_provider_date",
        table_name="ad_metric_daily",
        schema="marketing",
    )
    op.drop_index(
        "ix_ad_metric_daily_tenant_id",
        table_name="ad_metric_daily",
        schema="marketing",
    )
    op.drop_table("ad_metric_daily", schema="marketing")
    op.drop_index(
        "ix_ad_campaign_tenant_provider",
        table_name="ad_campaign",
        schema="marketing",
    )
    op.drop_index(
        "ix_ad_campaign_tenant_id",
        table_name="ad_campaign",
        schema="marketing",
    )
    op.drop_table("ad_campaign", schema="marketing")
    # The schema holds ONLY the two tables dropped above, so a plain
    # DROP SCHEMA without CASCADE is correct and safer.
    op.execute("DROP SCHEMA IF EXISTS marketing")
