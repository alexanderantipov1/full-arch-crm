# ENG-313 Readiness Report

Date: 2026-06-02

## Scope covered

ENG-314/315/316/317 are implemented in the shared worktree as one semantic
catalog review slice:

- durable `insight` semantic catalog proposal and version storage;
- analytics review service contracts and FastAPI routes;
- approval/edit/reject/unresolved review actions with audit logging;
- proposal history and term version history APIs;
- staff review UI wired to backend API hooks and schemas;
- focused backend, frontend schema, typecheck, lint, and full pytest coverage.

## Verification status

Passed:

- `make lint`
- `uv run mypy .`
- `apps/web npm run lint`
- `apps/web npm run typecheck`
- `apps/web npm run test -- schemas.test.ts`
- focused semantic/audit backend suite: `36 passed`
- tenant isolation suite after applying the ENG-314 migration: `184 passed`
- full Python suite with uv after DB migration: `1227 passed`
- `cd packages/db && alembic check` after sourcing local development env:
  `No new upgrade operations detected.`

Fixed during readiness:

- The new ENG-314 migration initially failed on existing development databases
  because the `insight` schema did not exist yet. The migration now creates the
  schema idempotently before creating tables.
- The workflow-ready e2e fixture used near-term June 2026 dates and became
  time-sensitive under Salesforce temporal status inference. The shared fixture
  now uses 2036 dates for stable scheduled-event semantics.

Known local mismatch:

- `make test` uses the system Python in this checkout and fails on missing
  local dependencies; `PYTHONPATH=. uv run pytest -q` is the working regression
  command and passed.

## PR-ready SCR scope

Core backend/API:

- `apps/api/dependencies.py`
- `apps/api/main.py`
- `apps/api/routers/semantic_catalog.py`
- `packages/analytics/*`
- `packages/insight/*`
- `packages/audit/service.py`
- `packages/db/alembic/env.py`
- `packages/db/registry.py`
- `packages/db/alembic/versions/20260602_0900_c2d3e4f5a6b7_add_insight_semantic_catalog_storage.py`
- `infra/docker/init-schemas.sql`

Frontend:

- `apps/web/components/semantic/CatalogProposalReview.tsx`
- `apps/web/lib/api/client.ts`
- `apps/web/lib/api/hooks/useSemanticCatalog.ts`
- `apps/web/lib/api/schemas/index.ts`
- `apps/web/lib/api/schemas/semanticCatalog.ts`
- `apps/web/tests/unit/schemas.test.ts`
- `apps/web/app/(staff)/dev/semantic-analytics/page.tsx`

Tests and local fixtures:

- `tests/analytics/*`
- `tests/api/test_semantic_catalog_routes.py`
- `tests/insight/*`
- `tests/audit/test_audit_service.py`
- `tests/conftest.py`
- `tests/integration/test_tenant_isolation.py`
- `tests/integration/test_workflow_ready_e2e.py`
- `tests/_fixtures/workflow_ready.py`
- narrow lint-only fixes in ingest/interaction tests and repositories

Architecture/docs:

- `CLAUDE.md`
- `packages/CLAUDE.md`
- `packages/analytics/CLAUDE.md`
- `packages/analytics/AGENTS.md`
- `packages/insight/CLAUDE.md`
- `packages/insight/AGENTS.md`
- `packages/audit/CLAUDE.md`
- mission reports for ENG-314/315/316/317
- `semantic-catalog-proposal-review-v1.md`

## Changes requiring owner decision before PR

These changes are present in the dirty worktree but are not required to ship
the SCR implementation unless explicitly accepted into the same PR:

- `.claude/settings.json` removes the pinned Claude model setting.
- `apps/web/lib/msw/handlers.ts` removes dashboard and inspector mock handlers.
- `.agents/orchestration/current/incidents.md` records an ENG-312 incident,
  outside the ENG-313/SCR PR scope.
- broader `.agents/strategy/*` and orchestration narrative updates may be useful
  mission bookkeeping, but should be staged deliberately rather than swept in.

## Remaining items before closing ENG-313

1. Decide whether the out-of-scope worktree changes listed above belong in the
   SCR PR, a separate PR, or should remain unstaged.
2. Update Linear statuses for ENG-314/315/316/317 and the ENG-313 parent.
