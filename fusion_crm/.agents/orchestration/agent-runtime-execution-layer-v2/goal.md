# Agent Runtime Execution Layer V2 Goal

## Mission

Turn the completed LLM Agent Runtime Pilot V1 into a broader governed
execution layer for internal analytics and agent workflows.

The pilot proved that Agent Runtime can call OpenAI with tenant-scoped
credentials, validate an approved tool plan, run policy gates, and execute the
first safe aggregate analytics path. V2 turns that proof into a more reusable
control plane: deterministic query/read-model matching, broader approved tool
execution, reviewable run history, human approvals, audit summaries, and links
to Semantic Catalog and Data Intelligence Agent outputs.

## Business Outcome

Staff and developers should be able to ask a safe internal manager analytics
question, see which approved tool/query/read model was selected, understand why
policy allowed, clarified, denied, or paused the run, and review the resulting
execution metadata without exposing PHI, secrets, raw provider payloads, raw
SQL, or row-level data.

## Guardrails

- Agents never access the database directly.
- Tools call services only.
- No raw SQL is generated or accepted as executable work.
- No PHI, secrets, raw provider payloads, raw prompts with sensitive values,
  unmasked samples, row-level exports, or LLM-owned calculations are stored,
  logged, returned by APIs, or rendered in the frontend.
- Semantic Catalog meaning is never auto-approved by LLM output or DIA output.
- Write-capable tools, scheduled reports, row-level worklists, XLSX, and exports
  remain out of scope unless separately approved.

## Linear

- Parent: ENG-363 — Agent Runtime Execution Layer V2 Mission Control
- Setup: ENG-364 — ARX-01 Mission Setup And Orchestrator Runtime Sync
- Implementation:
  - ENG-365 — ARX-02 Approved Query And Read Model Matching V2
  - ENG-366 — ARX-03 Approved Tool Execution Registry Expansion V2
  - ENG-367 — ARX-04 Run History Operations And Audit Review V1
  - ENG-368 — ARX-05 Approval Workflow Integration V1
  - ENG-369 — ARX-06 DIA And Semantic Catalog Linkage V2
  - ENG-370 — ARX-07 Evals, Documentation, Production Smoke, And Closure

## Execution Order

1. Open the mission and runtime state.
2. Build deterministic approved query/read-model matching.
3. Expand registry-driven approved tool execution.
4. Improve run history operations and audit review.
5. Add approval workflow behavior.
6. Link Agent Runtime runs to DIA and Semantic Catalog metadata.
7. Run evals, update documentation, smoke production, and close the mission.
