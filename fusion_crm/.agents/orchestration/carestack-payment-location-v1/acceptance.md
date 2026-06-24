# Acceptance — ENG-267

- [ ] Payment events (`CareStackAccountingTransactionIngestService`) and treatment
      events (`CareStackTreatmentIngestService`) resolve `row["locationId"]` →
      tenant.location UUID via `TenantService.find_by_carestack_id` and store
      `location_id` (string UUID) in the safe event payload. Unmapped/missing CS
      location → omit `location_id`, event still emits.
- [ ] `interaction.get_treatment_payment_aggregate` gains optional
      `location_id: UUID | None`; when set, filters events by
      `Event.payload["location_id"].astext == str(location_id)` alongside the
      existing window/provider filters.
- [ ] PM dashboard endpoint passes its `location_id` into the aggregate, so
      Collected / Presented / Completed / Payments / payment_event_count
      recalculate when location changes.
- [ ] Outstanding / AR-risk stay tenant-wide (payment_summary has no location);
      widget labels them as not location-scoped (small hint), no false precision.
- [ ] No new schema/migration (payload-based). No PHI in events/logs/response.
      Cross-domain rules respected (ingest → tenant via service).
- [ ] Full verify green: `make lint`, `mypy .`, `make test`,
      `cd packages/db && alembic check` (no drift).
- [ ] Tests: location resolved+stored (mapped / unmapped / missing), aggregate
      filters by location (in/out), dashboard passes location through, no-PHI.
- [ ] Report at `reports/ENG-267-worker-report.md`.
