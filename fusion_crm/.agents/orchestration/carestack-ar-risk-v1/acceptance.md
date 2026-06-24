# Acceptance — ENG-266 (AR-risk count)

- [ ] Ingest read counts at-risk patients: latest `carestack.payment_summary.snapshot`
      per patient where `balanceDuePatient` > threshold (module constant, documented).
      Tenant-scoped; latest snapshot per patient only (reuse the MAX(received_at)
      per external_id pattern from `sum_latest_payment_summary_balances`).
- [ ] `ar_risk_count` populated in the PM dashboard endpoint (only when provider
      filter is `None`/`carestack`, matching the existing outstanding logic).
      No longer hard-`None`.
- [ ] Frontend treatment/payments widget shows the AR-risk count; Zod schema +
      MSW fixture stay in sync.
- [ ] No new CareStack call, no new schema/migration. No PHI in the response
      (count + threshold only). Cross-domain rules respected.
- [ ] Full verify green: `make lint`, `mypy .`, `make test`,
      `cd packages/db && alembic check` (no drift).
- [ ] Tests: above/below threshold counting, latest-snapshot-per-patient,
      tenant scoping, dashboard wiring, no-PHI.
- [ ] Worker report at `reports/ENG-266-worker-report.md` (incl. chosen threshold).
