# ENG-384 Worker Report — Extend ingest change-guard

- **Task:** ENG-384 — Extend ingest change-guard to carestack
  accounting_transaction + invoice pullers
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-384/extend-ingest-change-guard-to-carestack-accounting-transaction-invoice
- **Role / agent:** worker / claude-code (self-execute)
- **Branch / worktree:** codex/eng-371-manager-answer-layer-v1 / canonical checkout
- **Allowed scope:** packages/ingest, apps/worker/jobs, tests/ingest,
  tests/worker, tests/infra, infra/scripts (per ownership.yaml)

## What changed

Pullers (capture change-guard, mirrors the ENG-381 pattern):

- `packages/ingest/carestack_accounting_transaction_service.py` —
  added `_latest_captured_keys` that batches the composed
  `(id:lastUpdatedOn)` external_ids over `IngestService.latest_payload_values`
  and the per-row guard in both `import_recent_accounting_transactions`
  and `pull_all_since`. Rows whose composed external_id already has a
  captured `lastUpdatedOn` are counted as `unchanged` and skipped before
  raw write / patient resolution / payment-event emit. Rows without a
  `lastUpdatedOn` fall through to capture (bare-id fallback path is
  intentionally unguarded so a stamp-less row is captured at least once,
  matching the spec contract).
- `packages/ingest/carestack_invoice_service.py` — added
  `_latest_captured_stamps` (appointment-style, since invoice keeps the
  bare invoice_id as raw_event.external_id) and the per-row guard in
  both `import_recent_invoices` and `pull_all_since`. Same `unchanged`
  bucket on match.

Cleanup script: no edit required.
`infra/scripts/cleanup_raw_event_duplicates.py` already lists both
event types with `lastUpdatedOn` as the stamp key in
`DEFAULT_EVENT_TYPE_STAMP_KEYS`.

Tests:

- `tests/ingest/test_carestack_accounting_transaction_service.py` —
  fixture `spec=` extended with `latest_payload_values`; defaults to an
  empty captured map so existing tests keep passing. New unit tests:
  - guard skips a row whose composed (id, lastUpdatedOn) already
    matches captured stamp;
  - guard captures a row when the upstream stamp moved;
  - guard falls through when the row has no `lastUpdatedOn`;
  - `pull_all_since` honors the same guard.
- `tests/ingest/test_carestack_invoice_service.py` — same shape for
  invoice (bare external_id, payload-key comparison).
- `tests/ingest/test_ingest_idempotency_sql.py` — extended with four
  real-PG tests (under the `tenant schema` skip guard): double-import
  of an unchanged row writes raw_event ONCE; a moved `lastUpdatedOn`
  writes a second raw row. Covers both feeds. Stub clients are local
  classes so the SQL test does not touch the integrations package.

## Tests run

- `make lint` → ✓ (ruff: All checks passed!)
- `mypy .` → ✓ (Success: no issues found in 365 source files)
- `pytest` (full suite) → ✓ (1455 passed in 157 s)
- `alembic check` → ✓ (No new upgrade operations detected — no
  migrations introduced this task, as expected)
- Targeted: `pytest tests/ingest/test_carestack_*_service.py` → 96/96 ✓
- Targeted: `pytest tests/ingest/test_ingest_idempotency_sql.py` → 7/7 ✓

## Verification status

PASSED.

## Cleanup script dry-run (local DB)

`infra/scripts/cleanup_raw_event_duplicates.py --event-type
carestack.accounting_transaction.upsert --event-type
carestack.invoice.upsert`:

```
would delete (dry-run): 3392 duplicate raw_event rows
  carestack.accounting_transaction.upsert: 3266
  carestack.invoice.upsert: 126
```

`--apply` NOT executed — the orchestrator runs the final apply after
integration per task constraint. These rows are the accumulated
overlap-tick duplicates between the previous ENG-381 cleanup and this
guard landing; with the guard active the pullers stop producing new
duplicates immediately.

## Risks

- The guard skips downstream resolution AND emit for matched rows.
  This is the same trade-off the appointment/payment-summary guards
  already made: unresolved patient links DO NOT self-heal mid-tick on
  unchanged rows. They self-heal on the next stamp move, or on a
  patient-side pull. Acceptable: the cross-pull
  `create_event_idempotent` was already a no-op on those rows.
- Accounting_transaction's composed external_id encodes the stamp, so
  the guard probes by composed key — presence is the unchanged signal.
  A row first captured under the bare-id fallback (no stamp present
  upstream) is NOT guarded on subsequent runs even if the stamp later
  appears; this matches the existing payment-summary handling of
  stamp-less rows and the bare-id fallback used by other feeds.
- The local arq worker / CareStack scheduled job was NOT running
  during this work; the new guard activates on the next worker start.
  Prod jobs (`fusion-job-cs-pull`) pick it up on next deploy.

## Blockers / questions

None.

## Suggested next task

Orchestrator runs `cleanup_raw_event_duplicates.py --apply` over the
two event types to drop the 3,392 accumulated duplicates after this
change merges. ENG-381's follow-ups still cover the remaining
lead/patient FK-pinned duplicates if/when needed.

## Do-not-merge conditions

- Do not merge together with the parallel Codex working-tree changes
  in `apps/web/` and `packages/agent_runtime/` (separate ownership in
  this checkout). Commit-by-path on this branch keeps the cuts
  separated, but the integrator should still verify before any merge.
