# ENG-317 Frontend History Report

## Scope

Exposed semantic catalog proposal review history and version history in the frontend contract layer and review UI.

## Changes

- Added frontend Zod schemas for:
  - proposal review history
  - semantic term version history
- Added React Query hooks for:
  - `GET /semantic/catalog/proposals/{proposal_id}/history`
  - `GET /semantic/catalog/versions?term=...`
- Invalidated history/version queries after proposal mutations.
- Added read-only review history and version history panels to `CatalogProposalReview`.
- Extended frontend schema tests with representative backend history payloads.
- Updated the catalog review workbench document so it no longer describes browser-local draft storage as the current V1 behavior.
- Widened the reviewer note field in the review form.

## Verification

- `npm run test -- schemas.test.ts` in `apps/web`
- `npm run typecheck` in `apps/web`
- `npm run lint` in `apps/web`
- `make lint`
- `uv run mypy .`
- `uv run pytest tests/analytics/test_catalog_review_insight_integration.py tests/insight/test_catalog_service.py tests/api/test_semantic_catalog_routes.py tests/analytics/test_catalog_review_contracts.py tests/analytics/test_catalog_review_service.py tests/audit/test_audit_service.py -q`
- `PYTHONPATH=. uv run pytest -q`
- One-off Playwright visual check against `http://localhost:3000/dev/semantic-analytics?doc=catalog-review` with semantic catalog API routes mocked.

## Visual QA

- Screenshot: `/tmp/fusion-semantic-catalog-review-history.png`
- Confirmed visible:
  - selected proposal row
  - review history panel
  - version history panel
  - approved review event
  - approved version event

## Follow-Up

- No frontend history contract follow-up remains from this pass.
