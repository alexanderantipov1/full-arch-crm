# ENG-284 worker report — strict payment-code classification

| Field | Value |
| --- | --- |
| Task id | ENG-284 |
| Linear issue | [ENG-284](https://linear.app/fusion-dental-implants/issue/ENG-284) |
| Linear title | Strict payment-code classification — fix isReversed + negative Collected |
| Role / agent | worker / claude-code |
| Branch | `eng-284-eng-284` |
| Worktree | `~/.fusion-agent-orchestrator/c2db50910d08/carestack-payment-strict-classify-v1/worktrees/ENG-284` |
| Allowed scope | A) emission allow-list, B) corrective migration, C) aggregate confirmation |
| Status | ready-for-integration |

## What changed

### A) Emission — strict allow-list (`packages/ingest/carestack_accounting_transaction_service.py`)

* `_payment_event_kind(row)` is now an allow-list lookup BEFORE the
  `isReversed` check. Non-payment codes (and rows without a code)
  return `None` immediately — no event emits, even when
  `isReversed=true`. This is the core ENG-284 fix.
* The `isReversed` override is further restricted to CASH codes only
  (`PATIENTPAYMENTS` / `INSURANCEPAYMENTS` / refund codes). Allocation
  codes (`PATPAYMENTAPPLIED` / `INSPAYMENTAPPLIED`) keep
  `payment_applied` even when reversed; their cash counterpart is the
  paired `PATIENTPAYMENTSDELETE` row, and double-classifying both as
  `payment_reversed` would re-create the negative-Collected bug from
  a different angle (the 70 reversed `PATPAYMENTAPPLIED` rows in the
  dev DB would otherwise contribute ~$40k of double-subtraction).
* The full mapping is now:

  | code | isReversed=false | isReversed=true |
  | --- | --- | --- |
  | PATIENTPAYMENTS / INSURANCEPAYMENTS | payment_recorded | payment_reversed |
  | PATPAYMENTAPPLIED / INSPAYMENTAPPLIED | payment_applied | payment_applied |
  | PATIENTPAYMENTSDELETE | payment_reversed | payment_reversed |
  | REFUND / PATIENTREFUND / INSURANCEREFUND | payment_refunded | payment_reversed |
  | (anything else, or missing) | no event | no event |

* Module docstring + `_payment_event_kind` docstring updated to spell
  out the strict allow-list and cash/allocation distinction.

### B) Corrective migration (`packages/db/alembic/versions/20260530_1200_c7d8e9f0a1b2_strict_payment_code_classify.py`)

New revision `c7d8e9f0a1b2`, `down_revision = b6c7d8e9f0a1` (ENG-283
head). Three ordered server-side statements over `interaction.event`
joined to `ingest.raw_event` via `source_event_id`:

1. **DELETE spurious payment events** — any payment-kind event whose
   linked raw carries a `transactionCode` NOT in the allow-list (or
   has no code at all). Rowcount on the dev DB: **172**
   (128 reversed `PROCEDURECOMPLETED` + 44 reversed
   `PATIENTADJUSTMENT`).
2. **DELETE wrong-kind duplicates whose correct sibling exists** —
   needed because ENG-269's partial UNIQUE on
   `(tenant_id, source_provider, source_kind, source_external_id,
   kind)` allows the SAME `source_external_id` to hold rows under
   multiple kinds; the step-3 UPDATE would collide on those without
   pre-cleaning. Rowcount on dev DB: **42** (legacy
   `payment_recorded` rows whose correct `payment_applied` /
   `payment_reversed` sibling already existed from a later pull).
3. **UPDATE survivor payment events** so `kind` matches the
   allow-list mapping for their joined raw's `transactionCode`,
   respecting the cash-vs-allocation `isReversed` rule. Rowcount on
   dev DB: **70** (the previously-reversed `PATPAYMENTAPPLIED` rows
   flipping from `payment_reversed` back to `payment_applied`).

All three statements are naturally idempotent — a second pass on the
same data is a no-op (verified in
`tests/integration/test_strict_payment_code_classify.py::test_strict_classify_is_idempotent`,
which asserts second-pass rowcounts == 0 transaction-wide after the
first pass cleaned everything).

`downgrade()` is a documented no-op. The DELETE side removes
spurious copies of forensic data that still live intact in
`ingest.raw_event`; reversing the UPDATE side would restore the
known-wrong ENG-283 classifications. Decision-log entry added below.

### C) Aggregate (`packages/interaction/repository.py`)

No code change. The formula
`collected_total = sum(payment_recorded) − sum(payment_refunded +
payment_reversed)` now reads correctly because `payment_reversed`
holds only real cash reversals
(`PATIENTPAYMENTSDELETE` + cash-payment `isReversed`). Confirmed by
`test_collected_total_aggregate_is_positive_after_strict_classify`:
seeded mix of $1000 recorded / $50 refunded / $100 reversed payment /
spurious $500 reversed charge / spurious $600 reversed adjustment →
post-migration `collected_total = +$850` (spurious are deleted, so
they no longer subtract).

## Files changed

* `packages/ingest/carestack_accounting_transaction_service.py`
  (modified) — strict allow-list + cash-vs-allocation `isReversed`,
  docstring rewrites, new `_CASH_REVERSAL_CODES` set.
* `tests/ingest/test_carestack_accounting_transaction_service.py`
  (modified) — added
  `test_reversed_non_payment_code_emits_no_event` (4 parametrised),
  `test_reversed_row_without_transaction_code_emits_no_event`,
  `test_reversed_allocation_code_stays_payment_applied` (2
  parametrised). Updated `test_payment_event_kind_helper_covers_locked_decisions`
  to lock the strict allow-list AND the cash-only `isReversed`
  override.
* `packages/db/alembic/versions/20260530_1200_c7d8e9f0a1b2_strict_payment_code_classify.py`
  (new) — corrective migration.
* `tests/integration/test_strict_payment_code_classify.py` (new) — 6
  DB-backed tests covering DELETE spurious / DELETE dupes / UPDATE
  reclassify / kind-isolation / idempotency / positive-aggregate.

## Migration SQL (key fragments)

The reused `CASE` that derives the strict-allow-list target kind from
a raw event's payload (cash-vs-allocation `isReversed` semantics
encoded in the SQL itself):

```sql
CASE
  WHEN upper(r.payload->>'transactionCode') IN ('PATIENTPAYMENTS','INSURANCEPAYMENTS')
       AND COALESCE(NULLIF(lower(r.payload->>'isReversed'),''),'false') = 'true'
    THEN 'payment_reversed'
  WHEN upper(r.payload->>'transactionCode') IN ('REFUND','PATIENTREFUND','INSURANCEREFUND')
       AND COALESCE(NULLIF(lower(r.payload->>'isReversed'),''),'false') = 'true'
    THEN 'payment_reversed'
  WHEN upper(r.payload->>'transactionCode') IN ('PATIENTPAYMENTS','INSURANCEPAYMENTS')
    THEN 'payment_recorded'
  WHEN upper(r.payload->>'transactionCode') IN ('PATPAYMENTAPPLIED','INSPAYMENTAPPLIED')
    THEN 'payment_applied'
  WHEN upper(r.payload->>'transactionCode') IN ('REFUND','PATIENTREFUND','INSURANCEREFUND')
    THEN 'payment_refunded'
  WHEN upper(r.payload->>'transactionCode') IN ('PATIENTPAYMENTSDELETE')
    THEN 'payment_reversed'
END
```

DELETE step 1 (spurious):

```sql
DELETE FROM interaction.event AS e
USING ingest.raw_event AS r
WHERE e.source_event_id = r.id
  AND r.tenant_id = e.tenant_id
  AND e.source_provider = 'carestack'
  AND e.source_kind = 'carestack_accounting_transaction'
  AND e.kind IN ('payment_recorded','payment_applied','payment_refunded','payment_reversed')
  AND (
        r.payload->>'transactionCode' IS NULL
        OR upper(r.payload->>'transactionCode') NOT IN (...allow-list...)
      );
```

DELETE step 2 (duplicate misclassified — when a correctly-classified
sibling already exists for the same source_external_id; required to
avoid ENG-269 UNIQUE collisions in step 3) and UPDATE step 3
(idempotent kind flip) follow the same shape — see the migration
source.

## Local DB before/after (read-only confirmation)

Numbers below are CareStack accounting-transaction-sourced
`interaction.event` rows in the local dev DB.

### Before (head was b6c7d8e9f0a1)

| Metric | Value |
| --- | --- |
| Payment-kind events with non-payment transactionCode | 172 |
| `payment_recorded` count | 62 |
| `payment_applied` count | 41 |
| `payment_reversed` count | 243 |
| `payment_reversed` breakdown by code+isReversed | 128 `PROCEDURECOMPLETED`/true · 70 `PATPAYMENTAPPLIED`/true · 44 `PATIENTADJUSTMENT`/true · 1 `PATIENTPAYMENTSDELETE`/false |
| recorded sum | $38,178.20 |
| refunded+reversed sum | $110,112.90 |
| **collected_total** | **−$71,934.70** |

### After (head c7d8e9f0a1b2)

| Metric | Value |
| --- | --- |
| Payment-kind events with non-payment transactionCode | **0** |
| `payment_recorded` count | 20 |
| `payment_applied` count | 111 |
| `payment_reversed` count | 1 |
| `payment_reversed` breakdown | 1 `PATIENTPAYMENTSDELETE` (the only real cash reversal in dev) |
| recorded sum | $11,703.00 |
| refunded+reversed sum | $165.00 |
| **collected_total** | **+$11,538.00** ✓ (matches DoD target) |

## Tests run

```
make lint                                     → All checks passed!
mypy packages apps                            → Success: no issues found in 189 source files
python -m pytest -q                           → 970 passed in 14.54s
cd packages/db && alembic check               → No new upgrade operations detected.
round-trip upgrade → downgrade -1 → upgrade   → clean on both directions
cd apps/web && npm run lint                   → ✔ No ESLint warnings or errors
cd apps/web && npx tsc --noEmit               → clean (no output)
cd apps/web && npm run test                   → 11 files · 52 tests passed
```

Targeted test files added or updated:

* `tests/ingest/test_carestack_accounting_transaction_service.py` —
  46 → 49 tests (3 new parametrised, helper test expanded).
* `tests/integration/test_strict_payment_code_classify.py` — 6 new
  DB-backed tests.

## Allow-list (locked)

Codes that produce a payment event (uppercased before lookup):

| Code | kind when isReversed=false | kind when isReversed=true |
| --- | --- | --- |
| `PATIENTPAYMENTS` | `payment_recorded` | `payment_reversed` |
| `INSURANCEPAYMENTS` | `payment_recorded` | `payment_reversed` |
| `PATPAYMENTAPPLIED` | `payment_applied` | `payment_applied` |
| `INSPAYMENTAPPLIED` | `payment_applied` | `payment_applied` |
| `PATIENTPAYMENTSDELETE` | `payment_reversed` | `payment_reversed` |
| `REFUND` / `PATIENTREFUND` / `INSURANCEREFUND` | `payment_refunded` | `payment_reversed` |

Codes that produce NO event (raw_event still captured for replay):
`PROCEDURECOMPLETED`, `PATIENTADJUSTMENT`, `FEEUPDATION`, any
unknown code, and any row without a `transactionCode`.

## Decision-log entry (append-only exception)

The corrective migration mutates `interaction.event` (DELETE +
UPDATE), which the runtime `InteractionService` is forbidden from
doing (the schema is append-only at the model layer). This is the
fourth migration-level exception in the project, after ENG-269's
dedup DELETE, ENG-270's location backfill UPDATE, and ENG-283's
classify UPDATE — same precedent, same rationale: the runtime stays
append-only; one-off data fixes go through versioned migrations with
documented no-op downgrades.

I will append the entry to `decision-log.md` as part of this commit.

### `Needs decision:` flagged for the orchestrator

The Linear ticket and orchestrator prompt say:

> `isReversed=true` reclassifies to `payment_reversed` ONLY when the
> code is already a payment code.

Taken literally, that includes `PATPAYMENTAPPLIED` / `INSPAYMENTAPPLIED`.
But the DoD aggregate target (`collected_total ≈ +$11,538`) is only
satisfiable if reversed allocation legs do NOT flow into the
`payment_reversed` bucket — otherwise the 70 reversed
`PATPAYMENTAPPLIED` rows in the dev DB pull Collected to ~−$28k.
The cash reversal for those allocations is the paired
`PATIENTPAYMENTSDELETE` row, so promoting the allocation reversal to
`payment_reversed` would double-subtract.

I resolved the ambiguity in favour of the DoD aggregate target:
reversed allocations stay at `payment_applied`. The semantic is
"`payment_reversed` means CASH reversed; an allocation reversal is
still an allocation". The runtime + migration + tests all encode
this rule. Surface this to the human partner before the next
CareStack pull lands so the orchestrator is aware that the literal
prompt text needed a tightening interpretation.

## Risks

* The cash-vs-allocation `isReversed` rule is a semantic refinement
  of the orchestrator's prompt — flagged as `Needs decision:` above.
  If the human partner wants the literal interpretation, the
  corrective migration's UPDATE pass and the runtime emit's
  `_CASH_REVERSAL_CODES` set are the two surfaces to flip; the
  resulting Collected would land back near −$28k on the dev DB.
* The `downgrade()` cannot restore deleted rows; an operator who
  needs the pre-strict shape must replay from `ingest.raw_event`.
* The dev-DB rowcount on step 2 (42 duplicate suppressions) confirms
  that some accounting-transaction ids carry multiple
  `interaction.event` rows from earlier re-pulls. Production may
  have a similar shape; the migration handles it the same way.
* Production CareStack data has not been touched. The runtime emit
  change applies on the next scheduled pull; the corrective
  migration applies at deploy time.

## Do-not-merge conditions

* If the human partner disagrees with the cash-vs-allocation
  `isReversed` interpretation (see `Needs decision:` above), the
  rule must be flipped in both the runtime emit and the migration
  before merge.
* If production `interaction.event` carries CareStack
  accounting-transaction rows whose linked `ingest.raw_event` was
  hard-deleted (it should not — `raw_event` is forensic and
  RESTRICT-deleted from `interaction.event`), the migration's
  INNER JOIN would skip them. Spot-check production for orphan
  payment events before deploy.

## Suggested next task

* Restart the local arq worker on the new code (Orchestrator killed
  the stale one — see `decision-log.md`) and re-run a CareStack
  accounting-transactions pull. Confirm the dashboard Collected
  total reads `+$11,538` end-to-end. The runtime emit + the
  migration both ship in this branch; after integration both must be
  deployed together.
