# Acceptance — ENG-270

- [ ] New Alembic revision (down_revision = current head `f4a5b6c7d8e9`). `upgrade()`
      server-side UPDATE: for `interaction.event` rows of kind in
      (invoice_created, payment_recorded, payment_refunded, payment_reversed,
      treatment_proposed, treatment_completed) lacking `payload.location_id`, join
      `ingest.raw_event` on `source_event_id`, resolve `raw.payload->>'locationId'`
      → `tenant.location.id` (via `external_ref->>'carestack_location_id'`, same
      tenant), set `payload = jsonb_set(payload,'{location_id}', to_jsonb(uuid::text))`.
- [ ] Only rows with a mappable location are touched; unmapped/locationless rows
      unchanged. Re-run is a no-op. `downgrade()` no-op (documented).
- [ ] No new schema; `alembic check` clean. No PHI.
- [ ] Full verify green: `make lint`, `mypy .`, `make test`,
      `cd packages/db && alembic check`; migration round-trip.
- [ ] After local upgrade: invoice/payment/treatment events with a mappable CS
      locationId now carry `payload.location_id` (with_location > 0); a wide-window
      dashboard query with a location filter returns non-zero for a billing location.
- [ ] Report at `reports/ENG-270-worker-report.md` (rows updated count per kind).
