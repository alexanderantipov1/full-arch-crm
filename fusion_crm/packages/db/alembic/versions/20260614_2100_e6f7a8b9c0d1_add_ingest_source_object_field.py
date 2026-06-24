"""ENG-426: add ingest.source_object_field (full-fidelity schema registry).

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-06-14 21:00:00.000000+00:00

Additive only — creates ``ingest.source_object_field``, the durable schema
registry for the Full-Fidelity Ingestion Framework (ENG-425). One row per
``(tenant_id, provider, object_name, field_name)`` records the field's type,
whether the integration user can read it (``readable`` — False for an
FLS-blocked Salesforce field), whether it is still present (``active``), and
first/last seen timestamps. Rows are never deleted; a disappeared field is
marked ``active = False`` so history is preserved like ``raw_event``.

Constraints/indexes mirror :class:`packages.ingest.models.SourceObjectField`:

* ``UNIQUE (tenant_id, provider, object_name, field_name)`` — idempotent
  per-field upserts.
* ``ix_source_object_field_tenant_id`` — tenant-wide scans.
* ``ix_source_object_field_object`` — per-object schema lookups.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_object_field",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("object_name", sa.String(length=128), nullable=False),
        sa.Column("field_name", sa.String(length=255), nullable=False),
        sa.Column("field_type", sa.String(length=64), nullable=True),
        sa.Column("readable", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
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
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_source_object_field_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_object_field")),
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "object_name",
            "field_name",
            name="uq_source_object_field_tenant_provider_object_field",
        ),
        schema="ingest",
    )
    op.create_index(
        "ix_source_object_field_tenant_id",
        "source_object_field",
        ["tenant_id"],
        schema="ingest",
    )
    op.create_index(
        "ix_source_object_field_object",
        "source_object_field",
        ["tenant_id", "provider", "object_name"],
        schema="ingest",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_source_object_field_object",
        table_name="source_object_field",
        schema="ingest",
    )
    op.drop_index(
        "ix_source_object_field_tenant_id",
        table_name="source_object_field",
        schema="ingest",
    )
    op.drop_table("source_object_field", schema="ingest")
