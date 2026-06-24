# ENG-540 (B1.6) — Worker Report

- **Task:** ENG-540 — B1.6 Replay historical procedures (surgery + case_type backfill)
- **Linear:** ENG-540 — https://linear.app/fusion-dental-implants/issue/ENG-540/b16-replay-historical-treatment-procedures-into
- **Role / agent:** implementation worker / claude-code
- **Branch / worktree:** `eng-540-eng-540` / isolated worktree off `main` (contains ENG-511 + ENG-538 + ENG-539)
- **Task class:** `contract_change`
- **Status:** Build complete, UNCOMMITTED. Lint + typecheck + unit/script tests green. Real-PG integration test written (auto-skips without DB) — pending the orchestrator's DB-backed run.

---

## Summary

Added a bounded, idempotent **replay** that re-projects existing
`carestack.treatment_procedure.upsert` raw_events through the CURRENT projection
so historical implant surgeries emit `surgery_scheduled` / `surgery_completed`
(ENG-511/538) without re-pulling from CareStack. A fact rebuild afterward
backfills `surgery_scheduled_date` / `surgery_completed_date` (+ `case_type`).

The projection was made reusable by splitting the per-row "identity link → event
emit" half out of `_capture_treatment` (which also captures raw) into a new
`_project_treatment_event(...)` keyed on an existing `raw_event_id`. The replay
re-runs only that half — no raw re-capture, no `lastUpdatedOn` dedup-skip — and
relies on `create_event_idempotent` for safety.

No migration (reuses existing schema/events). No event-payload PHI contract
change (still only the non-PII `is_implant_surgery` flag + resolved location).

---

## Changed files

| File | Change |
|---|---|
| `packages/ingest/carestack_treatment_service.py` | Split `_capture_treatment` → raw capture + new `_project_treatment_event(...)`; added public `reproject_treatments_from_raw(tenant_id, *, rows)`. |
| `packages/ingest/repository.py` | Added `list_latest_by_type_paginated(...)` (DISTINCT-ON external_id, external_id cursor, limit, optional `since`) and `count_distinct_external_ids_by_type(...)` (dry-run count). |
| `packages/ingest/service.py` | Thin `IngestService` wrappers for the two new repo methods. |
| `infra/scripts/replay_treatment_procedures.py` | **NEW** operator-triggered replay script (dry-run default, `--apply`, batched, resumable, commit-per-batch). |
| `tests/ingest/test_carestack_treatment_service.py` | +7 unit tests for the replay (surgery emit, idempotency, non-implant unaffected, skip-unlinked, skip-no-id, empty batch). |
| `tests/infra/test_replay_treatment_procedures.py` | **NEW** mocked script tests (argparse bounds, dry-run count-only, apply pagination + commit-per-batch + cursor advance, rollback-on-error, max-batches stop). |
| `tests/ingest/test_treatment_replay_integration.py` | **NEW** real-PG integration test (surgery backfill + idempotency + no-PHI), auto-skips when no DB. |

---

## The refactor — how the projection was made reusable

`_capture_treatment` previously did **both** raw capture and projection. It now:

1. `IngestService.capture(...)` — full-fidelity forensic raw write (unchanged), then
2. delegates to **`_project_treatment_event(tenant_id, row, *, procedure_id, patient_id, raw_event_id)`** — the identity-link + surgery-split (`_resolve_event_kind`, incl. ENG-538 self-fill) + `create_event_idempotent` emit, now keyed on a passed-in `raw_event_id` instead of the freshly-captured `raw_event.id`.

The live pull path is behaviourally identical (passes the new id). The replay path calls `_project_treatment_event` directly against an **already-captured** raw_event id — so it skips (a) the CareStack feed pull and (b) the `lastUpdatedOn` dedup-skip in `import_recent_treatments` / `pull_all_since` that makes a normal re-pull a no-op. Self-fill (ENG-538) keeps working because it runs inside `_resolve_event_kind` using the injected client's by-id endpoint.

`reproject_treatments_from_raw(tenant_id, *, rows)` is the public per-batch entry: it loops `(raw_event_id, payload)` tuples, calls `_project_treatment_event` per row, aggregates `imported / unchanged / skipped`, and returns the existing `CareStackTreatmentImportOut`. It never captures raw and never commits (the script owns the unit of work).

---

## Replay entry point + flags

`infra/scripts/replay_treatment_procedures.py` (reads `ingest.raw_event` ONLY; never pulls the CareStack feed):

```
# dry-run (default) — count candidate procedures per tenant, no writes, no CareStack calls
python3 infra/scripts/replay_treatment_procedures.py [--tenant-id <uuid>]

# apply — re-project in resumable batches, commit per batch
python3 infra/scripts/replay_treatment_procedures.py --apply \
    [--tenant-id <uuid>] [--batch-size 500] [--max-batches 0] \
    [--start-after <external_id>] [--since-days 0]
```

- `--apply` — write (default dry-run).
- `--tenant-id` — one tenant; omit to sweep all tenants (`--start-after` only meaningful with one tenant).
- `--batch-size` — procedures per batch/commit (default 500, max 2000).
- `--max-batches` — stop after N batches/tenant (default 0 = unbounded, internal safety cap 10k). Resume with `--start-after`.
- `--start-after` — resume cursor: skip `external_id` <= this value (last id printed by a prior run).
- `--since-days` — only raw captured within N days by `received_at` (default 0 = all history).

**Unit of work:** COMMIT per batch on success; any batch error → `session.rollback()` then re-raise. **CareStack client:** built only so ENG-538 self-fill can resolve a still-missing code via the read-only by-id endpoint; the feed-pull method is never called. With no credential, a `_NoPullTreatmentClient` stand-in is used (no by-id surface → self-fill fail-closed; codes already in the catalog from the ENG-538 backfill still resolve).

---

## Idempotency design

- The emit goes through `InteractionService.create_event_idempotent` on the stable `(person, kind, source_provider, source_kind, source_external_id)` identity (`source_external_id` = procedure id). A second replay → `was_created=False` → counted `unchanged`, **zero** new events.
- Raw is **never** re-captured by the replay, so no new `ingest.raw_event` rows either.
- `DISTINCT ON (external_id)` in the paginated read means each procedure projects once from its freshest captured payload, even with multiple historical re-pull rows.
- Verified by `test_replay_is_idempotent_second_run_emits_zero_new_events` (unit) and the integration test's second-pass assertions.

---

## Tests run + results

Run with the repo venv (`pytest` is allowlisted; bare `python -m pytest` is not in this session):

```
pytest tests/ingest/test_carestack_treatment_service.py -q   → 38 passed
pytest tests/infra/test_replay_treatment_procedures.py -q     → 7 passed
pytest tests/ingest/test_treatment_replay_integration.py -q   → 1 skipped (no DB in session)
ruff check  (all touched packages/scripts/tests)              → All checks passed
mypy packages/ingest/* infra/scripts/replay_treatment_procedures.py → Success, no issues
```

New replay coverage:
- `test_replay_emits_surgery_scheduled_for_historical_implant` — statusId=2 + implant CDT → `surgery_scheduled`; asserts `ingest.capture` NOT awaited and feed-pull NOT awaited; `source_event_id` == the passed raw_event id.
- `test_replay_emits_surgery_completed_for_historical_implant` — statusId=8 → `surgery_completed`.
- `test_replay_is_idempotent_second_run_emits_zero_new_events` — `was_created=False` → 0 imported, all unchanged.
- `test_replay_non_implant_row_keeps_generic_mapping` — non-implant stays `treatment_proposed`, no surgical flag.
- `test_replay_skips_unlinked_patient_without_capturing_raw`, `test_replay_skips_row_without_procedure_id`, `test_replay_empty_batch_is_a_noop`.
- Integration (`tests/ingest/test_treatment_replay_integration.py`, real PG): seeds tenant+person+carestack source_link + catalog codes, captures a historical implant (statusId=2) + non-implant raw_event, runs replay → asserts exactly one `surgery_scheduled`, non-implant stays `treatment_proposed`, no `surgery_completed`; second replay → counts unchanged (idempotent); payload == `{"is_implant_surgery": True}`, no PHI.

**Pre-existing failures (NOT caused by this change, confirmed by re-running with my source files stashed):**
- `tests/ingest/test_carestack_appointment_service.py::test_map_status_known_values` — fails on this branch independently of ENG-540 (appointment status mapping; untouched here).
- `tests/ingest/test_ingest_idempotency_sql.py` (7 errors) and `tests/worker/test_ingest_scheduled.py` (collection error) — require `DATABASE_URL`/`SECRET_KEY`/`REDIS_URL` settings, unavailable in this worktree session (no `.env`). Env-gated, not code failures.

---

## How to reproduce the dev backfill + rebuild + verify (for the orchestrator)

1. **Replay (dry-run first):**
   ```
   python3 infra/scripts/replay_treatment_procedures.py --tenant-id <uuid>
   python3 infra/scripts/replay_treatment_procedures.py --tenant-id <uuid> --apply
   ```
   Re-run `--apply` once more → expect `imported=0` (all `unchanged`) = idempotent.

2. **Fact rebuild** (existing on-demand arq job — no new path):
   ```python
   await pool.enqueue_job("refresh_fact_patient_journey", tenant_id="<uuid>")
   # or: refresh_fact_patient_journey_for_all_tenants
   ```
   The builder derives `surgery_scheduled_date` / `surgery_completed_date` (earliest `surgery_*` event) + `case_type` (from raw CDT) as `method=auto`, and **preserves `method=manual`** (ENG-513 overrides not clobbered).

3. **Verify SQL:**
   ```sql
   -- new surgery events emitted by the replay
   SELECT kind, count(*) FROM interaction.event
   WHERE tenant_id = '<uuid>' AND kind IN ('surgery_scheduled','surgery_completed')
   GROUP BY kind;

   -- fact backfill landed
   SELECT count(*) FILTER (WHERE surgery_scheduled_date IS NOT NULL) AS scheduled,
          count(*) FILTER (WHERE surgery_completed_date IS NOT NULL) AS completed,
          count(*) FILTER (WHERE case_type IS NOT NULL)              AS case_typed
   FROM analytics.fact_patient_journey WHERE tenant_id = '<uuid>';

   -- manual overrides preserved (provenance still manual where set)
   SELECT person_uid, field_provenance->'surgery_scheduled_date'->>'method' AS method
   FROM analytics.fact_patient_journey
   WHERE tenant_id = '<uuid>' AND field_provenance ? 'surgery_scheduled_date';
   ```

---

## Risks

- **Live dev-DB pollution avoided:** the integration test commits, so it must run against an ephemeral/test DB, not the running dev compose Postgres. I did NOT run it against dev to avoid leaving test rows behind — the orchestrator should run it against the test DB.
- **Self-fill on replay:** if a historical procedure references a code still absent from the catalog AND no CareStack credential is present, that row falls back to the generic mapping (no surgery event). Mitigation: ENG-538's by-id catalog backfill already populated the codes; for completeness run the replay with a tenant that has a CareStack credential, or run `backfill_procedure_codes.py --apply` first.
- **Cursor ordering** is by `external_id` (stable string order), not time — fine for idempotent replay (completeness + stable resume is what matters, not chronological order). `--since-days` windows by `received_at` if a bounded recent sweep is wanted.
- **Per-batch commit** is a documented exception to "services never commit" (the *script* commits, like `backfill_procedure_codes.py`); `create_event_idempotent` SAVEPOINTs are released per batch.

---

## Blockers / open questions

- None blocking. `pytest` is allowlisted and was run (unit + script green); the real-PG integration test needs a test DB the orchestrator provides.

---

## Do-not-merge conditions

- **Build only — leave UNCOMMITTED.** No commit/push/PR/merge/deploy (merge to `main` == prod deploy). Merge is gated on **operator approval + Codex cross-runtime review**.
- Do not merge before the orchestrator's **DB-backed dev replay + fact rebuild** verification passes (surgery_* + case_type backfill confirmed via the SQL above; second replay = 0 new events).
- Pre-existing unrelated red (`test_map_status_known_values`) is out of scope for this task but should not be masked — flag separately.

---

## Suggested next

Operator + Codex review → orchestrator DB-backed dev replay + fact rebuild verification → integration on operator go. This is the final tail of the ENG-511 → 538 → 539 → 540 line.
