# Incidents

## 2026-06-06T04:47:20Z — Needs Linear: PR #115 review follow-ups

Production review found four follow-up tasks for PR #115, but ENG-343 through
ENG-350 are already closed Done. Worker assignment is blocked until the
Orchestrator creates or links active Linear issues for the follow-ups.

See `reports/PR115-production-review-followups.md`.

## 2026-06-06T19:07:26Z — Needs Linear: PR #115 round-2 follow-ups

Second-pass production review on PR #115 surfaced six open items after the
first-pass follow-ups landed in `b155dfd`. The bundle
`AR-PR115-ROUND-2-FOLLOWUPS` has no Linear issue. Mechanical mission-state
fix (`current/` symlink switch) was completed by the reviewer in the same
turn; remaining items are decision-bound and handed to the Orchestrator.

See `reports/PR115-ROUND-2-followups.md`.

## 2026-06-06T19:07:26Z — Mission redirect drift: closed

`.agents/orchestration/current/` previously described the orphaned ENG-312
mission while the live mission was `agent-runtime-control-plane-v1/`. The
first-pass FIX-004 only synced `ownership.yaml` of the named mission; the
canonical `current/` redirect was not switched. Round-2 reviewer archived
ENG-312 spec to `archived/2026-06-02-eng-312-person-dob-ssn-backfill/` and
recreated `current` as a symlink to `agent-runtime-control-plane-v1/`. The
dashboard default path now resolves to the live mission.
