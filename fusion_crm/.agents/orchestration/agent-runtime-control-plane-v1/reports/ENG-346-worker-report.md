# ENG-346 Worker Report — Agent Run History V1

## Status

Implemented and ready for review.

## Changed Files

- `packages/agent_runtime/models.py`
- `packages/agent_runtime/repository.py`
- `packages/agent_runtime/schemas.py`
- `packages/agent_runtime/service.py`
- `packages/agent_runtime/CLAUDE.md`
- `packages/db/registry.py`
- `packages/db/alembic/versions/20260605_0900_d3e4f5a6b7c8_add_agent_runtime_run_history.py`
- `packages/audit/CLAUDE.md`
- `apps/api/routers/agent_runtime.py`
- `apps/api/routers/tenant.py`
- `tests/agent_runtime/test_service.py`
- `tests/api/test_agent_runtime_routes.py`
- `tests/api/test_tenant_credential_routes.py`
- `apps/web/lib/api/schemas/agentRuntime.ts`
- `apps/web/lib/api/hooks/useAgentRuntime.ts`
- `apps/web/lib/msw/handlers.ts`
- `apps/web/app/(staff)/dev/agent-runtime/page.tsx`
- `apps/web/tests/unit/schemas.test.ts`

## Delivered

- Added `audit.agent_runtime_run` as a persisted safe run-summary table.
- Added `AgentRuntimeRun` model and repository.
- Added run history DTOs with status values:
  `success`, `failure`, `blocked`, `approval_required`, `denied`.
- Changed OpenAI health-check execution to record a successful
  `provider_health_check` run summary.
- Added `GET /agent-runtime/runs`.
- Added frontend Zod schema and React Query hook for run history.
- Added MSW local run-history examples.
- Added `/dev/agent-runtime` Run history panel.

## Safety

- Run history is not a trace store.
- It does not store prompt bodies, provider payloads, API keys, raw SQL, PHI,
  or unmasked row-level data.
- The first persisted event stores only safe metadata for the provider health
  check.

## Verification

- `.venv/bin/python -m pytest -q tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/api/test_tenant_credential_routes.py`
- `ruff check packages/agent_runtime packages/db/registry.py apps/api/routers/agent_runtime.py apps/api/routers/tenant.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/api/test_tenant_credential_routes.py packages/db/alembic/versions/20260605_0900_d3e4f5a6b7c8_add_agent_runtime_run_history.py`
- `mypy packages/agent_runtime packages/db/registry.py apps/api/routers/agent_runtime.py apps/api/routers/tenant.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/api/test_tenant_credential_routes.py`
- `npm run typecheck`
- `npm run test -- tests/unit/schemas.test.ts`
- `npm run lint -- --file 'app/(staff)/dev/agent-runtime/page.tsx' --file lib/api/hooks/useAgentRuntime.ts --file lib/api/schemas/agentRuntime.ts --file lib/msw/handlers.ts --file tests/unit/schemas.test.ts`
- Browser debug smoke: `/api/agent-runtime/runs` returned 200 and `/dev/agent-runtime` rendered Run history, `Fusion OpenAI Health Check`, and `policy: allowed`.
- `alembic heads` shows `d3e4f5a6b7c8 (head)`.
- Metadata import check confirms `audit.agent_runtime_run` is registered in
  `Base.metadata`.

## Blocked Verification

- `alembic check` was attempted, but the local dev database returned
  `Target database is not up to date`. This indicates local DB revision state,
  not a detected metadata drift. Run `alembic upgrade head` on the dev DB before
  repeating `alembic check`.

## Risks

- The dev database has not been upgraded to the new migration in this session.
- Full repository verification was not run.

## Remaining Work

- Review and optionally close ENG-346 after DB upgrade/check.
- Continue with ENG-347 Human Approval Requests V1.
