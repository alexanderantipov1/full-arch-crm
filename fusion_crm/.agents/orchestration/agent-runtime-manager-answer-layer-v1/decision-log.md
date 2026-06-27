# Decision Log

- 2026-06-08T16:55:21Z — User approved opening a new mission for manager-facing
  answer generation. Orchestrator created a dedicated Linear project instead of
  extending the completed Agent Runtime Execution Layer V2 project.
- 2026-06-08T17:11:44Z — ENG-374 uses `gpt-4.1` for final manager answer
  generation while keeping planner selection on `gpt-4.1-mini`. The answer
  model receives approved aggregate execution envelopes only.
- 2026-06-08T17:27:09Z — ENG-375 persists only answer audit metadata in run
  history. Full answer body fields remain response-only and are not stored in
  `audit.agent_runtime_run.audit_summary`.
- 2026-06-08T17:52:50Z — ENG-376 makes final manager answers visible in the
  Agent Runtime workbench and keeps persisted answer audit metadata visually
  separate from response-only answer body content.
- 2026-06-08T20:47:44Z — ENG-377 closes the Manager Answer Layer V1 mission with
  focused verification and smoke evidence passing. Full-suite failures are
  documented as environment/default-python dependency gaps and unrelated Project
  Manager dashboard tests.
