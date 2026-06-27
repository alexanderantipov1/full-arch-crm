# ENG-366 Worker Report

## Task

ARX-03 Approved Tool Execution Registry Expansion V2.

## Linear

- ENG-366 — ARX-03 Approved Tool Execution Registry Expansion V2
- Parent: ENG-363 — Agent Runtime Execution Layer V2 Mission Control

## Changed Files

- `packages/agent_runtime/schemas.py`
- `packages/agent_runtime/service.py`
- `packages/tools/manager_chat_tools.py`
- `tests/agent_runtime/test_service.py`
- `tests/tools/test_manager_chat_tools.py`
- `apps/web/lib/api/schemas/agentRuntime.ts`
- `apps/web/lib/msw/handlers.ts`
- `apps/web/app/(staff)/dev/agent-runtime/page.tsx`

## What Changed

- Added explicit Agent Runtime tool execution posture:
  `executable`, `planning_only`, `approval_required`, or `blocked`.
- Exposed execution posture in backend DTOs, web schemas, MSW fixtures, and
  the Agent Runtime dev workbench tool registry projection.
- Added a registry-driven LLM execution adapter map so only approved tools can
  move from planning into execution.
- Kept planning-only tools visible but non-executed when they have no approved
  Agent Runtime adapter.
- Added direct execution support for `run_analytics_query` using canonical
  approved query ids and safe structured params.
- Preserved deterministic `ask_manager_analytics` execution with approved
  query/read-model matching and drift protection.
- Added audit evidence for approved query/read-model execution decisions.

## Verification

- `.venv/bin/python -m pytest -q tests/agent_runtime/test_service.py tests/tools/test_manager_chat_tools.py`
  - Result: 36 passed.
- `.venv/bin/ruff check packages/agent_runtime/service.py packages/agent_runtime/schemas.py packages/tools/manager_chat_tools.py tests/agent_runtime/test_service.py tests/tools/test_manager_chat_tools.py`
  - Result: passed.
- `.venv/bin/mypy packages/agent_runtime/service.py packages/agent_runtime/schemas.py packages/tools/manager_chat_tools.py tests/agent_runtime/test_service.py tests/tools/test_manager_chat_tools.py`
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

- Only `ask_manager_analytics` and `run_analytics_query` are executable through
  the Agent Runtime LLM path in this slice.
- Approval-required tools are intentionally projected but not executed until
  ENG-368 connects approval workflow handling.
- Richer run-history operations and audit review remain ENG-367.

## Status

Complete.
