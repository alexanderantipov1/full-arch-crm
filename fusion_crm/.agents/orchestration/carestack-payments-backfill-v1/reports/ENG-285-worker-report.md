# ENG-285 — Throttled 2026 CareStack payments backfill — Worker Report

- **Task**: ENG-285 (Linear: https://linear.app/fusion-dental-implants/issue/ENG-285)
- **Role / Agent**: worker / claude-code
- **Runtime / Session**: claude-code / `ba8e8807ffc6`
- **Worktree branch**: `eng-285-eng-285`
- **Allowed scope**: backend-only (FastAPI router + ingest services + tests).
  No migration, no schema, no frontend, no cron change.

## What changed

Added an operator-triggered, rate-limit-safe historical backfill of CareStack
accounting-transactions (the partial-payment ledger feeding the Collected /
refund / reversal totals) and payment-summary snapshots (the per-patient
outstanding balance feed) for 2026. Both paths reuse the existing ingest
services unchanged for capture + classification — the new code is an
unbounded-but-throttled pagination wrapper on top.

### Touched files

| File | Change |
| --- | --- |
| `packages/ingest/carestack_accounting_transaction_service.py` | New `pull_all_since(...)` method + `_fetch_page_with_backoff(...)` helper + retry-classifier helpers (`_is_retryable_carestack_error`, `_carestack_error_status`). Defaults: `since=2026-01-01T00:00:00Z`, `page_size=500`, `page_safety_cap=2000`, `sleep_seconds=0.5`, `max_retries=5`, `backoff_base_seconds=1.0`. |
| `packages/ingest/carestack_payment_summary_service.py` | New `pull_all_payment_summaries(...)` method + `_fetch_summary_with_backoff(...)` helper + `_carestack_error_status`. Defaults: `max_patients=10000`, `sleep_seconds=0.5`, `max_retries=5`, `backoff_base_seconds=1.0`. |
| `apps/api/routers/backfill.py` | Two new `EntityName` literals (`carestack_accounting_transactions`, `carestack_payment_summary`), two new `_run_*` leg helpers, sync_run journaling. Operator-omitted `since` resolves to **2026-01-01** for the AT leg (override-able from the request body). |
| `apps/api/dependencies.py` | Two new FastAPI dependencies (`get_carestack_accounting_transaction_ingest_service`, `get_carestack_payment_summary_ingest_service`) plus stubbed methods on `_UnavailableCareStackClient` so missing credentials close the sync_run as `skipped_credential` instead of raising. |
| `tests/ingest/test_carestack_accounting_transaction_service.py` | +10 tests covering pagination, throttle sleep, 429/5xx retry+backoff, resume token on exhausted retries, safety cap, non-retryable propagation, idempotent re-run via `create_event_idempotent`, argument validation, naive-since UTC fallback. |
| `tests/ingest/test_carestack_payment_summary_service.py` | +8 tests covering unbounded sweep, throttle sleep, 429 retry, per-patient error isolation, skip-on-blank-source-id, empty tenant, argument validation, safety cap propagation. |
| `tests/api/test_backfill.py` | +6 tests covering the two new entities in `POST /backfill/run`: sync_run open/close, default-since anchoring at 2026-01-01, operator override, resume-token propagation, credential-missing → `skipped_credential`, provider failure → `failed`. |

### Files I did NOT touch

- No Alembic revisions (rule).
- No `.env*` (rule).
- No frontend (`apps/web/...`) — out of scope.
- No cron / scheduled-job code (`apps/worker/jobs/ingest_scheduled.py`)
  — the scheduled `import_recent_accounting_transactions` path stays
  capped at `max_pages=5` exactly as it was.

## How to invoke

The new entities ride the existing `POST /backfill/run` endpoint.

### Accounting transactions (the cash ledger driving Collected)

```bash
curl -X POST 'http://localhost:8000/backfill/run' \
  -H 'Content-Type: application/json' \
  -d '{
    "entities": ["carestack_accounting_transactions"]
  }'
```

Omitting `since` anchors at **2026-01-01T00:00:00Z** (the fiscal year being
reconstructed). Supply `since` explicitly to override:

```bash
curl -X POST 'http://localhost:8000/backfill/run' \
  -H 'Content-Type: application/json' \
  -d '{
    "since": "2026-03-15T00:00:00Z",
    "entities": ["carestack_accounting_transactions"]
  }'
```

### Payment-summary snapshot sweep (per-patient balances)

```bash
curl -X POST 'http://localhost:8000/backfill/run' \
  -H 'Content-Type: application/json' \
  -d '{
    "entities": ["carestack_payment_summary"]
  }'
```

`since` is not meaningful here — CareStack has no bulk feed for balances; the
sweep walks every linked CareStack patient point-in-time. Capture is
append-only and the dashboard reads the LATEST snapshot per patient, so
re-runs are safe and add fresh snapshots.

### Both at once

```bash
curl -X POST 'http://localhost:8000/backfill/run' \
  -H 'Content-Type: application/json' \
  -d '{
    "entities": [
      "carestack_accounting_transactions",
      "carestack_payment_summary"
    ]
  }'
```

### Response shape

Each leg returns `EntityBackfillOut`:

```json
{
  "entity": "carestack_accounting_transactions",
  "imported": 1280,
  "skipped": 17,
  "pages": 23,
  "next_continue_token": null,
  "sync_run_id": "uuid",
  "sync_run_status": "succeeded",
  "error": null
}
```

When backoff is exhausted mid-sweep, `next_continue_token` carries the
last `continueToken` from CareStack. The operator re-invokes the same
endpoint to resume — re-emission is deduped at the event layer
(`create_event_idempotent`, ENG-269), so the partial work from the
first run is not duplicated.

## Throttle / backoff defaults

| Knob | Default | Rationale |
| --- | --- | --- |
| `sleep_seconds` (between pages / between patients) | **0.5s** | Keeps the unbounded sweep well below CareStack's rate limit; gentle enough that a 5000-page backfill takes ~42 minutes. |
| `max_retries` per page / per patient | **5** | Five doublings of `backoff_base_seconds=1.0` = up to 31s of cumulative back-off (1+2+4+8+16) before giving up. |
| `backoff_base_seconds` | **1.0** | First retry waits 1s, then 2, 4, 8, 16. |
| `page_safety_cap` (AT) | **2000** pages | At `page_size=500` that's 1M rows — comfortably above any realistic 2026 history but a hard ceiling against an infinite continueToken loop. |
| `max_patients` (payment summary) | **10000** | Defensive ceiling against an unbounded tenant table; today's tenant has ~1k linked patients. |
| Retryable status codes | **429, 500, 502, 503, 504** | 429 is CareStack's explicit rate-limit signal; the 5xx set covers transient upstream outages. Everything else (401, 4xx other than 429, …) propagates without retry so the leg helper can close the sync_run as `skipped_credential` or `failed`. |

All knobs are kwargs on `pull_all_since` / `pull_all_payment_summaries` —
the operator can override per call, but the router today uses defaults
only (no plumbing for per-request overrides — separate ticket if
needed).

## Resume behaviour

1. The throttled loop pages through CareStack via `continueToken` until
   exhausted, the safety cap is hit, or backoff exhausts on a page.
2. On backoff exhaustion, the loop **stops** and the service returns
   the current `continue_token` (the one CareStack returned with the
   last successful page) inside `CareStackAccountingTransactionImportOut.next_continue_token`.
3. The router surfaces that token in the response as
   `legs[].next_continue_token`.
4. The operator re-invokes `POST /backfill/run` with the same entity
   scope. Idempotency:
   - Raw events are re-captured (forensic; intentional).
   - `interaction.event` rows are deduped at the
     `create_event_idempotent` layer (ENG-269), so the second run
     reports `imported_count == 0` for any row already promoted to a
     timeline event.
5. The `next_continue_token` from the second run reflects where THAT
   loop stopped — chain re-invokes until the response carries a `null`
   token.

## Tests run

All CareStack interactions are mocked. No test issues a real CareStack
HTTP call (asserted by the suite: the mock client object is the only
thing the services call into, and the `_FakeCareStackApiError`
duck-types via `.details` to drive the retry path).

| Suite | Status |
| --- | --- |
| `tests/ingest/test_carestack_accounting_transaction_service.py` (63 tests, 10 new) | ✅ PASS |
| `tests/ingest/test_carestack_payment_summary_service.py` (16 tests, 8 new) | ✅ PASS |
| `tests/api/test_backfill.py` (15 tests, 6 new) | ✅ PASS |
| Full unit suite (816 tests) | ✅ PASS |
| Full suite incl. integration (1001 tests) | ✅ PASS |

Key new tests (mocked client, all green):

- **Multi-page loop stops on null `continueToken`** —
  `test_pull_all_since_paginates_until_null_continue_token` (AT),
  `test_pull_all_walks_every_linked_patient_unbounded` (PS).
- **Throttle sleep invoked between pages / patients** —
  `test_pull_all_since_sleeps_between_pages_but_not_after_last_page`,
  `test_pull_all_sleeps_between_patients_but_not_after_last`.
- **429/5xx triggers backoff then succeeds** —
  `test_pull_all_since_retries_with_exponential_backoff_on_429_then_succeeds`,
  parametrised across `{429,500,502,503,504}`;
  `test_pull_all_retries_with_exponential_backoff_on_429` (PS).
- **Retries exhausted → resume token returned** —
  `test_pull_all_since_returns_resume_token_when_retries_exhausted`,
  `test_pull_all_counts_patient_as_error_when_retries_exhausted` (PS,
  failure-isolation variant).
- **Safety cap** — `test_pull_all_since_stops_at_page_safety_cap_and_returns_token`,
  `test_pull_all_honours_max_patients_safety_cap`.
- **Non-retryable errors propagate** —
  `test_pull_all_since_propagates_non_retryable_errors` (AT — 401 bubbles up).
- **Idempotent re-run** —
  `test_pull_all_since_idempotent_rerun_via_create_event_idempotent`
  (proves `was_created=False` collapses second run to `imported_count == 0`).
- **sync_run recorded** —
  `test_cs_accounting_transactions_leg_opens_and_closes_sync_run`,
  `test_cs_payment_summary_leg_opens_and_closes_sync_run`,
  `test_cs_payment_summary_credential_error_closes_skipped_credential`,
  `test_cs_accounting_transactions_provider_failure_closes_failed`.

## Verification

```text
make lint                 # ✅ ruff: All checks passed!
mypy .                    # ✅ no NEW errors. 4 pre-existing errors in
                          #    tests/integration/test_strict_payment_code_classify.py
                          #    inherited from ENG-284 (commit d9f2d16) — not in
                          #    ENG-285 scope.
make test                 # ✅ 1001 passed
cd packages/db && \
  alembic check           # ✅ "No new upgrade operations detected."
```

## Risks

- **Reuses existing classification path.** The pull_all_since loop
  delegates to `_capture_transaction`, which calls the unchanged
  ENG-284 strict allow-list classifier. Any classification bug shipped
  by ENG-284 will be amplified by a 2026-wide backfill (more rows
  routed). Mitigation: the strict allow-list is well-tested at the
  classifier level (`test_payment_event_kind_helper_covers_locked_decisions`),
  and the operator can compare aggregate Collected before/after on the
  PM Payments dashboard to spot drift.
- **Defaults are conservative but not zero-risk.** A 5000-page backfill
  at `sleep_seconds=0.5` takes ~42 minutes wall-clock. The operator
  should run the backfill OFF-HOURS for the dental clinic — peak
  CareStack traffic during business hours combined with the backfill
  could still tickle the rate limit even at 0.5s/page. Knob is
  available; raise to 1.0s if the first run gets close to a 429.
- **Per-tenant scope only.** Both legs read tenant from the request
  principal (`principal.require_tenant()`). The single-tenant Phase 1
  resolver is in `get_tenant_id` (uses `Settings.tenant_default_slug`)
  — runs against the operator's home tenant. Multi-tenant rollout
  needs the same wrapper the SF / CS patients legs would need (out of
  scope for ENG-285).
- **No background-job wrapper.** Like the other backfill legs, this
  runs inline on the HTTP request. A 42-minute backfill request will
  occupy one uvicorn worker for the duration. For prod this should
  move to an arq job (Phase 4 in the existing `backfill.py` module
  docstring — separate ticket).

## Do-not-merge conditions

- ⛔ **Do NOT merge if the operator has run the backfill against
  the real CareStack tenant.** The Mission Orchestrator owns the real
  run; this worker has not executed it. Per the absolute-rules block
  in the worker prompt: *the real backfill run is an operator action
  the Orchestrator performs AFTER merge — NOT you.* If any real
  CareStack traffic was issued from this worktree (it was not),
  flag it and pause.
- ⛔ **Do NOT merge if `make lint`, `mypy .`, or the unit test suite
  is red.** Today they are green except for the 4 pre-existing mypy
  errors in `tests/integration/test_strict_payment_code_classify.py`
  inherited from ENG-284 — fix those in their own ticket, not this PR.
- ⛔ **Do NOT change `sleep_seconds` to 0 in `apps/api/routers/backfill.py`
  without explicit operator approval.** A zero throttle would page
  CareStack as fast as the network allows and is exactly the loop
  that previously triggered the ~24-hour rate-limit ban.
- ⛔ **Do NOT run the backfill against production during clinic
  business hours.** Off-hours only on the first real run; tune
  `sleep_seconds` upward if the response shows even one 429 retry.

## Blockers / questions

None blocking. Possible follow-ups (NOT part of ENG-285):

- Wire the throttle / backoff knobs into the request body so the
  operator can tune them per-call without a code change.
- Move backfill execution to an arq background job (Phase 4 per the
  router module docstring) so the HTTP request returns immediately
  with a `sync_run_id` the operator can poll.
- Add a sync-run history UI surface for the PM dashboard (existing
  ticket per the router module docstring).

## Suggested next task

Hand to Orchestrator / Verifier. Once merged, the Orchestrator runs
the real backfill (off-hours), starting with `entities=["carestack_accounting_transactions"]`
alone, observes the response for any non-null `next_continue_token`,
re-invokes if needed, and only then runs the payment-summary leg.

— end of report —
