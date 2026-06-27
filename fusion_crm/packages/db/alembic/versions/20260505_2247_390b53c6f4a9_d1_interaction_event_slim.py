"""D1: interaction.event (slim Phase 1 subset) — ENG-2

Revision ID: 390b53c6f4a9
Revises: a3b1c5d7e9f0
Create Date: 2026-05-05 22:47:00.000000+00:00

Chains after ENG-3 / D2's a3b1c5d7e9f0 (identity.source_link +
merge_event), which merged first.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "390b53c6f4a9"
down_revision: str | None = "a3b1c5d7e9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("person_uid", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=48), nullable=False),
        sa.Column("source_provider", sa.String(length=32), nullable=False),
        sa.Column("source_event_id", sa.UUID(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
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
        sa.Column("created_by_actor_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "kind IN ('lead_created', 'lead_updated', 'consultation_created', "
            "'consultation_rescheduled', 'consultation_cancelled')",
            name=op.f("ck_event_kind"),
        ),
        sa.CheckConstraint(
            "source_provider IN ('salesforce', 'carestack')",
            name=op.f("ck_event_source_provider"),
        ),
        sa.ForeignKeyConstraint(
            ["person_uid"],
            ["identity.person.id"],
            name=op.f("fk_event_person_uid_person"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_event_id"],
            ["ingest.raw_event.id"],
            name=op.f("fk_event_source_event_id_raw_event"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_actor_id"],
            ["actor.actor.id"],
            name=op.f("fk_event_created_by_actor_id_actor"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event")),
        schema="interaction",
    )
    op.create_index(
        "ix_event_person_occurred",
        "event",
        ["person_uid", "occurred_at"],
        schema="interaction",
    )
    op.create_index(
        "uq_event_source",
        "event",
        ["source_provider", "source_event_id"],
        unique=True,
        schema="interaction",
        postgresql_where=sa.text("source_event_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_event_source", table_name="event", schema="interaction")
    op.drop_index("ix_event_person_occurred", table_name="event", schema="interaction")
    op.drop_table("event", schema="interaction")
