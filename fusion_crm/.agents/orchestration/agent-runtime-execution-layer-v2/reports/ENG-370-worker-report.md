# ENG-370 Worker Report

## Task

ARX-07 Evals, Documentation, Production Smoke, And Closure.

## Linear

- ENG-370 — ARX-07 Evals, Documentation, Production Smoke, And Closure
- Parent: ENG-363 — Agent Runtime Execution Layer V2 Mission Control

## Changed Files

- `.agents/orchestration/agent-runtime-execution-layer-v2/evals.md`
- `.agents/orchestration/agent-runtime-execution-layer-v2/closure.md`
- `.agents/orchestration/agent-runtime-execution-layer-v2/ownership.yaml`
- `.agents/orchestration/agent-runtime-execution-layer-v2/reports/ENG-370-worker-report.md`
- `apps/web/app/(staff)/dev/agent-runtime/page.tsx`

## Summary

- Added the V2 eval matrix covering allowed aggregate execution,
  clarification, no-match, denied unsafe requests, approval-required proposals,
  missing credentials, audit-safe persistence, and DIA/Semantic Catalog
  lineage.
- Added mission closure documentation with closed scope, product meaning,
  deliberately unfinished work, safety posture, and recommended next mission
  candidates.
- Updated the Agent Runtime workbench docs and status UI so the page now
  explains Execution Layer V2, ENG-363 through ENG-370, V2 eval scenarios, and
  second-layer work.
- Updated mission ownership to show ENG-370 and the parent mission completed
  after closure checks.

## Verification

- `.venv/bin/python -m pytest -q tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/tools/test_manager_chat_tools.py`
  - Passed: 50 tests.
- `.venv/bin/ruff check packages/agent_runtime packages/tools apps/api/routers/agent_runtime.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/tools/test_manager_chat_tools.py`
  - Passed.
- `.venv/bin/mypy packages/agent_runtime packages/tools apps/api/routers/agent_runtime.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/tools/test_manager_chat_tools.py`
  - Passed for 19 source files.
- `npm run test -- schemas.test.ts` in `apps/web`
  - Passed: 18 tests.
- `npm run lint -- --file app/(staff)/dev/agent-runtime/page.tsx --file lib/api/schemas/agentRuntime.ts --file lib/api/hooks/useAgentRuntime.ts` in `apps/web`
  - Passed.
- `npm run typecheck` in `apps/web`
  - Passed.
- `git diff --check`
  - Passed.
- Local browser smoke:
  - `/dev/agent-runtime` rendered Agent Runtime, Execution Layer V2 closure,
    ENG-370, run history, approval requests, and DIA/Semantic Catalog linkage.
  - `/dev/agent-runtime?doc=overview&lang=ru` rendered Russian docs, Execution
    Layer V2, and the not-done-yet V2 section.
  - No console errors, no 404, and no internal server error were observed.
- Production route smoke:
  - `https://fusioncrm.app/dev/agent-runtime` returned Google IAP protected
    redirect (`302`) instead of `404`.

Alembic check was not run because ENG-370 changed documentation and frontend
workbench copy only; no DB models or migrations changed.

## Risks

- Production smoke depends on the deployed build and authentication state.
- Final manager-facing answer generation is not part of V2 and must not be
  represented as complete.

## Remaining Questions

- None for ENG-370 closure scope.
