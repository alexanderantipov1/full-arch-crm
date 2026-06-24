# ENG-360 Worker Report - Evaluation, Audit, And Safety Tests V1

## Linear

- Issue: ENG-360 - LLM-06 Evaluation, Audit, And Safety Tests V1
- URL: https://linear.app/fusion-dental-implants/issue/ENG-360/llm-06-evaluation-audit-and-safety-tests-v1
- Status: In Review

## Summary

Implemented the first LLM planner evaluation and safety test pack for the Agent
Runtime pilot. The pack covers allowed aggregate analytics, ambiguous prompts,
database-access refusal, row-level PHI denial, export approval, and Semantic
Catalog proposal approval posture.

The work also fixed one safety issue found during testing: FastAPI's default
request validation response could echo invalid request input. Agent Runtime now
uses a safe request validation envelope that does not reflect prompt bodies or
blocked markers.

## Changed Files

- `apps/api/main.py`
- `apps/api/middleware.py`
- `apps/web/app/(staff)/dev/agent-runtime/page.tsx`
- `apps/web/lib/api/schemas/agentRuntime.ts`
- `apps/web/tests/unit/schemas.test.ts`
- `packages/agent_runtime/schemas.py`
- `packages/integrations/openai/schemas.py`
- `tests/agent_runtime/test_service.py`
- `tests/api/test_agent_runtime_routes.py`
- `tests/integrations/openai/test_client.py`
- `.agents/orchestration/llm-agent-runtime-pilot-v1/incidents.md`

## Implementation Details

- Added LLM eval cases for:
  - allowed aggregate analytics planning;
  - clarification-required ambiguous prompts;
  - database-access refusal;
  - row-level PHI denial;
  - export approval-required posture;
  - Semantic Catalog mapping proposal approval-required posture.
- Asserted every outcome writes safe run history and audit summaries.
- Asserted persisted run data and API responses do not include prompt bodies,
  secrets, raw provider payload markers, PHI marker names, raw SQL markers, or
  unmasked sample posture.
- Added raw SQL prompt marker rejection across backend Agent Runtime schemas,
  OpenAI integration schemas, and frontend Zod schemas.
- Added a global FastAPI `RequestValidationError` handler that returns the
  platform error envelope without echoing invalid request input.
- Added workbench verification evidence and known-not-done-yet notes to
  `/dev/agent-runtime`.

## Verification

- `.venv/bin/python -m pytest -q tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/integrations/openai/test_client.py tests/integrations/openai/test_service.py`
  - Passed: 45 tests.
- `.venv/bin/ruff check apps/api/main.py apps/api/middleware.py packages/agent_runtime/schemas.py packages/integrations/openai/schemas.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/integrations/openai/test_client.py`
  - Passed.
- `.venv/bin/mypy apps/api/main.py apps/api/middleware.py packages/agent_runtime/schemas.py packages/integrations/openai/schemas.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/integrations/openai/test_client.py`
  - Passed.
- `cd apps/web && npm run test -- tests/unit/schemas.test.ts`
  - Passed: 18 tests.
- `cd apps/web && npm run typecheck`
  - Passed.
- `cd apps/web && npm run lint`
  - Passed.
- Headless browser check on `http://127.0.0.1:3000/dev/agent-runtime`
  - Passed: ENG-360 evaluation coverage and known limits render.

## Known Limits

- No live-key smoke was run in this worker; it remains optional and should use
  tenant-owned credentials only.
- The workbench still returns a plan, not a final manager-facing answer.
- Tool execution, resumable LLM runs, and full LLM planner promotion remain
  deferred to later slices.

## Risks And Follow-Up

- ENG-361 should document the live smoke path, production readiness posture, and
  remaining second-layer evaluation work.
- Future evals should include replayable golden fixtures once real manager
  prompts exist.
