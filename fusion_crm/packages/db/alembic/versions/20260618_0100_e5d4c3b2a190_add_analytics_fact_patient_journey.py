"""ENG-505: add analytics schema + fact_patient_journey (read-model + provenance).

Revision ID: e5d4c3b2a190
Revises: f6a7b8c9d0e1
Create Date: 2026-06-18 01:00:00.000000+00:00

Additive only — creates the operator-approved ``analytics`` schema (ENG-504 /
ENG-505) and its first table ``fact_patient_journey``: one row per
``person_uid`` projecting the full revenue journey (ad spend → collected
revenue). The ``analytics`` schema is a **rebuildable projection, never a source
of truth** — every row is derived by the fact builder (ENG-506) and can be
dropped and rebuilt.

Per the operator decision every column is nullable except the ``person_uid``
primary key. No cross-domain FK (plain UUID columns, invariant #2/#3).
``field_provenance`` is a JSONB sidecar holding per-field
``{source, method, confidence, resolved_at}``.

``CREATE SCHEMA IF NOT EXISTS`` is in-migration (mirrors the attribution-chain
revision) so a fresh/scratch DB upgrades cleanly without depending on
``infra/docker/init-schemas.sql`` having been re-run.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5d4c3b2a190"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "analytics"


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))

    op.create_table(
        "fact_patient_journey",
        # Identity (PK) — global person reference, plain UUID (no FK).
        sa.Column("person_uid", sa.UUID(), nullable=False),
        # Dimensions (all nullable).
        sa.Column("campaign_id", sa.UUID(), nullable=True),
        sa.Column("campaign_name", sa.String(length=240), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=True),
        sa.Column("vendor_id", sa.UUID(), nullable=True),
        sa.Column("caller_id", sa.UUID(), nullable=True),
        sa.Column("coordinator_id", sa.UUID(), nullable=True),
        sa.Column("doctor_id", sa.UUID(), nullable=True),
        sa.Column("location_id", sa.UUID(), nullable=True),
        # Stage timestamps (all nullable, tz-aware).
        sa.Column("lead_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_contact_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consult_scheduled_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("show_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "treatment_presented_date", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "treatment_accepted_date", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("surgery_scheduled_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("surgery_completed_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_payment_date", sa.DateTime(timezone=True), nullable=True),
        # Money (all nullable).
        sa.Column("revenue_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("collected_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column(
            "marketing_cost_allocated",
            sa.Numeric(precision=14, scale=2),
            nullable=True,
        ),
        # Provenance sidecar — NOT NULL, defaults to '{}'.
        sa.Column(
            "field_provenance",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        # Build-tracking timestamps (TimestampMixin).
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
        sa.PrimaryKeyConstraint("person_uid", name=op.f("pk_fact_patient_journey")),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fact_patient_journey_location_id",
        "fact_patient_journey",
        ["location_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fact_patient_journey_lead_date",
        "fact_patient_journey",
        ["lead_date"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fact_patient_journey_source",
        "fact_patient_journey",
        ["source"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fact_patient_journey_campaign_id",
        "fact_patient_journey",
        ["campaign_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fact_patient_journey_first_payment_date",
        "fact_patient_journey",
        ["first_payment_date"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("fact_patient_journey", schema=SCHEMA)
