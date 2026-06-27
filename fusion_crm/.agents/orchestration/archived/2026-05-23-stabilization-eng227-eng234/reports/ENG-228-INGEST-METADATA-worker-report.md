# ENG-228-INGEST-METADATA Worker Report

- Task id: `ENG-228-INGEST-METADATA`
- Title: Fix ingest normalized person hint metadata test failures
- Linear issue id: `ENG-228`
- Linear issue URL: `https://linear.app/fusion-dental-implants/issue/ENG-228/triage-and-fix-full-pytest-suite-failures`
- Role: worker
- Agent: Codex
- Branch: `main`
- Worktree: `/Users/eduardkarionov/Desktop/Fusion_crm`
- Allowed scope: `tests/ingest/test_normalized_person_hint_model.py`; this report file
- Completed at: `2026-05-22T15:54:53Z`

## Touched Files

- `tests/ingest/test_normalized_person_hint_model.py`
- `.agents/orchestration/current/reports/ENG-228-INGEST-METADATA-worker-report.md`

## What Changed

- Updated the `NormalizedPersonHint` metadata smoke test expected columns to include `source_instance`.
- Added `source_instance` to the required non-null column assertions.
- Updated the source index expectation to match the current model shape:
  `tenant_id`, `source_system`, `source_instance`, `source_kind`, `source_id`.

## Commands Run

- `.venv/bin/python -m pytest -q tests/ingest/test_normalized_person_hint_model.py`

## Verification Status

- Passed: focused ingest metadata test suite.
- Result: `9 passed in 0.03s`.

## Risks

- This worker only fixed the scoped normalized person hint metadata failures.
- No broader pytest suite, mypy, lint, or Alembic checks were run in this worker scope.

## Blockers Or Questions

- None.

## Suggested Next Task

- Continue ENG-228 with the next isolated full-suite failure cluster.

## Do Not Merge Conditions

- Do not merge ENG-228 until the orchestrator/integrator confirms the full intended verification scope for the issue.
