# ENG-362 Worker Report - Approved Analytics Tool Execution V1

## Linear

- Issue: ENG-362 - LLM-08 Approved Analytics Tool Execution V1
- URL: https://linear.app/fusion-dental-implants/issue/ENG-362/llm-08-approved-analytics-tool-execution-v1
- Status: In Review

## Summary

Added the first approved aggregate analytics execution path after LLM planning.

When the LLM planner returns an allowed `ask_manager_analytics` plan with a safe
`question` or `analytics_question` argument, Agent Runtime now executes the
registered tool through `packages.tools` and service-owned aggregate
analytics/read-model code. The response distinguishes planner metadata from
execution metadata and returns aggregate-only result data.

Unsafe, ambiguous, denied, approval-gated, missing-argument, and no-match paths
still stop before execution.

## Changed Files

- `.agents/orchestration/llm-agent-runtime-pilot-v1/acceptance.md`
- `.agents/orchestration/llm-agent-runtime-pilot-v1/contract.md`
- `.agents/orchestration/llm-agent-runtime-pilot-v1/decision-log.md`
- `.agents/orchestration/llm-agent-runtime-pilot-v1/goal.md`
- `.agents/orchestration/llm-agent-runtime-pilot-v1/ownership.yaml`
- `.agents/orchestration/llm-agent-runtime-pilot-v1/verification.md`
- `packages/agent_runtime/CLAUDE.md`
- `packages/agent_runtime/schemas.py`
- `packages/agent_runtime/service.py`
- `tests/agent_runtime/test_service.py`
- `apps/web/lib/api/schemas/agentRuntime.ts`
- `apps/web/lib/msw/handlers.ts`
- `apps/web/app/(staff)/dev/agent-runtime/page.tsx`
- `apps/web/tests/unit/schemas.test.ts`

## Behavior

- `generate_llm_plan` still validates the OpenAI plan and policy gate first.
- Only `ask_manager_analytics` is executable in this slice.
- Execution requires a safe text question argument.
- Execution uses `ToolContext` and the registered tool; Agent Runtime does not
  query repositories, SQL, or the database directly.
- Successful execution records `safe_aggregate_tool_execution` posture and
  `aggregate_only` audit data level.
- No-match and clarification states are represented as safe blocked metadata.
- The workbench shows execution status, query id, read model id, row count,
  data classes, explanation, and aggregate result JSON.

## Verification

- `.venv/bin/python -m pytest -q tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
  - Passed: 39 tests.
- `.venv/bin/ruff check packages/agent_runtime/service.py packages/agent_runtime/schemas.py tests/agent_runtime/test_service.py`
  - Passed.
- `.venv/bin/mypy packages/agent_runtime/service.py packages/agent_runtime/schemas.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
  - Passed.
- `cd apps/web && npm run typecheck`
  - Passed.
- `cd apps/web && npm run lint`
  - Passed.
- `cd apps/web && npm run test -- schemas.test.ts`
  - Passed: 18 tests.
- `git diff --check`
  - Passed.

## Remaining Second-Layer Work

- Broader manager question coverage still depends on approved query/read-model
  metadata and stronger catalog consumption from ENG-320/ENG-335.
- Final natural-language manager answers are still not generated; the UI shows
  safe execution metadata and aggregate result JSON.
- Production inside-IAP live-key execution smoke should be run after this branch
  is merged and deployed.
- Row-level worklists, exports, write tools, catalog approval, and full planner
  promotion remain out of scope.
