# Mission Goal — Process Supervision + Granular Activity States (M-3)

## Linear

- Issue: ENG-226 — Process supervision + granular activity states (M-3)
- URL: https://linear.app/fusion-dental-implants/issue/ENG-226/process-supervision-granular-activity-states-m-3
- Status: In Progress
- Branch (suggested): `eduardk/eng-226-process-supervision`

## Business goal

Make running workers fully controllable from a single CLI surface
(`worker_ctl.py`): attach to tail, kill, status, list. And make the
dashboard tell the truth about whether a worker is actually alive
vs whether `runtime.json` last said so — currently `status: running`
can be stale by hours and there's no signal for "process is gone".

## Why now

M-1 (ENG-224) and M-2 (ENG-225) closed the orchestrator-runtime
cleanup arc up to "isolated parallel workers in their own worktrees".
Without M-3, the orchestrator launches workers and forgets them; the
dashboard's `running` indicator is unreliable; and "is that worker
still working or stuck?" requires manual `ps aux` + `tail -f`.

Solo dev does not scale past 2-3 parallel workers without this.

## Expected outcome

1. `worker_ctl.py` exposes `--list`, `--status <sid>`, `--kill <sid>`,
   `--attach <sid>`.
2. Sessions in `runtime.json` (as rendered by dashboard /api/snapshot)
   carry two derived state dimensions:
   - `runtime_status` ∈ {`alive`, `exited`, `missing`} — from
     `os.kill(pid, 0)`.
   - `agent_activity` ∈ {`active`, `idle`, `waiting_input`, `blocked`}
     — heuristic from log mtime delta + `Needs decision:` marker
     search.
3. `--kill` does SIGTERM + 10s grace + SIGKILL (override via `--grace`),
   updates runtime.json status to `cancelled`, appends a runlog line.
4. `start_control_plane.py` runs status_wave + starts the dashboard +
   opens the browser (`--no-open` opt-out).
5. Activity heuristic is explicitly labeled as heuristic in docs so
   readers don't treat it as a contract.

## Out of scope

- Worker auto-restart after kill.
- UI redesign for new columns (just expose data; column ordering
  punted to a separate mission).
- Cross-platform support beyond macOS / Linux.

## Constraints

- `runtime_status` is derived, NOT persisted between runs.
- `agent_activity` is heuristic; surface labels it as such.
- Dashboard stays read-only. `worker_ctl.py` is the only new writer
  (and only on `--kill`).
- `--kill` is the only write action — no `--kill-all`.
- `gh pr view` calls cached 30s.
- Linear gate stays. No PHI, no secrets, no `.env*`, no new
  third-party deps, no product code changes.
- Repository files in English.
