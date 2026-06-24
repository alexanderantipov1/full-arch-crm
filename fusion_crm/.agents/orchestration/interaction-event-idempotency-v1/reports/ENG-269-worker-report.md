# ENG-269 — Worker Report

- **Task id:** ENG-269
- **Linear:** [ENG-269 — Idempotent interaction.event emission + dedupe existing](https://linear.app/fusion-dental-implants/issue/ENG-269/idempotent-interactionevent-emission-stop-re-pull-duplication-5-dedupe)
- **Role / agent:** worker / claude-code
- **Branch:** `eng-269-eng-269`
- **Worktree:** `~/.fusion-agent-orchestrator/c2db50910d08/interaction-event-idempotency-v1/worktrees/ENG-269/`
- **Allowed scope:** migration + interaction service + CareStack ingest callers + tests + decision-log
- **Status:** report-ready (verify loop green, committed to worktree branch, ready for orchestrator integration — do NOT touch main, do NOT push)

## What changed

### A. Migration (new revision, immutable once shipped)

- **`packages/db/alembic/versions/20260530_0600_f4a5b6c7d8e9_idempotent_interaction_event_dedupe.py`** (new)
  - `down_revision = "e3f4a5b6c7d8"` (previous head).
  - `upgrade()` dedupes existing `interaction.event` rows server-side via one window-function DELETE:
    keeps the earliest row per `(tenant_id, source_provider, source_kind, source_external_id, kind)` where `source_external_id IS NOT NULL AND source_kind IS NOT NULL`, ordered `(created_at ASC, id ASC)`.
  - `upgrade()` then `CREATE UNIQUE INDEX uq_event_provider_source_kind ON interaction.event (tenant_id, source_provider, source_kind, source_external_id, kind) WHERE source_external_id IS NOT NULL`.
  - `downgrade()` drops the index only — does NOT resurrect deleted rows (the docstring is explicit; forensic replay is via `ingest.raw_event`).

### B. Model + service

- **`packages/interaction/models.py`** — reflected the new partial UNIQUE as a sibling `Index(...)` next to the legacy `uq_event_source`, matching the migration's columns and `postgresql_where` exactly. `alembic check` reports no drift.
- **`packages/interaction/service.py`**
  - Added `EventEmissionResult(event, was_created)` (frozen dataclass).
  - Added `create_event_idempotent(tenant_id, payload) -> EventEmissionResult` — wraps the INSERT in `session.begin_nested()` (SAVEPOINT), catches `IntegrityError`, and on conflict tries the **new cross-pull key first** (`find_provider_event_by_external_id` — re-pulls produce a fresh `source_event_id`, so legacy lookup would miss) then falls back to the legacy `(source_provider, source_event_id)` key. On either match, returns the existing row with `was_created=False`. On unresolved conflict, the original `IntegrityError` is re-raised — silent swallow only happens when we can prove which row collided.
  - `create_event(...)` preserved as a thin wrapper that drops the `was_created` flag, so existing callers compile unchanged.
- **`packages/interaction/repository.py`** — unchanged (data-only contract preserved).

### C. CareStack ingest callers (the actual dupe source)

Switched the three CareStack handlers that had no `was_changed` pre-check to use `create_event_idempotent` and treat `was_created=False` as `"skipped"`:

- `packages/ingest/carestack_invoice_service.py` (`_capture_invoice`)
- `packages/ingest/carestack_treatment_service.py` (`_capture_treatment_procedure`)
- `packages/ingest/carestack_accounting_transaction_service.py` (the payment-folio emit branch)

Other ingest callers were intentionally left on `create_event`:

- `sf_lead_service`, `sf_event_service`, `consultation_timeline.emit_consultation_timeline_event` are gated on `was_changed` (re-pulls without a state change don't reach `create_event` at all).
- `sf_task_service`, `sf_opportunity_service`, `sf_case_service` use `_find_existing_task_event` / `_create_event_once` pre-checks. The new DB constraint still protects them as a backstop; their counters already treat the no-op correctly.

### D. Tests added / updated

- **`tests/interaction/test_models.py`** — added `test_event_provider_source_kind_partial_unique_index` asserting the new partial UNIQUE shows up on `Event.__table__.indexes` with the right columns + predicate.
- **`tests/interaction/test_service.py`**
  - `_make_service()` now wires `session.begin_nested = AsyncMock(return_value=savepoint)` so every unit test sees a usable savepoint mock.
  - Updated `test_create_event_returns_existing_on_partial_unique_collision` to assert against the savepoint, not the session, and to drive the new "try-new-key-then-legacy" lookup path.
  - Added `test_create_event_returns_existing_on_provider_source_kind_collision` — the re-pull case (fresh `source_event_id`, conflict on the new key, looked up via `find_provider_event_by_external_id`, legacy lookup not called).
  - Added `test_create_event_idempotent_returns_was_created_true_on_insert` and `test_create_event_idempotent_returns_was_created_false_on_conflict` — the new API surface.
  - Added `test_create_event_idempotent_different_kind_same_external_id_inserts` — `treatment_proposed` and `treatment_completed` on the same `procedure_id` both succeed (`kind` is part of the dedup key).
  - Kept `test_create_event_reraises_when_existing_not_found_after_collision` and `test_create_event_reraises_integrity_when_source_event_id_is_none` — both lookups miss → IntegrityError surfaces.
- **`tests/ingest/test_carestack_invoice_service.py`, `tests/ingest/test_carestack_treatment_service.py`, `tests/ingest/test_carestack_accounting_transaction_service.py`**
  - Mocks switched from `spec=["create_event"]` to `spec=["create_event_idempotent"]` returning `SimpleNamespace(event=..., was_created=True)` by default.
  - Added one `test_cross_pull_conflict_counts_as_skipped_not_imported` per service: mocks `was_created=False`, asserts `imported_count == 0`, `skipped_count == 1`, and that the `raw_event.capture` still fired (capture-then-route survives).

## Tests run

| Command | Result |
| --- | --- |
| `ruff check .` | All checks passed |
| `mypy packages apps` | Success: no issues found in 183 source files |
| `pytest -q` (whole suite, env from main `.env`) | **930 passed in 15.16s** |
| `cd packages/db && alembic check` | `No new upgrade operations detected.` |
| `alembic upgrade head` then `alembic downgrade -1` then `alembic upgrade head` | Round-trip clean (`e3f4a5b6c7d8` ↔ `f4a5b6c7d8e9`) |
| Live DB `create_event_idempotent` re-emit (Python integration probe) | `was_created=False`, event count unchanged, `ingest.raw_event` survived the savepoint rollback |

## Verification status

**Green.** All acceptance items satisfied:

- New revision shipped with working downgrade; the DELETE is migration-only (runtime service stays append-only).
- `create_event_idempotent` never raises on either partial UNIQUE conflict; returns the existing row with `was_created=False`.
- Local DB post-upgrade: `count(*) == count(distinct source_external_id)` per kind across all 15 emitted kinds.
- `Collected` total (sum of `payment_recorded.payload.amount`) = **$38,178.20** — exactly the deduped figure from the mission goal.
- Re-pull is now idempotent (verified end-to-end against live Postgres).
- No PHI in logs (no logging changes). `except Exception` only (no BaseException). All repo files in English.

### Local-DB dedup numbers (one-time, captured before/after `alembic upgrade head`)

| kind | before total | before distinct | after total |
| --- | --- | --- | --- |
| invoice_created | 880 | 176 | 176 |
| payment_recorded | 310 | 62 | 62 |
| payment_reversed | 1210 | 242 | 242 |
| treatment_completed | 1000 | 200 | 200 |
| treatment_proposed | 1500 | 300 | 300 |
| lead_updated | 3031 | 1929 | 1929 |
| consultation_rescheduled | 109 | 105 | 105 |
| _(other kinds — already distinct)_ | — | — | — |
| **TOTAL** | **17158** | **12132** | **12132 (5026 rows deleted)** |

## Risks

- **Append-only contract exception.** The migration DELETEs from `interaction.event`. Recorded in `decision-log.md`; the runtime `InteractionService` exposes no update/delete methods. Future migrations doing similar one-time data fixes should follow the same pattern (single Alembic revision, no runtime API change).
- **Two partial UNIQUE indexes on the same table.** `uq_event_source` (legacy, on `source_provider, source_event_id`) stays; `uq_event_provider_source_kind` (new) is additive. Insert path executes both checks. Index storage cost on `interaction.event` is modest (~12k rows post-dedup).
- **NULL columns in the dedup key.** PostgreSQL treats NULLs as distinct in multi-column UNIQUE, so rows with NULL `source_kind` (but non-null `source_external_id`) would not collide. The migration's DELETE explicitly skips those rows (`source_kind IS NOT NULL`) so dedup and index agree on scope. In practice every emit caller sets `source_kind`; this is defensive.
- **Index does not cover concurrent inserts at high QPS.** Theoretical race between two workers inserting the same key in parallel still possible at the row-insert phase, but the constraint + savepoint resolves it to "second writer reads existing" rather than "duplicate row". Not a new risk — same shape as the legacy `uq_event_source` index.
- **Migration runs the DELETE inside the same transaction as the index creation.** On large prod tables this is a single statement and should be fast (~5026 rows locally). If prod has materially more rows, the DELETE could lock the table longer; acceptable because the prod alembic Job runs on deploy with the API quiesced.

## Blockers / open questions

None. Ready for verifier and integrator.

## Suggested next task

- Orchestrator: integrate to `main` and trigger the prod alembic Job (the migration is a deploy-gated one-time data fix).
- Optional follow-up (NOT in this scope): the SF callers that pre-check via `_find_existing_task_event` could simplify by deleting the pre-check and relying on the new DB constraint — cleaner code, one less DB round-trip per row. Defer until someone has a reason to touch those files.

## Do-not-merge conditions

- Do NOT push or merge to `main` from this worktree; the orchestrator handles integration.
- Do NOT amend the migration filename or `revision`/`down_revision` once this report is in — migrations are immutable once shipped.
- Do NOT roll the dedupe DELETE into a model/service `delete_event` method; the append-only runtime contract stays.
