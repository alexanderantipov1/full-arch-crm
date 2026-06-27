# ENG-538-fix — Worker report (Codex review fixes, round 1)

**Task:** B1.4 — catalog by-id + ENG-511 surgery fix — apply Codex
CHANGES-REQUESTED review fixes on top of the existing ENG-538 worktree.
**Linear:** ENG-538 —
https://linear.app/fusion-dental-implants/issue/ENG-538/b14-real-carestack-procedure-code-catalog-by-id-sync-drift-detection
**Class:** contract_change. **Runtime:** claude-code. **Branch:** `eng-538-eng-538`
(existing isolated worktree off `main`).
**Status:** Review fixes COMPLETE, all changes UNCOMMITTED. Do NOT merge
(merge to `main` == prod deploy; do-not-merge conditions from the base report stand).

Full design context: `reports/ENG-538-worker-report.md` (round 0) + its new
**"Review fixes (Codex round 1)"** section. This file is the fix-round summary.

---

## What changed (2 review items)

### BLOCKER — `packages/catalog/service.py`: by-id fetch must not mask real failures
`_fetch_one_with_backoff` previously converted **every** non-retryable CareStack
status to `unresolved` (return `None`) and also returned `None` on exhausted
429/5xx retries — so 401/403/400 (auth/config) and a transient outage were
silently reported as "unresolved code", letting the backfill/job COMMIT a partial
catalog and report success. Now:

- New `_MISSING_STATUS_CODES = {404, 410}` — the **only** statuses that return
  `None` (→ non-fatal `unresolved`).
- **401 / 403 / 400 and any other non-retryable, non-missing status → RAISE**
  (logged `catalog.procedure_codes.fatal_status`).
- **Exhausted 429 / 5xx retries → RAISE** (logged
  `catalog.procedure_codes.retries_exhausted`).
- Non-CareStack-shaped errors still propagate (unchanged).

No entry-point change needed: the backfill script and weekly job already
`try/except → session.rollback() → raise` around the service call, so a raised
auth/outage failure now flows to **rollback + failed**, not commit + success.

### CONCERN — `packages/ingest/carestack_treatment_service.py`: cheap, non-repeating self-fill
- `CatalogService.ensure_procedure_codes` gained `max_retries` (default **0**)
  and `sleep_seconds` (default **0.0**): the ingest self-fill does a **single
  by-id attempt, no throttle** — it never holds the capture unit of work through
  the multi-second backoff the standalone backfill uses.
- Added a per-run, instance-scoped **negative cache**
  `_procedure_code_self_fill_misses`. An id that resolves-missing (404/410) or
  fails once (any raised error, incl. a now-propagating 401) is recorded and
  **skipped for the rest of the pull** — no repeat CareStack calls for the same
  bad id. Resets each pull (fresh service per invocation).
- Self-fill stays best-effort: `try/except` swallows+logs every failure (incl.
  hard auth) so ingest never breaks; the row keeps the generic mapping. The
  standalone (non-self-fill) backfill/job path still propagates.

## Changed files
- `packages/catalog/service.py` — `_MISSING_STATUS_CODES`; raise-on-fatal +
  raise-on-retry-exhaustion in `_fetch_one_with_backoff`; `ensure_procedure_codes`
  low-retry params.
- `packages/ingest/carestack_treatment_service.py` — negative cache + low-retry
  self-fill wiring.
- `tests/catalog/test_service.py` — +6 tests (401/403/400 propagate, 503
  retry-exhaustion propagates, 410 unresolved, ensure single-attempt).
- `tests/ingest/test_carestack_treatment_service.py` — +2 tests (negative cache
  on miss; failure negative-cached + never breaks ingest).

No migration. No schema/DTO/contract change beyond the two new optional kwargs
on `ensure_procedure_codes` (additive, internal to catalog/ingest).

## Tests run / verification
- **ruff check** — PASS (4 touched files).
- **mypy** — PASS (`packages/catalog/service.py`,
  `packages/ingest/carestack_treatment_service.py`).
- **pytest** — `tests/catalog tests/ingest` → **482 passed** (incl. all new
  tests); `tests/infra/test_backfill_procedure_codes.py` → 7 passed;
  `tests/ingest/test_procedure_code_worklist.py` → passed.

## Risks
- Self-fill now makes a single attempt only; a one-off transient blip during
  ingest leaves that code generic-mapped for the rest of the pull (negative
  cached). Acceptable + intended — the weekly job / backfill (full backoff)
  reconcile it, and ENG-511 self-heals on the next pull. Steady-state the
  catalog is filled so self-fill rarely fires.
- Negative cache is in-memory and per-pull only — no cross-run persistence
  (by design; a new pull re-attempts).

## Blockers
- None functional. Only the env-limited worker-job test execution (below).

## Do-not-merge conditions
- **Do NOT merge / push / deploy from this worker** (merge to `main` =
  unattended prod deploy + prod migration). Gated on operator approval AND Codex
  cross-runtime re-review (contract_change).
- Env-limited gap (unchanged from round 0):
  `tests/worker/test_carestack_procedure_codes_pull_job.py` cannot collect in
  this sandbox (import-time `packages.db.session` needs
  `SECRET_KEY`/`DATABASE_URL`/`REDIS_URL`; no `.env` here, editing `.env*`
  forbidden). Worker job code unchanged this round; the BLOCKER path is covered
  by the existing `test_pull_for_tenant_rolls_back_when_service_raises`. Must run
  green under CI env before merge.
- Pre-existing failures unrelated to this task (in untouched files):
  `test_carestack_appointment_service.py::test_map_status_known_values` (fails on
  HEAD), `test_ingest_idempotency_sql.py` (DB/`.env` gap).
- `D6010.A` / `D6011NC` surgery-set entries remain operator-confirmed; any
  further change is a new operator decision (decision-log).
