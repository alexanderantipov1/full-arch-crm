# ENG-365 Worker Report

## Task

ARX-02 Approved Query And Read Model Matching V2.

## Linear

- ENG-365 — ARX-02 Approved Query And Read Model Matching V2
- Parent: ENG-363 — Agent Runtime Execution Layer V2 Mission Control

## Changed Files

- `packages/tools/manager_chat_tools.py`
- `packages/agent_runtime/schemas.py`
- `packages/agent_runtime/service.py`
- `tests/tools/test_manager_chat_tools.py`
- `tests/agent_runtime/test_service.py`
- `apps/web/lib/api/schemas/agentRuntime.ts`
- `apps/web/lib/msw/handlers.ts`
- `apps/web/app/(staff)/dev/agent-runtime/page.tsx`

## What Changed

- Added deterministic manager analytics query/read-model match metadata:
  query id, read model id, confidence, reason, and matched keywords.
- Agent Runtime now checks the approved query/read-model match before calling
  `ask_manager_analytics`.
- Unmatched manager questions stop as `no_match` before tool execution.
- Executed results expose safe match metadata in API DTOs and the dev
  workbench.
- Run history tool calls now include matched query/read-model metadata when
  available.
- Audit summaries now include an `approved_query_read_model_match` policy gate
  for matched executions.
- Added drift protection: if a tool execution returns a different query/read
  model than the deterministic match, the run fails safely.

## Verification

- `.venv/bin/python -m pytest -q tests/tools/test_manager_chat_tools.py tests/agent_runtime/test_service.py`
  - Result: 34 passed.
- `.venv/bin/ruff check packages/tools/manager_chat_tools.py packages/agent_runtime/service.py packages/agent_runtime/schemas.py tests/tools/test_manager_chat_tools.py tests/agent_runtime/test_service.py`
  - Result: passed.
- `.venv/bin/mypy packages/tools/manager_chat_tools.py packages/agent_runtime/service.py packages/agent_runtime/schemas.py tests/tools/test_manager_chat_tools.py tests/agent_runtime/test_service.py`
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

- This slice still covers manager analytics matching only.
- Broader registry-driven tool execution remains ENG-366.
- Richer run-history filtering and approval workflow remain ENG-367/ENG-368.

## Status

Complete.
