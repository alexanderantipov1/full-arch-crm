"""ENG-573: vendor monthly fee (flat rate + per-month overrides)

Block D (money) of the vendor-attribution epic (ENG-569), folded onto the
vendor-entity branch. Two modes per vendor:

* ``flat_monthly_fee = true`` (default) → ``monthly_fee`` applies to every month
  (the common case: a fixed retainer);
* ``flat_monthly_fee = false`` → the amount varies month to month and is taken
  from ``attribution.vendor_cost`` rows (one per month).

Adds three columns to ``attribution.vendor`` and a new ``attribution.vendor_cost``
table. Additive; derived/operator data, no PHI. Downgrade drops them.

Revision ID: d5f3a7b9c2e4
Revises: c4d2e6f8a9b1
Create Date: 2026-06-23 02:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5f3a7b9c2e4"
down_revision: str | Sequence[str] | None = "c4d2e6f8a9b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "attribution"


def upgrade() -> None:
    op.add_column(
        "vendor",
        sa.Column("monthly_fee", sa.Numeric(precision=12, scale=2), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "vendor",
        sa.Column(
            "flat_monthly_fee",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "vendor",
        sa.Column(
            "fee_currency",
            sa.String(length=3),
            server_default="USD",
            nullable=False,
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "vendor_cost",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("vendor_id", sa.UUID(), nullable=False),
        sa.Column("period_month", sa.String(length=7), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
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
            name=op.f("fk_vendor_cost_vendor_id_vendor"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_vendor_cost_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vendor_cost")),
        sa.UniqueConstraint(
            "tenant_id",
            "vendor_id",
            "period_month",
            name="uq_vendor_cost_tenant_vendor_month",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_vendor_cost_vendor",
        "vendor_cost",
        ["tenant_id", "vendor_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_vendor_cost_vendor", table_name="vendor_cost", schema=SCHEMA)
    op.drop_table("vendor_cost", schema=SCHEMA)
    op.drop_column("vendor", "fee_currency", schema=SCHEMA)
    op.drop_column("vendor", "flat_monthly_fee", schema=SCHEMA)
    op.drop_column("vendor", "monthly_fee", schema=SCHEMA)
