# Worker Prompt — ENG-223 Dashboard Auto-Track

## Linear

- Issue: **ENG-223** — Dashboard: auto-track active mission (resolve mission per snapshot)
- URL: https://linear.app/fusion-dental-implants/issue/ENG-223/dashboard-auto-track-active-mission-resolve-mission-per-snapshot
- Branch (create from `main`): `eduardk/eng-223-dashboard-auto-track-active-mission`

## Mission folder

```
.agents/orchestration/dashboard-auto-track/
├── goal.md
├── acceptance.md
├── verification.md
├── contract.md
├── ownership.yaml
├── board.md
├── linear-sync.md
├── runtime.json
├── runlog.md
└── reports/  (write your report here when done)
```

Read all five decision artifacts above before touching code. They are
the contract; this prompt is the brief.

## What to build

Modify `.agents/dashboard/server.py` (and add tests) so that:

1. The dashboard resolves the active mission **per request**, inside
   `build_snapshot()` (and `/api/logs`), not once at startup.
2. Without `--mission`, a detector infers the active mission from:
   - git branch `ENG-\d+` matched against `runtime.json.sessions[].linear_issue_id` and `handoffs[].linear_issue_id` across `.agents/orchestration/*/` (excluding `archived/` and dotfiles);
   - fallback: newest folder mtime under the same constraints;
   - last resort: `None` with `resolution_reason="no-mission"`.
3. Explicit `--mission <path>` still pins to that path — return reason `explicit-flag`.
4. Snapshot payload exposes `mission.active_mission_name`,
   `mission.resolution_reason`, and `mission.path`.

See `contract.md` for the exact resolution order and payload shape.

## Allowed scope (do not exceed)

- `.agents/dashboard/` — server, helpers, static assets if needed.
- New tests under `.agents/skills/agent-orchestrator/tests/` (preferred)
  OR `.agents/dashboard/tests/` (acceptable if you keep imports clean).
- This mission folder for runlog/report updates.

Forbidden: any change under `apps/`, `packages/`, `infra/`, `.env*`,
`.claude/`, `docs/`. Forbidden: new third-party dependencies. Forbidden:
hardcoded mission paths.

## Verification you must run before marking done

```bash
python3 -m py_compile .agents/dashboard/server.py
.venv/bin/python -m pytest .agents/skills/agent-orchestrator/tests/ -v
```

Plus the new ENG-223-specific unit tests you added.

Plus the manual smoke flow in `verification.md` §"Smoke test (manual)".

## Tests you must add (minimum)

- Explicit `--mission` override returns reason `explicit-flag` and
  ignores branch/mtime signals.
- Branch like `eduardk/eng-219-...` resolves to the folder whose
  `runtime.json` references `ENG-219` (build a temp folder layout in
  the test).
- Branch with no `ENG-\d+` (e.g. `main`) → reason `mtime-fallback`,
  pointing at the newest non-archived folder.
- Archived folders are never chosen even when newer (mtime).
- Empty `.agents/orchestration/` → reason `no-mission`,
  `active_mission_name` is `null`.

## Process rules

1. **Never commit unless the human partner explicitly approves.**
2. Update `runlog.md` when you: start work, change phase, hit a
   blocker, finish, or hand off. Use the existing line format.
3. When done (or blocked), write
   `reports/ENG-223-worker-report.md` per the contract in
   `.agents/orchestration/CLAUDE.md` §"Worker Report Contract".
4. If anything in `acceptance.md` is unclear, write `Needs decision:`
   to `runlog.md` and pause — do not guess.
5. Conversation with the human partner is in Russian; everything in
   the repo stays English.

## Out of scope

- Migrating runtime state out of repo.
- Orchestrator-side discipline (empty mission folders).
- Worktree-as-default machinery.
- UI styling beyond surfacing the new fields cleanly.

## Definition of done

- All boxes in `acceptance.md` are checked with evidence.
- Worker report exists at `reports/ENG-223-worker-report.md`.
- `runlog.md` and `runtime.json` show your start/finish entries.
- No file outside the allowed scope was touched.
- Tests are green locally.
