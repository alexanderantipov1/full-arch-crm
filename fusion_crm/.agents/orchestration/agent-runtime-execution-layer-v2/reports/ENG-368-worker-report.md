# ENG-368 Worker Report

## Task

ARX-05 Approval Workflow Integration V1.

## Linear

- ENG-368 — ARX-05 Approval Workflow Integration V1
- Parent: ENG-363 — Agent Runtime Execution Layer V2 Mission Control

## Changed Files

- `packages/agent_runtime/schemas.py`
- `packages/agent_runtime/service.py`
- `tests/agent_runtime/test_service.py`
- `apps/web/lib/api/schemas/agentRuntime.ts`
- `apps/web/app/(staff)/dev/agent-runtime/page.tsx`

## What Changed

- Approval-required LLM plans now pause before execution and automatically
  create a pending Agent Runtime approval request.
- Created approval requests are linked back to the source run through
  `source_run_id`, `linked_approval_request_ids`, and tool-call
  `approval_request_id`.
- Approval payloads store safe metadata only: tool id, target kind/ref, data
  classes, affected surfaces, risk flags, policy reason, and review posture.
- Human approval decisions now create a separate safe `approval_decision` audit
  run that records who decided, what status was selected, and which approval
  request was affected.
- Approval response DTOs now expose a workflow state such as
  `pending_review`, `approved_no_auto_execution`, `rejected`, `needs_edit`, or
  `unresolved`.
- Agent Runtime workbench now shows source run links, workflow state, and linked
  approval ids in run tool-call summaries.

## Verification

- `.venv/bin/python -m pytest -q tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
  - Result: 44 passed.
- `.venv/bin/ruff check packages/agent_runtime/service.py packages/agent_runtime/schemas.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
  - Result: passed.
- `.venv/bin/mypy packages/agent_runtime/service.py packages/agent_runtime/schemas.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
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

- Approval does not auto-execute downstream tools yet. This is intentional for
  V1 because unsafe categories must remain policy-gated and service-owned.
- Expired and executed-after-approval states are reserved in the DTO but are not
  produced until an explicit execution-after-approval worker is added.
- Browser smoke was not run in this slice because the dev server was not
  started during implementation.

## Status

Complete.
