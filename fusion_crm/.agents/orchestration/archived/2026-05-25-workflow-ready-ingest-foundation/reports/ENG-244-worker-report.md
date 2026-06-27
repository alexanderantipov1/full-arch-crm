# ENG-244 Worker Report

## Task

- Task id: ENG-244
- Linear issue: ENG-244
- Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-244
- Title: Task I: Sync docs and data catalog for workflow-ready ingest foundation
- Role / agent: worker / codex docs-catalog-worker
- Runtime session id: 9665c98b545b
- Branch: eng-244-eng-244
- Worktree: /Users/eduardkarionov/.fusion-agent-orchestrator/c2db50910d08/workflow-ready-ingest-foundation/worktrees/ENG-244
- Allowed scope: docs only

## Changed Files

- `docs/data-model/CATALOG.md`
- `docs/data-model/WORKFLOW_READY_TIMELINE.md`
- `packages/ingest/CLAUDE.md`
- `.agents/orchestration/workflow-ready-ingest-foundation/reports/ENG-244-worker-report.md`

## What Changed

- Documented workflow-ready `interaction.event` additions in the data catalog:
  `data_class`, `source_kind`, `source_external_id`,
  `projection_ref_type`, `projection_ref_id`, and `review_status`.
- Added the shipped workflow-ready `interaction.event.kind` taxonomy and
  noted that legacy `consultation_created` remains accepted for existing rows.
- Documented the `ops.followup_task` projection link through
  `projection_ref_type='ops_followup_task'`.
- Documented `integrations.sync_run` status values, direction values,
  provider scope dimensions, and `skipped_credential` behavior.
- Added `docs/data-model/WORKFLOW_READY_TIMELINE.md` describing raw provider
  rows through `ingest.raw_event`, identity/provenance, canonical projections,
  `interaction.event`, and `GET /persons/{uid}/operational-timeline`.
- Linked workflow-ready docs back to:
  `.agents/strategy/RAW_TO_CONTEXT_NORMALIZATION_SPEC.md` and
  `.agents/strategy/PERSON_DATA_EVENT_PROVENANCE_DOCTRINE.md`.
- Updated `packages/ingest/CLAUDE.md` with shipped handlers for Salesforce
  Lead/Event/Task and CareStack Patient/Appointment, plus shared helper notes
  for `consultation_timeline.py` and `call_reference.py`.

## Local Instruction Audit

- `packages/interaction/CLAUDE.md` and `packages/interaction/AGENTS.md` exist
  and already document workflow-ready event fields, kind values, append-only
  behavior, and the no-PII summary/payload contract.
- `packages/ingest/CLAUDE.md` and `packages/ingest/AGENTS.md` exist; the
  shipped source handler table was stale and is now updated.
- `packages/integrations/CLAUDE.md` and `packages/integrations/AGENTS.md`
  exist; ENG-239 sync run notes, including `skipped_credential`, are present.
- Provider subareas under `packages/integrations/` have both `CLAUDE.md` and
  `AGENTS.md`. No new thin local instruction file was needed.

## Tests Run

- `make lint` — passed
- `mypy .` — passed (`Success: no issues found in 246 source files`)
- `make test` — passed (`755 passed`)
- `cd packages/db && set -a && source ../../.env && set +a && alembic check`
  — passed (`No new upgrade operations detected.`)

## Verification Result

Passed. This is a docs-only diff; no product code, tests, migrations, `.env*`,
deployment files, secrets, OAuth/CORS URLs, Cloud Run resources, or GitHub
Actions workflows were changed.

## Risks

- Low. Documentation now reflects the current workflow-ready ingest shape.
- The catalog still uses the historical `sf_object` column name for
  provider object scope because that is the shipped schema.

## Blockers

- None.

## Do-Not-Merge Conditions

- Do not merge if later integration work changes the shipped
  `interaction.event` taxonomy or `integrations.sync_run` status/scope
  contract without updating these docs again.
- Do not merge if any non-doc or migration diff appears in this branch.

## Suggested Next Task

- Integrator/verifier should review the final mission docs against the merged
  ENG-236 through ENG-243 implementation commits before mission closeout.
