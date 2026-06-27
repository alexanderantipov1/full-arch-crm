# ENG-237 Worker Report

## Task

- Task id: ENG-237
- Title: Task B: Emit timeline events from Salesforce Lead pull
- Linear issue: ENG-237
- Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-237

## Role And Agent

- Role: worker
- Agent: codex/sf-lead-events-worker
- Runtime session id: e81e63e73cd0

## Branch And Worktree

- Branch: eng-237-eng-237
- Worktree: /Users/eduardkarionov/.fusion-agent-orchestrator/c2db50910d08/workflow-ready-ingest-foundation/worktrees/ENG-237

## Allowed Scope

- Emit `interaction.event` rows from `SfLeadIngestService._capture_lead` after `OpsService.upsert_lead`.
- Use `InteractionService` service surface only.
- Keep Salesforce Lead event payload allowlisted to `Status`, `LeadSource`, `Id`, `CreatedDate`, and `LastModifiedDate`.
- Do not touch SOQL strings, deployment/env/secrets, shipped Alembic revisions, or unrelated domains.

## Touched Files

- `packages/ingest/sf_lead_service.py`
- `tests/ingest/test_sf_lead_service.py`
- `tests/integration/test_sf_lead_timeline_events.py`
- `.agents/orchestration/workflow-ready-ingest-foundation/reports/ENG-237-worker-report.md`

## What Changed

- Added `InteractionService` wiring to `SfLeadIngestService`.
- Added post-`upsert_lead` event emission:
  - `was_created=True` emits `lead_created`.
  - `was_created=False` and `was_changed=True` emits `lead_updated`.
  - unchanged re-pulls emit no event.
- Event metadata uses `source_kind="salesforce_lead"`, `source_external_id=<SF Lead Id>`, `projection_ref_type="ops_lead"`, `projection_ref_id=<ops.lead.id>`, `data_class="operational"`, and `review_status="auto"`.
- Event summaries use `summary_for_event(...)`.
- Event payloads are allowlisted and exclude name, email, phone, company, description/free text, and raw Salesforce payload fields.
- Added mock-based unit coverage and DB-backed integration coverage for created, unchanged, and changed lead pulls.

## Tests Run And Results

- `python -m pytest tests/ingest/test_sf_lead_service.py tests/integration/test_sf_lead_timeline_events.py -q --cache-clear` — passed, 15 passed.
- `python -m pytest tests/integration/test_sf_lead_timeline_events.py tests/integration/test_tenant_isolation.py -q --cache-clear` — passed, 133 passed.
- `make lint` — passed.
- `mypy .` — passed.
- `make test` — passed, 704 passed.
- `cd packages/db && alembic check` — failed because `packages/db` cwd does not contain `.env`; Settings validation reported missing `SECRET_KEY`, `DATABASE_URL`, and `REDIS_URL`.
- `cd packages/db && set -a; . ../../.env; set +a; alembic check` — passed, "No new upgrade operations detected."

## Verification Status

- Product code and tests are verified.
- Required verify loop is effectively green when the root `.env` is loaded for Alembic from `packages/db`.

## Risks

- `cd packages/db && alembic check` depends on environment loading from the repo root. The command itself does not discover root `.env` after changing directory into `packages/db`.
- The new DB-backed integration test disposes the shared async engine after use to avoid cross-event-loop pooled connection leakage in later async tests.

## Blockers Or Questions

- No product blocker.
- No human decision needed.

## Suggested Next Task

- Run verifier/integrator pass for ENG-237 and then continue with the next workflow-ready ingest foundation task that consumes lead timeline events.

## Do-Not-Merge Conditions

- Do not merge if Alembic verification is run without the root `.env` and fails on missing settings.
- Do not merge if any downstream verifier finds raw Salesforce payload, PII, or clinical/free-text leakage into `interaction.event.summary` or `interaction.event.payload`.
