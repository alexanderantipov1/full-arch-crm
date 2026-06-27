You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: ENG-283
(https://linear.app/fusion-dental-implants/issue/ENG-283). Isolated git worktree.
Implement → verify → write a report. Do NOT touch `main`, do NOT push, do NOT open
a PR. Commit to YOUR worktree branch only once green; the Orchestrator integrates.

## Problem
CareStack payment events are classified by `folioType` (PATIENTCREDIT), which
catches BOTH legs of double-entry: PATIENTPAYMENTS (credit = cash received) AND
PATPAYMENTAPPLIED (debit = that cash applied to an invoice). So Collected ~3.3x
too high ($38,178 vs real ~$11,698). Classify by `transactionCode` instead.

## Verified transactionCode → meaning (from live data)
- PATIENTPAYMENTS (credit) / INSURANCEPAYMENTS (credit) = REAL cash received.
- PATPAYMENTAPPLIED / INSPAYMENTAPPLIED = allocation of received money to invoices (NOT cash).
- PATIENTPAYMENTSDELETE = a deleted/reversed payment.
- PROCEDURECOMPLETED (charges), PATIENTADJUSTMENT, FEEUPDATION = not payments.

## Read first
- `packages/ingest/carestack_accounting_transaction_service.py` — current
  `_PAYMENT_FOLIO_TO_KIND` map + emission. Replace folio-based with code-based.
- Migration pattern (enum-extend + data UPDATE): the ENG-269 dedupe migration and
  the ENG-270 backfill migration under `packages/db/alembic/versions/`.
- `packages/interaction/{models,schemas,service,repository,CLAUDE.md}` — EVENT_KINDS,
  _KIND_VERB, get_treatment_payment_aggregate.
- PM Payments page: `apps/web/app/(staff)/project-manager/payments/page.tsx` + its
  Zod schema/hook.

## Task

### A. Emission — classify by transactionCode (+ isReversed)
In the accounting-transaction service, map the row's `transactionCode` (upper-cased):
- `PATIENTPAYMENTS`, `INSURANCEPAYMENTS` → `payment_recorded`
- `PATPAYMENTAPPLIED`, `INSPAYMENTAPPLIED` → `payment_applied` (NEW kind)
- `PATIENTPAYMENTSDELETE` (+ any refund code) → `payment_reversed` (or payment_refunded for explicit refunds)
- `isReversed == true` overrides → `payment_reversed`
- any other code / no payment code → NO event (raw-only), as today.
Keep the safe payload (amount, transaction_type, location_id). Add nothing PII.

### B. New kind `payment_applied` (migration)
- New Alembic revision (down_revision = current head): extend the `interaction.event`
  `ck_event_kind` CHECK to include `payment_applied` (mirror the ENG-269 enum-extend).
- Update `packages/interaction/models.py` EVENT_KINDS, `schemas.py` EventKind
  Literal, `_KIND_VERB`, and the interaction CLAUDE.md kinds table to match exactly.

### C. Reclassify existing events (migration UPDATE, same or sibling revision)
- For existing `payment_recorded` events, join `ingest.raw_event` on source_event_id,
  read `payload->>'transactionCode'`, and UPDATE `kind`:
  PATPAYMENTAPPLIED/INSPAYMENTAPPLIED → `payment_applied`;
  PATIENTPAYMENTSDELETE → `payment_reversed`;
  leave PATIENTPAYMENTS/INSURANCEPAYMENTS as is.
- Idempotent (guard on current kind). Append-only exception (decision-log). The
  ENG-269 unique index includes `kind`; reclassify won't collide (one
  source_external_id per kind). `downgrade()` no-op (documented).

### D. Aggregate
- `get_treatment_payment_aggregate`: `collected_total` =
  sum(payment_recorded.amount) − sum(payment_refunded.amount + payment_reversed.amount).
  `payment_event_count` = count of payment_recorded. `payment_applied` excluded entirely.

### E. Frontend (PM Payments page)
- The list may include `payment_applied` rows but HIDE them by default; add a
  "Show applied" (or "Show all") toggle. Label each row by type: Payment /
  Applied / Refund / Reversal. Keep MSW ↔ Zod in sync.

## Hard constraints
- Read-only CareStack. No new table. Migrations immutable: new revision(s),
  working downgrade. No PHI in logs/response. `except Exception` only. English only.
  Cross-domain rules per `packages/CLAUDE.md`.

## Definition of done
1. `make lint` ; `mypy .` ; `make test` ; `cd packages/db && alembic check` green;
   migration round-trip (upgrade→downgrade -1→upgrade).
2. `cd apps/web && npm run lint && npx tsc --noEmit && npm run test` green.
3. After local upgrade verify Collected ≈ $11,698 (down from $38,178) and
   payment_applied events exist + are excluded from Collected; re-run migration = 0 changes.
4. Commit to your worktree branch only once green.
5. Write `.agents/orchestration/carestack-payment-classification-v1/reports/ENG-283-worker-report.md`
   (code→kind table, rows reclassified, aggregate math, FE toggle, tests, round-trip, risks, do-not-merge).
6. If a transactionCode's meaning is ambiguous, treat unknown codes as raw-only
   (no event) and list them in the report; if blocked, write `Needs decision:`.
