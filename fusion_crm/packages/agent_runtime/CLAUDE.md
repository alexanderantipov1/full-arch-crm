# CLAUDE.md — `packages/agent_runtime`

Application-owned AI agent runtime for Fusion CRM.

This package owns orchestration concerns: agent definitions, runner entry
points, provider health checks, guardrails, approvals, tool execution policy,
state handoff, and future trace/audit integration.

## Boundaries

- Provider adapters live in `packages.integrations.<provider>`.
- Tool implementations live in `packages.tools`.
- Business data access stays in domain services.
- Agents must never import repositories, models from other domains, or open
  database sessions directly.

Allowed imports:

- `packages.core`
- `packages.tenant` for tenant-scoped credential resolution
- `packages.integrations` for provider adapters
- `packages.tools` for governed agent-callable tools
- `packages.audit` when runtime-level audit rows land

Do not import `packages.phi` directly. PHI access must go through registered
tools/services that already enforce PHI policy and audit.

## Current Scope

The first slices expose:

- `AgentRuntimeService.test_openai_connection(principal)`
- `AgentRuntimeService.list_tools_projection()`
- `AgentRuntimeService.list_run_history(tenant_id)`
- `AgentRuntimeService.create_approval_request(principal, payload)`
- `AgentRuntimeService.list_approval_requests(tenant_id)`
- `AgentRuntimeService.decide_approval_request(principal, approval_id, payload)`
- `AgentRuntimeService.list_dia_catalog_linkages()`
- `AgentRuntimeService.generate_llm_plan(principal, payload)`

The OpenAI path reads the tenant-owned credential through the OpenAI
integration service and runs a minimal Agents SDK turn. The response is safe
metadata only and never includes the API key.

Run history is persisted as safe summaries in `audit.agent_runtime_run`. It is
not a trace store: no prompt bodies, provider payloads, API keys, PHI, raw SQL,
or unmasked row-level data may be written there.

Run audit summaries are safe posture summaries attached to run history. They
may include data classes, data level, policy gates, policy decisions, final
outcome, safe evidence references, approval links, and compliance notes. They
must not include detailed audit payloads or sensitive input/output.

Human approval requests are persisted as safe summaries in
`audit.agent_runtime_approval_request`. They record review posture and human
decisions for agent-proposed actions, but they do not mutate downstream business
truth. Semantic Catalog approval remains the source of truth for catalog
meaning.

DIA and Semantic Catalog linkages are safe projections. They describe how agent
outputs can move through review, approval, catalog proposal review, and approved
versions. They are not write paths and must keep downstream catalog consumption
approved-version-only.

LLM planning is the first OpenAI-powered pilot path. It sends a safe prompt
envelope to the OpenAI integration, validates the returned `agent_plan_v1`
contract, records safe run history/audit metadata, and can execute the first
approved aggregate analytics tool slice when policy allows it.

ENG-362 enables only `ask_manager_analytics` execution from an allowed plan.
That execution runs through `packages.tools` and service-owned aggregate
analytics/read-model code. It does not access the database directly, store
prompt bodies, persist raw provider payloads, expose PHI or row-level rows, or
approve business meaning.

The LLM policy gate is intentionally conservative for V1:

- approved aggregate/metadata tools can be planned;
- PHI-bearing tools are denied;
- write-capable, export, or catalog-mutation tools require approval;
- non-aggregate row/worklist-style tools are blocked until a later policy
  slice explicitly approves them.

## Future Responsibilities

- Manager AI Chat agent runner.
- Data Intelligence Agent proposal generation runner.
- Tool registry projection into OpenAI Agents SDK function tools.
- Guardrails and human approval pauses.
- Agent run state and resumability.
- Audit-safe trace metadata.

## Hard Rules

- No raw SQL.
- No direct DB access from agents.
- No plaintext secret logging, tracing, or response payloads.
- Disable sensitive trace payloads unless an explicit audited tracing policy
  is approved.
- Human-review-only suggestions must not mutate business truth.
