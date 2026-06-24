You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: ENG-284
(https://linear.app/fusion-dental-implants/issue/ENG-284). Isolated git worktree.
Implement → verify → write a report. Do NOT touch `main`, do NOT push, do NOT open
a PR. Commit to YOUR worktree branch only once green; the Orchestrator integrates.

## Problem (ENG-283 follow-up — Collected went NEGATIVE)
ENG-283's `isReversed` override applied to ALL transactionCodes, so reversed
CHARGES (PROCEDURECOMPLETED) and ADJUSTMENTS (PATIENTADJUSTMENT) became
`payment_reversed`. With `collected = recorded − refunded − reversed`, that
subtracted ~$110k of reversed non-payments → Collected = −$71,934.

## Fix — STRICT payment-code allowlist
A payment event exists ONLY for these transactionCodes (everything else → NO
event, even isReversed=true):
- `PATIENTPAYMENTS`, `INSURANCEPAYMENTS` → `payment_recorded`
- `PATPAYMENTAPPLIED`, `INSPAYMENTAPPLIED` → `payment_applied`
- `PATIENTPAYMENTSDELETE` → `payment_reversed`; explicit refund codes (containing
  `REFUND`) → `payment_refunded`
- `isReversed=true` reclassifies to `payment_reversed` ONLY when the code is
  already a payment code. It NEVER promotes a non-payment code to a payment event.

## Read first
- `packages/ingest/carestack_accounting_transaction_service.py` — the ENG-283
  `_PAYMENT_CODE_TO_KIND` map + isReversed handling. Make it a strict allowlist;
  non-payment code (or missing code) → return None (no event), BEFORE the
  isReversed check.
- The ENG-283 migration `…b6c7d8e9f0a1…` and the ENG-270 backfill migration for
  the data-fix pattern (op.execute UPDATE/DELETE, working downgrade docstring).

## Task

### A. Emission — strict allowlist
Refactor classification: look up transactionCode in the payment allowlist; if not
present → no event (even if isReversed). isReversed override applies only inside
the payment set (a reversed PATIENTPAYMENTS → payment_reversed).

### B. Corrective migration (new revision, down_revision = current head)
`upgrade()` two server-side statements over `interaction.event` joined to
`ingest.raw_event` (via source_event_id), for kinds in (payment_recorded,
payment_applied, payment_refunded, payment_reversed):
1. DELETE events whose `raw.payload->>'transactionCode'` is NOT a payment code
   (PROCEDURECOMPLETED, PATIENTADJUSTMENT, FEEUPDATION, NULL, anything not in the
   allowlist) — these are spurious.
2. UPDATE the remaining payment events' `kind` to the correct mapped kind for
   their code (fixes ENG-283 mislabels and the local re-pollution where
   PATPAYMENTAPPLIED landed in payment_recorded). Respect isReversed for the
   reversed mapping.
Idempotent (re-run = 0 changes). `downgrade()` no-op (documented — cannot restore
deleted rows). Append-only exception (decision-log).

### C. Aggregate
No formula change — `collected_total = sum(payment_recorded) − sum(payment_refunded
+ payment_reversed)` is correct once reversed/refunded hold only real payment
reversals/refunds. Just confirm with a test.

## Hard constraints
- Read-only CareStack. No new table. Migration immutable: new revision, working
  downgrade. No PHI. `except Exception` only. English only.

## Definition of done
1. `make lint` ; `mypy .` ; `make test` ; `cd packages/db && alembic check` green;
   round-trip (upgrade→downgrade -1→upgrade).
2. `cd apps/web && npm run lint && npx tsc --noEmit && npm run test` green.
3. After local upgrade: NO payment-kind event has a non-payment transactionCode;
   `payment_reversed` holds only real payment reversals; the dashboard aggregate
   `collected_total` is POSITIVE (~$11,538). Record before/after in the report.
4. Commit to your worktree branch only once green.
5. Write `.agents/orchestration/carestack-payment-strict-classify-v1/reports/ENG-284-worker-report.md`
   (allowlist, migration SQL, rows deleted/reclassified, collected before/after,
   tests, round-trip, risks, do-not-merge).
6. If a code's payment-status is ambiguous, treat it as NON-payment (no event) and
   list it in the report; if blocked, write `Needs decision:`.

## Tests
- isReversed=true on PROCEDURECOMPLETED → no event.
- isReversed=true on PATIENTPAYMENTS → payment_reversed.
- PATPAYMENTAPPLIED → payment_applied (not recorded).
- Corrective migration deletes a spurious (non-payment) payment event and
  reclassifies a mislabeled one; re-run = 0.
- Aggregate collected_total positive with a seeded mix.
