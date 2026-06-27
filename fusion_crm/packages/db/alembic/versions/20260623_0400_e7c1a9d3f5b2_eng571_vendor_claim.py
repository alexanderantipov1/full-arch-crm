"""ENG-571: vendor_claim — bind traffic to a vendor

Block B of the vendor-attribution epic (ENG-569). A ``vendor_claim`` is a
mapping rule specialised to the vendor level and tied to a configured
``attribution.vendor`` entity: "traffic whose ``match_field`` ``match_op``
``match_value`` belongs to this vendor". The resolver loads active claims as
vendor-level rules.

Additive; derived/operator data, no PHI. Downgrade drops the table.

Revision ID: e7c1a9d3f5b2
Revises: d5f3a7b9c2e4
Create Date: 2026-06-23 04:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7c1a9d3f5b2"
down_revision: str | Sequence[str] | None = "d5f3a7b9c2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "attribution"


def upgrade() -> None:
    op.create_table(
        "vendor_claim",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("vendor_id", sa.UUID(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("match_field", sa.String(length=64), nullable=False),
        sa.Column("match_op", sa.String(length=16), nullable=False),
        sa.Column("match_value", sa.String(length=240), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
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
            ["vendor_id"],
            [f"{SCHEMA}.vendor.id"],
            name=op.f("fk_vendor_claim_vendor_id_vendor"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_vendor_claim_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vendor_claim")),
        sa.UniqueConstraint(
            "tenant_id",
            "vendor_id",
            "match_field",
            "match_op",
            "match_value",
            name="uq_vendor_claim_signature",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_vendor_claim_tenant_active",
        "vendor_claim",
        ["tenant_id", "active", "priority"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_vendor_claim_vendor",
        "vendor_claim",
        ["tenant_id", "vendor_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_vendor_claim_vendor", table_name="vendor_claim", schema=SCHEMA)
    op.drop_index(
        "ix_vendor_claim_tenant_active", table_name="vendor_claim", schema=SCHEMA
    )
    op.drop_table("vendor_claim", schema=SCHEMA)
