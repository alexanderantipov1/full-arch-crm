"""ENG-189: add ops.person_location_profile.

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-05-22 09:00:00.000000+00:00

Adds the CRM-safe per-location relationship projection between a global
``identity.person`` and a clinic/location context. Raw provider payloads and
clinical facts stay outside ``ops``; this table stores only evidence-derived
status used by staff UI and agent context.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "f3a4b5c6d7e8"
down_revision: str | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "consultation",
        "id",
        existing_type=PG_UUID(as_uuid=True),
        existing_nullable=False,
        server_default=None,
        schema="ops",
    )
    op.alter_column(
        "consultation",
        "status",
        existing_type=sa.String(16),
        existing_nullable=False,
        server_default=None,
        schema="ops",
    )
    op.alter_column(
        "consultation",
        "consultation_kind",
        existing_type=sa.String(16),
        existing_nullable=False,
        server_default=None,
        schema="ops",
    )
    op.create_foreign_key(
        "fk_consultation_tenant_id_tenant",
        "consultation",
        "tenant",
        ["tenant_id"],
        ["id"],
        source_schema="ops",
        referent_schema="tenant",
        ondelete="RESTRICT",
    )

    op.create_table(
        "person_location_profile",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("person_uid", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column(
            "relationship_kind",
            sa.String(32),
            nullable=False,
        ),
        sa.Column(
            "relationship_status",
            sa.String(32),
            nullable=False,
        ),
        sa.Column("last_evidence_provider", sa.String(32), nullable=True),
        sa.Column("last_evidence_source_instance", sa.String(96), nullable=True),
        sa.Column("last_evidence_external_id", sa.String(240), nullable=True),
        sa.Column("last_evidence_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_consultation_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("last_raw_event_id", PG_UUID(as_uuid=True), nullable=True),
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
            "relationship_kind IN ('prospect', 'patient')",
            name="ck_person_location_profile_relationship_kind",
        ),
        sa.CheckConstraint(
            "relationship_status IN ('unknown', 'consult_scheduled', "
            "'consult_completed', 'no_show', 'cancelled')",
            name="ck_person_location_profile_relationship_status",
        ),
        sa.CheckConstraint(
            "last_evidence_provider IS NULL OR last_evidence_provider IN "
            "('salesforce', 'carestack', 'manual', 'import')",
            name="ck_person_location_profile_evidence_provider",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "person_uid",
            "location_id",
            name="uq_person_location_profile_tenant_person_location",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name="fk_person_location_profile_tenant_id_tenant",
            ondelete="RESTRICT",
        ),
        schema="ops",
    )
    op.create_index(
        "ix_person_location_profile_tenant_id",
        "person_location_profile",
        ["tenant_id"],
        schema="ops",
    )
    op.create_index(
        "ix_person_location_profile_person_uid",
        "person_location_profile",
        ["person_uid"],
        schema="ops",
    )
    op.create_index(
        "ix_person_location_profile_location_id",
        "person_location_profile",
        ["location_id"],
        schema="ops",
    )
    op.create_index(
        "ix_person_location_profile_tenant_location",
        "person_location_profile",
        ["tenant_id", "location_id"],
        schema="ops",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_person_location_profile_tenant_location",
        table_name="person_location_profile",
        schema="ops",
    )
    op.drop_index(
        "ix_person_location_profile_location_id",
        table_name="person_location_profile",
        schema="ops",
    )
    op.drop_index(
        "ix_person_location_profile_person_uid",
        table_name="person_location_profile",
        schema="ops",
    )
    op.drop_index(
        "ix_person_location_profile_tenant_id",
        table_name="person_location_profile",
        schema="ops",
    )
    op.drop_table("person_location_profile", schema="ops")
    op.execute(
        "ALTER TABLE ops.consultation "
        "DROP CONSTRAINT IF EXISTS fk_consultation_tenant_id_tenant"
    )
    op.alter_column(
        "consultation",
        "consultation_kind",
        existing_type=sa.String(16),
        existing_nullable=False,
        server_default="other",
        schema="ops",
    )
    op.alter_column(
        "consultation",
        "status",
        existing_type=sa.String(16),
        existing_nullable=False,
        server_default="scheduled",
        schema="ops",
    )
    op.alter_column(
        "consultation",
        "id",
        existing_type=PG_UUID(as_uuid=True),
        existing_nullable=False,
        server_default=sa.text("gen_random_uuid()"),
        schema="ops",
    )
