# Acceptance Criteria

- ENG-227 migration drift is fixed and verified with Alembic checks.
- ENG-228 focused pytest failure clusters are resolved or intentionally split
  into follow-up Linear issues instead of being hidden by skipped tests.
- ENG-228-TENANT-ISOLATION is no longer an active blocker after ENG-229,
  ENG-230, and ENG-231 resolved the tenant-isolation contract, credential
  scoping, and Phase B live harness.
- ENG-232 clears the remaining full-repository `mypy .` backlog.
- ENG-233 keeps active Salesforce OAuth credentials fresh using the existing
  refresh-token flow, persists refreshed access tokens, marks invalid refresh
  tokens as requiring reconnect, and exposes reconnect state without logging
  credential payloads.
- ENG-234 wires Salesforce token keepalive into the canonical production
  Cloud Run Job and Cloud Scheduler contract without creating a long-running
  worker service.
- Production activation is confirmed by an operator deploy without
  `CI_MODE=1`, followed by Google Cloud state checks for
  `fusion-job-salesforce-token-keepalive`,
  `fusion-sched-salesforce-token-keepalive`, `fusion-job-sf-pull`, and
  `fusion-job-cs-pull`.
- Scheduled production pulls are smoke-verified from app-level summaries, not
  only Cloud Run exit status: Salesforce and CareStack each report one tenant
  processed with zero failed tenants.
- Runtime state is dashboard-visible and synchronized across `runtime.json`,
  `board.md`, `linear-sync.md`, and `runlog.md`.
- Commit/PR scope is separated: commit `44d704e` contains production-reviewer
  work; current dirty web/strategy/mission-state changes are reviewed and
  verified separately before any PR.
