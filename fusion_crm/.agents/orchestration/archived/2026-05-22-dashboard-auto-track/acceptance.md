# Acceptance Criteria — ENG-223

A — Mission resolution per snapshot
- [ ] `build_snapshot()` resolves the mission path on every invocation.
- [ ] `/api/snapshot` and `/api/logs` both honor the live-resolved path.
- [ ] Explicit `--mission <path>` continues to pin the dashboard to that
      path regardless of git branch or folder mtimes.

B — Active-mission detector
- [ ] When `--mission` is omitted, the detector reads the current git
      branch (e.g. via `git rev-parse --abbrev-ref HEAD`).
- [ ] If branch contains `ENG-\d+`, the detector searches
      `.agents/orchestration/*/runtime.json` for a matching
      `sessions[].linear_issue_id` or `handoffs[].linear_issue_id`.
- [ ] `archived/` is excluded from the search.
- [ ] If no Linear-id match, fall back to newest folder mtime under
      `.agents/orchestration/` (excluding `archived/` and dotfiles).
- [ ] If no orchestration folder exists, return empty mission state
      with a clear `resolution_reason` (no inferred state).

C — Snapshot payload
- [ ] `mission.active_mission_name` is the folder name (e.g.
      `carestack-appointments-fetcher`) or `null` when no mission found.
- [ ] `mission.resolution_reason` is one of: `explicit-flag`,
      `branch-match`, `mtime-fallback`, `no-mission`.
- [ ] Existing snapshot fields stay backward-compatible.

D — Tests
- [ ] Unit test: explicit `--mission` overrides everything else.
- [ ] Unit test: branch `eduardk/eng-219-...` resolves to the folder
      whose `runtime.json` references `ENG-219`.
- [ ] Unit test: branch with no `ENG-\d+` falls back to mtime; archived
      folders never win even if newer.
- [ ] Unit test: empty `.agents/orchestration/` → `no-mission` reason.
- [ ] Existing tests in `.agents/skills/agent-orchestrator/tests/` still
      pass.

E — Smoke check
- [ ] Manually run the dashboard without `--mission`, switch git
      branches between two real mission folders, confirm `/api/snapshot`
      reflects the switch within one request (no restart required).

F — Hygiene
- [ ] Repository files in English.
- [ ] No secrets, no PHI, no `.env*` reads added.
- [ ] No new third-party dependencies.
- [ ] No changes to product code (`apps/`, `packages/`, `infra/`).
