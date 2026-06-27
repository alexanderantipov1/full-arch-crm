# ENG-314/315/317 Integration Report

- Timestamp: 2026-06-02T06:23:09Z
- Integrator: codex/orchestrator
- Linear: ENG-314, ENG-315, ENG-317

## Summary

Integrated the semantic catalog proposal review API facade with durable
`packages.insight` catalog storage. FastAPI dependency injection now builds
`AnalyticsCatalogReviewService` with `InsightCatalogService` instead of the
process-local in-memory repository. The in-memory repository remains only for
focused contract tests.

Approved review transitions now create an insight catalog version and return the
`catalog_version_id` through the API-facing review response. Analytics DTOs still
own the route contract; insight remains the storage service; audit remains
write-only through `AuditService`.

## Changed Files

- `apps/api/dependencies.py`
- `packages/analytics/service.py`
- `packages/analytics/CLAUDE.md`
- `packages/insight/service.py`
- `packages/insight/CLAUDE.md`
- `tests/analytics/test_catalog_review_insight_integration.py`

## Verification

- `uv run pytest tests/analytics/test_catalog_review_insight_integration.py tests/insight/test_catalog_service.py tests/api/test_semantic_catalog_routes.py tests/analytics/test_catalog_review_contracts.py tests/analytics/test_catalog_review_service.py tests/audit/test_audit_service.py -q` — passed, 33 tests.
- `uv run ruff check packages/analytics packages/insight apps/api/dependencies.py apps/api/routers/semantic_catalog.py tests/analytics/test_catalog_review_insight_integration.py tests/analytics/test_catalog_review_contracts.py tests/analytics/test_catalog_review_service.py tests/api/test_semantic_catalog_routes.py tests/insight/test_catalog_service.py tests/audit/test_audit_service.py` — passed.
- `uv run mypy packages/analytics packages/insight apps/api/dependencies.py apps/api/routers/semantic_catalog.py tests/analytics/test_catalog_review_insight_integration.py` — passed.
- `uv run mypy .` — passed, 324 source files.

## Remaining Risks

- `make lint`, `make test`, and `alembic check` were not rerun in this
  integration pass because worker reports already identified unrelated lint and
  local environment blockers. The focused surface and repo-wide mypy are green.
- The checkout remains dirty with broader parallel mission changes; no commit or
  push was performed.
