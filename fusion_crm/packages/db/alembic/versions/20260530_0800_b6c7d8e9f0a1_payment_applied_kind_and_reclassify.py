"""Classify CareStack payments by transactionCode — add payment_applied kind
and reclassify existing payment_recorded events (ENG-283).

CareStack's accounting-transactions feed is a double-entry ledger: every
real payment (``transactionCode`` ``PATIENTPAYMENTS`` /
``INSURANCEPAYMENTS``) is paired with an allocation entry
(``PATPAYMENTAPPLIED`` / ``INSPAYMENTAPPLIED``) when that money is
applied onto an invoice. The original ENG-257 emit classified rows by
``folioType=PATIENTCREDIT``, which catches BOTH legs and inflated the
Project Manager Payments page Collected total by ~3.3x (locally
$38,178 vs the real $11,698).

This revision does two things:

1. Extend the ``interaction.event`` ``ck_event_kind`` CHECK constraint
   to include the new ``payment_applied`` kind. The Python ``EVENT_KINDS``
   tuple, ``EventKind`` Literal, ``_KIND_VERB`` map, and interaction
   ``CLAUDE.md`` kinds table are updated in the same commit so the four
   sources of truth move together (see ``packages/interaction/CLAUDE.md``
   "Adding a new value" rule).

2. Reclassify already-emitted rows by reading the verbatim
   ``transactionCode`` off the linked ``ingest.raw_event``:

   * ``PATPAYMENTAPPLIED`` / ``INSPAYMENTAPPLIED`` →
     ``kind='payment_applied'``.
   * ``PATIENTPAYMENTSDELETE`` → ``kind='payment_reversed'``.
   * ``PATIENTPAYMENTS`` / ``INSURANCEPAYMENTS`` stay as
     ``payment_recorded``.

   The UPDATE is naturally idempotent — guarded on the current
   ``kind`` AND the source transactionCode — so re-running the
   migration changes zero rows. The ENG-269 cross-pull partial UNIQUE
   keys on ``(tenant_id, source_provider, source_kind,
   source_external_id, kind)``; flipping ``kind`` for a row that
   shares ``source_external_id`` with another row of a different kind
   cannot collide (kind is part of the key). For the ENG-283 problem
   set there is exactly one event per CareStack accounting-transaction
   id, so the UPDATE never has to choose between competing kinds.

   The UPDATE is a migration-level append-only exception — the runtime
   ``InteractionService`` stays append-only and exposes no
   ``update_event`` method. The decision is logged in
   ``.agents/orchestration/carestack-payment-classification-v1/decision-log.md``
   (same precedent as ENG-269's dedup DELETE and ENG-270's location
   backfill UPDATE).

``downgrade()`` reverses the CHECK constraint widening (drops
``payment_applied`` from the allowed values) and, before doing so,
flips any ``payment_applied`` rows back to ``payment_recorded`` so the
narrower CHECK does not reject existing data. The CHECK narrows after
the data UPDATE so the constraint never sees a forbidden value. The
reclassification of ``PATIENTPAYMENTSDELETE`` → ``payment_reversed`` is
NOT undone on downgrade because the pre-ENG-283 mapping for that code
was also ``payment_reversed`` via the ``isReversed`` heuristic on the
deleted row; reverting it would re-introduce a known-wrong
classification.

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-05-30 08:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b6c7d8e9f0a1"
down_revision: str | None = "a5b6c7d8e9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# New full tuple — must match packages/interaction/models.py EVENT_KINDS.
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
    "payment_applied",
)

# Previous tuple (for downgrade) — matches what e3f4a5b6c7d8 shipped.
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
    "payment_recorded",
    "payment_refunded",
    "payment_reversed",
)


# Exposed as module-level constants so an integration test can re-execute
# the same SQL against a test database without re-running alembic.
RECLASSIFY_APPLIED_SQL = """
UPDATE interaction.event AS e
SET kind = 'payment_applied'
FROM ingest.raw_event AS r
WHERE e.source_event_id = r.id
  AND r.tenant_id = e.tenant_id
  AND e.kind = 'payment_recorded'
  AND e.source_kind = 'carestack_accounting_transaction'
  AND upper(r.payload->>'transactionCode') IN (
        'PATPAYMENTAPPLIED',
        'INSPAYMENTAPPLIED'
      );
"""

RECLASSIFY_DELETE_SQL = """
UPDATE interaction.event AS e
SET kind = 'payment_reversed'
FROM ingest.raw_event AS r
WHERE e.source_event_id = r.id
  AND r.tenant_id = e.tenant_id
  AND e.kind = 'payment_recorded'
  AND e.source_kind = 'carestack_accounting_transaction'
  AND upper(r.payload->>'transactionCode') = 'PATIENTPAYMENTSDELETE';
"""

DOWNGRADE_APPLIED_TO_RECORDED_SQL = """
UPDATE interaction.event
SET kind = 'payment_recorded'
WHERE kind = 'payment_applied';
"""


def _sql_in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    # 1. Widen the CHECK so the new kind is accepted before any UPDATE
    #    can need to write it.
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

    # 2. Reclassify existing rows. Both UPDATEs are guarded so a re-run
    #    touches zero rows (current kind already matches the target, so
    #    the WHERE no longer selects them).
    op.execute(RECLASSIFY_APPLIED_SQL)
    op.execute(RECLASSIFY_DELETE_SQL)


def downgrade() -> None:
    # Flip any payment_applied rows back to payment_recorded so the
    # narrower CHECK does not reject them. PATIENTPAYMENTSDELETE rows
    # stay as payment_reversed — the pre-ENG-283 emitter would have
    # produced the same kind via the isReversed heuristic, so there is
    # no correct earlier value to restore.
    op.execute(DOWNGRADE_APPLIED_TO_RECORDED_SQL)

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
