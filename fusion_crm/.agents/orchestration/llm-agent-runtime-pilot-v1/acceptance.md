# Acceptance Criteria

## Mission Setup

- Mission spec files exist under
  `.agents/orchestration/llm-agent-runtime-pilot-v1/`.
- Runtime telemetry exists under the Orchestrator runtime home.
- Linear sync maps ENG-354 through ENG-361.
- Dashboard-visible runtime state shows the mission and current task.

## Product Acceptance

- A constrained OpenAI/LLM call path exists inside Agent Runtime.
- The LLM receives only a safe prompt envelope and approved tool/query summary.
- The model output is validated before any tool/service execution.
- Policy preflight can allow, deny, clarify, or require approval.
- Run history and audit summary are written for success, denial,
  clarification, and credential failure paths.
- An internal dev workbench can submit safe test prompts and show safe results.

## ENG-362 Approved Analytics Tool Execution Acceptance

- `ask_manager_analytics` is the first executable approved aggregate tool.
- Safe tool arguments from the LLM planner are resolved to an approved
  analytics query/read-model contract before execution.
- Execution calls service-owned analytics/read-model code only.
- The API response distinguishes planner metadata from executed aggregate
  results.
- The workbench renders executed aggregate result metadata without PHI,
  row-level rows, secrets, raw provider payloads, raw prompts containing
  sensitive data, or LLM-owned calculations.
- No-match, denied, and clarification outcomes stop before execution and remain
  visible in run history/audit summaries.

## Safety Acceptance

- No direct DB access from LLM or agent code.
- No raw SQL execution path.
- No PHI, secrets, raw provider payloads, or unmasked samples in persisted run
  history, API responses, logs, or frontend state.
- Write-capable actions and catalog approval remain out of scope.
- Tests cover allowed, denied, ambiguous, credential failure, validation
  failure, and sensitive-field exclusion paths.

## Closure Acceptance

- Local focused backend and frontend verification pass.
- Alembic check passes if DB models/migrations change.
- Browser smoke verifies the workbench renders and safe paths are visible.
- Live-key smoke runs where credentials are configured, or records a safe
  credential/policy failure.
- Linear and Orchestrator runtime statuses are synchronized before closure.
- ENG-362 closure must explicitly document which manager analytics questions
  still lack approved query/read-model coverage.
