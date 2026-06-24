# Acceptance — ENG-257 (billing ingest slice)

- [ ] CareStack client gains `list_accounting_transactions_modified_since(...)`
      (GET `/api/{version}/sync/accounting-transactions`, accepts `billing/`-prefixed
      next-page path) and `get_payment_summary(patient_id)`
      (GET `/api/{version}/billing/payment-summary/{patientId}`). GET only.
- [ ] `CareStackAccountingTransactionIngestService` captures verbatim rows to
      `ingest.raw_event` as `carestack.accounting_transaction.upsert`,
      idempotency `(id, lastUpdatedOn)`, resolves `patientId`→person via
      `source_link` (`source_instance="carestack-main"`), skips-but-captures
      rows with no `patientId`.
- [ ] Payment-summary capture writes `carestack.payment_summary.snapshot`;
      trigger choice (scheduled sweep vs on-demand) documented in the report.
- [ ] Accounting-transactions added to the scheduled CareStack fanout
      (`apps/worker/jobs/ingest_scheduled.py`, `_CS_OBJECT_SCOPE`), bounded pages.
- [ ] Tests in `tests/ingest/` mirror invoice/treatment: row extraction,
      patient-link skip path, idempotency, and NO PHI / clinical / patient
      identifiers in any emitted timeline summary.
- [ ] No new DB schema. No CareStack write path. No PHI in logs.
- [ ] Full verify loop green: `make lint`, `mypy .`, `make test`,
      `cd packages/db && alembic check`.
- [ ] Worker report written to `reports/ENG-257-worker-report.md` listing
      changed files, tests run, verification status, risks, and the
      payment-summary trigger decision.
