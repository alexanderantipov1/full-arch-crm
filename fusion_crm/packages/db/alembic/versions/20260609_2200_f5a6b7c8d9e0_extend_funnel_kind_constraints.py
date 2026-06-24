"""extend funnel kind constraints (ENG-382)

Adds the SF funnel segments to the value-checked enums:

- ``interaction.event.kind``: + ``opportunity_stage_changed``,
  ``contact_created``.
- ``interaction.event.source_kind``: + ``salesforce_contact``,
  ``salesforce_account``, ``salesforce_opportunity_history``.
- ``identity.source_link.source_kind``: + ``account``.

Pure CHECK-constraint widening — no data movement; downgrade restores
the previous lists (and would fail if rows with the new values exist,
which is the correct guard against silently orphaning them).

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-06-09 22:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5a6b7c8d9e0"
down_revision: str | Sequence[str] | None = "e4f5a6b7c8d9"
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
    "payment_recorded",
    "payment_refunded",
    "payment_reversed",
    "payment_applied",
)
_NEW_EVENT_KINDS = _OLD_EVENT_KINDS + (
    "opportunity_stage_changed",
    "contact_created",
)

_OLD_EVENT_SOURCE_KINDS = (
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
_NEW_EVENT_SOURCE_KINDS = _OLD_EVENT_SOURCE_KINDS + (
    "salesforce_contact",
    "salesforce_account",
    "salesforce_opportunity_history",
)

_OLD_LINK_SOURCE_KINDS = (
    "lead",
    "contact",
    "patient",
    "caller",
    "sms_sender",
    "submitter",
)
_NEW_LINK_SOURCE_KINDS = _OLD_LINK_SOURCE_KINDS + ("account",)


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
    op.drop_constraint(
        "ck_source_link_source_kind", "source_link", schema="identity"
    )
    op.create_check_constraint(
        "source_kind",
        "source_link",
        f"source_kind IN ({_values_sql(_NEW_LINK_SOURCE_KINDS)})",
        schema="identity",
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
    op.drop_constraint(
        "ck_source_link_source_kind", "source_link", schema="identity"
    )
    op.create_check_constraint(
        "source_kind",
        "source_link",
        f"source_kind IN ({_values_sql(_OLD_LINK_SOURCE_KINDS)})",
        schema="identity",
    )
