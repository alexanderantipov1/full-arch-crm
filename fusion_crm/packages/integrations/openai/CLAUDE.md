# CLAUDE.md — `packages/integrations/openai`

OpenAI provider plumbing for tenant-owned AI credentials and agent-runtime
health checks. Read `packages/integrations/CLAUDE.md` first for the
cross-cutting rules (provider code only, no PHI imports, no plaintext
secret logging).

## Current Scope

This package exposes:

- `OpenAIAgentHealthClient` — minimal OpenAI Agents SDK runner used to
  verify that a tenant-scoped OpenAI API key can execute an agent run.
- `OpenAIAgentPlanningClient` — constrained OpenAI Agents SDK runner used by
  Agent Runtime to produce a validated JSON planning contract.
- `OpenAIIntegrationService` — reads the active
  `tenant.integration_credential` row for `(openai, api_key)` and passes the
  key in memory to health or planning clients.
- `OpenAIConnectionCheckOut` — safe response DTO for API health checks.
- `OpenAIAgentPlanOut` — safe validated plan metadata; never raw provider
  payload.

The API key is stored only in `tenant.integration_credential`. Do not add
an `OPENAI_API_KEY` environment fallback for product runtime; env keys are
only acceptable for one-off local experiments outside the product path.

## Health Check Contract

The health check must:

1. Read the tenant credential through `IntegrationCredentialService`.
2. Run a minimal Agents SDK call using a per-request model provider.
3. Disable tracing for the check unless a later audited tracing policy is
   explicitly approved.
4. Return only safe metadata: `ok`, provider/kind, model id, agent name,
   and a short non-secret output.

The health check must never return, log, trace, or audit the API key.

## Planning Contract

The LLM planning path must:

1. Read the tenant credential through `IntegrationCredentialService`.
2. Send only a safe prompt envelope: user question, policy summary, approved
   tool metadata, and the expected JSON output shape.
3. Disable tracing and sensitive trace data unless a later audited tracing
   policy is explicitly approved.
4. Validate the provider response as `agent_plan_v1` before returning it.
5. Reject unknown tools, missing required clarification/refusal fields, invalid
   JSON, secrets, PHI markers, or unsafe provider output.
6. Return only safe metadata: model, agent name, outcome, intent, approved
   tool id, validated tool arguments, confidence, clarification/refusal text,
   and safety notes.

The planning path must never return, log, trace, or audit the raw provider
payload or the API key.

## Out Of Scope

- Data Intelligence Agent proposal generation.
- PHI-bearing prompt construction.
- Tool execution against Fusion services.
- Automatic catalog proposal approval.

Those land behind dedicated policy, audit, and human-review tasks.
