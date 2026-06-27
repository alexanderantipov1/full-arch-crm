# Contract — carestack-payments-backfill-v1

- `POST /backfill/run` gains scope options `carestack_accounting_transactions` and
  `carestack_payment_summary`, with a `since` (default 2026-01-01), throttle, and
  backoff. Drives the existing ingest services with unbounded resumable pagination.
- Returns counts + a resume continueToken; idempotent; sync_run journaled.
- No schema/migration/frontend. The real run is operator-triggered (Orchestrator),
  not automatic.
