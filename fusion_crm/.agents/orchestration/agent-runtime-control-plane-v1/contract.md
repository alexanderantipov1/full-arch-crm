# Contract

## Runtime Boundary

Agent Runtime owns orchestration, provider execution, tool access posture,
human approvals, run summaries, and audit summaries.

It does not own direct data reads. Product data access remains inside approved
services and tools.

## Import And Ownership Rules

- `packages.agent_runtime` may depend on `packages.core`,
  `packages.integrations.openai`, and service-owned tool metadata.
- Agent Runtime must not import repositories directly.
- Agent Runtime must not import PHI services except through approved service
  contracts with explicit policy posture.
- API routes wire DTOs to services only.
- Frontend code consumes Zod schemas and never stores provider secrets.

## Data Safety

Never expose these fields in runtime DTOs, prompts, run history, docs, logs, or
frontend responses:

- OpenAI API keys or credential payloads;
- raw provider payloads;
- raw SQL;
- PHI or unmasked row-level sensitive values;
- full prompt text when it contains sensitive context.

## V1 Surfaces

- Backend: Agent Runtime service and API contracts.
- Frontend: `/dev/agent-runtime` workbench.
- Linear: ENG-343 through ENG-350.
- Orchestrator: mission artifacts and runtime state.

## Deferred

- Full autonomous planner.
- Write-capable tools.
- XLSX, scheduled reports, or row-level exports.
- Provider traces in the UI beyond safe summaries.
