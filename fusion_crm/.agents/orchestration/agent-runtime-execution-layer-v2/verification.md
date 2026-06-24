# Verification Plan

## Backend

- Run focused `pytest` for Agent Runtime service, API routes, tool registry,
  approval, and audit-summary tests touched by the mission.
- Run `ruff` and `mypy` for changed backend modules.
- Run Alembic check if DB models or migrations change.

## Frontend

- Run focused schema/component tests for `/dev/agent-runtime` workbench changes.
- Run `npm run typecheck` and `npm run lint` in `apps/web` for changed UI work.
- Use browser smoke for local workbench rendering and important states:
  allowed execution, clarification, denial, approval-required, no-match, and
  missing credential.

## Safety

- Assert API responses exclude secrets, raw provider payloads, PHI, raw prompts
  with sensitive values, row-level rows, raw SQL, and unmasked samples.
- Assert unsafe prompt categories stop before execution.
- Assert approval-required runs do not execute before approval.
- Assert catalog/DIA linkage remains review-only unless approved catalog
  versions already exist.

## Production Closure

- PR checks must pass.
- Production deploy must pass.
- Production route smoke must prove `/dev/agent-runtime` is present and
  protected.
- Live-key smoke should run where credentials are configured; otherwise record
  the safe missing-credential result.
- Linear and Orchestrator runtime must be synchronized before the mission is
  marked complete.

## ENG-370 Verification Results

Completed on 2026-06-08:

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

Browser smoke:

- Local `/dev/agent-runtime` after staff login rendered Agent Runtime, Execution
  Layer V2 closure, ENG-370, run history, approval requests, and DIA/Semantic
  Catalog linkage with no console errors, no 404, and no internal server error.
- Local `/dev/agent-runtime?doc=overview&lang=ru` rendered Russian docs,
  Execution Layer V2, and the V2 not-done-yet section with no console errors,
  no 404, and no internal server error.
- Production `https://fusioncrm.app/dev/agent-runtime` returned Google IAP
  protected redirect (`302`) instead of `404`, proving the route is present and
  protected by production auth.

Alembic check was not run for ENG-370 because this closure slice changed only
documentation and frontend workbench copy; no DB models or migrations changed.
