"""Backfill ``interaction.event.payload.location_id`` from ``ingest.raw_event``.

ENG-270. ENG-269 dedup kept the earliest row per
``(tenant_id, source_provider, source_kind, source_external_id, kind)``;
those earliest rows predate the ENG-267/268 location emit feature, so
zero existing invoice / payment / treatment events carry
``payload.location_id``. Every dashboard location filter currently
returns zero. Because the runtime emit is idempotent (ENG-269), a
re-pull does not regain the missing location — only a one-time
data-only migration can.

``upgrade()`` runs a single server-side UPDATE against
``interaction.event``: for billing / treatment kinds that lack
``payload.location_id``, join the linked ``ingest.raw_event`` and
resolve its CareStack ``locationId`` (verbatim from the provider row)
to the tenant's ``tenant.location.id`` via
``external_ref->>'carestack_location_id'``. ``jsonb_set`` writes the
resolved location UUID (as a string, matching the runtime emit shape
in ``carestack_invoice_service`` / ``carestack_accounting_transaction_service``
/ ``carestack_treatment_service``).

Guards on the UPDATE:

- ``e.kind IN (...)`` restricts the touch set to the six
  location-bearing CareStack kinds that ENG-267/268 enriched.
- ``NOT (e.payload ? 'location_id')`` makes the UPDATE naturally
  idempotent: rows that already carry ``location_id`` (newly emitted
  ones, or ones backfilled by a previous run) are skipped. Re-running
  the migration changes zero rows.
- ``r.payload ? 'locationId' AND r.payload->>'locationId' IS NOT NULL``
  skips raw_events that never carried a locationId (e.g. SF-sourced
  raws or older CareStack pulls that pre-dated the field). Those events
  stay as-is.
- ``l.tenant_id = e.tenant_id`` enforces same-tenant resolution. The
  ``(tenant_id, external_ref->>'carestack_location_id')`` partial
  unique on ``tenant.location`` (``uq_location_tenant_id_carestack_id``)
  guarantees at most one matching location per CareStack id per
  tenant, so the UPDATE never fans out.
- ``r.tenant_id = e.tenant_id`` is defence-in-depth: raw_event ids are
  UUIDs so cross-tenant collision is theoretically impossible, but the
  predicate also lets PostgreSQL use the per-tenant indexes on both
  sides.

Rows that have no mappable locationId — either because the raw payload
lacks one OR because the operator has not imported the CareStack
location yet — are intentionally left untouched. This matches the
runtime behaviour: ``CareStackInvoiceIngestService._resolve_location_uid``
returns ``None`` in both cases and the event emits without
``location_id``. The backfill stays consistent with that contract.

``downgrade()`` is a no-op. After the UPDATE we cannot tell a
backfilled ``location_id`` from one that the runtime emitted with the
event, so we cannot strip them on downgrade without corrupting newly
emitted rows. A future operator who needs the pre-backfill shape can
replay from ``ingest.raw_event`` (the forensic record is intact). The
docstring records this so downgrade reviewers are not surprised.

The UPDATE is a migration-level append-only exception (recorded in the
mission decision log), same precedent as the ENG-269 DELETE: the
runtime ``InteractionService`` stays append-only and exposes no
``update_event`` method.

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-05-30 07:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "a5b6c7d8e9f0"
down_revision: str | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Single server-side UPDATE. Exposed as a module-level constant so the
# integration test can import and execute the same SQL against the test
# database without re-running the full alembic upgrade.
BACKFILL_SQL = """
UPDATE interaction.event AS e
SET payload = jsonb_set(e.payload, '{location_id}', to_jsonb(l.id::text))
FROM ingest.raw_event AS r
JOIN tenant.location AS l
  ON l.tenant_id = r.tenant_id
 AND l.external_ref->>'carestack_location_id' = r.payload->>'locationId'
WHERE e.source_event_id = r.id
  AND r.tenant_id = e.tenant_id
  AND e.kind IN (
        'invoice_created',
        'payment_recorded',
        'payment_refunded',
        'payment_reversed',
        'treatment_proposed',
        'treatment_completed'
      )
  AND NOT (e.payload ? 'location_id')
  AND r.payload ? 'locationId'
  AND r.payload->>'locationId' IS NOT NULL;
"""


def upgrade() -> None:
    op.execute(BACKFILL_SQL)


def downgrade() -> None:
    # Intentional no-op. The UPDATE is irreversible without forensic
    # replay because backfilled location_id values are indistinguishable
    # from runtime-emitted ones; stripping them on downgrade would
    # corrupt rows that the runtime correctly enriched. See module
    # docstring for the replay path via ingest.raw_event.
    pass
