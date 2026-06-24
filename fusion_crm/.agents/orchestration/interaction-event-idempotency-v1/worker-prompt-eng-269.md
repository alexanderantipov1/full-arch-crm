You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: ENG-269
(https://linear.app/fusion-dental-implants/issue/ENG-269). Isolated git worktree
on your own branch. Implement → verify → write a report. Do NOT touch `main`, do
NOT push, do NOT open a PR. Commit to YOUR worktree branch only once green; the
Orchestrator integrates.

## Problem
Ingest services emit `interaction.event` rows on EVERY pull with no dedup, so
re-pulls duplicate timeline events ×(pull count) — measured ×5. Dashboard money
is inflated (Collected shows $190,891; real deduped $38,178). `raw_event` is
idempotent; the event layer is not. Fix it at the event layer.

## Read first
- `packages/interaction/{models,repository,service,CLAUDE.md}` — the event model,
  `create_event`, the existing CHECK constraints, and the append-only note.
- A recent migration for the pattern:
  `packages/db/alembic/versions/20260529_1500_e3f4a5b6c7d8_extend_event_kinds_for_carestack_payments.py`.
- The emit callers in `packages/ingest/*` (carestack invoice/treatment/accounting,
  sf_event/sf_task/etc.) — they call `InteractionService.create_event`.

## Task

### A. Migration (new revision; down_revision = current `alembic heads`)
1. **Dedupe existing rows** in `upgrade()`: delete duplicate `interaction.event`
   rows, keeping the earliest per
   `(tenant_id, source_provider, source_kind, source_external_id, kind)` where
   `source_external_id IS NOT NULL`. Keep the row with the smallest
   `created_at` (tie-break smallest `id`). Use a single SQL statement (e.g.
   `DELETE ... USING (SELECT ... row_number() OVER (PARTITION BY ... ORDER BY
   created_at, id)) ...` or a NOT IN min(id) subquery). Do it in raw SQL via
   `op.execute(...)` so it runs server-side.
2. **Add a partial UNIQUE INDEX** on
   `(tenant_id, source_provider, source_kind, source_external_id, kind)`
   `WHERE source_external_id IS NOT NULL` (name it e.g.
   `uq_event_provider_source_kind`).
3. `downgrade()` drops the index only (does not resurrect deleted rows — note in
   the docstring).
4. Reflect the index in `packages/interaction/models.py` (add the
   `Index(..., postgresql_where=...)` / `UniqueConstraint` analog so `alembic
   check` sees no drift). Match the migration EXACTLY.

### B. Idempotent emission
1. `InteractionRepository.create_event` (and the `InteractionService` wrapper):
   insert with `ON CONFLICT DO NOTHING` against the new unique index (use
   `postgresql.insert(...).on_conflict_do_nothing(index_elements=[...])` with the
   partial-index predicate, or catch `IntegrityError` and roll back to a savepoint).
   On conflict, return the existing row (look it up) OR a clear "skipped" signal —
   NEVER raise. Preserve the existing return contract as much as possible.
2. Ingest callers that count imported/skipped must count a conflict as **skipped**,
   not imported, and not as an error. Keep the raw_event capture unchanged
   (still happens every pull — that's fine and intended).

## Hard constraints
- Migrations are immutable once shipped: NEW revision only; working downgrade.
- The DELETE lives ONLY in the migration (a one-time data fix). Do NOT add
  update/delete methods to the interaction runtime service — the append-only
  service contract stays. (This exception is recorded in decision-log.md.)
- No PHI in logs. `except Exception` only (never BaseException). English only.
- Cross-domain rules per `packages/CLAUDE.md`.

## Definition of done
1. `make lint` ; `mypy .` ; `make test` ; `cd packages/db && alembic check` green.
2. Migration round-trips: `alembic upgrade head` → `downgrade -1` → `upgrade head`.
3. After upgrade on the local DB (which currently HAS duplicates), verify per-kind
   `count(*) == count(distinct source_external_id)` and a re-pull keeps counts flat.
4. Commit to your worktree branch only once green.
5. Write `.agents/orchestration/interaction-event-idempotency-v1/reports/ENG-269-worker-report.md`
   (changed files, dedup SQL approach, how many rows the migration deleted locally,
   idempotency mechanism, tests, migration round-trip result, risks, do-not-merge).
6. If you hit a design wall (e.g. a kind legitimately needs multiple rows per
   source_external_id), STOP and write `Needs decision:`.

## Tests
- create_event twice with the same key → one row, second is a no-op (no raise).
- same source_external_id, different kind → two rows.
- source_external_id NULL → unconstrained (multiple allowed).
- A focused test (or DB-backed) proving the migration collapses duplicates.
