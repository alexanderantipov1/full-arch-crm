# ENG-375 Worker Report

## Task

MANS-04 Answer Audit, Run History, And Safety Metadata.

## Linear

- ENG-375 — MANS-04 Answer Audit, Run History, And Safety Metadata
- Parent: ENG-371 — Agent Runtime Manager Answer Layer V1 Mission Control

## Changed Files

- `packages/agent_runtime/schemas.py`
- `packages/agent_runtime/service.py`
- `tests/agent_runtime/test_service.py`
- `apps/web/lib/api/schemas/agentRuntime.ts`
- `apps/web/tests/unit/schemas.test.ts`
- `.agents/orchestration/agent-runtime-manager-answer-layer-v1/ownership.yaml`
- `.agents/orchestration/agent-runtime-manager-answer-layer-v1/reports/ENG-375-worker-report.md`

## Summary

- Added safe answer audit metadata to Agent Runtime run history.
- Added `audit_summary.answer` with status, eligibility, reason, model,
  confidence, source refs, caveats, safety notes, and validation errors.
- Updated Agent Runtime to persist answer metadata after generation or
  fail-closed not-generated/block/validation-failed outcomes.
- Intentionally excluded answer body fields from persisted run history:
  summary, explanation, key numbers, prompt body, raw provider payload, secrets,
  and unsafe SQL markers are not stored.
- Updated frontend Zod schemas for the new run-history answer audit block.
- Added tests that prove generated and not-generated answer metadata is visible
  while forbidden content remains excluded.

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

- Workbench UI still needs to render the final answer and answer audit metadata.
  That is owned by ENG-376.
- Live browser smoke is still pending until the UI surfaces the new fields.

## Remaining Questions

- None for ENG-375 scope.
