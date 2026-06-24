You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: ENG-285
(https://linear.app/fusion-dental-implants/issue/ENG-285). Isolated git worktree.
Implement → verify → write a report. Do NOT touch `main`, do NOT push, do NOT open
a PR. Commit to YOUR worktree branch only once green; the Orchestrator integrates.

## Mission
Add an operator-triggered, RATE-LIMIT-SAFE historical backfill of CareStack
accounting-transactions (+ payment-summary) for 2026. Backend only, no migration.

## ⚠️ ABSOLUTE RULES (read twice)
- **Your tests MUST mock the CareStack client. Do NOT make a single real CareStack
  HTTP call during development or in tests.** CareStack rate-limited this project
  for ~24 hours before; a stray real loop could do it again. The real backfill run
  is an operator action the Orchestrator performs AFTER merge — NOT you.
- The backfill itself must be gentle when it eventually runs: throttle + backoff +
  resumable (see below).

## Read first
- `apps/api/routers/backfill.py` — the operator backfill router
  (`POST /backfill/run`, `_run_cs_patients`, `_run_cs_appointments`, sync_run
  journaling). Mirror these.
- `packages/ingest/carestack_accounting_transaction_service.py` +
  `packages/ingest/carestack_payment_summary_service.py` — the ingest services
  (capture + ENG-284 classification). They already paginate with `max_pages`;
  you'll add a since-based, unbounded-but-throttled backfill path.
- `packages/integrations/carestack/client.py` —
  `list_accounting_transactions_modified_since` (continueToken).

## Task (backend)
1. Add `_run_cs_accounting_transactions` and `_run_cs_payment_summary` to the
   backfill router, wired into `POST /backfill/run` scope options
   (`carestack_accounting_transactions`, `carestack_payment_summary`).
2. Backfill loop (in the router helper or a service method):
   - `since` datetime param (default `2026-01-01T00:00:00Z`).
   - Page through ALL pages via continueToken — NOT the scheduled 5-page cap — with
     a configurable **sleep between pages** (default ~0.5–1.0s).
   - **Backoff**: on a rate-limit/5xx error from the client, exponential backoff +
     bounded retries; if retries exhausted, STOP and return the last continueToken
     so the operator can resume. Never hammer.
   - A high safety cap on total pages (e.g. 2000) to avoid an infinite loop.
   - Idempotent (raw_event dedupe + ENG-269 idempotent emission) — re-runs safe.
   - Record a `sync_run` like the other backfill steps; return counts + resume token.
3. Reuse the ENG-284 classification unchanged (payment events only for payment
   codes). Do NOT change the scheduled cron.

## Hard constraints
- Read-only CareStack (GET). No migration, no schema, no frontend.
- No PHI in logs. `except Exception` only (never BaseException). English only.
  Cross-domain rules per `packages/CLAUDE.md`.

## Definition of done
1. `make lint` ; `mypy .` ; `make test` ; `cd packages/db && alembic check` green —
   with ALL CareStack interactions MOCKED.
2. Tests (mocked): multi-page loop stops on null continueToken; throttle sleep
   invoked between pages (patch the sleep); a 429/5xx triggers backoff then returns
   a resume token; idempotent re-run; sync_run recorded. Assert NO real HTTP call.
3. Commit to your worktree branch only once green.
4. Write `.agents/orchestration/carestack-payments-backfill-v1/reports/ENG-285-worker-report.md`
   with: how to invoke (`POST /backfill/run` body), throttle/backoff defaults,
   resume behaviour, tests, verification, risks, do-not-merge.
5. If unsure about an interface, MOCK it and document; never call CareStack for real.
