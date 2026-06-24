# Mission Goal — Dashboard Auto-Track Active Mission

## Linear

- Issue: ENG-223 — Dashboard: auto-track active mission (resolve mission per snapshot)
- URL: https://linear.app/fusion-dental-implants/issue/ENG-223/dashboard-auto-track-active-mission-resolve-mission-per-snapshot
- Status: In Progress
- Branch (Linear-suggested): `eduardk/eng-223-dashboard-auto-track-active-mission`

## Business goal

Stop the read-only mission dashboard from showing stale state when the
operator switches to a new mission folder mid-session. Today the
dashboard pins `--mission` once at startup; an empty new mission folder
silently leaves the dashboard rendering the previous mission.

Observed 2026-05-21: dashboard ran against
`.agents/orchestration/person-card-enrichment/` while branch
`eduardk/eng-219-carestack-appointments-fetcher` was active and the
human operator was steering a different mission. Result: stale ENG-218
state, eroded trust in the dashboard.

## Expected outcome

`.agents/dashboard/server.py` resolves the active mission on every
`/api/snapshot` (and `/api/logs`) request:

1. Explicit `--mission <path>` keeps current pinned behavior.
2. Without `--mission`, the dashboard infers active mission from:
   - primary: parse `ENG-\d+` from current git branch, match against
     `runtime.json.sessions[].linear_issue_id` and
     `handoffs[].linear_issue_id` across `.agents/orchestration/*/`,
     excluding `archived/`;
   - fallback: newest folder mtime under `.agents/orchestration/`,
     excluding `archived/`.
3. Snapshot payload exposes `mission.active_mission_name` and
   `mission.resolution_reason` so the UI can surface
   `Tracking: <mission> — matched ENG-N from branch`.

## Out of scope

- Orchestrator-side discipline (mission folders shipping empty is a
  separate concern; this mission only stops the dashboard from lying).
- Migration of runtime state out of the repo (handled by separate
  strategy mission "Move Session Runtime State Out Of The Repository").
- Worktree-as-default for workers (M-2 strategy mission).

## Constraints

- Dashboard stays read-only and localhost-only.
- No PHI, no secrets, no `.env*` reads.
- No new dependencies; pure stdlib + existing dashboard code.
- Existing test suite at `.agents/skills/agent-orchestrator/tests/`
  must stay green.
- Repository files in English.
