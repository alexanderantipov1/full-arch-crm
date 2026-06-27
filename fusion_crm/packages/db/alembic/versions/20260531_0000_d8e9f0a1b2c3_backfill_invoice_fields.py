"""Backfill ``payload.invoice_id`` onto payment events (ENG-303).

The PM Payments page now shows, per payment, the invoice it belongs to.
The join key is the CareStack ``invoiceId``, which lives verbatim in
``ingest.raw_event`` (the accounting-transaction rows) but was never copied
into the dashboard-safe ``interaction.event.payload``. We now store it as
``payload.invoice_id`` so a payment row can resolve its invoice's human
number + date (those are read at query time from the invoice raw rows, which
have far better coverage than the sparse ``invoice_created`` events).

The runtime emit (``carestack_accounting_transaction_service``) writes
``invoice_id`` going forward; this one-time, data-only migration backfills the
existing rows. The emit is idempotent (ENG-269) so a re-pull would NOT regain
it — only this migration can.

The UPDATE is idempotent: it only touches a row when the raw ``invoiceId`` is
present AND the event's current value differs, so a second run changes zero
rows.

``downgrade()`` is a no-op: after the backfill we cannot distinguish a
backfilled value from one the runtime emitted with the event, so stripping the
key would corrupt newly-emitted rows. The forensic record in
``ingest.raw_event`` stays intact for replay. Same precedent as the ENG-270
location backfill. The UPDATE is a migration-level append-only exception
(``InteractionService`` stays append-only at runtime).

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-05-31 00:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d8e9f0a1b2c3"
down_revision: str | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Payment events: copy the raw ``invoiceId`` to ``payload.invoice_id``.
BACKFILL_PAYMENT_INVOICE_ID_SQL = """
UPDATE interaction.event AS e
SET payload = jsonb_set(
    coalesce(e.payload, '{}'::jsonb),
    '{invoice_id}',
    to_jsonb(r.payload->>'invoiceId'),
    true
)
FROM ingest.raw_event AS r
WHERE e.source_event_id = r.id
  AND r.tenant_id = e.tenant_id
  AND e.kind IN (
        'payment_recorded',
        'payment_refunded',
        'payment_reversed',
        'payment_applied'
      )
  AND r.payload ? 'invoiceId'
  AND r.payload->>'invoiceId' IS NOT NULL
  AND (e.payload->>'invoice_id') IS DISTINCT FROM (r.payload->>'invoiceId');
"""


def upgrade() -> None:
    op.execute(BACKFILL_PAYMENT_INVOICE_ID_SQL)


def downgrade() -> None:
    # Intentional no-op. Backfilled invoice_id is indistinguishable from a
    # runtime-emitted one; stripping it would corrupt newly-emitted rows.
    # Replay from ingest.raw_event if the pre-backfill shape is ever needed.
    pass
