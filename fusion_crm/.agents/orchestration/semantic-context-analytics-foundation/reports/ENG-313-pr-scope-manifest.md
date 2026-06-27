# ENG-313 PR Scope Manifest

Date: 2026-06-02
Current branch observed: `main`

## State

ENG-314/315/316/317 implementation and verification are present in the shared
worktree. Local verification is green after applying the ENG-314 migration to
the development database:

- `make lint`: passed
- `uv run mypy .`: passed
- `cd packages/db && alembic check`: passed
- `PYTHONPATH=. uv run pytest -q`: `1227 passed`
- `PYTHONPATH=. uv run pytest tests/integration/test_tenant_isolation.py -q`:
  `184 passed`
- `apps/web npm run lint`: passed in prior verification
- `apps/web npm run typecheck`: passed in prior verification
- `apps/web npm run test -- schemas.test.ts`: passed in prior verification

The worktree is dirty and currently on `main`. Do not commit from `main`; create
a feature branch first.

## Include In ENG-313/SCR PR

Product backend/API:

- `apps/api/dependencies.py`
- `apps/api/main.py`
- `apps/api/routers/semantic_catalog.py`
- `packages/analytics/`
- `packages/insight/`
- `packages/audit/service.py`
- `packages/db/alembic/env.py`
- `packages/db/registry.py`
- `packages/db/alembic/versions/20260602_0900_c2d3e4f5a6b7_add_insight_semantic_catalog_storage.py`
- `infra/docker/init-schemas.sql`

Product frontend:

- `apps/web/app/(staff)/dev/semantic-analytics/page.tsx`
- `apps/web/components/semantic/`
- `apps/web/lib/api/client.ts`
- `apps/web/lib/api/hooks/useSemanticCatalog.ts`
- `apps/web/lib/api/schemas/index.ts`
- `apps/web/lib/api/schemas/semanticCatalog.ts`
- `apps/web/tests/unit/schemas.test.ts`

Backend tests:

- `tests/analytics/`
- `tests/api/test_semantic_catalog_routes.py`
- `tests/insight/`
- `tests/audit/test_audit_service.py`
- `tests/conftest.py`
- `tests/integration/test_tenant_isolation.py`

Supporting verification fixes:

- `packages/ingest/repository.py`
- `packages/interaction/repository.py`
- `tests/ingest/test_carestack_patients_with_payments_sql.py`
- `tests/_fixtures/workflow_ready.py`
- `tests/integration/test_workflow_ready_e2e.py`

Policy and local area docs:

- `CLAUDE.md`
- `packages/CLAUDE.md`
- `packages/audit/CLAUDE.md`
- `packages/analytics/CLAUDE.md`
- `packages/analytics/AGENTS.md`
- `packages/insight/CLAUDE.md`
- `packages/insight/AGENTS.md`
- `.agents/orchestration/semantic-context-analytics-foundation/acceptance.md`
- `.agents/orchestration/semantic-context-analytics-foundation/contract.md`
- `.agents/orchestration/semantic-context-analytics-foundation/decision-log.md`
- `.agents/orchestration/semantic-context-analytics-foundation/goal.md`
- `.agents/orchestration/semantic-context-analytics-foundation/semantic-catalog-proposal-review-v1.md`
- `.agents/orchestration/semantic-context-analytics-foundation/reports/ENG-313-readiness-report.md`
- `.agents/orchestration/semantic-context-analytics-foundation/reports/ENG-314-315-317-integration-report.md`
- `.agents/orchestration/semantic-context-analytics-foundation/reports/ENG-314-worker-report.md`
- `.agents/orchestration/semantic-context-analytics-foundation/reports/ENG-315-worker-report.md`
- `.agents/orchestration/semantic-context-analytics-foundation/reports/ENG-316-frontend-api-integration-report.md`
- `.agents/orchestration/semantic-context-analytics-foundation/reports/ENG-317-frontend-history-report.md`
- `.agents/orchestration/semantic-context-analytics-foundation/reports/ENG-317-history-api-report.md`
- `.agents/orchestration/semantic-context-analytics-foundation/reports/ENG-317-worker-report.md`
- `.agents/orchestration/semantic-context-analytics-foundation/reports/ENG-313-pr-scope-manifest.md`

## Hold Back Unless Explicitly Accepted

These files are modified in the worktree but are not necessary for the
ENG-313/SCR implementation:

- `.claude/settings.json` removes the pinned Claude model setting.
- `apps/web/lib/msw/handlers.ts` removes dashboard and inspector MSW handlers.
  This is risky because those endpoints are unrelated to semantic catalog
  review. Frontend policy says to delete an MSW handler when its matching
  backend endpoint lands; this diff deletes unrelated handlers.
- `.agents/orchestration/current/incidents.md` records an ENG-312 incident,
  outside the ENG-313/SCR PR scope.
- `.agents/orchestration/HYBRID_KICKOFF.md` updates fleet/ENG-312 state, not
  ENG-313 implementation.
- `.agents/strategy/CANDIDATE_MISSIONS.md`
- `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md`
- `.agents/strategy/SEMANTIC_CONTEXT_ANALYTICS_FOUNDATION_PLAN.md`
- `.agents/orchestration/semantic-context-analytics-foundation/data-intelligence-agent-contract-v1.md`
- `.agents/orchestration/semantic-context-analytics-foundation/semantic-analytics-foundation-overview-ru.md`

The strategy/orchestration narrative updates may be useful, but they should be
staged deliberately in a mission-docs PR or accepted into this PR by owner
decision.

## Suggested Staging Command

Run only after creating a feature branch:

```bash
git switch -c eng-313-semantic-catalog-review
git add \
  CLAUDE.md \
  apps/api/dependencies.py \
  apps/api/main.py \
  apps/api/routers/semantic_catalog.py \
  apps/web/app/'(staff)'/dev/semantic-analytics/page.tsx \
  apps/web/components/semantic \
  apps/web/lib/api/client.ts \
  apps/web/lib/api/hooks/useSemanticCatalog.ts \
  apps/web/lib/api/schemas/index.ts \
  apps/web/lib/api/schemas/semanticCatalog.ts \
  apps/web/tests/unit/schemas.test.ts \
  infra/docker/init-schemas.sql \
  packages/CLAUDE.md \
  packages/analytics \
  packages/audit/CLAUDE.md \
  packages/audit/service.py \
  packages/db/alembic/env.py \
  packages/db/registry.py \
  packages/db/alembic/versions/20260602_0900_c2d3e4f5a6b7_add_insight_semantic_catalog_storage.py \
  packages/ingest/repository.py \
  packages/insight \
  packages/interaction/repository.py \
  tests/_fixtures/workflow_ready.py \
  tests/analytics \
  tests/api/test_semantic_catalog_routes.py \
  tests/audit/test_audit_service.py \
  tests/conftest.py \
  tests/ingest/test_carestack_patients_with_payments_sql.py \
  tests/insight \
  tests/integration/test_tenant_isolation.py \
  tests/integration/test_workflow_ready_e2e.py \
  .agents/orchestration/semantic-context-analytics-foundation/acceptance.md \
  .agents/orchestration/semantic-context-analytics-foundation/contract.md \
  .agents/orchestration/semantic-context-analytics-foundation/decision-log.md \
  .agents/orchestration/semantic-context-analytics-foundation/goal.md \
  .agents/orchestration/semantic-context-analytics-foundation/semantic-catalog-proposal-review-v1.md \
  .agents/orchestration/semantic-context-analytics-foundation/reports/ENG-313-readiness-report.md \
  .agents/orchestration/semantic-context-analytics-foundation/reports/ENG-313-pr-scope-manifest.md \
  .agents/orchestration/semantic-context-analytics-foundation/reports/ENG-314-315-317-integration-report.md \
  .agents/orchestration/semantic-context-analytics-foundation/reports/ENG-314-worker-report.md \
  .agents/orchestration/semantic-context-analytics-foundation/reports/ENG-315-worker-report.md \
  .agents/orchestration/semantic-context-analytics-foundation/reports/ENG-316-frontend-api-integration-report.md \
  .agents/orchestration/semantic-context-analytics-foundation/reports/ENG-317-frontend-history-report.md \
  .agents/orchestration/semantic-context-analytics-foundation/reports/ENG-317-history-api-report.md \
  .agents/orchestration/semantic-context-analytics-foundation/reports/ENG-317-worker-report.md
```

After staging, verify the index before committing:

```bash
git diff --cached --name-only
git diff --cached --check
```

## Risks

- Current checkout is `main`; committing directly would mix local WIP into the
  canonical branch.
- `apps/web/lib/msw/handlers.ts` has a large unrelated removal and can
  accidentally regress dev/test mock behavior if swept into the PR.
- `.claude/settings.json` is tool configuration, not product or mission scope.
- Linear statuses are not yet updated from this session's verified state.

## Next Actions

1. Create a feature branch for ENG-313.
2. Stage only the manifest include list above.
3. Re-run cached diff checks.
4. Re-run frontend checks if the staged set includes frontend files:
   `cd apps/web && npm run lint && npm run typecheck && npm run test -- schemas.test.ts`.
5. Commit only after explicit owner approval.
6. Update Linear statuses for ENG-314/315/316/317 and the ENG-313 parent after
   the PR scope is confirmed.
