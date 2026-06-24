# Agent Runtime Manager Answer Layer V1 Goal

## Mission

Generate safe manager-facing answers from approved aggregate Agent Runtime
execution results.

The previous Agent Runtime execution layer can validate an LLM plan, select an
approved tool, match approved query/read-model metadata, run policy preflight,
execute the first safe aggregate analytics path, and persist safe run/audit
metadata. This mission adds the next product layer: a concise answer that a
manager can read and act on.

## Business Outcome

A developer or future manager-chat surface should be able to ask a safe
aggregate analytics question and receive:

- a short answer summary;
- key aggregate numbers;
- a plain-language explanation;
- caveats when data is incomplete or limited;
- source refs for selected tool, query id, read model, and approved metadata;
- safety notes explaining what was not included.

## Guardrails

- Agents never access the database directly.
- Tools call services only.
- LLM answer generation receives only safe aggregate result envelopes and
  approved metadata.
- No PHI, row-level rows, raw SQL, raw provider payloads, secrets, prompt
  bodies, unmasked samples, or unapproved catalog meaning may enter answer
  generation, persistence, API responses, or UI state.
- Final answers must not invent metrics, query ids, read-model ids, catalog
  definitions, source refs, or business meaning.
- Clarification, no-match, denied, blocked, approval-required, and missing
  credential paths must stop safely before final answer generation.

## Linear

- Parent: ENG-371 — Agent Runtime Manager Answer Layer V1 Mission Control
- Setup: ENG-372 — MANS-01 Mission Setup And Runtime Sync
- Implementation:
  - ENG-373 — MANS-02 Manager Answer Contract V1
  - ENG-374 — MANS-03 LLM Answer Generation From Approved Aggregates
  - ENG-375 — MANS-04 Answer Audit, Run History, And Safety Metadata
  - ENG-376 — MANS-05 Agent Runtime Workbench Final Answer UI
  - ENG-377 — MANS-06 Evals, Documentation, Smoke, And Closure

## Execution Order

1. Open mission and runtime state.
2. Define the answer contract.
3. Add backend answer generation after approved aggregate execution.
4. Extend run history and audit summaries with safe answer metadata.
5. Render final answer states in the Agent Runtime workbench.
6. Run evals, update docs, smoke local/production, and close the mission.
