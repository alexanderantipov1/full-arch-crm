"""ENG-570: attribution.vendor entity (first-class configured vendor)

Block A of the vendor-attribution epic (ENG-569). Promotes the vendor from a
controlled-vocabulary ``source_node`` level to a first-class configured entity
that carries operator settings (name, kind, color, notes) and — in later blocks
— money. Each vendor links 1:1 to the vendor-level ``source_node`` it owns via
``source_node_id``.

This migration does NOT repoint ``lead_attribution.vendor_id`` (still ->
``source_node``); that repoint lands in Block C (ENG-572) when the funnel tree
is re-rooted on vendors. Here we only add the table and backfill one vendor row
per existing vendor-level node, so the operator's vendor list reflects reality.

Backfill rules:
* one ``vendor`` per ``source_node`` with ``level = 'vendor'``;
* the ``unassigned`` / ``__none__`` buckets are the NULL sink — NOT vendors —
  and are skipped (unbound traffic stays Unassigned, never a vendor);
* ``in_house`` -> ``kind = 'in_house'``; everything else -> ``kind = 'agency'``.

Derived data — fully rebuildable by the resolver — so the table may be dropped
and rebuilt at any time. Downgrade drops it.

Revision ID: c4d2e6f8a9b1
Revises: fd36dd4df2f3
Create Date: 2026-06-23 01:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c4d2e6f8a9b1"
down_revision: str | Sequence[str] | None = "fd36dd4df2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "attribution"
_TABLE = "vendor"

# Backfill one vendor per existing vendor-level node, excluding the NULL-bucket
# sentinels. gen_random_uuid() is built into PostgreSQL 13+ (no pgcrypto needed).
_BACKFILL_SQL = sa.text(
    f"""
    INSERT INTO {SCHEMA}.{_TABLE}
        (id, tenant_id, slug, name, kind, active, color, notes,
         source_node_id, meta, created_at, updated_at)
    SELECT gen_random_uuid(),
           sn.tenant_id,
           sn.slug,
           sn.label,
           CASE WHEN sn.slug = 'in_house' THEN 'in_house' ELSE 'agency' END,
           sn.active,
           NULL,
           NULL,
           sn.id,
           '{{}}'::jsonb,
           now(),
           now()
    FROM {SCHEMA}.source_node sn
    WHERE sn.level = 'vendor'
      AND sn.slug NOT IN ('unassigned', '__none__')
    """
)


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("source_node_id", sa.UUID(), nullable=True),
        sa.Column(
            "meta",
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
            ["source_node_id"],
            [f"{SCHEMA}.source_node.id"],
            name=op.f("fk_vendor_source_node_id_source_node"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_vendor_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vendor")),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_vendor_tenant_slug"),
        sa.UniqueConstraint(
            "tenant_id", "source_node_id", name="uq_vendor_tenant_source_node"
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_vendor_tenant_id", _TABLE, ["tenant_id"], schema=SCHEMA)
    op.create_index(
        "ix_vendor_active", _TABLE, ["tenant_id", "active"], schema=SCHEMA
    )

    op.execute(_BACKFILL_SQL)


def downgrade() -> None:
    op.drop_index("ix_vendor_active", table_name=_TABLE, schema=SCHEMA)
    op.drop_index("ix_vendor_tenant_id", table_name=_TABLE, schema=SCHEMA)
    op.drop_table(_TABLE, schema=SCHEMA)
