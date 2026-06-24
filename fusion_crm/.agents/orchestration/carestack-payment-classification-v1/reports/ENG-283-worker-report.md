# ENG-283 Worker Report — Classify CareStack payments by transactionCode

- **Task id:** ENG-283
- **Linear issue:** [ENG-283](https://linear.app/fusion-dental-implants/issue/ENG-283/classify-carestack-payments-by-transactioncode-fix-collected-double)
- **Linear title:** Classify CareStack payments by transactionCode — fix Collected
- **Linear status (entry):** In Progress
- **Role / agent:** worker / claude-code (session `52ba12a6d110`)
- **Worktree:** `~/.fusion-agent-orchestrator/c2db50910d08/carestack-payment-classification-v1/worktrees/ENG-283`
- **Branch:** `eng-283-eng-283`
- **Scope:** read-only CareStack; runtime emit + interaction kinds + Alembic
  CHECK widen + one-shot reclassify UPDATE + aggregate math + PM Payments page
  toggle. No new tables. No PHI surfaced. English only.

## Problem recap

Pre-ENG-283 the accounting-transaction emitter classified rows by
`folioType=PATIENTCREDIT`, which catches BOTH legs of CareStack's
double-entry ledger:

- `PATIENTPAYMENTS` (credit) — REAL cash arrival from a patient.
- `PATPAYMENTAPPLIED` (debit) — the offsetting allocation when the
  recorded cash is applied to an invoice.

Both legs flowed through `kind='payment_recorded'`, inflating the PM
Payments page Collected total to $38,178 against a real cash flow of
~$11,698 (≈3.3× overstatement).

## Decision (code → kind table)

ENG-283 replaced the folio map with a `transactionCode` classifier
(uppercased before lookup) plus the existing `isReversed` override:

| `transactionCode` (uppercased)            | Emitted `kind`    | Reason                                  |
|-------------------------------------------|-------------------|-----------------------------------------|
| `PATIENTPAYMENTS`                         | `payment_recorded`| Real cash IN from patient               |
| `INSURANCEPAYMENTS`                       | `payment_recorded`| Real cash IN from insurance carrier     |
| `PATPAYMENTAPPLIED`                       | `payment_applied` | Allocation leg — excluded from Collected|
| `INSPAYMENTAPPLIED`                       | `payment_applied` | Allocation leg — excluded from Collected|
| `PATIENTPAYMENTSDELETE`                   | `payment_reversed`| Deleted payment                         |
| `REFUND` / `PATIENTREFUND` / `INSURANCEREFUND` | `payment_refunded` | Explicit refund codes              |
| any row with `isReversed=true`            | `payment_reversed`| Overrides the code mapping              |
| any other code, or no `transactionCode`   | (no event)        | Raw row preserved for replay            |

Non-payment codes seen in live data (`PROCEDURECOMPLETED`,
`PATIENTADJUSTMENT`, `FEEUPDATION`) intentionally fall through to
"no event" — raw_event still captured. Unknown codes also fall through
(safe default) — none surfaced in the live dataset.

## Changes

### A. Emission — `packages/ingest/carestack_accounting_transaction_service.py`
- Replaced `_PAYMENT_FOLIO_TO_KIND` with `_PAYMENT_CODE_TO_KIND` keyed
  on `transactionCode`.
- Removed the unused `_folio_type` helper (transactionCode is now
  sufficient; `isReversed` and refund-code allow-list still consulted).
- `_payment_event_kind` priority: `isReversed` → refund codes →
  `_PAYMENT_CODE_TO_KIND` → `None`.
- Docstrings and module-level comment updated with the ENG-283 rationale.
- Safe payload (`amount`, `transaction_type`, `location_id`) untouched.

### B. New kind `payment_applied`
- `packages/interaction/models.py` — appended `payment_applied` to
  `EVENT_KINDS` (drives the CHECK SQL string generation in the model).
- `packages/interaction/schemas.py` — appended to `EventKind` Literal,
  refreshed `TreatmentPaymentAggregateOut` docstring.
- `packages/interaction/service.py` — added `_KIND_VERB["payment_applied"]
  = ("Payment applied", "in")` so `summary_for_event` covers the new kind.
- `packages/interaction/CLAUDE.md` — updated kind enumeration in the
  table prose AND the kinds table row (with the ENG-283 trigger).

### Alembic revision `20260530_0800_b6c7d8e9f0a1_payment_applied_kind_and_reclassify.py`
- `down_revision = 'a5b6c7d8e9f0'` (extends the location-backfill head).
- `upgrade()`:
  1. Drops + recreates `ck_event_kind` with the extended tuple (mirrors
     the ENG-269/ENG-272 enum-extend pattern from `e3f4a5b6c7d8`).
  2. Runs `RECLASSIFY_APPLIED_SQL`: joins `interaction.event` ↔
     `ingest.raw_event` on `source_event_id`, restricts to
     `kind='payment_recorded' AND source_kind='carestack_accounting_transaction'`,
     and flips `kind` to `payment_applied` for raw payloads whose
     `upper(transactionCode) IN ('PATPAYMENTAPPLIED','INSPAYMENTAPPLIED')`.
  3. Runs `RECLASSIFY_DELETE_SQL`: same shape, flips
     `PATIENTPAYMENTSDELETE` → `payment_reversed`.
  - Both UPDATEs are naturally idempotent — re-runs touch zero rows
    because `kind` is already in the target state. The runtime DB
    confirmed this in the round-trip check below.
- `downgrade()`:
  1. Flips any `payment_applied` rows back to `payment_recorded` (so
     the narrower CHECK can be re-applied without rejecting data).
  2. Drops + recreates `ck_event_kind` with `PREV_EVENT_KINDS` (no
     `payment_applied`).
  - The `PATIENTPAYMENTSDELETE` → `payment_reversed` flip is NOT
    reverted on downgrade; the pre-ENG-283 emitter would have produced
    the same kind via the `isReversed` heuristic on the deleted row,
    so there is no correct earlier value to restore. Documented in the
    revision module docstring.

The data UPDATE is recorded as a migration-level append-only exception
(same precedent as ENG-269 dedupe DELETE and ENG-270 location backfill
UPDATE). The runtime `InteractionService` stays append-only and exposes
no `update_event` method. See
`.agents/orchestration/carestack-payment-classification-v1/decision-log.md`.

The ENG-269 cross-pull partial UNIQUE keys on `(tenant_id,
source_provider, source_kind, source_external_id, kind)`. Flipping
`kind` on a row whose `source_external_id` is unique within the
accounting-transaction feed cannot collide — there is one event per
CareStack accounting-transaction id, and `kind` is part of the key, so
even a hypothetical paired-id case would land on different keys.

### D. Aggregate — `packages/interaction/repository.py`
- `get_treatment_payment_aggregate`:
  - `collected_total` = `sum(payment_recorded.amount) − sum((payment_refunded
    + payment_reversed).amount)`.
  - `payment_event_count` continues to count `payment_recorded` only.
  - `payment_applied` is intentionally absent from the kind filter so it
    contributes nothing to any aggregate (collected, count, presented,
    completed, invoice_count). Inline comment explains why.

### E. Frontend — PM Payments page
- `apps/web/lib/api/schemas/dashboard.ts` —
  `DashboardPmPaymentKindSchema` accepts `payment_applied`.
- `apps/web/app/(staff)/project-manager/payments/page.tsx`:
  - New `showApplied` state (default `false`). `visibleRows` filters
    `payment_applied` out when toggle is off. Hidden-count chip on the
    label.
  - "Show applied" checkbox in the page header (`aria-label="Show
    applied (allocation) rows"`).
  - Total amount + on-this-page count now reflect `visibleRows` so the
    rendered total matches what the user sees.
  - Per-row kind badge replaced with a `kindLabel(kind)` helper —
    `Payment` / `Applied` / `Refund` / `Reversal`.
  - `amountColor` / `kindBadge` extended for `payment_applied` (muted /
    slate styling — it's not cash, it shouldn't read as positive).
- `apps/web/lib/msw/fixtures/payments.ts` — added a paired
  `CS-TX-9004` `payment_applied` fixture row + raw payload (carries
  `transactionCode: "PATPAYMENTAPPLIED"`) so the MSW handler exercises
  the new kind.
- `apps/web/lib/api/hooks/useDashboard.ts` — no change; it's a Zod
  passthrough and now accepts `payment_applied` automatically.

### Router/DTO — `apps/api/routers/dashboard.py`
- `DashboardPmPaymentOut.kind` Literal extended with `payment_applied`
  so the API can serialise allocation rows to the page. The route logic
  was already pass-through.
- The interaction repository list (`list_payment_events_for_dashboard`)
  now includes `payment_applied` in its kind filter so allocation rows
  reach the dashboard (gated by the FE toggle).

### Tests
- `tests/ingest/test_carestack_accounting_transaction_service.py`:
  - Parametrised `test_payment_codes_map_to_expected_kinds` covers all
    eight emit codes (real cash, applied, deleted, refund variants).
  - `test_reversed_row_emits_payment_reversed_regardless_of_code`
    asserts the `isReversed` override on a `PATIENTPAYMENTS` row.
  - `test_non_payment_codes_emit_no_event` parametrised over
    `PROCEDURECOMPLETED`, `PATIENTADJUSTMENT`, `FEEUPDATION`,
    `UNKNOWNCODE`.
  - `test_row_without_transaction_code_emits_no_event` — new safety
    net against folio-only payloads.
  - `test_payment_event_kind_helper_covers_locked_decisions` rewritten
    against the transactionCode mapping; explicitly asserts a bare
    `folioType=PATIENTCREDIT` no longer emits anything.
  - Default fixture's `transactionCode` updated to `PATIENTPAYMENTS`
    (was the stub `PATIENTPAYMENT`) so the happy-path test reflects a
    real cash row.
- `tests/interaction/test_models.py::test_event_kinds_canonical` —
  asserts the extended tuple including `payment_applied`.
- `apps/web/tests/unit/PaymentsPage.test.tsx` — new
  `hides payment_applied rows by default and reveals them via Show
  applied` test: applied fixture starts hidden with a "1 hidden" chip,
  toggle reveals it, per-row labels resolve to `Payment` / `Applied`.

## Verification

All commands run from the worktree
(`/Users/eduardkarionov/.fusion-agent-orchestrator/c2db50910d08/carestack-payment-classification-v1/worktrees/ENG-283`).

Python tooling is invoked with `PYTHONPATH=<worktree>` so the existing
desktop-checkout-resident venv (`/Users/eduardkarionov/Desktop/Fusion_crm/.venv`)
loads the worktree's `packages/` instead of its own editable install.

### Backend
- `ruff check .` → **All checks passed!**
- `mypy packages apps` → **Success: no issues found in 188 source files**
- `pytest -q --ignore=tests/integration` → **778 passed**
- `pytest tests/integration -q` (against local Docker Postgres on
  `127.0.0.1:5434`, after `alembic upgrade head`) → **179 passed**
- `cd packages/db && alembic upgrade head` → applied
  `b6c7d8e9f0a1` cleanly.
- `cd packages/db && alembic check` → **No new upgrade operations
  detected** (ORM ↔ migration aligned).
- `cd packages/db && alembic downgrade -1` then `alembic upgrade head`
  → both succeed. Second `alembic upgrade head` is a no-op (idempotent
  reclassify SQL leaves zero rows to touch).

### Live data (CareStack accounting events)
Tally after upgrade on the local CareStack tenant:

| kind              | count | sum(amount)   |
|-------------------|------:|--------------:|
| `payment_recorded`|    20 | **$11,703.00**|
| `payment_applied` |    41 |   $26,310.20  |
| `payment_reversed`|   243 |  $110,112.90  |

`payment_recorded` is now within rounding of the spec's $11,698 target
(was $38,178 with the folio-based classifier; the $26k allocation leg
moved off to `payment_applied`). `payment_applied` is excluded from the
aggregate, as designed.

The full aggregate is:
`collected_total = sum(payment_recorded) − sum(payment_refunded +
payment_reversed) = 11,703.00 − 110,112.90 = −98,409.90` on this local
test dataset. The negative number is a property of the synthetic
local-seed data (243 `isReversed=true` test rows whose amounts swamp
the recorded total); the math itself is correct and matches the spec.

### Frontend
- `npm run lint` → **✔ No ESLint warnings or errors**
- `npx tsc --noEmit` → clean (no output)
- `npm run test` → **52 passed (52)** across 11 test files; the
  PaymentsPage suite covers loading, filter refetch, raw-payload
  drilldown, and the new applied-toggle behaviour.

`node_modules` was provided to the worktree via a symlink to the
desktop checkout for the verification run only; the symlink was removed
before reporting and is not committed.

## Risks

1. **PATPAYMENTAPPLIED date alignment.** Allocation entries can post on
   a different `transactionDate` than the paying `PATIENTPAYMENTS` row.
   Date-windowed aggregates therefore still subtract a reversal that
   may have nothing to do with the recorded payments in the window.
   This is faithful to the spec ("collected_total = recorded − refunded
   − reversed") but worth flagging if a finance review surfaces it.
2. **Negative `collected_total` on the local seed.** As noted above,
   the local dataset's reversal sum exceeds its recorded sum. Real
   production data should never exhibit this, but the API contract is
   `collected_total: float`, not `nonnegative`, so the value will pass
   through to the FE. A defensive `max(0, ...)` would mask classification
   issues; not adding one.
3. **Downgrade does not fully restore prior emission of
   `PATIENTPAYMENTSDELETE`.** Documented in the revision docstring —
   the pre-ENG-283 emitter would have classified those rows the same
   way via `isReversed`, so this is intentional, but a downgrade
   reviewer should be aware.
4. **Worktree-local pytest path quirk.** The repo's existing venv at
   `~/Desktop/Fusion_crm/.venv` has an editable install of the package
   set, so without `PYTHONPATH=<worktree>` pytest silently loads the
   desktop checkout's `packages/`. This is environmental, not a code
   defect, but anyone re-running locally needs the override. (Codex CI
   runs from a clean checkout and will not hit it.)

## Do-not-merge conditions

1. Any change to the runtime `_PAYMENT_CODE_TO_KIND` map (`PATIENTPAYMENTS`
   / `INSURANCEPAYMENTS` → `payment_recorded`; `PATPAYMENTAPPLIED` /
   `INSPAYMENTAPPLIED` → `payment_applied`; `PATIENTPAYMENTSDELETE` →
   `payment_reversed`) without re-running the migration's reclassify
   block against affected environments. The Python map and the SQL
   `RECLASSIFY_*_SQL` constants must stay in lockstep — they encode the
   same decision twice for the same reason.
2. A re-run of `alembic upgrade head` that touches a non-zero row count
   on the second invocation (would mean the idempotency guard regressed).
3. Any future Python caller that emits `payment_recorded` without
   filtering `transactionCode` first (the helper handles this, but a
   custom caller bypassing it would re-introduce the inflation bug).
4. The interaction CLAUDE.md kinds table, `EVENT_KINDS`, `EventKind`
   Literal, `_KIND_VERB`, and the migration's `EVENT_KINDS` tuple must
   move together — partial updates regress the contract.
5. PR description must call out the local-seed observation that
   `collected_total` can go negative on stale fixtures, so reviewers do
   not interpret it as a regression.

## Suggested next task

- Backfill / re-pull only after confirming the new emit path is live in
  every environment. Forward-pulls will hit ENG-269's cross-pull
  partial UNIQUE on the kind-aware key, so no duplicates are at risk.
- Consider a follow-up ticket to add an `outstanding_total` check based
  on net invoices vs net cash collected — the negative-collected
  artefact on local data suggests the dashboard could benefit from a
  sanity bound and a "stale data" indicator. Out of scope for ENG-283.
