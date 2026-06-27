"""ENG-217: ops.consultation domain table.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-05-21 19:00:00.000000+00:00

Establishes the canonical ``ops.consultation`` table for the ENG-216 umbrella
mission. The table holds the marketing-safe projection of a CareStack
appointment or a Salesforce calendar Event. Clinical notes / treatment
plans / diagnoses stay in the provider source (and land in ``phi.*`` at
M3+); only the columns AI agents and operator dashboards are allowed to see
live here.

Tenant-scoped (ENG-128) and source-instance scoped (ENG-181). Idempotent
on ``(tenant_id, source_provider, source_instance, external_id)`` — the
cron-driven puller (ENG-220) re-upserts on every run.

No backfill — table is empty at creation; first writes come from
ENG-218 / ENG-219.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "e2f3a4b5c6d7"
down_revision: str | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consultation",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("person_uid", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("source_provider", sa.String(32), nullable=False),
        sa.Column("source_instance", sa.String(96), nullable=False),
        sa.Column("external_id", sa.String(240), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column(
            "consultation_kind",
            sa.String(16),
            nullable=False,
            server_default="other",
        ),
        sa.Column("location_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("provider_clinician_name", sa.String(240), nullable=True),
        sa.Column("raw_event_id", PG_UUID(as_uuid=True), nullable=True),
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
            "source_provider IN ('salesforce', 'carestack')",
            name="ck_consultation_source_provider",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "source_provider",
            "source_instance",
            "external_id",
            name="uq_consultation_source",
        ),
        schema="ops",
    )
    op.create_index(
        "ix_consultation_tenant_id",
        "consultation",
        ["tenant_id"],
        schema="ops",
    )
    op.create_index(
        "ix_consultation_person_uid",
        "consultation",
        ["person_uid"],
        schema="ops",
    )
    op.create_index(
        "ix_consultation_tenant_person_scheduled",
        "consultation",
        ["tenant_id", "person_uid", "scheduled_at"],
        schema="ops",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_consultation_tenant_person_scheduled",
        table_name="consultation",
        schema="ops",
    )
    op.drop_index(
        "ix_consultation_person_uid",
        table_name="consultation",
        schema="ops",
    )
    op.drop_index(
        "ix_consultation_tenant_id",
        table_name="consultation",
        schema="ops",
    )
    op.drop_table("consultation", schema="ops")
