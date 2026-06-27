# Worker Report — ENG-226 (M-3) Process Supervision + Granular Activity States

- **Task:** ENG-226 — Process supervision + granular activity states (M-3)
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-226/process-supervision-granular-activity-states-m-3
- **Linear status:** In Progress
- **Role / Agent:** worker / claude-code (self-execute via /orchestrator)
- **Branch:** `eduardk/eng-226-process-supervision`
- **Worktree:** `.` (canonical checkout)
- **Allowed scope:** per `ownership.yaml`. Confirmed no file outside
  scope was touched. No product code, no `.env*`, no `static/`.

## Touched files

```
.agents/skills/agent-orchestrator/scripts/pid_check.py            (new)
.agents/skills/agent-orchestrator/scripts/activity_heuristic.py   (new)
.agents/skills/agent-orchestrator/scripts/worker_ctl.py           (new — CLI)
.agents/skills/agent-orchestrator/scripts/start_control_plane.py  (new — wrapper)
.agents/skills/agent-orchestrator/scripts/status_wave.py          (M-3 enrichment)
.agents/dashboard/server.py                                       (snapshot enrichment)
.agents/skills/agent-orchestrator/tests/test_pid_check.py          (new — 7 tests)
.agents/skills/agent-orchestrator/tests/test_activity_heuristic.py (new — 10 tests)
.agents/skills/agent-orchestrator/tests/test_worker_ctl.py         (new — 10 tests)
.agents/skills/agent-orchestrator/tests/test_start_control_plane.py (new — 1 smoke)
.agents/orchestration/CLAUDE.md                                   (control plane section)
.agents/skills/agent-orchestrator/SKILL.md                        (worker_ctl + start_control_plane docs)
.agents/skills/agent-orchestrator/tests/README.md                 (new fixtures + heuristic disclaimer)
.agents/orchestration/process-supervision/*                       (mission folder, this report)
```

No product-code changes. No `static/`. No `.env*`. No new third-party
dependencies.

## Task-by-task summary

### Task A — `pid_check.py` ✅
Single helper: `runtime_status(pid) -> "alive" | "exited" | "missing"`.
Pure stdlib. 7 tests covering None / 0 / negative / non-int / live
subprocess / exited subprocess / unreachable pid.

### Task B — `activity_heuristic.py` ✅
`activity_state(log_path, idle_threshold_seconds=60)` returns one of
`active` / `idle` / `waiting_input` / `blocked`. Marker priority:
`Needs decision:` → `waiting_input`, `Blocked:` → `blocked`. Then mtime
within threshold → `active`. Else `idle`. Markers only scan last 50
lines (proven by test). 10 tests.

### Task C — `worker_ctl.py` ✅
Single CLI with mutex action group (`--list` / `--status` / `--kill` /
`--attach`). Auto-detects current mission via mtime fallback or honors
explicit `--mission`. `--kill` does SIGTERM → 10s grace → SIGKILL
(override via `--grace`), updates runtime.json `status=cancelled` +
appends runlog line. `--attach` tails the log file in follow mode with
clean Ctrl-C handling. 10 tests including a real-subprocess kill
lifecycle.

### Task D-E — `status_wave.py` enrichment ✅
Now imports `activity_heuristic` + `pid_check` and adds `rt=<status>`
and `activity=<state>` columns to each session line. `runtime_status`
and `agent_activity` are computed at render time, not persisted.

### Task F — Dashboard snapshot enrichment ✅
`collect_mission()` walks `runtime.json.sessions[]` and adds derived
`runtime_status` + `agent_activity` per session before returning the
payload. Existing 19 dashboard tests stay green.

### Task G — `start_control_plane.py` ✅
Convenience wrapper: ensures runtime root exists, runs `status_wave`
once, spawns dashboard subprocess (uses `.venv/bin/python` when
available), polls `/api/snapshot` until 200 (10s timeout), opens
browser (`--no-open` opt-out), blocks until Ctrl-C, then SIGTERM
dashboard with 5s grace + SIGKILL fallback. Smoke test on a free port
passes.

### Task H — Tests + docs ✅
- 28 new tests across pid_check + activity_heuristic + worker_ctl +
  start_control_plane.
- `.agents/orchestration/CLAUDE.md` gained the "Process Supervision
  Control Plane" section.
- `SKILL.md` gained the `worker_ctl.py` + `start_control_plane.py`
  CLI snippets.
- `tests/README.md` gained the M-3 fixtures section AND an explicit
  "Activity heuristic is a heuristic, not a contract" disclaimer.

## Tests run

```
.venv/bin/python -m pytest .agents/skills/agent-orchestrator/tests/  → 98 passed, 4 skipped
.venv/bin/python -m pytest .agents/dashboard/tests/                  → 19 passed
make verify                                                          → ruff ✓ mypy ✓ pytest 25 passed
```

`make verify` was run BEFORE this report (M-1 + M-2 lesson). One ruff
cycle was caught and fixed locally: removed unused `pytest` import
from `test_start_control_plane.py` and added `S310` to the file's
`noqa` line (urllib.request usage for the localhost liveness probe).

## Acceptance recheck

All 10 boxes in `acceptance.md` checked with evidence in the
task-by-task summary above. The pivotal acceptance criterion —
"--kill terminates a real fake worker within grace + updates
runtime.json + adds runlog line" — is proven by
`test_kill_live_subprocess_terminates_within_grace`.

## Risks + follow-ups

- The activity heuristic is intentionally heuristic. Surfaces label
  it explicitly; future readers must not treat it as a contract. The
  tests/README disclaimer makes this explicit.
- `--kill` flow trusts `os.kill(pid, 0)` semantics; behavior on
  PID-namespaced environments (containers) is the same as native
  macOS/Linux. We do not run on Windows.
- `start_control_plane.py` shutdown path waits 5s for SIGTERM before
  SIGKILL. If the dashboard installs a handler that ignores SIGTERM,
  the SIGKILL fires. Current dashboard does not install such a handler.
- The `pr_status` (gh pr view) dimension mentioned in the original
  candidate mission is NOT implemented in this PR. It's an optional
  per-session enrichment and the candidate mission marks it as
  cached/optional. Punted to a follow-up if/when it's worth the gh
  shell-out cost on every dashboard refresh.
- Worktree cleanup integration with `--kill` (auto-prune the killed
  worker's worktree) is out of scope here; would be a small bolt-on
  in a follow-up. Today the operator runs `cleanup_worktrees.py
  --apply` manually after kills.

## Blockers / questions

None. Ready for verifier handoff.

## Suggested next task

Open PR. CI should pass first try (we honored the M-1 + M-2 lesson:
`make verify` locally before push). Verifier walks acceptance, then
integrator (human) reviews + merges.

## Do-not-merge conditions

- `make verify` fails on a fresh clone.
- `test_kill_live_subprocess_terminates_within_grace` regresses.
- `start_control_plane.py` leaves a port leak or a zombie dashboard
  after `--no-open` shutdown.
