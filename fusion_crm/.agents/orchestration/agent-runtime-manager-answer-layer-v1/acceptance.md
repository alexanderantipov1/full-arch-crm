# Acceptance Criteria

## Mission Setup

- Mission spec files exist under
  `.agents/orchestration/agent-runtime-manager-answer-layer-v1/`.
- Runtime telemetry exists under the Orchestrator runtime home.
- Linear sync maps ENG-371 through ENG-377.
- Dashboard-visible runtime state shows the Orchestrator and planned workers.
- ENG-372 closes only after repo spec and runtime state are synchronized.

## Product Acceptance

- A strict manager answer contract exists for summary, key numbers,
  explanation, caveats, source refs, confidence, and safety notes.
- Final answer generation runs only after allowed aggregate execution succeeds.
- Final answer generation uses only safe aggregate execution result envelopes
  and approved metadata.
- Clarification, no-match, denied, blocked, approval-required, missing
  credential, PHI, row-level, raw SQL, export, and write-capable paths stop
  before answer generation.
- Run history and audit summaries show answer status and source refs without
  storing sensitive provider traces.
- `/dev/agent-runtime` can show planner metadata, execution metadata, and final
  answer metadata as distinct sections.

## Safety Acceptance

- No direct DB access from LLM or agent code.
- No raw SQL execution path.
- No PHI, secrets, raw provider payloads, raw prompts with sensitive values,
  unmasked samples, row-level rows, or export payloads in persisted run history,
  API responses, logs, docs, or frontend state.
- Final answers cannot introduce unapproved catalog meaning or invented metric
  definitions.
- Source refs and caveats are required for successful generated answers.
- Tests cover allowed answer, validation failure, no-match, clarification,
  denied, blocked, approval-required, missing credential, and sensitive-field
  exclusion paths.

## Closure Acceptance

- Local focused backend and frontend verification passes for changed areas.
- Alembic check passes if DB models or migrations change.
- Browser smoke verifies answer rendering and blocked/denied states.
- Production route smoke proves `/dev/agent-runtime` remains present and
  protected.
- Linear and Orchestrator runtime statuses are synchronized before closure.
- Remaining future work is visible in Linear and mission artifacts.
