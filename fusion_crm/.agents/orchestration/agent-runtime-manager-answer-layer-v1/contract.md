# Agent Runtime Manager Answer Layer V1 Contract

## Runtime Flow

```text
Workbench or future manager-chat prompt
  -> Agent Runtime API
  -> LLM planner
  -> approved tool registry check
  -> policy preflight
  -> deterministic query/read-model matching
  -> service-owned aggregate execution
  -> answer eligibility gate
  -> safe answer prompt envelope
  -> validated manager answer contract
  -> run history + audit summary
  -> safe UI/API response
```

## Answer Eligibility

Answer generation may run only when all conditions are true:

- planner outcome is an approved aggregate tool plan;
- policy result is `allowed`;
- selected tool execution completed through a service-owned adapter;
- execution result is aggregate-only;
- selected query id and read-model id are known approved refs;
- source refs and caveats can be populated;
- no approval is pending;
- no PHI, row-level rows, raw SQL, raw provider payloads, secrets, or unmasked
  samples are present in the answer envelope.

If any condition fails, the runtime must return the safe stop outcome and must
not call the answer generator.

## Answer Contract

The manager answer must include:

- `status`: generated, not_generated, validation_failed, or blocked;
- `summary`: concise manager-facing answer;
- `key_numbers`: named aggregate values with units and optional comparison
  posture;
- `explanation`: plain-language reasoning grounded in the aggregate result;
- `caveats`: limitations, missing data, date/filter limits, or confidence
  concerns;
- `source_refs`: selected tool id, query id, read-model id, approved catalog refs
  where available, and execution run id;
- `confidence`: high, medium, or low;
- `safety_notes`: what the answer intentionally excludes.

## Forbidden Content

The answer generator prompt, response, run history, audit summary, API response,
and UI state must not contain:

- PHI or clinical details;
- row-level rows or row identifiers not already approved for safe metadata;
- raw SQL;
- raw provider payloads;
- API keys, credentials, tokens, or secret metadata;
- raw prompt bodies with sensitive user content;
- unmasked samples;
- unapproved Semantic Catalog meaning;
- invented metric definitions or unregistered source refs.

## Ownership

- `packages.agent_runtime` owns orchestration, answer eligibility, answer
  prompt envelope construction, answer validation, safe run history, and audit
  metadata.
- `packages.tools` owns service-facing aggregate execution contracts.
- Domain services own business logic and data access.
- API routes only wire DTOs to services.
- Frontend workbench renders safe DTOs only.
