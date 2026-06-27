# ENG-239 Worker Report

## Task

- Task id: ENG-239
- Title: Task D: Add real provider sync-run journaling for scheduled and manual pulls
- Linear issue: ENG-239
- Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-239/task-d-add-real-provider-sync-run-journaling-for-scheduled-and-manual
- Role and agent: worker, codex/sync-run-journaling-worker
- Session id: d70a685b893f

## Branch and Worktree

- Branch: eng-239-eng-239
- Worktree: /Users/eduardkarionov/.fusion-agent-orchestrator/c2db50910d08/workflow-ready-ingest-foundation/worktrees/ENG-239

## Allowed Scope

- Wire real `IntegrationService.open_sync_run` / `close_sync_run` journaling for scheduled and manual Salesforce / CareStack pulls.
- Return real `sync_run_id` from manual pull responses.
- Add audit summary rows through the existing `AuditService.log_sync_run_summary` contract.
- Add tests for `succeeded`, `partial`, `skipped_credential`, and `failed` lifecycle cases.
- No deployment, env, secret, Cloud Run, OAuth URL, or GitHub Actions changes were made.
- No `.env*` files or shipped Alembic revisions were edited.

## Touched Files

- `apps/api/dependencies.py`
- `apps/api/routers/carestack.py`
- `apps/api/routers/integrations.py`
- `apps/worker/jobs/ingest_scheduled.py`
- `.agents/orchestration/workflow-ready-ingest-foundation/reports/ENG-239-worker-report.md`
- `packages/audit/CLAUDE.md`
- `packages/audit/service.py`
- `packages/db/alembic/versions/20260524_0915_b8c9d0e1f2a3_sync_run_provider_journaling.py`
- `packages/ingest/schemas.py`
- `packages/integrations/CLAUDE.md`
- `packages/integrations/models.py`
- `packages/integrations/schemas.py`
- `packages/integrations/service.py`
- `tests/api/test_integrations_carestack_import.py`
- `tests/api/test_integrations_salesforce.py`
- `tests/worker/test_ingest_scheduled.py`

## What Changed

- Added provider-level sync-run lifecycle helpers on `IntegrationService` that:
  - open inbound provider runs without copying tenant credential payloads;
  - close runs with `succeeded`, `partial`, `failed`, or `skipped_credential`;
  - sanitize short error summaries;
  - write `AuditService.log_sync_run_summary` rows.
- Updated `integrations.sync_run` ORM/DTO vocabulary for `direction="inbound"` and `status="succeeded"` / `status="skipped_credential"`, with legacy values preserved.
- Added a new Alembic revision for the sync-run direction/status constraints, `status` length expansion, and tenant-scoped `integration_account` uniqueness.
- Wired scheduled Salesforce and CareStack tenant pulls to open/close real sync runs, including no-credential and provider-error paths.
- Wired manual Salesforce and CareStack pull/import endpoints to return real `sync_run_id` values.
- Changed API provider ingest dependencies so missing tenant credentials surface inside route execution, after the route can open and close a `skipped_credential` sync run.
- Removed CareStack pull-path fallback to env credentials in favor of tenant-scoped credentials.
- Added focused tests covering success, partial, skipped credential, and failed lifecycle handling.

## Tests Run and Results

- `make lint`
  - Result: passed.
- `mypy .`
  - Result: passed.
- `python -m pytest tests/worker/test_ingest_scheduled.py tests/api/test_integrations_salesforce.py tests/api/test_integrations_carestack_import.py tests/audit/test_audit_service.py`
  - Env used: dummy local `SECRET_KEY`, `DATABASE_URL`, and `REDIS_URL`.
  - Result: passed, 40 tests.
- `make test`
  - Env used: dummy local `SECRET_KEY`, `DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/fusion_test`, and `REDIS_URL`.
  - Result: blocked by local database credentials. Pytest completed 606 tests, then 61 tenant-isolation integration tests errored during fixture setup with `asyncpg.exceptions.InvalidAuthorizationSpecificationError: role "user" does not exist`.
- `cd packages/db && alembic check`
  - Env used: dummy local `SECRET_KEY`, `DATABASE_URL`, `DATABASE_URL_SYNC=postgresql+psycopg://user:pass@localhost:5432/fusion_test`, and `REDIS_URL`.
  - Result: blocked by local database credentials with `psycopg.OperationalError: role "user" does not exist`.

## Verification Status

Paused / not complete. Focused verification passes, but the required full verification loop is not green because the local test database credentials are unavailable in this worker environment.

## Risks

- The new Alembic revision must be run and checked against a real migrated test database before merge.
- Manual pull routes now write sync-run rows before executing provider ingest; if the DB transaction rolls back, both ingest and journal rows roll back together as intended.
- CareStack env fallback was removed from API pull dependencies to honor tenant-scoped credential resolution; confirm no local-only workflows still rely on env fallback for pull/import endpoints.

## Blockers or Questions

- Blocked: full `make test` and `alembic check` require valid local PostgreSQL test credentials. The dummy role used for verification does not exist on the local server.

## Suggested Next Task

- Add a dashboard/operator view for recent provider `sync_run` history and failed/skipped credential triage.
- Define retry policy for failed provider sync runs.
- Add archival or retention policy for old sync-run rows.

## Do-Not-Merge Conditions

- Do not merge until `make test` passes against a real test database.
- Do not merge until `cd packages/db && alembic check` passes against a real test database.
- Do not merge if the CareStack tenant-credential-only behavior conflicts with an approved local-dev fallback requirement.
