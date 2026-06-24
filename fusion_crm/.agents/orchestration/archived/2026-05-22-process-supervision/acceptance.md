# Acceptance Criteria — ENG-226 (M-3)

A — `pid_check.py` helper
- [ ] New module `.agents/skills/agent-orchestrator/scripts/pid_check.py`.
- [ ] `runtime_status(pid)` returns `"alive"` | `"exited"` | `"missing"`.
- [ ] `None` / non-int / `0` / negative pid → `"missing"`.
- [ ] Permission error from `os.kill(pid, 0)` → `"alive"` (process
      exists but we can't signal it).
- [ ] Pure stdlib; no new deps.

B — Activity heuristic
- [ ] New helper `activity_state(log_path, idle_threshold_seconds=60)`
      in a module like `activity_heuristic.py`.
- [ ] Returns one of `"active"` (log written within threshold),
      `"idle"` (no log growth past threshold), `"waiting_input"`
      (last lines contain `Needs decision:` marker), `"blocked"`
      (last lines contain `Blocked:` marker).
- [ ] Marker check wins over mtime: a 5-minute-old `Needs decision:`
      tail returns `"waiting_input"`, not `"idle"`.
- [ ] Missing log file → `"idle"` with no exception.

C — `worker_ctl.py`
- [ ] New CLI under `.agents/skills/agent-orchestrator/scripts/worker_ctl.py`.
- [ ] Subcommands (argparse subparsers OR mutually-exclusive flag
      group): `--list`, `--status <sid>`, `--kill <sid>`, `--attach <sid>`.
- [ ] `--list`: prints every session for the current mission with
      task_id, role/agent, execution_status, runtime_status,
      agent_activity, pid, last_activity. Honors `--mission <path>`
      override (defaults to ENG-223 active-mission detection).
- [ ] `--status <sid>`: compact one-screen block including the last
      20 log lines.
- [ ] `--kill <sid>`: SIGTERM, wait up to `--grace <seconds>`
      (default 10), then SIGKILL if still alive. Updates runtime.json
      `status` to `cancelled`, appends `runlog` entry.
- [ ] `--attach <sid>`: tail the worker log to stdout (`follow=True`
      semantics); does NOT modify runtime state. Ctrl-C exits cleanly.
- [ ] Refuses to act on an unknown session id with a clear error.
- [ ] No `--kill-all` (or similar mass-write) by design.

D — runtime.json schema additions
- [ ] Sessions carry `runtime_status` and `agent_activity` when
      RENDERED (by status_wave + dashboard); these fields are NOT
      persisted by the launcher.
- [ ] `runtime_json_schema` test acknowledges these as derived /
      optional.

E — `status_wave.py`
- [ ] Output includes `runtime_status` and `agent_activity` columns
      next to existing `status` per session.

F — Dashboard snapshot
- [ ] `.agents/dashboard/server.py` snapshot enriches
      `mission.runtime.sessions[]` with derived `runtime_status` +
      `agent_activity` per session at render time.
- [ ] No UI changes required (data passes through; columns deferred).
- [ ] Existing 19 dashboard tests stay green.

G — `start_control_plane.py`
- [ ] New wrapper under
      `.agents/skills/agent-orchestrator/scripts/start_control_plane.py`.
- [ ] Runs `status_wave.py --mission <auto>` once, prints output.
- [ ] Starts `.agents/dashboard/server.py` as a child process.
- [ ] Prints the local URL (`http://127.0.0.1:8787`).
- [ ] Opens the browser by default; `--no-open` opt-out.
- [ ] Exits cleanly on Ctrl-C; terminates the dashboard child.

H — Tests + docs
- [ ] `test_pid_check.py` — alive/exited/missing matrix using a
      short-lived `subprocess.Popen` that we kill.
- [ ] `test_activity_heuristic.py` — log mtime + marker cases:
      fresh write → active; stale log → idle; `Needs decision:` in
      tail → waiting_input; `Blocked:` in tail → blocked; missing
      log → idle.
- [ ] `test_worker_ctl.py` — full cycle: spawn fake worker subprocess
      → `--list` shows it → `--status <sid>` includes log tail →
      `--kill <sid>` terminates within grace → `--list` shows it as
      `exited`/`cancelled`.
- [ ] `test_start_control_plane.py` — smoke that starts the dashboard
      child with `--no-open`, hits `/api/snapshot`, shuts it down
      cleanly (no port leak, no zombie).
- [ ] Existing test_runtime_json_schema acknowledges new optional
      derived fields.
- [ ] Docs updated: `.agents/orchestration/CLAUDE.md` (worker_ctl +
      control plane), `SKILL.md` (CLI surface), `tests/README.md`
      (new fixtures, heuristic-is-heuristic note).

Hygiene
- [ ] Repository files in English.
- [ ] No PHI, no secrets, no `.env*` reads.
- [ ] No new third-party dependencies.
- [ ] No product-code changes.
- [ ] `make verify` is green locally BEFORE push (M-1 + M-2 lesson).
