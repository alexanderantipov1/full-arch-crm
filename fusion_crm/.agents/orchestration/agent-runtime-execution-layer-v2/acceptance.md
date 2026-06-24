# Acceptance Criteria

## Mission Setup

- Mission spec files exist under
  `.agents/orchestration/agent-runtime-execution-layer-v2/`.
- Runtime telemetry exists under the Orchestrator runtime home.
- Linear sync maps ENG-363 through ENG-370.
- Dashboard-visible runtime state shows the Orchestrator and planned workers.
- ENG-364 closes only after repo spec and runtime state are synchronized.

## Product Acceptance

- Safe LLM tool arguments can resolve to deterministic approved query and
  read-model contracts before execution.
- Tool execution is registry-driven and service-owned.
- Unsupported, ambiguous, unsafe, export, row-level, PHI, raw SQL,
  write-capable, and catalog-auto-approval paths fail closed before execution.
- Run history can be filtered and reviewed by safe metadata.
- Audit summaries explain allowed, clarified, denied, approval-required,
  no-match, executed, and failed outcomes.
- Approval-required runs pause before execution and can be approved or rejected
  without exposing sensitive data.
- Agent Runtime can show safe links to relevant Semantic Catalog, Query
  Registry, Read Model, and DIA metadata.

## Safety Acceptance

- No direct DB access from LLM or agent code.
- No raw SQL execution path.
- No PHI, secrets, raw provider payloads, raw prompts with sensitive values,
  unmasked samples, row-level data, or export payloads in persisted run history,
  API responses, logs, docs, or frontend state.
- Catalog changes remain human-reviewed and versioned.
- Tests cover allowed, denied, ambiguous, no-match, approval-required,
  credential failure, validation failure, and sensitive-field exclusion paths.

## Closure Acceptance

- Local focused backend and frontend verification passes for changed areas.
- Alembic check passes if DB models or migrations change.
- Browser smoke verifies the workbench renders and V2 states are visible.
- Live-key smoke runs where credentials are configured, or records a safe
  credential/policy failure.
- Production deploy and smoke pass.
- Linear and Orchestrator runtime statuses are synchronized before closure.
- Remaining future work is visible in Linear and mission artifacts.
