# Verification — ENG-257 (billing ingest slice)

Run the full repository verify loop before declaring done:

```bash
make lint
mypy .
make test
cd packages/db && alembic check
```

Focused checks:

- New `tests/ingest/` tests for accounting-transactions extraction, patient
  linkage skip, idempotency key `(id, lastUpdatedOn)`.
- Assert NO clinical codes, tooth numbers, or patient identifiers leak into
  emitted `interaction.event` summaries (billing data_class only).
- Confirm the CareStack client methods are GET-only (no write path added).
- A local scheduled/manual pull produces `carestack.accounting_transaction.upsert`
  rows in `ingest.raw_event` (document the count in the report).
- `alembic check` reports no drift (this slice adds no migration).
