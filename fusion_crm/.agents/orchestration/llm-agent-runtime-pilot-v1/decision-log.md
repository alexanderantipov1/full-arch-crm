# Decision Log

- 2026-06-07T01:36:00Z — User decision: LLM/OpenAI must be part of the
  primary pilot now, not deferred behind deterministic-only planning. Mission
  scope changed to live LLM-first testing through Agent Runtime guardrails.

- 2026-06-07T19:25:00Z — Orchestrator created ENG-362 as the next child task
  under ENG-354. Reason: ENG-356 through ENG-361 established the LLM planner,
  policy gate, API/workbench, safety tests, and production visibility, but the
  system still needs a separately tracked layer for planner-selected approved
  aggregate analytics tool execution.

- 2026-06-07T19:25:00Z — Handoff: orchestrator/codex -> worker/codex
  self-execute accepted for ENG-362. Scope is aggregate-only
  `ask_manager_analytics` execution through service-owned read models; raw SQL,
  row-level output, PHI, exports, write tools, and catalog auto-approval remain
  out of scope.
