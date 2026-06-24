# ENG-377 Worker Report

## Task

MANS-06 Evals, Documentation, Smoke, And Closure.

## Linear

- ENG-377 — MANS-06 Evals, Documentation, Smoke, And Closure
- Parent: ENG-371 — Agent Runtime Manager Answer Layer V1 Mission Control

## Changed Files

- `.agents/orchestration/agent-runtime-manager-answer-layer-v1/evals.md`
- `.agents/orchestration/agent-runtime-manager-answer-layer-v1/closure.md`
- `.agents/orchestration/agent-runtime-manager-answer-layer-v1/verification.md`
- `.agents/orchestration/agent-runtime-manager-answer-layer-v1/incidents.md`
- `.agents/orchestration/agent-runtime-manager-answer-layer-v1/ownership.yaml`
- `.agents/orchestration/agent-runtime-manager-answer-layer-v1/reports/ENG-377-worker-report.md`

## Summary

- Added final eval matrix for allowed aggregate answer, clarification, no-match,
  denied PHI, denied row-level/export, raw SQL rejection, approval-required,
  missing credential, run-history answer audit, and frontend schema parsing.
- Added mission closure summary with closed scope, verification evidence, known
  external failures, and not-done-yet future work.
- Recorded local and production smoke results.
- Recorded full-suite verification caveats:
  - default `make test` uses system `python` and fails due missing dependencies;
  - `.venv` full suite has three unrelated Project Manager dashboard failures.
- Confirmed focused Agent Runtime backend/frontend verification passes.

## Verification

- `make lint`
  - Passed.
- `mypy .`
  - Passed: 357 source files.
- `make test`
  - Failed during collection because default shell `python` lacks project
    dependencies.
- `PATH=.venv/bin:$PATH make test`
  - Failed: 1398 passed, 3 failed in `tests/api/test_dashboard_pm.py`, outside
    Agent Runtime scope.
- `.venv/bin/python -m pytest -q tests/api/test_agent_runtime_routes.py tests/agent_runtime/test_answer_schemas.py tests/agent_runtime/test_service.py`
  - Passed: 48 tests.
- `.venv/bin/ruff check packages/integrations/openai packages/agent_runtime tests/agent_runtime/test_answer_schemas.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
  - Passed.
- `.venv/bin/mypy packages/integrations/openai packages/agent_runtime tests/agent_runtime/test_answer_schemas.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
  - Passed.
- `npm run test -- schemas.test.ts`
  - Passed: 19 tests.
- `npm run lint -- --file app/(staff)/dev/agent-runtime/page.tsx --file lib/api/schemas/agentRuntime.ts --file lib/msw/handlers.ts --file tests/unit/schemas.test.ts`
  - Passed.
- `npm run typecheck`
  - Passed.
- `alembic check` from `packages/db`
  - Passed: no new upgrade operations detected.
- Local browser smoke
  - Passed for allowed answer, clarification, denied, missing credential, and
    run-history answer audit.
- Production route smoke
  - `https://fusioncrm.app/dev/agent-runtime` returns IAP `302`.

## Risks

- Full-suite `.venv` failures in Project Manager dashboard tests remain outside
  this mission and should be handled separately before treating the whole repo as
  fully green.
- Manager Answer Layer V1 is still an internal workbench and runtime layer; it
  is not yet promoted into production Manager AI Chat.

## Remaining Questions

- None for ENG-377 scope.
