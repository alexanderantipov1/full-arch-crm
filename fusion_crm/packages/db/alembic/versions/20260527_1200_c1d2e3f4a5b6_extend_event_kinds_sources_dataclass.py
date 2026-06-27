"""Extend interaction.event CHECK constraints for treatment, invoice, case, opportunity.

Adds new allowed values to the ``kind``, ``source_kind``, and ``data_class``
CHECK constraints on ``interaction.event``:

- EVENT_KINDS: +treatment_proposed, +treatment_completed, +invoice_created,
  +case_opened, +case_closed, +opportunity_created, +opportunity_won,
  +opportunity_lost
- SOURCE_KINDS: +carestack_treatment_procedure, +carestack_invoice,
  +salesforce_opportunity, +salesforce_case
- DATA_CLASSES: +billing

No column additions or data changes — pure constraint widening.

Revision ID: c1d2e3f4a5b6
Revises: b8c9d0e1f2a3
Create Date: 2026-05-27 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# New full tuples — must match models.py exactly.
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
    "treatment_proposed",
    "treatment_completed",
    "invoice_created",
    "case_opened",
    "case_closed",
    "opportunity_created",
    "opportunity_won",
    "opportunity_lost",
)
DATA_CLASSES = (
    "public",
    "operational",
    "clinical_summary",
    "phi_protected",
    "billing",
    "call_recording_ref",
)
SOURCE_KINDS = (
    "salesforce_lead",
    "salesforce_event",
    "salesforce_task",
    "salesforce_opportunity",
    "salesforce_case",
    "carestack_appointment",
    "carestack_patient",
    "carestack_treatment_procedure",
    "carestack_invoice",
)

# Previous values (for downgrade).
PREV_EVENT_KINDS = (
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
PREV_DATA_CLASSES = (
    "public",
    "operational",
    "clinical_summary",
    "phi_protected",
    "call_recording_ref",
)
PREV_SOURCE_KINDS = (
    "salesforce_lead",
    "salesforce_event",
    "salesforce_task",
    "carestack_appointment",
    "carestack_patient",
)


def _sql_in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    # Drop old CHECK constraints and recreate with wider value sets.
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

    op.drop_constraint(
        op.f("ck_event_data_class"),
        "event",
        schema="interaction",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_event_data_class"),
        "event",
        f"data_class IN ({_sql_in(DATA_CLASSES)})",
        schema="interaction",
    )

    op.drop_constraint(
        op.f("ck_event_source_kind"),
        "event",
        schema="interaction",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_event_source_kind"),
        "event",
        f"source_kind IS NULL OR source_kind IN ({_sql_in(SOURCE_KINDS)})",
        schema="interaction",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_event_source_kind"),
        "event",
        schema="interaction",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_event_source_kind"),
        "event",
        f"source_kind IS NULL OR source_kind IN ({_sql_in(PREV_SOURCE_KINDS)})",
        schema="interaction",
    )

    op.drop_constraint(
        op.f("ck_event_data_class"),
        "event",
        schema="interaction",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_event_data_class"),
        "event",
        f"data_class IN ({_sql_in(PREV_DATA_CLASSES)})",
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
        f"kind IN ({_sql_in(PREV_EVENT_KINDS)})",
        schema="interaction",
    )
