# ENG-316 Frontend API Integration Report

## Scope

Replaced the browser-local Semantic Catalog Proposal Review draft with API-backed frontend contracts and React Query integration.

## Changes

- Added semantic catalog Zod schemas for proposal list/create/update/review, impact preview, and draft patch responses.
- Added React Query hooks for `/semantic/catalog` proposal listing, creation, update, review, impact preview, and draft patch generation.
- Added `api.patch` support to the shared web API client.
- Reworked `CatalogProposalReview` to remove `localStorage` persistence and use backend-backed save/review/patch flows.
- Added schema coverage for semantic catalog frontend contracts.
- Extended tenant-isolation test infrastructure so new insight repositories are covered when the local test database has the new insight tables, and skipped explicitly when it does not.

## Verification

- `npm run lint` in `apps/web`
- `npm run typecheck` in `apps/web`
- `npm run test -- schemas.test.ts` in `apps/web`
- `make lint`
- `uv run mypy .`
- `uv run pytest tests/analytics/test_catalog_review_insight_integration.py tests/insight/test_catalog_service.py tests/api/test_semantic_catalog_routes.py tests/analytics/test_catalog_review_contracts.py tests/analytics/test_catalog_review_service.py tests/audit/test_audit_service.py -q`
- `PYTHONPATH=. uv run pytest tests/integration/test_tenant_isolation.py -q`
- `PYTHONPATH=. uv run pytest -q`

## Known Environment Blockers

- `make test` uses system `python -m pytest` in this checkout and fails collection because that interpreter is missing project dependencies such as `structlog`, `respx`, `chevron`, and `arq`.
- `cd packages/db && alembic check` cannot run in this shell without `SECRET_KEY`, `DATABASE_URL`, and `REDIS_URL`.
- Local live tenant-isolation DB does not currently have `insight.semantic_catalog_*` tables applied, so three insight live sweep cases skip until the ENG-314 migration is applied to that database.
