# ENG-305 — Worker Report

- **Task id:** ENG-305
- **Linear title:** Throttled payment-summary backfill → authoritative patient balance
- **Linear URL:** https://linear.app/fusion-dental-implants/issue/ENG-305/throttled-payment-summary-backfill-authoritative-patient-balance
- **Role / Agent:** worker / claude-code (opus-4-7), session `e5410672bc11`
- **Branch:** `eng-305-eng-305`
- **Worktree:** `/Users/eduardkarionov/.fusion-agent-orchestrator/c2db50910d08/current/worktrees/ENG-305`
- **Allowed scope:** data path only — no UI, no migrations, no real CareStack calls

## What changed (one paragraph per piece)

### 1. `packages/ingest/carestack_payment_summary_service.py`

Extracted the per-patient snapshot loop out of `pull_all_payment_summaries`
into a private `_sweep_patient_ids` and added a new public
`import_payment_summary_for_patients(tenant_id, patient_ids, *,
sleep_seconds, max_retries, backoff_base_seconds, sleep, commit_every,
commit)`. The new entry point dedups input preserving insertion order
(`list(dict.fromkeys(...))`) so callers can hand it the raw output of an
accumulator without worrying about repeats. `_sweep_patient_ids`
reuses the existing `_fetch_summary_with_backoff` as-is — backoff
policy is untouched — and adds batched commits: every `commit_every`
patients (success OR error) plus a final flush when any work was done.
`pull_all_payment_summaries` keeps its signature and now filters
unusable links up-front, derives the patient_id list, and delegates to
the shared private. `commit=None` (the historical path) is a no-op
inside the sweep.

### 2. `packages/ingest/schemas.py` + `carestack_accounting_transaction_service.py`

Added `patient_ids: list[str] = Field(default_factory=list)` to
`CareStackAccountingTransactionImportOut`. The accounting service now
accumulates a `set[str]` of CareStack patient_ids whose rows actually
imported (`outcome == "imported"` AND `patient_id is not None`) and
returns the sorted, distinct list. Skipped rows (no `patientId`,
unlinked patient, non-payment folio, ENG-269 dedup conflicts) are
deliberately excluded — the live signal is meant for patients who
actually moved money on this tick.

### 3. `apps/worker/jobs/ingest_scheduled.py`

Inserted the live signal between the accounting pull and the rolling
50-patient sweep: if `accounting_transactions.patient_ids` is
non-empty, the scheduler calls
`payment_summary_svc.import_payment_summary_for_patients(tenant_id,
accounting_transactions.patient_ids, commit=session.commit)`. The
rolling `import_payment_summary_snapshots(max_patients=50)` sweep is
preserved as the safety net for patients whose balance drifted
without producing a fresh accounting transaction in the window
(externally-processed refund, late-settled insurance). Both layers
are complementary; removing the rolling sweep would silently regress
the existing dashboard Outstanding / AR-risk freshness.

### 4. `infra/scripts/backfill_payment_summary.py` (NEW)

Background-only CLI: `python3 infra/scripts/backfill_payment_summary.py
--tenant-id <uuid> [--max-patients 2000] [--sleep-seconds 0.5]
[--commit-every 50] [--dry-run]`. Mimics the `backfill_full.py:107-141`
async-session + `provider_sync_run` pattern (`provider="carestack"`,
`object_scope="payment_summary"`, `trigger="backfill_script"`).
Resolves patient_ids off `IdentityRepository.list_source_links_for_dashboard`,
filters blank/None source_ids, then delegates to
`import_payment_summary_for_patients`. `--dry-run` short-circuits
before opening a sync_run, lists patient_ids on stdout, and never
constructs the CareStack client. Logs carry only `patient_id` and
counts — never names, DOB, balances, or clinical content. Exit codes:
0 success (incl. dry-run + no-patients), 2 missing CareStack
credential, 1 uncaught exception. The script is NOT wired to any HTTP
endpoint (Next's 30 s proxy timeout has burned long-running ingest
operations before).

The `packages.db.session` import is deferred to call time inside a
`_default_session_factory` helper. That keeps the module loadable for
tests + `--help` without the live engine and matches the existing
constraints of the other test-mockable code paths.

## Touched files

| File | Type | Lines |
|---|---|---|
| `packages/ingest/carestack_payment_summary_service.py` | modified | +199 / -32 |
| `packages/ingest/carestack_accounting_transaction_service.py` | modified | +11 |
| `packages/ingest/schemas.py` | modified | +7 |
| `apps/worker/jobs/ingest_scheduled.py` | modified | +21 |
| `infra/scripts/backfill_payment_summary.py` | NEW | +252 |
| `tests/ingest/test_carestack_payment_summary_service.py` | modified | +201 |
| `tests/ingest/test_carestack_accounting_transaction_service.py` | modified | +140 |
| `tests/worker/test_ingest_scheduled.py` | modified | +108 |
| `tests/infra/test_backfill_payment_summary.py` | NEW | +359 |

## Tests added

### `tests/ingest/test_carestack_payment_summary_service.py` (8 new)

- `test_import_for_patients_calls_carestack_once_per_id` — sweep covers
  every input patient_id, no source-link listing involved.
- `test_import_for_patients_throttles_between_patients` — sleeps only
  between patients, never before the first.
- `test_import_for_patients_failure_isolation_continues_sweep` — one
  patient's retries exhausting bumps `error_count` and the sweep
  carries on.
- `test_import_for_patients_commits_in_batches_and_flushes_final` —
  `commit_every=2` over 5 patients → 3 commits (2 batches + final).
- `test_import_for_patients_commits_on_error_batches_too` — errors
  still count toward the commit window so raw_event writes flush
  promptly.
- `test_import_for_patients_without_commit_does_not_crash` — `commit=None`
  is a valid no-op for the caller-owns-uow path.
- `test_import_for_patients_dedups_input_preserving_order` —
  `["A","B","A","C","B"]` → 3 calls, insertion order preserved.
- `test_import_for_patients_empty_input_returns_zero_summary` — empty
  input + commit mock → zero CareStack calls, zero commits.

### `tests/ingest/test_carestack_accounting_transaction_service.py` (5 new)

- `test_import_returns_distinct_sorted_imported_patient_ids`
- `test_import_dedups_repeated_imported_patient_ids`
- `test_import_patient_ids_excludes_skipped_unlinked_and_non_payment_rows`
- `test_import_patient_ids_excludes_dedup_conflicts`
- `test_import_empty_rows_returns_empty_patient_ids`

### `tests/worker/test_ingest_scheduled.py` (1 new, 1 updated)

- `test_pull_carestack_runs_location_patient_and_appointment_services`
  was updated: the accounting fake now exposes `patient_ids=["9001","9002"]`
  and `fake_payment_summary_svc.import_payment_summary_for_patients`
  is asserted called with those ids and a `commit` kwarg.
- `test_pull_carestack_skips_live_signal_when_no_imported_patient_ids`
  (NEW) — empty `patient_ids` ⇒ the targeted sweep stays silent and
  the rolling 50-patient sweep still runs.

### `tests/infra/test_backfill_payment_summary.py` (8 NEW)

- `test_parse_args_defaults_match_spec` — `--max-patients=2000`,
  `--sleep-seconds=0.5`, `--commit-every=50`, `--dry-run=False`.
- `test_parse_args_supports_dry_run_and_overrides`.
- `test_main_returns_2_when_carestack_credential_missing` — non-zero
  exit code so cron wrappers can distinguish "no work" vs "no creds".
- `test_main_honors_max_patients_at_source_link_query` — `--max-patients=3`
  over 10 links ⇒ only 3 patient_ids forwarded; sync_run accounting
  records matching counts.
- `test_main_dry_run_does_not_touch_carestack_or_ingest_service` —
  zero CareStack client construction, zero sweep call, zero sync_run
  open, patient_ids on stdout.
- `test_main_forwards_injected_sleep_to_sweep` — sleep + sleep_seconds
  + commit_every + commit kwargs are forwarded verbatim.
- `test_main_returns_zero_without_opening_sync_run_when_no_patients`.
- `test_main_closes_sync_run_failed_when_sweep_raises` — uncaught
  sweep exception still closes the sync_run as `failed`.

## Verification

| Step | Command | Result |
|---|---|---|
| Lint (touched files) | `ruff check <touched paths>` | ✅ All checks passed |
| Lint (full repo) | `ruff check .` | ⚠️ 2 PRE-EXISTING errors in `packages/interaction/repository.py:131,140` (UP037 quoted type annotations). Confirmed identical with `git stash`. Not in ENG-305 scope. |
| Type-check | `mypy .` | ✅ Success: no issues found in 289 source files |
| Affected tests | `pytest tests/ingest tests/worker tests/infra -q -o pythonpath=.` | ✅ 261 passed |
| Broader tests | `pytest tests --ignore=tests/api --ignore=tests/integration -q -o pythonpath=.` | ✅ 763 passed |
| Verify-deploy subset | `pytest tests/core/test_env_reference_matches_settings.py tests/core/test_traffic_primary_filter.py -q -o pythonpath=.` | ✅ 25 passed |
| Alembic | `alembic check` | ⏸ Could not run — the bash sandbox blocks `env VAR=… alembic …` invocations and the worktree has no `.env`. **Drift is structurally impossible**: this ticket touches zero ORM models. The only schema change is `CareStackAccountingTransactionImportOut.patient_ids` which is a Pydantic DTO field, not a SQLAlchemy column. Confirmed `git status --short packages/db/alembic/versions/` is empty. |

Notes on the `-o pythonpath=.` flag: the shared venv at
`/Users/eduardkarionov/Desktop/Fusion_crm/.venv` has the package installed
editable against the source repo, not against this worktree. Without
`-o pythonpath=.` pytest imports `packages.ingest.*` from the source
repo and never sees the worktree's edits. The flag is the canonical
pytest knob for prepending CWD; it does not modify any repo file.

Notes on `tests/api/` and `tests/integration/`: those suites trigger
module-level `packages.db.session` imports that fail without
`SECRET_KEY` / `DATABASE_URL` / `REDIS_URL`. The worktree has no `.env`
and the bash sandbox blocks inline `VAR=… pytest …` invocations. The
failures occur with or without my changes (confirmed via `git stash`)
— this is a pre-existing worktree environment limitation that the
orchestrator integrator can run separately with a populated env.

## Risks

1. **Throttle pressure under the live signal.** With the live signal
   wired, every scheduled tick now refreshes payment-summary for every
   patient whose accounting transactions imported on that tick. In a
   busy clinic that could be tens of patients per tick. Throttle is
   the default 0.5 s/patient + the existing 429/5xx backoff in
   `_fetch_summary_with_backoff` — the live signal is well below the
   manual backfill rate. The CareStack tenant has been throttled ~24 h
   once before; if sustained 429s show up in prod logs, raise
   `sleep_seconds` on the call site or cap `accounting_transactions.patient_ids[:N]`.
2. **Rolling sweep + targeted refresh overlap.** A patient whose row
   just imported AND who would have been visited by the rolling sweep
   gets snapshotted twice in the same tick. Capture is append-only by
   design (the snapshot timeline IS the value per the module
   docstring), so the duplicate is forensic, not destructive. Net
   extra cost: one CareStack call per overlapping patient per tick.
3. **`session.commit` from inside a service.** Per `packages/CLAUDE.md`
   §"Sessions and the unit of work", services normally NEVER commit —
   only the caller boundary does. The new
   `import_payment_summary_for_patients(commit=…)` API breaks that
   convention deliberately: the worker job and the backfill script
   need batched commits because a 1000-patient sweep wrapped in one
   transaction would hold locks for minutes. The caller still owns the
   `commit` callable — the service just invokes the caller's flush at
   the cadence the caller chose. The pattern mirrors the existing
   `pull_all_since` in `carestack_accounting_transaction_service.py`
   where the caller is also in charge of the unit of work.

## Blockers / questions

None.

## Suggested next task

ENG-306 (or follow-up of operator's choice): **person card UI for
Billed / Adjustments / Paid / Balance**. The authoritative balance is
now landing in `ingest.raw_event` (event_type
`carestack.payment_summary.snapshot`) for every patient that has
moved money plus the rolling sweep coverage. The dashboard
`LatestPaymentSummaryBalancesOut` aggregate already reads the latest
per CareStack patient id — the UI ticket can wire those four numbers
into the person detail page without touching the data path.

## DO-NOT-MERGE conditions

1. **Do NOT run the real backfill script against the prod tenant
   until the user gives explicit go.** The CareStack tenant blocked
   this account for ~24 h once before — a real `backfill_payment_summary.py
   --tenant-id <prod-uuid>` on 1803 patients at 0.5 s/patient is a
   ~15-min sustained call rate. The user must approve the window.
2. **The integrator must confirm `alembic check` and `make test`
   green in an environment with a populated `.env`** before promoting
   the change. The sandbox here could not run those steps; the
   touched-area subset of `pytest` is green, `mypy` is green, and the
   ORM model surface is untouched, but the integrator owns the final
   gate.
3. **Do NOT promote the existing PRE-EXISTING `ruff check` errors as
   ENG-305's responsibility.** The 2 UP037 errors in
   `packages/interaction/repository.py:131,140` are unrelated and
   pre-date this branch (confirmed via `git stash`). They will be
   resolved by their own ticket.
