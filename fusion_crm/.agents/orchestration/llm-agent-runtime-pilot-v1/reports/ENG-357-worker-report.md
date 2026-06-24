# ENG-357 Worker Report — Approved Tool Planning And Policy Gate V1

## Status

Completed; ready for review.

## Linear

- Parent: ENG-354 — LLM Agent Runtime Pilot V1 Mission Control
- Task: ENG-357 — LLM-03 Approved Tool Planning And Policy Gate V1

## Summary

Added the first Agent Runtime policy gate for validated LLM plans. The planner
still does not execute tools, but every model-selected tool is now classified
before execution as allowed, denied, blocked, or approval-required.

## Changed Files

- `packages/agent_runtime/schemas.py`
- `packages/agent_runtime/service.py`
- `packages/agent_runtime/CLAUDE.md`
- `tests/agent_runtime/test_service.py`

## Delivered

- `AgentRuntimeLlmPlanOut` now includes policy posture:
  `policy_result`, `policy_reason`, and `approval_required`.
- Safe aggregate/metadata tools are allowed for the pilot.
- PHI-bearing tools are denied.
- Write/export/catalog-mutation tools become approval-required.
- Non-aggregate row/worklist-style tools are blocked until a later policy slice.
- Run history and audit summaries reflect the policy outcome.

## Verification

- `python -m pytest -q tests/agent_runtime/test_service.py tests/integrations/openai/test_client.py tests/integrations/openai/test_service.py`
  - Result: 22 passed
- `ruff check packages/agent_runtime packages/integrations/openai tests/agent_runtime/test_service.py tests/integrations/openai/test_client.py tests/integrations/openai/test_service.py`
  - Result: passed
- `mypy packages/agent_runtime packages/integrations/openai tests/agent_runtime/test_service.py tests/integrations/openai/test_client.py tests/integrations/openai/test_service.py`
  - Result: passed

## Risks And Follow-Ups

- The gate is conservative by design. ENG-358 should expose the API path and
  make these postures visible to callers.
- Later slices can expand the allowlist when row-level allowlists, approval
  UX, and audit rules are stronger.

