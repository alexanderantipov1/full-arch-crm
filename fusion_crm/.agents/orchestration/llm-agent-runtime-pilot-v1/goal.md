# LLM Agent Runtime Pilot V1 Goal

## Mission

Build the first real OpenAI/LLM-powered agent runtime path on top of Agent
Runtime Control Plane V1.

This mission intentionally starts with live LLM behavior instead of deferring
LLM use behind a deterministic-only planner. The goal is to test model prompts,
tool planning, policy gates, run history, audit summaries, and workbench UX
early while keeping the runtime bounded by Fusion CRM safety rules.

## Business Outcome

The team should be able to open an internal workbench, submit a safe test
question, run a real tenant-scoped OpenAI model call, see the model-selected
plan, policy posture, final answer, run history, and audit summary, and know
why any denied or ambiguous request was blocked.

## Guardrails

- Agents never access the database directly.
- Tools call services only.
- No raw SQL is accepted or generated as executable work.
- No PHI, secrets, raw provider payloads, or unmasked samples are stored,
  logged, returned by APIs, or rendered in the frontend.
- LLM output cannot approve catalog meaning or execute write-capable actions in
  V1.
- V1 starts with aggregate-only analytics and safe internal test prompts.

## Linear

- Parent: ENG-354 — LLM Agent Runtime Pilot V1 Mission Control
- Setup: ENG-355 — LLM-01 Mission Setup And Linear Sync
- Implementation: ENG-356 through ENG-361
- Current follow-up execution slice: ENG-362 — LLM-08 Approved Analytics Tool
  Execution V1

## Current Follow-Up Slice

ENG-356 through ENG-361 made the production-visible LLM planning pilot work:
OpenAI can choose an approved tool plan, policy can allow/clarify/deny, safe run
metadata is persisted, and the internal workbench can test the flow.

ENG-362 is the next layer. It must turn the safe planner result for
`ask_manager_analytics` into service-owned aggregate analytics execution:
planner result -> approved query/read model -> real aggregate result -> safe UI
response and audit summary.
