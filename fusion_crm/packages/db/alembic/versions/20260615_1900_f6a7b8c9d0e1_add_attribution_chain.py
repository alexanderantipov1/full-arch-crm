"""ENG-447: add attribution chain schema (source_node, lead_attribution, mapping_rule).

Revision ID: f6a7b8c9d0e1
Revises: f4d5e6a7b8c9
Create Date: 2026-06-15 19:00:00.000000+00:00

Additive only — creates the ``attribution`` schema and its three tables for the
Lead Source Attribution framework (ENG-446). ``source_node`` is the controlled
distribution-chain vocabulary (vendor → channel → campaign → ad_set → ad →
form via ``parent_id``); ``lead_attribution`` is the resolved chain per
person; ``mapping_rule`` holds editable pattern → node rules.

Schema-only. The controlled-vocabulary seed is a separate operator action
(``AttributionService.seed_default_nodes`` / ``infra/scripts/seed_attribution_vocab.py``)
because it is tenant-scoped data, not schema.

NOTE: originally branched from the ``catalog`` head (d5e6f7a8b9c0) with an
Alembic merge revision to rejoin main. On the 2026-06-17 integration rebase
the chain was linearized: this additive, order-independent migration is
re-pointed onto the then-current main head (f4d5e6a7b8c9, the marketing
provider-kinds migration) and the merge revision was dropped, restoring a
single linear head.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "f4d5e6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "attribution"


def _node_fk_column(name: str, *, nullable: bool, ondelete: str) -> sa.Column:
    return sa.Column(
        name,
        sa.UUID(),
        sa.ForeignKey(f"{SCHEMA}.source_node.id", ondelete=ondelete),
        nullable=nullable,
    )


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))

    op.create_table(
        "source_node",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("label", sa.String(length=240), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
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
            ["parent_id"],
            [f"{SCHEMA}.source_node.id"],
            name=op.f("fk_source_node_parent_id_source_node"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_source_node_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_node")),
        sa.UniqueConstraint(
            "tenant_id", "level", "slug", name="uq_source_node_tenant_level_slug"
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_source_node_tenant_id", "source_node", ["tenant_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_source_node_level", "source_node", ["tenant_id", "level"], schema=SCHEMA
    )
    op.create_index(
        "ix_source_node_parent", "source_node", ["parent_id"], schema=SCHEMA
    )

    op.create_table(
        "lead_attribution",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("person_uid", sa.UUID(), nullable=False),
        sa.Column("sf_lead_id", sa.String(length=32), nullable=True),
        _node_fk_column("vendor_id", nullable=True, ondelete="SET NULL"),
        _node_fk_column("channel_id", nullable=True, ondelete="SET NULL"),
        _node_fk_column("campaign_id", nullable=True, ondelete="SET NULL"),
        _node_fk_column("ad_set_id", nullable=True, ondelete="SET NULL"),
        _node_fk_column("ad_id", nullable=True, ondelete="SET NULL"),
        _node_fk_column("form_id", nullable=True, ondelete="SET NULL"),
        sa.Column("created_by_name", sa.String(length=240), nullable=True),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("source_signal", sa.String(length=32), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
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
            name=op.f("fk_lead_attribution_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_attribution")),
        sa.UniqueConstraint(
            "tenant_id", "person_uid", name="uq_lead_attribution_tenant_person"
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_lead_attribution_tenant_id",
        "lead_attribution",
        ["tenant_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_lead_attribution_vendor",
        "lead_attribution",
        ["tenant_id", "vendor_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_lead_attribution_channel",
        "lead_attribution",
        ["tenant_id", "channel_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_lead_attribution_method",
        "lead_attribution",
        ["tenant_id", "method"],
        schema=SCHEMA,
    )

    op.create_table(
        "mapping_rule",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("match_field", sa.String(length=64), nullable=False),
        sa.Column("match_op", sa.String(length=16), nullable=False),
        sa.Column("match_value", sa.String(length=240), nullable=False),
        sa.Column("set_level", sa.String(length=16), nullable=False),
        _node_fk_column("set_node_id", nullable=False, ondelete="CASCADE"),
        sa.Column("active", sa.Boolean(), nullable=False),
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
            name=op.f("fk_mapping_rule_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mapping_rule")),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_mapping_rule_tenant_id", "mapping_rule", ["tenant_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_mapping_rule_active",
        "mapping_rule",
        ["tenant_id", "active", "priority"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("mapping_rule", schema=SCHEMA)
    op.drop_table("lead_attribution", schema=SCHEMA)
    op.drop_table("source_node", schema=SCHEMA)
