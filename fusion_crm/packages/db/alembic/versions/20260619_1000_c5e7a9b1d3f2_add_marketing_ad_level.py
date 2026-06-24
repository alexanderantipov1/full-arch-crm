"""Add marketing ad-level tables: ad_set + ad + ad_metric_daily_ad (ENG-512).

Revision ID: c5e7a9b1d3f2
Revises: c3d4e5f6a7b8
Create Date: 2026-06-19 10:00:00.000000+00:00

Additive only — adds three ad-tier tables to the existing ``marketing`` schema
for the ad-level cost-per-lead allocator. Campaign-level tables (``ad_campaign``
/ ``ad_metric_daily``) are untouched.

* ``marketing.ad_set`` — one row per ad set / ad group, idempotent on
  ``(tenant_id, provider, external_id)``.
* ``marketing.ad`` — one row per ad / creative, idempotent on
  ``(tenant_id, provider, external_id)``.
* ``marketing.ad_metric_daily_ad`` — daily ad-level spend/impressions/clicks/
  conversions, idempotent on ``(tenant_id, provider, ad_external_id,
  metric_date)``.

Constraints/indexes mirror :mod:`packages.marketing.models`. The ``provider``
CHECK stays in lock-step with ``AD_PROVIDERS`` in that module. ``tenant_id``
FKs ``tenant.tenant.id``. The ``marketing`` schema already exists (revision
c1a2b3d4e5f6), so this revision does NOT create/drop it.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5e7a9b1d3f2"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROVIDER_SQL = "provider IN ('google_ads', 'meta_ads', 'tiktok_ads')"


def upgrade() -> None:
    op.create_table(
        "ad_set",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=240), nullable=False),
        sa.Column("name", sa.String(length=480), nullable=True),
        sa.Column("campaign_external_id", sa.String(length=240), nullable=True),
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
        sa.CheckConstraint(_PROVIDER_SQL, name=op.f("ck_ad_set_provider")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_ad_set_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ad_set")),
        sa.UniqueConstraint(
            "tenant_id", "provider", "external_id", name="uq_ad_set_natural"
        ),
        schema="marketing",
    )
    op.create_index(
        "ix_ad_set_tenant_id", "ad_set", ["tenant_id"], schema="marketing"
    )
    op.create_index(
        "ix_ad_set_tenant_provider",
        "ad_set",
        ["tenant_id", "provider"],
        schema="marketing",
    )

    op.create_table(
        "ad",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=240), nullable=False),
        sa.Column("name", sa.String(length=480), nullable=True),
        sa.Column("adset_external_id", sa.String(length=240), nullable=True),
        sa.Column("campaign_external_id", sa.String(length=240), nullable=True),
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
        sa.CheckConstraint(_PROVIDER_SQL, name=op.f("ck_ad_provider")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_ad_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ad")),
        sa.UniqueConstraint(
            "tenant_id", "provider", "external_id", name="uq_ad_natural"
        ),
        schema="marketing",
    )
    op.create_index("ix_ad_tenant_id", "ad", ["tenant_id"], schema="marketing")
    op.create_index(
        "ix_ad_tenant_provider",
        "ad",
        ["tenant_id", "provider"],
        schema="marketing",
    )

    op.create_table(
        "ad_metric_daily_ad",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("ad_external_id", sa.String(length=240), nullable=False),
        sa.Column("adset_external_id", sa.String(length=240), nullable=True),
        sa.Column("campaign_external_id", sa.String(length=240), nullable=True),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column(
            "spend",
            sa.Numeric(precision=14, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "impressions", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "clicks", sa.BigInteger(), server_default=sa.text("0"), nullable=False
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
        sa.CheckConstraint(
            _PROVIDER_SQL, name=op.f("ck_ad_metric_daily_ad_provider")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_ad_metric_daily_ad_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ad_metric_daily_ad")),
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "ad_external_id",
            "metric_date",
            name="uq_ad_metric_daily_ad_natural",
        ),
        schema="marketing",
    )
    op.create_index(
        "ix_ad_metric_daily_ad_tenant_id",
        "ad_metric_daily_ad",
        ["tenant_id"],
        schema="marketing",
    )
    op.create_index(
        "ix_ad_metric_daily_ad_tenant_provider_date",
        "ad_metric_daily_ad",
        ["tenant_id", "provider", "metric_date"],
        schema="marketing",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ad_metric_daily_ad_tenant_provider_date",
        table_name="ad_metric_daily_ad",
        schema="marketing",
    )
    op.drop_index(
        "ix_ad_metric_daily_ad_tenant_id",
        table_name="ad_metric_daily_ad",
        schema="marketing",
    )
    op.drop_table("ad_metric_daily_ad", schema="marketing")
    op.drop_index("ix_ad_tenant_provider", table_name="ad", schema="marketing")
    op.drop_index("ix_ad_tenant_id", table_name="ad", schema="marketing")
    op.drop_table("ad", schema="marketing")
    op.drop_index(
        "ix_ad_set_tenant_provider", table_name="ad_set", schema="marketing"
    )
    op.drop_index("ix_ad_set_tenant_id", table_name="ad_set", schema="marketing")
    op.drop_table("ad_set", schema="marketing")
