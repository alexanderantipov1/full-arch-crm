# Worker Prompt — ENG-226 (M-3) Process Supervision + Granular Activity States

## Linear

- Issue: **ENG-226** — Process supervision + granular activity states (M-3)
- URL: https://linear.app/fusion-dental-implants/issue/ENG-226/process-supervision-granular-activity-states-m-3
- Branch (create from `main`): `eduardk/eng-226-process-supervision`

## Mission folder

```
.agents/orchestration/process-supervision/
├── goal.md
├── acceptance.md
├── verification.md
├── contract.md            ← read this first; specifies pid_check / activity heuristic / worker_ctl CLI / start_control_plane semantics
├── ownership.yaml
├── board.md
├── linear-sync.md
├── runtime.json           ← lives under runtime path now (M-1)
├── runlog.md              ← lives under runtime path now (M-1)
└── reports/
```

## Required pre-flight (mandatory)

1. `git rev-parse --verify eduardk/eng-226-process-supervision` —
   if exists, inspect commits before touching code (M-1 lesson).
2. Read `contract.md` end to end — it specifies all four new helpers'
   APIs, the runtime.json derived-field rules, and the
   `start_control_plane.py` lifecycle.
3. Re-read the "Mission Open Order" section in
   `.agents/orchestration/CLAUDE.md` — applies to any new mission
   folder you might open.
4. Re-read the "Workspace Isolation" section — `worker_ctl.py --kill`
   needs to know about the new `worktree` field on sessions so future
   worktree cleanup can be wired in M-4 (out of scope here, but don't
   block it).

## Tasks A → H (sequential)

### Task A — `pid_check.py`

- Single helper module at
  `.agents/skills/agent-orchestrator/scripts/pid_check.py`.
- `runtime_status(pid) -> Literal["alive", "exited", "missing"]` per
  contract semantics.
- Pure stdlib.

### Task B — Activity heuristic

- Module at
  `.agents/skills/agent-orchestrator/scripts/activity_heuristic.py`.
- `activity_state(log_path, idle_threshold_seconds=60) -> str`.
- Markers in tail (last 50 lines) win over mtime: `Needs decision:`
  → `waiting_input`, `Blocked:` → `blocked`. Then mtime within
  threshold → `active`. Else `idle`. Missing file → `idle`.

### Task C — `worker_ctl.py`

- Single CLI with mutex action group: `--list` / `--status <sid>` /
  `--kill <sid>` / `--attach <sid>`. See `contract.md` §"`worker_ctl.py` CLI".
- `--mission <path>` override or auto-detect via ENG-223 detector.
- `--list`: read sessions from current mission's runtime.json, enrich
  each with `runtime_status` + `agent_activity`, print compact table.
- `--status <sid>`: same enrichment + last 20 log lines (configurable
  via `--tail-lines`).
- `--kill <sid>`: SIGTERM, wait up to `--grace` (default 10) seconds,
  then SIGKILL. Update runtime.json `status` to `cancelled`, append
  runlog line. Refuses unknown sid with clear error.
- `--attach <sid>`: tail log to stdout in follow mode. Ctrl-C exits
  cleanly. No runtime.json mutation.

### Task D — runtime.json schema

- Add a short docstring at the top of `runtime.json`-touching code
  (and a paragraph in `.agents/orchestration/CLAUDE.md`) noting that
  `runtime_status` and `agent_activity` are DERIVED at render time
  and NEVER persisted by the launcher.
- Update `test_runtime_json_schema.py` to acknowledge these as
  optional/derived (the schema test should still pass even when the
  fields are absent on disk).

### Task E — `status_wave.py`

- Enrich each session line with `runtime_status` + `agent_activity`
  computed via the new helpers.
- Keep the existing columns; add the new ones at the end.

### Task F — Dashboard snapshot

- `.agents/dashboard/server.py` `collect_mission()` reads each session
  from runtime.json, enriches with `runtime_status` (via `pid_check`)
  and `agent_activity` (via `activity_heuristic` on each session's
  `log_path`).
- Snapshot exposes the two fields per session. No UI redesign.
- Existing 19 dashboard tests must stay green; add 2-3 new cases that
  exercise the enrichment path with a mocked pid and a tmp log file.

### Task G — `start_control_plane.py`

- New wrapper per `contract.md` §"`start_control_plane.py` semantics".
- Uses `webbrowser.open()` for the open-default behavior; `--no-open`
  opt-out.
- Polls `/api/snapshot` until 200 with 10s timeout.
- Ctrl-C → SIGTERM dashboard, 5s wait, SIGKILL.

### Task H — Tests + docs

- `test_pid_check.py`: pid=None / negative / unknown → missing;
  spawn short subprocess → alive while running, exited after wait.
- `test_activity_heuristic.py`: marker wins over mtime; fresh write →
  active; stale → idle; missing file → idle.
- `test_worker_ctl.py`: full lifecycle with a fake launcher session
  written to runtime.json + a sleep-based fake worker process; assert
  list/status/kill/attach paths.
- `test_start_control_plane.py`: smoke that starts dashboard with
  `--no-open` on an available port, hits /api/snapshot, clean shutdown.
- Docs updates: `.agents/orchestration/CLAUDE.md` (M-3 control plane
  section), `SKILL.md` (worker_ctl + start_control_plane CLI),
  `tests/README.md` (heuristic-is-heuristic disclaimer).

## Allowed scope (do not exceed)

See `ownership.yaml` `scope_allow`. Forbidden: any product code,
`.env*`, `.claude/`, `docs/`, `.agents/orchestration/archived/`, AND
`.agents/dashboard/static/` (no UI redesign).

## Verification you must run BEFORE push (M-1 + M-2 lesson, hard gate)

```bash
make verify                              # ruff + mypy + product pytest
.venv/bin/python -m pytest .agents/skills/agent-orchestrator/tests/ -v
.venv/bin/python -m pytest .agents/dashboard/tests/ -v
```

Plus the manual smoke flow in `verification.md` (6 cases).

## Process rules

1. **Never commit unless the human partner explicitly approves.**
2. Update `runlog.md` when you: start, change phase, hit a blocker,
   finish, or hand off.
3. When done (or blocked), write
   `reports/ENG-226-worker-report.md` per
   `.agents/orchestration/CLAUDE.md` §"Worker Report Contract".
4. If anything in `acceptance.md` is unclear, write `Needs decision:`
   to `runlog.md` and pause — do not guess.
5. Conversation with the human partner is in Russian; everything in
   the repo stays English.
6. Pre-push gate: `make verify`. The cost of saving one CI cycle is
   30 seconds of local run time. (M-2 PR was green out-of-gate; that's
   the target.)

## Definition of done

- Every box in `acceptance.md` is checked with evidence.
- Worker report exists at `reports/ENG-226-worker-report.md`.
- `runlog.md` shows start + finish entries.
- No file outside the allowed scope was touched.
- `make verify` green locally.
- Smoke test demonstrably proves: `--kill` terminates a real fake
  worker within grace + updates runtime.json + adds runlog line.
