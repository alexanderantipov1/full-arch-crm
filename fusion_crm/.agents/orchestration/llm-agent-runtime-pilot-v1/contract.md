# LLM Agent Runtime Pilot V1 Contract

## Runtime Flow

```text
Workbench prompt
  -> Agent Runtime API
  -> LLM prompt envelope
  -> OpenAI tenant credential
  -> validated LLM plan
  -> approved tool/query registry check
  -> policy preflight
  -> approved service/tool execution or deny/clarify/approval posture
  -> run history + audit summary
  -> safe UI response
```

## ENG-362 Execution Flow

```text
Validated LLM plan for ask_manager_analytics
  -> normalize safe tool arguments
  -> match approved analytics query/read-model contract
  -> run service-owned aggregate analytics/read-model code
  -> persist safe executed/blocked/no-match run summary
  -> return planner metadata + execution metadata + aggregate result summary
```

## Allowed Inputs

- Staff/dev user prompt text.
- Tenant and actor context already authorized by the application.
- Approved tool/query registry metadata.
- Aggregate-only analytics context that is safe for LLM planning.

## Disallowed Inputs

- Raw SQL.
- Secrets or credential values.
- Raw provider payloads.
- PHI or row-level clinical data.
- Unmasked sample rows.
- Catalog drafts as production truth.

## LLM Output Contract

The model may propose:

- an allowed intent;
- a known tool/query id;
- safe arguments matching a validated schema;
- a clarification question;
- a refusal/blocked explanation.

The model may not:

- execute SQL;
- call repositories or databases;
- invent unavailable tools;
- approve catalog meaning;
- request write-capable actions in V1;
- return secrets, PHI, raw rows, or raw provider payloads.

## Approved Analytics Execution Contract

The execution layer may only execute an LLM plan when all of these are true:

- the selected tool is allowlisted by Agent Runtime;
- policy posture is `allowed`;
- the tool is aggregate-only;
- safe arguments match a known approved analytics query/read-model contract;
- the implementation calls services/read models, not repositories or SQL;
- the response can be represented as aggregate metadata and safe numeric
  summaries.

If any condition fails, the execution layer must return a safe blocked,
clarification, denied, or no-match outcome before tool execution.

## Ownership

- `packages.agent_runtime` owns orchestration, planning validation, policy
  posture, approved analytics execution coordination, run history, audit
  summaries, and the safe response envelope.
- `packages.integrations.openai` owns provider-specific OpenAI call mechanics
  and credential use.
- API routes only wire DTOs to services.
- Frontend dev workbench renders safe API DTOs only.
