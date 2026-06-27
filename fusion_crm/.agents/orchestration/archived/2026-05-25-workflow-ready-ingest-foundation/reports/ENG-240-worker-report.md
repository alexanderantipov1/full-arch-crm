# ENG-240 Worker Report

## Task

- Task id: ENG-240
- Linear issue: ENG-240
- Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-240
- Linear title: Task E: Add bounded Salesforce Task ingest and deterministic classification
- Role: worker
- Agent: codex/sf-task-ingest-worker
- Runtime session id: a8c36554ed80
- Branch: eng-240-eng-240
- Worktree: /Users/eduardkarionov/.fusion-agent-orchestrator/c2db50910d08/workflow-ready-ingest-foundation/worktrees/ENG-240
- Allowed scope: Salesforce Task ingest service, API/manual wiring, scheduled Salesforce pull wiring, focused tests, worker report

## Changed Files

- apps/api/dependencies.py
- apps/api/routers/integrations.py
- apps/worker/jobs/ingest_scheduled.py
- packages/ingest/schemas.py
- packages/ingest/sf_task_service.py
- packages/interaction/repository.py
- packages/interaction/service.py
- tests/api/test_integrations_salesforce.py
- tests/ingest/test_sf_task_service.py
- tests/integration/test_tenant_isolation.py
- tests/worker/test_ingest_scheduled.py
- .agents/orchestration/workflow-ready-ingest-foundation/reports/ENG-240-worker-report.md

## What Changed

- Added `SfTaskIngestService` with bounded recent import and ASC cursor backfill support for Salesforce Task rows.
- Captures each Task row verbatim as `ingest.raw_event` with `event_type="salesforce.task.upsert"`.
- Resolves `WhoId` through Salesforce `lead` then `contact` source links; unresolved tasks are counted as skipped after raw capture.
- Added deterministic Task classification:
  - open, non-call Tasks create `ops.followup_task` and emit `interaction.event kind="task_created"`;
  - completed, non-call Tasks emit `task_completed`;
  - call-like Tasks emit `call_logged`, and emit `call_reference_found` when `CallObject` carries a URL or provider reference id.
- Kept `Description` and `Subject` out of event summaries, event payloads, and follow-up task text. `Description` remains only in raw ingest payload.
- Added service-level cross-pull idempotency by finding existing interaction events by stable provider Task id plus event kind before creating follow-ups or events.
- Added `POST /integrations/salesforce/import-tasks` with sync-run journaling.
- Added scheduled Salesforce Task import per tenant using `import_recent_tasks(days=7, limit=200)`.
- Added focused unit/API/worker coverage and tenant-isolation resolver coverage for the new interaction repository read method.

## Tests Run

- `PYTHONPATH=$PWD pytest tests/ingest/test_sf_task_service.py -q` — passed, 8 tests.
- `PYTHONPATH=$PWD pytest tests/api/test_integrations_salesforce.py -q` — passed, 15 tests.
- `PYTHONPATH=$PWD pytest tests/worker/test_ingest_scheduled.py -q` — passed, 17 tests.
- `make lint` — passed.
- `mypy .` — passed.
- `make test` — passed, 710 tests.
- `cd packages/db && alembic check` — failed before migration drift check because required settings were absent.
- `SECRET_KEY=test-secret-key DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/fusion_test REDIS_URL=redis://localhost:6379/0 alembic check` from `packages/db` — failed to connect because local PostgreSQL role `user` does not exist.

## Verification Result

Code-level verification passed for lint, type-checking, focused tests, and full pytest.

Required Alembic verification is blocked by local database configuration, not by a detected schema diff. No schema or migration files were changed.

## Risks

- Idempotency for Task projections is service-level, keyed by existing `interaction.event` rows with stable Salesforce Task id and kind. There is no new DB uniqueness constraint for `(tenant_id, source_provider, source_kind, source_external_id, kind)`, so concurrent duplicate imports could still race.
- Follow-up task content is intentionally generic to avoid leaking Salesforce `Subject` or `Description`. Operators will need to inspect source-linked raw/provider data through an authorized workflow if they need the original Task text.
- Backfill router entity option `sf_tasks` remains out of scope and is not wired here.
- Audio download/transcription remains out of scope.

## Blockers Or Questions

- Blocked: `alembic check` cannot complete in this local environment until required settings and a reachable PostgreSQL role/database are available.
- No product-scope questions remain for ENG-240.

## Do-Not-Merge Conditions

- Do not merge until `cd packages/db && alembic check` is run successfully in a configured environment.
- Do not merge if reviewers require DB-enforced uniqueness for stable provider event ids rather than the service-level idempotency implemented here.

## Suggested Next Task

- ENG-246 can add the `sf_tasks` backfill entity option once this service is integrated.
- ENG-241 can consume `call_reference_found` metadata for gated call-reference handling.
