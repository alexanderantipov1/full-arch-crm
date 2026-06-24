# Contract — ENG-226 (M-3)

## `pid_check.runtime_status(pid)` semantics

```python
def runtime_status(pid: int | None) -> str:
    """Return 'alive' | 'exited' | 'missing'.

    - pid is None / not int / <= 0 → 'missing'
    - os.kill(pid, 0) raises ProcessLookupError → 'exited'
    - os.kill(pid, 0) raises PermissionError → 'alive'
      (process exists; we just can't signal it)
    - os.kill(pid, 0) succeeds → 'alive'
    """
```

## Activity heuristic semantics

```python
def activity_state(log_path: Path, idle_threshold_seconds: int = 60) -> str:
    """Return 'active' | 'idle' | 'waiting_input' | 'blocked'.

    Order of checks (first hit wins):
    1. Log file missing → 'idle'.
    2. Tail (last 50 lines) contains 'Needs decision:' → 'waiting_input'.
    3. Tail contains 'Blocked:' → 'blocked'.
    4. Log mtime within idle_threshold_seconds → 'active'.
    5. Otherwise → 'idle'.
    """
```

## `worker_ctl.py` CLI

```
python3 worker_ctl.py --list                    [--mission <path>]
python3 worker_ctl.py --status <session-id>     [--mission <path>] [--tail-lines N]
python3 worker_ctl.py --kill <session-id>       [--mission <path>] [--grace <seconds>]
python3 worker_ctl.py --attach <session-id>     [--mission <path>]
```

- Exactly one of `--list` / `--status` / `--kill` / `--attach` must
  be specified (mutex group).
- `--mission` defaults to the ENG-223 detector's choice (newest
  non-archived mission folder, or branch-id match if applicable).
- `--grace` default: 10.
- `--tail-lines` default: 20.

Exit codes:
- `0` — success.
- `2` — guardrail / argparse violation.
- `3` — unknown session id.
- `4` — git / signal operation failed.
- `5` — user interrupted (e.g. Ctrl-C in `--attach`).

## Derived runtime.json fields (status_wave + dashboard render-time)

When the dashboard snapshot or status_wave renders sessions, it
enriches each `runtime.json.sessions[i]` with:

```json
{
  "runtime_status": "alive" | "exited" | "missing",
  "agent_activity": "active" | "idle" | "waiting_input" | "blocked"
}
```

These are NEVER written to runtime.json on disk. Always recomputed.
The launcher does not produce them; only the read surfaces (dashboard,
status_wave, worker_ctl --list/--status) compute them.

## `start_control_plane.py` semantics

```
python3 start_control_plane.py [--no-open] [--port 8787]
```

Behavior:
1. Resolves the runtime root via `paths.runtime_root()`. Refuses if
   the directory doesn't exist (exit 2) with a clear message.
2. Runs `status_wave.py` once and prints its output.
3. Starts `.agents/dashboard/server.py --port <port>` as a child
   process (`subprocess.Popen`).
4. Polls `/api/snapshot` until it returns 200 (with a 10s timeout).
5. Prints `Agent dashboard: http://127.0.0.1:<port>`.
6. If not `--no-open`, calls `webbrowser.open(url)`.
7. Blocks until Ctrl-C; on signal, sends SIGTERM to the dashboard
   child, waits 5s, then SIGKILL if alive.
8. Exits 0 on clean shutdown.

## Activity heuristic disclaimer (docs)

The README + SKILL.md must include a one-paragraph note:

> The `agent_activity` field is a HEURISTIC derived from log file
> mtime and marker-string detection in the tail. It is NOT a contract.
> When a session is critical (e.g. waiting on a human decision),
> trust the worker's explicit `Needs decision:` / `Blocked:` markers
> in `runlog.md` over the heuristic. The heuristic exists to provide
> "is this still moving?" context, not authoritative status.

## Mutex behavior

The CLI uses a single mutex group for the action flags. Calling
multiple action flags simultaneously is refused via argparse's
`add_mutually_exclusive_group(required=True)`.
