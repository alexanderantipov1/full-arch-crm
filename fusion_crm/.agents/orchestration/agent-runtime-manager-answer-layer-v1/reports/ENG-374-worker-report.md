# ENG-374 Worker Report

## Task

MANS-03 LLM Answer Generation From Approved Aggregates.

## Linear

- ENG-374 — MANS-03 LLM Answer Generation From Approved Aggregates
- Parent: ENG-371 — Agent Runtime Manager Answer Layer V1 Mission Control

## Changed Files

- `packages/integrations/openai/schemas.py`
- `packages/integrations/openai/client.py`
- `packages/integrations/openai/service.py`
- `packages/agent_runtime/schemas.py`
- `packages/agent_runtime/service.py`
- `tests/agent_runtime/test_service.py`
- `apps/web/lib/api/schemas/agentRuntime.ts`
- `apps/web/tests/unit/schemas.test.ts`
- `.agents/orchestration/agent-runtime-manager-answer-layer-v1/ownership.yaml`
- `.agents/orchestration/agent-runtime-manager-answer-layer-v1/reports/ENG-374-worker-report.md`

## Summary

- Added a separate manager answer OpenAI client that uses `gpt-4.1`.
- Kept the existing planner on `gpt-4.1-mini`.
- Added safe OpenAI manager answer input, decision, and output contracts.
- Added Agent Runtime answer generation after approved aggregate tool execution.
- Added answer eligibility metadata and manager answer payloads to the LLM plan
  response.
- Built the answer prompt envelope from approved aggregate execution output,
  data classes, caveats, query/read-model refs, evidence refs, and approved
  catalog version refs only.
- Added fail-closed answer states for not-generated, blocked, and validation
  failed outcomes.
- Updated frontend Zod response schemas to parse answer eligibility and manager
  answer payloads.

## Verification

- `.venv/bin/python -m pytest -q tests/agent_runtime/test_answer_schemas.py tests/agent_runtime/test_service.py`
  - Passed: 35 tests.
- `.venv/bin/python -m pytest -q tests/api/test_agent_runtime_routes.py`
  - Passed: 13 tests.
- `.venv/bin/ruff check packages/integrations/openai packages/agent_runtime tests/agent_runtime/test_answer_schemas.py tests/agent_runtime/test_service.py`
  - Passed.
- `.venv/bin/mypy packages/integrations/openai packages/agent_runtime tests/agent_runtime/test_answer_schemas.py tests/agent_runtime/test_service.py`
  - Passed.
- `npm run test -- schemas.test.ts` in `apps/web`
  - Passed: 19 tests.
- `npm run lint -- --file lib/api/schemas/agentRuntime.ts --file tests/unit/schemas.test.ts` in `apps/web`
  - Passed.
- `npm run typecheck` in `apps/web`
  - Passed.

## Risks

- The workbench UI does not yet render the final manager answer card. That is
  owned by ENG-376.
- Run history and audit summaries do not yet expose answer-specific metadata.
  That is owned by ENG-375.
- Live-key browser smoke is still owned by the mission closure task after the UI
  renders final answers.

## Remaining Questions

- None for ENG-374 scope.
