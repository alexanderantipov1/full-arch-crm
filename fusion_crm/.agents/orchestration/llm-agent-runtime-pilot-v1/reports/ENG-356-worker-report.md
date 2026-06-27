# ENG-356 Worker Report — OpenAI Gateway And Prompt Contract V1

## Status

Completed; ready for review.

## Linear

- Parent: ENG-354 — LLM Agent Runtime Pilot V1 Mission Control
- Task: ENG-356 — LLM-02 OpenAI Gateway And Prompt Contract V1

## Summary

Implemented the first constrained OpenAI planning gateway for Agent Runtime.
The new path reads tenant-scoped OpenAI credentials through the existing
credential service, sends a safe JSON planning envelope to OpenAI Agents SDK,
validates the returned `agent_plan_v1` contract, and records safe Agent Runtime
run history/audit metadata.

This slice does not execute tools or expose a user-facing API yet. ENG-357 and
ENG-358 own policy-gated tool planning and the execution API.

## Changed Files

- `packages/integrations/openai/schemas.py`
- `packages/integrations/openai/client.py`
- `packages/integrations/openai/service.py`
- `packages/integrations/openai/CLAUDE.md`
- `packages/agent_runtime/schemas.py`
- `packages/agent_runtime/service.py`
- `packages/agent_runtime/CLAUDE.md`
- `tests/integrations/openai/test_client.py`
- `tests/integrations/openai/test_service.py`
- `tests/agent_runtime/test_service.py`

## Delivered

- `OpenAIAgentPlanningClient` with tracing disabled and safe JSON-only planner
  instructions.
- `OpenAIAgentPlanIn` / `OpenAIAgentPlanOut` and safe OpenAI tool descriptors.
- `OpenAIIntegrationService.generate_agent_plan(...)` using tenant-owned
  `(openai, api_key)` credentials only.
- `AgentRuntimeService.generate_llm_plan(...)` that records safe run
  history/audit metadata for success and failure outcomes.
- Tests for tenant key usage, missing key, prompt envelope, unknown tools,
  service success, service failure, and sensitive-field exclusion.

## Safety Notes

- No `OPENAI_API_KEY` environment fallback was added.
- API keys are passed only in memory to the provider client.
- Provider tracing remains disabled and sensitive trace data is disabled.
- Prompt bodies and raw provider payloads are not persisted in Agent Runtime
  run history or audit summaries.
- Tool execution is intentionally not part of this slice.

## Verification

- `python -m pytest -q tests/integrations/openai/test_client.py tests/integrations/openai/test_service.py tests/agent_runtime/test_service.py`
  - Result: 18 passed
- `ruff check packages/integrations/openai packages/agent_runtime tests/integrations/openai/test_client.py tests/integrations/openai/test_service.py tests/agent_runtime/test_service.py`
  - Result: passed
- `mypy packages/integrations/openai packages/agent_runtime tests/integrations/openai/test_client.py tests/integrations/openai/test_service.py tests/agent_runtime/test_service.py`
  - Result: passed

## Risks And Follow-Ups

- Live-key smoke was not run in this slice because ENG-358 will expose the
  first API path for controlled browser/API execution.
- ENG-357 must validate model-selected tool plans against policy gates before
  any service/tool execution.
- ENG-358 must expose safe success, denial, clarification, and credential
  failure responses.

