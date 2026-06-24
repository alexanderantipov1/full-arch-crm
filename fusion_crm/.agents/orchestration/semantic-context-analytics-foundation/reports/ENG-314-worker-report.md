# Worker Report — ENG-314 SCR-01 Catalog Proposal And Version Storage

- Task id: ENG-314
- Linear issue: ENG-314
- Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-314/scr-01-catalog-proposal-and-version-storage
- Role: worker
- Agent: codex
- Branch: main
- Worktree: .
- Allowed scope: backend package/db/tests for service-owned catalog proposal and version storage

## Summary

Added service-owned persistence for semantic catalog proposals and approved
catalog versions under the new `insight` domain. Proposals are review inbox
rows and are not returned as approved business truth. Approval creates an
append-only `semantic_catalog_version` row with monotonic per-term versioning,
previous/new snapshots, actor metadata, timestamp, reason, and affected
analytics metadata.

## Touched Files

- `CLAUDE.md`
- `infra/docker/init-schemas.sql`
- `packages/CLAUDE.md`
- `packages/db/alembic/env.py`
- `packages/db/registry.py`
- `packages/db/alembic/versions/20260602_0900_c2d3e4f5a6b7_add_insight_semantic_catalog_storage.py`
- `packages/insight/AGENTS.md`
- `packages/insight/CLAUDE.md`
- `packages/insight/__init__.py`
- `packages/insight/models.py`
- `packages/insight/repository.py`
- `packages/insight/schemas.py`
- `packages/insight/service.py`
- `tests/insight/test_catalog_service.py`

## What Changed

- Added `packages.insight` as the semantic analytics storage domain.
- Added `insight.semantic_catalog_proposal` for proposed mappings, source-drift
  briefs, and gap briefs.
- Added `insight.semantic_catalog_version` for immutable approved catalog
  entries.
- Registered `insight` in Alembic schema filtering and model registry.
- Added the `insight` schema to `infra/docker/init-schemas.sql`.
- Added service methods to create, list, update, approve, reject, and mark
  proposals unresolved.
- Added approved-catalog read method that returns latest approved versions only.
- Added a guard preventing system-only principals from performing review
  actions.
- Added focused service tests for status transitions, version creation,
  previous/new snapshot preservation, approved-only truth reads, terminal
  approved proposal behavior, and system-only approval denial.

## Tests / Checks

- `python -m pytest tests/insight/test_catalog_service.py` — passed, 6 tests.
- `ruff check packages/insight tests/insight packages/db/registry.py packages/db/alembic/env.py packages/db/alembic/versions/20260602_0900_c2d3e4f5a6b7_add_insight_semantic_catalog_storage.py` — passed.
- `python -m mypy packages/insight tests/insight` — passed.
- `python -m mypy packages apps` — passed.
- `python -m pytest tests/core/test_db_session_registry.py` — passed.
- `python -m compileall -q packages/insight tests/insight packages/db/alembic/versions/20260602_0900_c2d3e4f5a6b7_add_insight_semantic_catalog_storage.py` — passed.
- Metadata smoke: imported `packages.db.registry` and confirmed
  `insight.semantic_catalog_proposal` and `insight.semantic_catalog_version`
  are present in `Base.metadata` with no table-sort warning.

## Verification Notes

- Direct `pytest tests/insight/test_catalog_service.py` failed in this local
  shell because the console-script path resolved an older editable namespace
  that did not include the new package. `python -m pytest ...` from the repo
  root passed.
- `make lint` failed on unrelated existing/parallel files:
  `packages/ingest/repository.py`, `packages/interaction/repository.py`, and
  `tests/ingest/test_carestack_patients_with_payments_sql.py`.
- `cd packages/db && alembic check` could not run because the local shell lacks
  required settings: `SECRET_KEY`, `DATABASE_URL`, and `REDIS_URL`.

## Risks / Blockers

- Existing environments must create schema `insight` before applying the new
  migration. Fresh Docker volumes pick it up from `infra/docker/init-schemas.sql`.
- Review audit is intentionally not implemented here; ENG-317 owns append-only
  audit and version-history surfacing.
- API route contracts and dashboard persistence are intentionally not
  implemented here; ENG-315/ENG-316 own those surfaces.
- Concurrent work appeared in the same checkout while this task was running
  (`packages/analytics`, API semantic catalog routes, audit review changes, and
  frontend workbench changes). This worker did not revert or edit those files.

## Integration Notes

- ENG-315 should call `InsightCatalogService` rather than persisting proposals
  in route handlers or `packages.analytics`.
- ENG-317 should add audit actions around the review service methods without
  making version rows mutable.
- ENG-320 approved catalog consumption should read from
  `InsightCatalogService.list_approved_catalog_entries`, not from proposal
  listings.
