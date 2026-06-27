# ENG-359 Worker Report - Dev LLM Chat Workbench V1

## Linear

- Issue: ENG-359 - LLM-05 Dev LLM Chat Workbench V1
- URL: https://linear.app/fusion-dental-implants/issue/ENG-359/llm-05-dev-llm-chat-workbench-v1
- Status: In Review

## Summary

Implemented the dev/internal LLM planning workbench inside `/dev/agent-runtime`.
The page now lets a staff/dev user submit a safe prompt to the Agent Runtime LLM
planning endpoint and inspect only safe metadata: run id, selected model,
planner outcome, intent, tool id, policy result, policy reason, approval
posture, safe tool arguments, and safety notes.

This is a planning pilot only. It does not execute tools, expose raw provider
payloads, expose tenant API keys, return PHI, return unmasked samples, or
provide a manager-facing chat UI.

## Changed Files

- `apps/web/app/(staff)/dev/agent-runtime/page.tsx`
- `apps/web/lib/api/hooks/useAgentRuntime.ts`
- `apps/web/lib/api/schemas/agentRuntime.ts`
- `apps/web/lib/msw/init.tsx`
- `apps/web/lib/msw/handlers.ts`
- `apps/web/tests/unit/schemas.test.ts`

## Implementation Details

- Added frontend Zod schemas for `AgentRuntimeLlmPlanIn` and
  `AgentRuntimeLlmPlanOut`.
- Added a React Query mutation for `POST /agent-runtime/llm/plans`.
- Added MSW coverage for safe aggregate, clarification, denied, validation, and
  missing credential states.
- Fixed the mock backend boot provider so server and first client render match
  before MSW starts, preventing React hydration replacement warnings.
- Added the `LLM planning pilot` workbench block to `/dev/agent-runtime`.
- Added Russian-facing product explanation inside the workbench block.
- Kept the UI safe by rendering planner metadata only and never rendering raw
  provider payloads, secrets, PHI, or unmasked samples.

## Verification

- `cd apps/web && npm run test -- tests/unit/schemas.test.ts`
  - Passed: 18 tests.
- `cd apps/web && npm run typecheck`
  - Passed.
- `cd apps/web && npm run lint`
  - Passed.
- Headless browser console check on `http://localhost:3000/dev/semantic-analytics`
  after the MSW boot fix
  - Passed: no relevant hydration mismatch console events.
- Browser smoke against mock dev server on `http://127.0.0.1:3108`
  - Login completed.
  - `/dev/agent-runtime` rendered the LLM planning pilot block.
  - Safe aggregate plan path rendered `allowed` planner result.
  - Clarification path rendered `clarification_required`.
  - Denied row-level/export path rendered `denied` / `refused`.
  - Missing credential path rendered the safe error state.

## Notes

- Existing local server on `http://127.0.0.1:3000` was running with real
  backend access. The demo principal received expected 403 responses for
  Agent Runtime control-plane APIs because those routes require admin/system
  principal access.
- A temporary MSW-enabled dev server on port `3108` was used for the mocked
  browser smoke and was stopped after verification.

## Risks And Follow-Up

- Live backend UI execution depends on an admin/system staff principal.
- ENG-360 should add broader safety/evaluation coverage around the LLM planner
  and audit expectations.
- ENG-361 should document the pilot and perform final production smoke.
