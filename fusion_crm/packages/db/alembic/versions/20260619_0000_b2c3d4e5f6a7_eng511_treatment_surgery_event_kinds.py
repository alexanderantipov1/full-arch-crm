"""ENG-511: treatment-accepted + surgery stage event kinds

Adds the B1.3 stage-capture enums to ``interaction.event`` so the fact
builder can auto-resolve ``treatment_accepted_date`` /
``surgery_scheduled_date`` / ``surgery_completed_date``:

- ``interaction.event.kind``: + ``treatment_accepted`` (CareStack
  TreatmentPlan ``StatusId=3``), ``surgery_scheduled`` (implant-surgery
  treatment procedure ``statusId=2``), ``surgery_completed`` (implant-surgery
  treatment procedure ``statusId=8``).
- ``interaction.event.source_kind``: + ``carestack_treatment_plan`` (the new
  per-patient TreatmentPlan ingest that emits ``treatment_accepted``).

Pure CHECK-constraint widening — no data movement; downgrade restores the
previous lists (and would fail if rows with the new values exist, which is the
correct guard against silently orphaning them).

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-19 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OLD_EVENT_KINDS = (
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
    "opportunity_stage_changed",
    "contact_created",
    "payment_recorded",
    "payment_refunded",
    "payment_reversed",
    "payment_applied",
)
_NEW_EVENT_KINDS = _OLD_EVENT_KINDS + (
    "treatment_accepted",
    "surgery_scheduled",
    "surgery_completed",
)

_OLD_EVENT_SOURCE_KINDS = (
    "salesforce_lead",
    "salesforce_event",
    "salesforce_task",
    "salesforce_opportunity",
    "salesforce_case",
    "salesforce_contact",
    "salesforce_account",
    "salesforce_opportunity_history",
    "carestack_appointment",
    "carestack_patient",
    "carestack_treatment_procedure",
    "carestack_invoice",
    "carestack_accounting_transaction",
)
_NEW_EVENT_SOURCE_KINDS = _OLD_EVENT_SOURCE_KINDS + ("carestack_treatment_plan",)


def _values_sql(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.drop_constraint("ck_event_kind", "event", schema="interaction")
    op.create_check_constraint(
        "kind",
        "event",
        f"kind IN ({_values_sql(_NEW_EVENT_KINDS)})",
        schema="interaction",
    )
    op.drop_constraint("ck_event_source_kind", "event", schema="interaction")
    op.create_check_constraint(
        "source_kind",
        "event",
        f"source_kind IS NULL OR source_kind IN ({_values_sql(_NEW_EVENT_SOURCE_KINDS)})",
        schema="interaction",
    )


def downgrade() -> None:
    op.drop_constraint("ck_event_kind", "event", schema="interaction")
    op.create_check_constraint(
        "kind",
        "event",
        f"kind IN ({_values_sql(_OLD_EVENT_KINDS)})",
        schema="interaction",
    )
    op.drop_constraint("ck_event_source_kind", "event", schema="interaction")
    op.create_check_constraint(
        "source_kind",
        "event",
        f"source_kind IS NULL OR source_kind IN ({_values_sql(_OLD_EVENT_SOURCE_KINDS)})",
        schema="interaction",
    )
