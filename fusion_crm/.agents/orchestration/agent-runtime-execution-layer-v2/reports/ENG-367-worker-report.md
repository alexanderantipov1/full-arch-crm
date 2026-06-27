# ENG-367 Worker Report

## Task

ARX-04 Run History Operations And Audit Review V1.

## Linear

- ENG-367 — ARX-04 Run History Operations And Audit Review V1
- Parent: ENG-363 — Agent Runtime Execution Layer V2 Mission Control

## Changed Files

- `packages/agent_runtime/repository.py`
- `packages/agent_runtime/schemas.py`
- `packages/agent_runtime/service.py`
- `apps/api/routers/agent_runtime.py`
- `tests/agent_runtime/test_service.py`
- `tests/api/test_agent_runtime_routes.py`
- `apps/web/lib/api/schemas/agentRuntime.ts`
- `apps/web/lib/api/hooks/useAgentRuntime.ts`
- `apps/web/lib/msw/handlers.ts`
- `apps/web/app/(staff)/dev/agent-runtime/page.tsx`

## What Changed

- Added safe run-history filters for status, tool id, policy result, final
  outcome, actor email, and started-at time range.
- Added an applied-filters DTO to the run-history response so UI and API
  callers can see exactly what filter posture was used.
- Repository filtering covers tenant-scoped column filters.
- Service filtering covers safe JSON metadata such as tool id, policy result,
  and final outcome without exposing raw prompts, raw provider payloads, PHI,
  secrets, or row-level values.
- `/agent-runtime/runs` now accepts the filter query params and caps `limit`
  to 100.
- Agent Runtime workbench now includes run-history review controls and applied
  filter badges.
- MSW fixtures now honor the same run-history filters for local UI testing.

## Verification

- `.venv/bin/python -m pytest -q tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
  - Result: 44 passed.
- `.venv/bin/ruff check packages/agent_runtime/repository.py packages/agent_runtime/service.py packages/agent_runtime/schemas.py apps/api/routers/agent_runtime.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
  - Result: passed.
- `.venv/bin/mypy packages/agent_runtime/repository.py packages/agent_runtime/service.py packages/agent_runtime/schemas.py apps/api/routers/agent_runtime.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
  - Result: passed.
- `cd apps/web && npm run typecheck`
  - Result: passed.
- `cd apps/web && npm run lint`
  - Result: passed.
- `cd apps/web && npm run test -- schemas.test.ts`
  - Result: 18 passed.
- `git diff --check`
  - Result: passed.

## Risks

- Browser smoke was not run in this slice because the dev server was not
  started during implementation.
- JSON metadata filters are applied in service after a bounded repository
  query. This is acceptable for the current dev/control-plane history volume;
  heavier production history can move these filters to indexed projections.
- Approval decision workflow integration remains ENG-368.

## Status

Complete.
