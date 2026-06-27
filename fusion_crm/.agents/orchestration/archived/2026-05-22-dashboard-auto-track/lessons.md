# Lessons — Dashboard Auto-Track Active Mission

## Never use broad `pkill -f` patterns to clean up spawned processes

**Trigger:** ENG-223 smoke test (2026-05-22T02:33Z) used `pkill -f
"dashboard/server.py"` to shut down the worker-spawned temporary
dashboard on port 8788. That pattern also killed the doctor's live
dashboard on port 8787.

**Rule:** When a script spawns a process for a smoke test, capture its
PID and target it explicitly:

```bash
.venv/bin/python .agents/dashboard/server.py --port 8788 > /tmp/log 2>&1 &
SMOKE_PID=$!
# ... probe ...
kill "$SMOKE_PID" 2>/dev/null
wait "$SMOKE_PID" 2>/dev/null
```

Or, even better, do not background it at all — run via
`subprocess.Popen` in a Python smoke harness and call `.terminate()`
on the same handle.

**Generalization:** `pkill -f <pattern>` is fine for interactive
cleanup when you know nothing else matches. It is unsafe inside an
automated worker flow because the worker cannot predict what else the
human partner has running.

## Always check whether a branch already exists before "starting" work

**Trigger:** ENG-223 worker discovered the branch
`eduardk/eng-223-dashboard-auto-track-active-mission` already
carried a complete implementation (commit `0d346fd`) plus an archive
sweep (`16924e8`), neither of which had a PR.

**Rule:** First step in any worker session is
`git rev-parse --verify <branch>` (or `git ls-remote`). If the branch
exists locally OR on the remote, inspect commits before touching code.
Cheap check, prevents 30 minutes of duplicate work.

**Generalization:** any worker prompt should include a pre-flight
"discover existing artifacts" step before touching code.
