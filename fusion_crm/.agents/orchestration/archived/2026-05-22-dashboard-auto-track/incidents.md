# Incidents — Dashboard Auto-Track Active Mission

## 2026-05-22T02:45:00Z — Smoke test killed doctor's live dashboard

### What happened

During the ENG-223 live-smoke step, worker started a temporary
dashboard on port 8788, hit `/api/snapshot`, then shut it down with:

```bash
pkill -f "dashboard/server.py"
```

That pattern is too broad — it matched ANY `dashboard/server.py`
process, including the doctor's pre-existing instance on port 8787.
Result: the production-of-the-moment dashboard at
`http://127.0.0.1:8787/#mc-activity` died. Doctor reported
"вообще отвалилось ничего нету упало все" at 02:45Z.

### Resolution

Restarted the dashboard on 8787 (`/.venv/bin/python
.agents/dashboard/server.py`). All endpoints return 200; mission
resolver correctly reports `dashboard-auto-track` matched via
`ENG-223` from the current branch. Doctor needs to reload the tab.

### Lesson

Never use `pkill -f "<broad-pattern>"` to clean up a worker-spawned
process. Use the captured PID and `kill <pid>` (or do not background
the smoke server at all — `subprocess.Popen` + `.terminate()` in a
single script is safer). Adding to `lessons.md`.

## 2026-05-22T02:25:00Z — Pre-existing branch with completed implementation

### Discovery

`git checkout -b eduardk/eng-223-dashboard-auto-track-active-mission`
failed: branch already exists. Inspection shows:

```text
0d346fd  2026-05-21T19:00 -0700  feat(agents): dashboard auto-tracks active mission (ENG-223)
16924e8  2026-05-21T19:05 -0700  chore(agents): archive completed missions ENG-213/214/215/218
```

`gh pr list --head eduardk/eng-223-...` → no PR exists. The work was
done locally yesterday but never pushed/PR'd. Doctor may not have
recalled the branch existed when picking ENG-223 from the
`/orchestrator` queue.

### Commit 0d346fd — implementation

- 6 files, +453/-8.
- Touches `.agents/dashboard/server.py` only (no product code).
- Adds new `re` import, helper `resolve_active_mission()` with order:
  explicit override → branch-id match → newest mtime → empty state.
- Surfaces `mission.active_mission_name` and `mission.resolution_reason`
  in snapshot payload; topbar UI line in `static/index.html` +
  `static/app.js`.
- Adds 19 unit tests under `.agents/dashboard/tests/` (separate from
  the existing skill-local suite under
  `.agents/skills/agent-orchestrator/tests/`).
- Per the commit message, the new tests pass and the existing
  orchestrator suite stays green (34 / 4 skipped).
- Differences vs `contract.md` for this mission:
  - `resolution_reason` strings are prose ("matched ENG-219 from git
    branch", "no missions found ...") rather than canonical short codes
    (`branch-match`, `mtime-fallback`, etc.). Functionally equivalent;
    cosmetic.
  - Tests live under `.agents/dashboard/tests/` not
    `.agents/skills/agent-orchestrator/tests/` — `acceptance.md` allows
    either location.

### Commit 16924e8 — archive sweep

- Moves four completed mission folders into
  `archived/2026-05-21-<name>/`:
  - `person-card-enrichment`            → ENG-218 (PR #85 merged)
  - `tenant-integrations-bootstrap-forms` → ENG-215 (PR #83 merged)
  - `tenant-integrations-reconnect-ui`    → ENG-214 (PR #81 merged)
  - `orchestrator-launcher-reliability`   → ENG-213 (verifier accepted)
- Reasoning per the commit message: their stale `runtime.json` files
  carried `"waiting"` / `"running"` states, so the new mtime-fallback
  detector would latch onto them and surface ghost backlog work.
- No content edits; pure `git mv`.
- This is reasonable hygiene and aligns with the existing precedent
  `archived/2026-05-19-integration-foundation/`.

### Conflict with this orchestration session

- I created `.agents/orchestration/dashboard-auto-track/` on `main`
  (uncommitted) before discovering the branch. If we adopt the branch,
  the new mission folder needs to land on that branch (either
  cherry-picked or recreated post-rebase).
- Main has one commit ahead of the branch: `31c001d` (ENG-222
  scheduled ingest, PR #88). Diff vs main currently shows large
  spurious deletions because the branch predates that merge — a
  rebase on main is required before opening a PR.

### Required decision

See `decision-log.md` — escalated to doctor.

### Status

`Needs decision:` — work paused.
