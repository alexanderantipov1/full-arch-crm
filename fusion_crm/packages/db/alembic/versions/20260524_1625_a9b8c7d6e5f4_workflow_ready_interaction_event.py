"""ENG-236: workflow-ready interaction.event contract.

Revision ID: a9b8c7d6e5f4
Revises: f3a4b5c6d7e8
Create Date: 2026-05-24 16:25:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9b8c7d6e5f4"
down_revision: str | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EVENT_KINDS = (
    "lead_created",
    "lead_updated",
    "consultation_scheduled",
    "consultation_created",
    "consultation_rescheduled",
    "consultation_cancelled",
    "consultation_completed",
    "consultation_no_show",
    "task_created",
    "task_completed",
    "call_logged",
    "call_reference_found",
)
LEGACY_EVENT_KINDS = (
    "lead_created",
    "lead_updated",
    "consultation_created",
    "consultation_rescheduled",
    "consultation_cancelled",
)
DATA_CLASSES = (
    "public",
    "operational",
    "clinical_summary",
    "phi_protected",
    "call_recording_ref",
)
SOURCE_KINDS = (
    "salesforce_lead",
    "salesforce_event",
    "salesforce_task",
    "carestack_appointment",
    "carestack_patient",
)
PROJECTION_REF_TYPES = (
    "ops_lead",
    "ops_consultation",
    "ops_followup_task",
)
REVIEW_STATUSES = (
    "auto",
    "pending_review",
    "reviewed",
    "rejected",
)


def _sql_in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.add_column(
        "event",
        sa.Column(
            "data_class",
            sa.String(length=32),
            server_default="operational",
            nullable=False,
        ),
        schema="interaction",
    )
    op.add_column(
        "event",
        sa.Column("source_kind", sa.String(length=64), nullable=True),
        schema="interaction",
    )
    op.add_column(
        "event",
        sa.Column("source_external_id", sa.String(length=240), nullable=True),
        schema="interaction",
    )
    op.add_column(
        "event",
        sa.Column("projection_ref_type", sa.String(length=64), nullable=True),
        schema="interaction",
    )
    op.add_column(
        "event",
        sa.Column("projection_ref_id", sa.UUID(), nullable=True),
        schema="interaction",
    )
    op.add_column(
        "event",
        sa.Column(
            "review_status",
            sa.String(length=32),
            server_default="auto",
            nullable=False,
        ),
        schema="interaction",
    )
    op.alter_column(
        "event",
        "data_class",
        existing_type=sa.String(length=32),
        existing_nullable=False,
        server_default=None,
        schema="interaction",
    )
    op.alter_column(
        "event",
        "review_status",
        existing_type=sa.String(length=32),
        existing_nullable=False,
        server_default=None,
        schema="interaction",
    )

    op.drop_constraint(
        op.f("ck_event_kind"),
        "event",
        schema="interaction",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_event_kind"),
        "event",
        f"kind IN ({_sql_in(EVENT_KINDS)})",
        schema="interaction",
    )
    op.create_check_constraint(
        op.f("ck_event_data_class"),
        "event",
        f"data_class IN ({_sql_in(DATA_CLASSES)})",
        schema="interaction",
    )
    op.create_check_constraint(
        op.f("ck_event_source_kind"),
        "event",
        f"source_kind IS NULL OR source_kind IN ({_sql_in(SOURCE_KINDS)})",
        schema="interaction",
    )
    op.create_check_constraint(
        op.f("ck_event_projection_ref_type"),
        "event",
        (
            "projection_ref_type IS NULL OR projection_ref_type IN "
            f"({_sql_in(PROJECTION_REF_TYPES)})"
        ),
        schema="interaction",
    )
    op.create_check_constraint(
        op.f("ck_event_review_status"),
        "event",
        f"review_status IN ({_sql_in(REVIEW_STATUSES)})",
        schema="interaction",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_event_review_status"),
        "event",
        schema="interaction",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_event_projection_ref_type"),
        "event",
        schema="interaction",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_event_source_kind"),
        "event",
        schema="interaction",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_event_data_class"),
        "event",
        schema="interaction",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_event_kind"),
        "event",
        schema="interaction",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_event_kind"),
        "event",
        f"kind IN ({_sql_in(LEGACY_EVENT_KINDS)})",
        schema="interaction",
    )
    op.drop_column("event", "review_status", schema="interaction")
    op.drop_column("event", "projection_ref_id", schema="interaction")
    op.drop_column("event", "projection_ref_type", schema="interaction")
    op.drop_column("event", "source_external_id", schema="interaction")
    op.drop_column("event", "source_kind", schema="interaction")
    op.drop_column("event", "data_class", schema="interaction")
