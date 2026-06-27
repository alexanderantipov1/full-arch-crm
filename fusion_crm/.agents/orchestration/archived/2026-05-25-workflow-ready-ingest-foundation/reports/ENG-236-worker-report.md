# ENG-236 Worker Report

## Task

- Task id: ENG-236
- Title: Task A: Define workflow-ready `interaction.event` schema contract
- Linear issue: ENG-236
- Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-236/task-a-define-workflow-ready-interactionevent-schema-contract

## Role And Agent

- Role: worker
- Agent: codex / interaction-schema-worker
- Session id: c5a203f3f0c3

## Branch And Worktree

- Branch: `eng-236-eng-236`
- Expected prompt branch: `eng-236-task-a`
- Worktree: `/Users/eduardkarionov/.fusion-agent-orchestrator/c2db50910d08/workflow-ready-ingest-foundation/worktrees/ENG-236`

## Allowed Scope

- Product scope touched: `packages/interaction/`
- Migration scope touched: `packages/db/alembic/versions/`
- Test scope touched: `tests/interaction/`
- Additional test helper touched: `tests/conftest.py`, because the shared tenant-isolation fixture directly creates `interaction.Event` rows and the task explicitly required updating fixture helpers used by tests.
- Mission reporting touched: `.agents/orchestration/workflow-ready-ingest-foundation/`
- No `.env*`, deployment, secrets, OAuth/CORS URL, Cloud Run, deploy script, GitHub Actions, `packages/workflow`, `packages/context`, or `packages/billing` files were changed.

## Touched Files

- `.agents/orchestration/workflow-ready-ingest-foundation/incidents.md`
- `.agents/orchestration/workflow-ready-ingest-foundation/reports/ENG-236-worker-report.md`
- `packages/db/alembic/versions/20260524_1625_a9b8c7d6e5f4_workflow_ready_interaction_event.py`
- `packages/interaction/CLAUDE.md`
- `packages/interaction/models.py`
- `packages/interaction/schemas.py`
- `packages/interaction/service.py`
- `tests/conftest.py`
- `tests/interaction/test_models.py`
- `tests/interaction/test_service.py`

## What Changed

- Documented the current gap: existing `interaction.event` had only `kind`, `source_provider`, and `source_event_id`; workflow-ready events need classification, provider object identity, projection references, and review state.
- Added workflow-ready columns to `interaction.event`: `data_class`, `source_kind`, `source_external_id`, `projection_ref_type`, `projection_ref_id`, and `review_status`.
- Expanded `kind` taxonomy with snake_case workflow-ready literals: `consultation_scheduled`, `consultation_completed`, `consultation_no_show`, `task_created`, `task_completed`, `call_logged`, and `call_reference_found`.
- Retained legacy `consultation_created` so already-shipped Phase 1 rows/callers remain valid; `consultation_scheduled` is the new workflow-ready scheduled appointment literal.
- Added DTO literals and validation requiring provider-backed events to include `source_kind`, `source_external_id`, and `data_class`; `projection_ref_type` and `projection_ref_id` must be supplied together.
- Extended `summary_for_event` with allowlisted summaries for every workflow-ready kind. Summaries still accept only `kind`, `source_provider`, and a non-PII source id.
- Added a new Alembic migration; no shipped migration was edited.
- Updated tests for kind validation, source-reference/data-class requirements, no raw-provider or clinical/free-text summary leakage, and append-only service/repository surface.

## Tests Run And Results

- `make lint` — passed.
- `mypy .` — passed (`Success: no issues found in 236 source files`).
- `PYTHONPATH=$PWD pytest tests/interaction -q` — passed (`63 passed`).
- `make test` — failed during collection before exercising this diff because `SECRET_KEY`, `DATABASE_URL`, and `REDIS_URL` are unset in the worker environment.
- `cd packages/db && alembic check` — failed before autogenerate comparison because the same required settings env vars are unset.
- Supplemental `make test` with temporary shell env values — progressed to DB integration tests, then failed because local Postgres lacks the expected `test` / `fusion` roles.
- Supplemental `cd packages/db && alembic check` with temporary shell env values — failed because local Postgres lacks the expected `fusion` role.

## Verification Status

Verification failed due local environment blockers. The code-level focused interaction tests, lint, and mypy pass, but required full verification is not green.

## Risks

- Existing rows backfill `data_class='operational'` and `review_status='auto'`; legacy rows may still have null `source_kind` / `source_external_id` because those references did not exist historically.
- `consultation_created` remains accepted for compatibility. A later cleanup task should decide whether and when to migrate callers/data fully to `consultation_scheduled`.
- `projection_ref_*` is intentionally generic and does not add a DB FK to `ops`, preserving the interaction package boundary.

## Blockers Or Questions

- Blocker: required full verification needs a configured test environment with `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, and a usable Postgres role/database.
- No product decision is requested.

## Suggested Next Task

- In the next ingest-mapping task, update Salesforce/CareStack emitters to populate `data_class`, `source_kind`, `source_external_id`, and `projection_ref_*` consistently.
- Add a follow-up cleanup decision on whether `consultation_created` should be data-migrated and retired after all workflow-ready emitters use `consultation_scheduled`.

## Do-Not-Merge Conditions

- Do not merge until the required verification loop is green in a configured environment:
  - `make lint`
  - `mypy .`
  - `make test`
  - `cd packages/db && alembic check`
- Do not merge if downstream tasks require an exact no-legacy taxonomy that excludes `consultation_created`; that would need an explicit compatibility decision and likely a data migration plan.
