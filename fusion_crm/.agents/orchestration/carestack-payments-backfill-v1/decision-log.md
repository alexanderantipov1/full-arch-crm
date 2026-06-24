# Decision Log — carestack-payments-backfill-v1

- 2026-05-30 | Handoff: orchestrator/claude-code -> worker/claude-code for ENG-285.
- 2026-05-30 | Decision: 2026-only backfill, throttled + resumable, operator-triggered. Single-DB per process; run twice (local now, prod after deploy) — NOT dual-DB write (prod-from-laptop risk + prod code not deployed yet).
- 2026-05-30 | Hard rule: tests MOCK the CareStack client; no real calls during dev/CI (CareStack blocked us ~24h before). Real run is an operator action.
