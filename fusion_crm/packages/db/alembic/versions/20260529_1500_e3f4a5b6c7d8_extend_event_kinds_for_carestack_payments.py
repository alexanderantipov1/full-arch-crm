"""Extend interaction.event CHECK constraints for CareStack payments.

Adds new allowed values to the ``kind`` and ``source_kind`` CHECK
constraints on ``interaction.event``:

- EVENT_KINDS: +payment_recorded, +payment_refunded, +payment_reversed
- SOURCE_KINDS: +carestack_accounting_transaction

``data_class="billing"`` is already allowed (added in
``c1d2e3f4a5b6``). No column additions or data changes — pure
constraint widening.

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-05-29 15:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: str | None = "d2e3f4a5b6c7"
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
    "payment_recorded",
    "payment_refunded",
    "payment_reversed",
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
    "carestack_accounting_transaction",
)

# Previous values (for downgrade) — match the tuples shipped in c1d2e3f4a5b6.
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
    "treatment_proposed",
    "treatment_completed",
    "invoice_created",
    "case_opened",
    "case_closed",
    "opportunity_created",
    "opportunity_won",
    "opportunity_lost",
)
PREV_SOURCE_KINDS = (
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


def _sql_in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
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
