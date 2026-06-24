# Agent Runtime Execution Layer V2 Contract

## Runtime Flow

```text
Workbench or internal API prompt
  -> Agent Runtime API
  -> LLM prompt envelope
  -> tenant-scoped provider credential
  -> validated LLM plan
  -> approved tool registry check
  -> policy preflight
  -> deterministic query/read-model matching
  -> approval gate when required
  -> service-owned tool execution or safe stop
  -> run history + audit summary
  -> safe UI/API response
```

## Matching Contract

Safe tool arguments may be used only to select known contracts. They are not
business truth by themselves.

The matching layer may use:

- approved tool ids;
- approved query ids;
- read-model ids;
- governed term metadata;
- safe synonyms and manager question metadata;
- data-class and output-posture metadata.

The matching layer must return one of:

- `matched`;
- `clarification_required`;
- `no_match`;
- `denied`;
- `approval_required`.

## Execution Contract

The execution layer may execute only when all conditions are true:

- the selected tool is allowlisted by Agent Runtime;
- policy posture is `allowed`;
- approval is not required or was completed;
- selected query/read-model metadata is approved for the requested posture;
- execution calls services/read models, not repositories, raw SQL, or direct DB;
- the response can be represented as safe aggregate or metadata-only output.

If any condition fails, the runtime must return a safe blocked, clarification,
denied, approval-required, or no-match outcome before tool execution.

## Approval Contract

Approval-required runs pause before execution. Approval metadata may include:

- run id;
- actor/principal metadata;
- requested tool/query/read model;
- safe policy reason;
- data classes;
- result posture;
- expiration;
- approval status.

Approval metadata must not include secrets, raw provider payloads, PHI, raw SQL,
unmasked samples, or row-level data.

## DIA And Semantic Catalog Contract

DIA and Semantic Catalog linkage may inform visibility and review-only
suggestions. They may not silently change production meaning.

Allowed linkage:

- approved catalog version ids;
- read-model ids;
- query registry ids;
- known/likely/unknown impact metadata;
- review-only DIA proposal references.

Disallowed linkage:

- treating DIA suggestions as approved business meaning;
- letting LLM output approve catalog terms;
- executing against stale docs when an approved catalog version is required.

## Ownership

- `packages.agent_runtime` owns orchestration, plan validation, policy posture,
  matching coordination, approval posture, run history, audit summaries, and
  safe response envelopes.
- `packages.tools` owns service-facing tool contracts and service-owned
  execution adapters.
- Semantic Catalog and read-model metadata remain owned by their existing
  domain packages and services.
- API routes only wire DTOs to services.
- Frontend workbench renders safe API DTOs only.
