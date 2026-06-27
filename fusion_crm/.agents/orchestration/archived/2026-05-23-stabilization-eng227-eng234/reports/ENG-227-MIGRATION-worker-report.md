# ENG-227 MIGRATION Worker Report

Linear issue: ENG-227
Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-227/fix-carestack-location-profile-migration-drift
Task: ENG-227-MIGRATION
Worker: codex/migration-drift-worker
Completed at: 2026-05-22T08:13:22Z

## Summary

Fixed the Alembic drift in the untracked `f3a4b5c6d7e8` migration by aligning
database DDL with SQLAlchemy metadata for `ops.consultation` and
`ops.person_location_profile`.

## Changed Files

- `packages/db/alembic/versions/20260522_0900_f3a4b5c6d7e8_add_person_location_profile.py`
- `.agents/orchestration/current/reports/ENG-227-MIGRATION-worker-report.md`

## Migration Changes

- Removed database-side defaults from `ops.person_location_profile.id`,
  `relationship_kind`, and `relationship_status`; these are client-side model
  defaults.
- Added `fk_person_location_profile_tenant_id_tenant` from
  `ops.person_location_profile.tenant_id` to `tenant.tenant.id`.
- Added an upgrade fix-up for the previously applied `ops.consultation` table:
  removed database-side defaults from `id`, `status`, and
  `consultation_kind`.
- Added `fk_consultation_tenant_id_tenant` from `ops.consultation.tenant_id`
  to `tenant.tenant.id`.
- Made the `f3a4b5c6d7e8` downgrade compatible with the already-applied local
  pre-fix migration by dropping the consultation FK with `IF EXISTS`, then
  restoring the previous consultation defaults.

## Commands Run

All Alembic commands used one-shot local environment overrides for the local
development database and runtime secrets. Exact values are intentionally not
recorded in the repository report.

- `cd packages/db && alembic current`
- `cd packages/db && alembic check`
- `cd packages/db && alembic downgrade e2f3a4b5c6d7`
- `cd packages/db && alembic upgrade head`
- `cd packages/db && alembic current`
- `cd packages/db && alembic check`
- `pytest tests/ops/test_consultation.py -q`
- `PYTHONPATH=/Users/eduardkarionov/Desktop/Fusion_crm python -m pytest tests/ops/test_consultation.py -q`

## Verification Status

- `alembic downgrade e2f3a4b5c6d7`: passed.
- `alembic upgrade head`: passed.
- `alembic current`: passed, database is at `f3a4b5c6d7e8 (head)`.
- `alembic check`: passed, `No new upgrade operations detected.`
- Focused ops consultation tests: passed with explicit current-checkout
  `PYTHONPATH`, `15 passed in 0.15s`.

## Blockers

None.

## Risks And Notes

- A first plain `pytest tests/ops/test_consultation.py -q` run failed during
  collection because the Python import path resolved `packages.ops.models` from
  a stale `.claude/worktrees/...` checkout. Re-running with
  `PYTHONPATH=/Users/eduardkarionov/Desktop/Fusion_crm` pinned imports to this
  checkout and passed.
- The new tenant foreign keys assume all existing local `ops.consultation` rows
  have valid `tenant_id` values. This matches the model invariant and the local
  upgrade succeeded.
- The migration file is still untracked local work, as expected for this task.
