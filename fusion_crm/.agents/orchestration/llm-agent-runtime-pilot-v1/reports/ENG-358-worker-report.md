# ENG-358 Worker Report — Agent Run Execution API V1

## Status

Completed; ready for review.

## Linear

- Parent: ENG-354 — LLM Agent Runtime Pilot V1 Mission Control
- Task: ENG-358 — LLM-04 Agent Run Execution API V1

## Summary

Added the first backend API surface for constrained LLM planning runs:
`POST /agent-runtime/llm/plans`.

The endpoint is still internal/dev Agent Runtime control-plane scope. It calls
`AgentRuntimeService.generate_llm_plan(...)`, persists safe run history through
the service layer, and returns only safe planning metadata for UI testing.

## Changed Files

- `apps/api/routers/agent_runtime.py`
- `tests/api/test_agent_runtime_routes.py`
- `.agents/orchestration/llm-agent-runtime-pilot-v1/ownership.yaml`

## Delivered

- API request DTO: `AgentRuntimeLlmPlanIn`.
- API response DTO: `AgentRuntimeLlmPlanOut`.
- Route: `POST /agent-runtime/llm/plans`.
- Tests for safe success response, denied policy posture, platform validation
  failure, and unsafe request-body validation.

## Safety Notes

- Route remains behind existing Agent Runtime staff/dev access guard.
- Route returns no prompt body, raw provider payload, API key, PHI, or raw SQL.
- Route does not execute tools; it exposes validated planning and policy posture
  only.

## Verification

- `python -m pytest -q tests/api/test_agent_runtime_routes.py tests/agent_runtime/test_service.py tests/integrations/openai/test_client.py tests/integrations/openai/test_service.py`
  - Result: 35 passed
- `ruff check apps/api/routers/agent_runtime.py packages/agent_runtime packages/integrations/openai tests/api/test_agent_runtime_routes.py tests/agent_runtime/test_service.py tests/integrations/openai/test_client.py tests/integrations/openai/test_service.py`
  - Result: passed
- `mypy apps/api/routers/agent_runtime.py packages/agent_runtime packages/integrations/openai tests/api/test_agent_runtime_routes.py tests/agent_runtime/test_service.py tests/integrations/openai/test_client.py tests/integrations/openai/test_service.py`
  - Result: passed

## Risks And Follow-Ups

- ENG-359 should add the dev workbench UI for manual browser testing.
- Live-key smoke should happen through the workbench/API once the UI path lands.

