# Acceptance — ENG-268

- [ ] `CareStackInvoiceIngestService._capture_invoice` resolves the invoice row's
      `locationId` → tenant.location UUID via `LocationService.find_by_carestack_id`
      and stores `location_id` (str UUID) in the safe event payload. Missing /
      unmapped `locationId` → omit `location_id`, event still emits.
- [ ] No aggregate/dashboard change (ENG-267 already filters `invoice_created` by
      location). Confirm Invoices + Payments recalc per location after a re-pull.
- [ ] No new schema/migration. No PHI in events/logs/response. Cross-domain rules
      respected (ingest → tenant via service).
- [ ] Full verify green: `make lint`, `mypy .`, `make test`,
      `cd packages/db && alembic check`.
- [ ] Tests: invoice event location_id mapped / unmapped / missing, no-PHI.
- [ ] Report at `reports/ENG-268-worker-report.md`.
