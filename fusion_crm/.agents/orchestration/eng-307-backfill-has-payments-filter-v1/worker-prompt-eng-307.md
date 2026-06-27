You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: **ENG-307**
(https://linear.app/fusion-dental-implants/issue/ENG-307/add-only-with-payments-filter-to-backfill-payment-summarypy).
Isolated git worktree. Implement → verify → write a report. Do NOT touch `main`,
do NOT push, do NOT open a PR. Commit to YOUR worktree branch only once green;
the Orchestrator integrates.

## Mission (backend-only, small)

Add a `--only-with-payments` boolean flag to
`infra/scripts/backfill_payment_summary.py`. When set, the patient_ids
list comes from a NEW filtered resolver that returns ONLY CareStack
patient_ids whose linked person has at least one payment-related
accounting raw event on the tenant. When NOT set, behavior is identical
to today.

This unblocks the real CareStack backfill: prod has 55,677 linked
patients but only ~1803 with payment activity. The current
`list_source_links_for_dashboard` resolver ordered by `first_seen_at DESC`
misses most of the active set under `--max-patients 2000`. With the
filter, ~1803 × 0.5s ≈ 15 min, low 429 risk. CareStack throttled this
account ~24 h once before — keep all existing rate-limiting intact.

## Pre-flight facts (audited — do NOT re-investigate)

### Canonical "has payments" source

`ingest.raw_event` filtered by:
- `source = 'carestack'`
- `event_type = 'carestack.accounting_transaction.upsert'`
- `payload->>'transactionCode' IN (...)` for payment-related codes

**Payment-related transactionCode set** (use ALL of these for "has any
payment activity"):
- `PATIENTPAYMENTS`
- `INSURANCEPAYMENTS`
- `PATIENTREFUND`         (note: pre-flight wrote `PATENTREFUND` — that's a typo; verify by grepping the existing payment classifier)
- `INSURANCEREFUND`
- `PATIENTPAYMENTSDELETE`
- `PATPAYMENTAPPLIED`
- `INSPAYMENTAPPLIED`

Confirm the canonical list by reading
`packages/ingest/carestack_accounting_transaction_service.py` (the
`_PAYMENT_CODE_TO_KIND` map or equivalent) before hard-coding. Use the
EXACT set the service treats as "payment-related" — do NOT invent your
own.

Distinct patient_ids are the distinct `payload->>'patientId'` values
across those rows.

### Existing pattern to mirror

`IngestRepository.sum_accounting_totals_by_patient` at
`packages/ingest/repository.py:381-465` already walks
`carestack.accounting_transaction.upsert` raw_events filtered by
transactionCode set, deduped by `external_id` (latest `received_at`).
Reuse this query SHAPE (JSONB extraction, `for_tenant` scoping, dedup
subquery) — do NOT invent a new SQL approach.

### patient_id mapping

`ingest.raw_event.payload['patientId']` (string, e.g. `'1448336'`) is
the same value stored at `identity.source_link.source_id` for
`(source_system='carestack', source_kind='patient')`. No JOIN across
tables is needed — match by the patient_id string directly.

### Entry point to modify

`infra/scripts/backfill_payment_summary.py:180-191` currently calls:
```python
identity_repo = IdentityRepository(session)
links = await identity_repo.list_source_links_for_dashboard(
    tenant_id, source_system="carestack", source_kind="patient",
    limit=args.max_patients,
)
patient_ids: list[str] = [
    str(link.source_id)
    for link in links
    if link.source_id is not None and str(link.source_id).strip()
]
```

The new resolver MUST return the same `list[SourceLink]`-compatible shape
so this extraction loop stays unchanged — return either real
`SourceLink` rows (filtered) or `SimpleNamespace`-shaped objects with
`.source_id`, `.source_system`, `.source_kind`, `.person_uid` (matches
the existing test factory `_link()`).

### Test scaffolds

`tests/infra/test_backfill_payment_summary.py` uses:
- `_fake_session_cm()` — async-context-manager mock for the session.
- `_link(patient_id)` — `SimpleNamespace` factory with
  `source_id`, `source_system`, `source_kind`, `person_uid`.
- `_args(...)` — `argparse.Namespace` builder.
- `_SleepRecorder` — async-sleep stand-in.
- The script is loaded via `importlib.util` (lines ~40-48) to avoid
  package-level side effects.

Existing tests mock `IntegrationCredentialService`, `IntegrationService`,
`IdentityRepository`, `CareStackPaymentSummaryIngestService`,
`CareStackClient`. For the new flag, you'll mock the new resolver
(wherever it lives) similarly.

## Tasks (TDD — tests first per piece)

### 1. New resolver

Add the filtered resolver. Two reasonable homes:

**Recommended:** new method `IngestRepository.list_carestack_patients_with_payment_activity(tenant_id, *, payment_codes: Sequence[str], limit: int)` returning `list[SourceLink]` of CS patient links whose `source_id` appears in the distinct `payload->>'patientId'` set from accounting raw events filtered by the code set. Two-step query:
1. `SELECT DISTINCT payload->>'patientId' FROM raw_event WHERE for_tenant + source='carestack' + event_type='carestack.accounting_transaction.upsert' + payload->>'transactionCode' = ANY(codes) AND payload->>'patientId' IS NOT NULL`
2. `SELECT * FROM source_link WHERE for_tenant + source_system='carestack' + source_kind='patient' + source_id = ANY(distinct_patient_ids) ORDER BY first_seen_at DESC LIMIT limit`

Or do it in a single SQL with a CTE / subquery — pick whichever fits the
repo's existing SQL style. Match `sum_accounting_totals_by_patient`'s
patterns (JSONB extraction, `for_tenant`, no manual tenant filter).

Alternative: put it on `IdentityRepository` since the return shape is
`SourceLink`. Either is fine; pre-flight suggested `IngestRepository` to
co-locate with the raw-event reading. Worker chooses based on
which-feels-natural; document the choice in the report.

**Tests** (`tests/ingest/...` or wherever the chosen repo's tests live):
- `test_resolver_returns_only_patients_with_payments` — seed 3 linked CS
  patients, 2 with payment raw events → resolver returns 2 links.
- `test_resolver_dedups_repeated_patient_ids` — 3 payment raw events on
  the same patient → resolver returns 1 link.
- `test_resolver_respects_tenant_scope` — payment rows on another tenant
  for the same patient_id → NOT included.
- `test_resolver_excludes_non_payment_codes` — accounting rows with
  `PROCEDURECOMPLETED` only → resolver returns 0 links.

### 2. Wire `--only-with-payments` into the script

In `infra/scripts/backfill_payment_summary.py`:

- Add `--only-with-payments` to `_parse_args` (boolean, default `False`).
- Just before line 180-191's resolver call, branch:
  ```python
  if args.only_with_payments:
      ingest_repo = IngestRepository(session)
      links = await ingest_repo.list_carestack_patients_with_payment_activity(
          tenant_id, payment_codes=PAYMENT_CODES, limit=args.max_patients,
      )
      selector = "has_payments"
  else:
      links = await identity_repo.list_source_links_for_dashboard(...)
      selector = "all_linked"
  ```
  Pull `PAYMENT_CODES` from a module-level constant in the script (or
  import from the accounting service if there's a clean public symbol).
- Include `selector=selector` in the structured log line that announces
  the resolved patient_ids count (current `backfill.payment_summary.*`
  log keys — find the right one).
- `--max-patients` continues to apply (the new resolver's `limit`
  argument carries it through).
- Keep `--dry-run` behavior identical (the resolver is still called;
  print patient_ids; no CareStack calls).

**Tests** (`tests/infra/test_backfill_payment_summary.py`):
- `test_only_with_payments_flag_invokes_filtered_resolver` — flag set →
  the new resolver method is called AND
  `IdentityRepository.list_source_links_for_dashboard` is NOT called
  (`.assert_not_awaited()`).
- `test_default_path_unchanged_when_flag_absent` — flag unset → the new
  resolver method is NOT called; existing behavior intact.
- `test_max_patients_caps_filtered_resolver` — `--max-patients 3` over
  10 has-payments matches → only 3 patient_ids forwarded (assert via
  the resolver mock receiving `limit=3`).
- `test_logs_include_selector_field` — capture the structured log line;
  assert `selector="has_payments"` or `"all_linked"` matches the chosen
  path.
- `test_dry_run_with_filter_still_skips_carestack` — `--dry-run
  --only-with-payments` → filtered resolver called, CareStack client
  never constructed/awaited.

### 3. Constants + log hygiene

- Module-level `_PAYMENT_TRANSACTION_CODES: tuple[str, ...]` in the
  script (or imported). Use the EXACT codes the accounting service
  classifies as payment events — read
  `packages/ingest/carestack_accounting_transaction_service.py` to
  confirm; do NOT hardcode my list above without verification (pre-flight
  may have a typo on `PATIENTREFUND` vs `PATENTREFUND`).
- Logs: only `patient_id`, counts, and the `selector` field. NO PHI.

## Hard constraints

- **CareStack stays MOCKED** in all tests. NO real API call in dev/CI.
- **No HTTP wiring** — script remains background-only.
- **Throttle / backoff / commit batching UNCHANGED.**
- **No new migrations.**
- **No PHI in logs** (patient_id + counts + selector + tenant_id_str only).
- **`except Exception`, never `except BaseException`.** Repo convention.
- **English in repo files.**
- **Do NOT touch `apps/web/lib/msw/handlers.ts`** — unrelated WIP.
- **TDD:** write tests first for each piece.
- **One commit at the end** on the worktree branch. Format:
  `ENG-307: add --only-with-payments filter to backfill_payment_summary.py`.
- **Verify the payment code set** by reading the accounting service
  before hard-coding (pre-flight may have a typo).

## Verify (sandbox-aware)

Worker MUST run the focused subset that does not need `.env`:

```bash
ruff check infra/scripts/backfill_payment_summary.py tests/infra/ packages/ingest/
mypy infra/scripts/backfill_payment_summary.py
```

If your sandbox allows `pytest` to run on the focused subset
(`pytest tests/infra/test_backfill_payment_summary.py -v`), do that too
— the integrator will re-run the full loop with `.env` regardless.

Document anything that did NOT run because of sandbox limits — the
integrator handles those.

## Definition of done

1. Lint + mypy on the touched files (sandbox-allowed subset) green.
2. Commit on worktree branch ONLY (NOT main).
3. Write `.agents/orchestration/current/reports/ENG-307-worker-report.md`
   covering: touched files, what changed, tests added + results, verify
   commands attempted (with outcomes — green / skipped / blocked),
   risks identified, blockers / questions, suggested next task,
   DO-NOT-MERGE conditions.
4. Do NOT trigger a real CareStack backfill — that is a SEPARATE
   operator decision after merge.

If you hit something the implementation map did not predict — especially
if the payment-code set differs from what I wrote above — STOP and
write `Blocked:` in the report rather than guess.
