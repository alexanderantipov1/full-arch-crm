# Lessons — ENG-226 (M-3) Process Supervision + Granular Activity States

## Big PRs (8 tasks) ship clean on first try when `make verify` discipline holds

**Trigger:** M-3 was the largest PR in the arc — 28 new tests, 4 new
scripts, 6 modified files. Yet CI passed on the first attempt because
`make verify` ran locally before push (one ruff cycle caught + fixed
inline: unused `pytest` import and `S310` for the localhost urlopen
liveness probe).

**Rule:** "Bigger PR" does not mean "more CI cycles". `make verify`
locally before every push, regardless of PR size. The marginal cost
of a 30-second local run is always less than the cost of a failed CI
cycle plus the context-switch back to fix it.

## Argparse mutex group is the cleanest pattern for subcommand-style CLIs

**Trigger:** `worker_ctl.py` had 4 actions (`--list`, `--status`,
`--kill`, `--attach`) and needed mutual exclusion. Initial impulse
was to write subparsers, but the four actions share most args (mission,
grace, tail-lines). Mutex group keeps everything flat:

```python
action = parser.add_mutually_exclusive_group(required=True)
action.add_argument("--list", action="store_true", ...)
action.add_argument("--status", metavar="SID", ...)
action.add_argument("--kill", metavar="SID", ...)
action.add_argument("--attach", metavar="SID", ...)
```

**Rule:** When 3-5 CLI actions share most args, use a mutually
exclusive group, not subparsers. Subparsers shine when each action
has a distinct argument set; here they would have duplicated 5+ shared
args across four subparser blocks.

## Heuristic surfaces must label themselves as heuristic

**Trigger:** `agent_activity` is a best-effort field derived from log
mtime + tail marker scan. Easy to mistake it for authoritative status.

**Rule:** Surfaces that render heuristic fields must label them in the
output. `worker_ctl --status` prints `Agent activity: <state>
[heuristic]`. `tests/README.md` has an explicit one-paragraph
disclaimer. Future readers MUST not treat the heuristic as a contract.

**Generalization:** any computed-best-effort field needs:
1. A label at the rendering point ("[heuristic]" or similar).
2. A documented authoritative alternative (here: worker's own
   `Needs decision:` / `Blocked:` runlog markers).
3. A test that explicitly proves the heuristic is best-effort
   (e.g. our test that proves a marker beyond the 50-line tail
   window is NOT picked up).

## `start_control_plane.py` pattern: spawn → poll → block → graceful shutdown

**Trigger:** Designing a wrapper that owns a long-lived dashboard
subprocess.

**Rule:** Standard shape:

1. Validate environment (runtime root exists, dashboard binary exists).
2. Spawn child via `subprocess.Popen` with PIPE'd stdout/stderr (so
   the wrapper can drain if needed) and `DEVNULL` stdin.
3. Poll a readiness endpoint with a fixed timeout — DON'T just
   `time.sleep(N)`; that's a flake source.
4. Install a SIGTERM handler that raises `KeyboardInterrupt` so the
   `try/except KeyboardInterrupt` path runs for both Ctrl-C and
   `kill <pid>`.
5. In the cleanup path: SIGTERM → grace timeout via `child.wait(timeout=N)`
   → SIGKILL fallback → final `child.wait(timeout=1)` to reap.

This is the same shape M-2's launcher background mode uses and M-3's
worker_ctl kill flow uses. Standardize.
