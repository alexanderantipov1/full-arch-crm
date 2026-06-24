"""ENG-308: add ingest.carestack_provider.

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-05-31 20:30:00.000000+00:00

Additive only — creates ``ingest.carestack_provider`` so the person card
can resolve ``carestack.patient.upsert``'s raw ``defaultProviderId``
integer into a readable "Dr First Last" via a tenant-scoped lookup.

The CareStack ``/api/v1.0/providers`` endpoint returns a flat array
(no pagination); the verbatim provider entry is preserved in
``payload`` JSONB so a future column extension does not require a
re-pull. Provider data is operational metadata (clinician name, type,
active flag), NOT PHI.

Constraints/indexes mirror :class:`packages.ingest.models.CareStackProvider`:

* ``UNIQUE (tenant_id, provider_carestack_id)`` — idempotent upserts
  keyed on the provider's CareStack id.
* ``ix_carestack_provider_tenant_id`` — tenant-wide scans for the
  backfill script.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e9f0a1b2c3d4"
down_revision: str | None = "d8e9f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "carestack_provider",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("provider_carestack_id", sa.BigInteger(), nullable=False),
        sa.Column("first_name", sa.String(length=120), nullable=True),
        sa.Column("last_name", sa.String(length=120), nullable=True),
        sa.Column("middle_name", sa.String(length=120), nullable=True),
        sa.Column("short_name", sa.String(length=64), nullable=True),
        sa.Column("provider_type", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "payload",
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
            name=op.f("fk_carestack_provider_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_carestack_provider")),
        sa.UniqueConstraint(
            "tenant_id",
            "provider_carestack_id",
            name="uq_carestack_provider_tenant_provider_id",
        ),
        schema="ingest",
    )
    op.create_index(
        "ix_carestack_provider_tenant_id",
        "carestack_provider",
        ["tenant_id"],
        schema="ingest",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_carestack_provider_tenant_id",
        table_name="carestack_provider",
        schema="ingest",
    )
    op.drop_table("carestack_provider", schema="ingest")
