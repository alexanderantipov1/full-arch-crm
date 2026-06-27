# Verification Plan — ENG-226 (M-3)

## Scope check

Touched files must stay under:
- `.agents/skills/agent-orchestrator/scripts/` (pid_check, activity
  heuristic, worker_ctl, start_control_plane, status_wave edits)
- `.agents/skills/agent-orchestrator/tests/`
- `.agents/dashboard/server.py` (snapshot enrichment only — no UI
  redesign)
- `.agents/orchestration/CLAUDE.md`
- `.agents/skills/agent-orchestrator/SKILL.md`
- `.agents/skills/agent-orchestrator/tests/README.md`
- `.agents/orchestration/process-supervision/`

Anything outside is an ownership violation.

## Compile + lint + type check

```bash
make verify
```

Run BEFORE push (M-1 lesson, M-2 confirmation). ruff + mypy + pytest
all green.

## Skill + dashboard suites

```bash
.venv/bin/python -m pytest .agents/skills/agent-orchestrator/tests/ -v
.venv/bin/python -m pytest .agents/dashboard/tests/ -v
```

Plus the new M-3 tests (`test_pid_check.py`, `test_activity_heuristic.py`,
`test_worker_ctl.py`, `test_start_control_plane.py`).

## Smoke test (manual)

1. `worker_ctl.py --list` against the current mission:
   ```bash
   python3 .agents/skills/agent-orchestrator/scripts/worker_ctl.py --list
   ```
   Expect: every session from `runtime.json` with derived
   `runtime_status` + `agent_activity`.

2. `worker_ctl.py --status <session-id>` on a real session:
   ```bash
   python3 .agents/skills/agent-orchestrator/scripts/worker_ctl.py --status orch-eng226-001
   ```
   Expect: compact block + last 20 lines of the session's log.

3. `worker_ctl.py --attach <session-id>`:
   ```bash
   python3 .agents/skills/agent-orchestrator/scripts/worker_ctl.py --attach <sid>
   ```
   Expect: tail follows live; Ctrl-C exits cleanly without modifying
   runtime.json.

4. `worker_ctl.py --kill <session-id>` against a controlled test
   worker:
   - Spawn a fake worker via `launch_worker.py --mode background`
     with a long-running prompt (sleep 60 in shim).
   - Kill it.
   - Confirm: SIGTERM sent first, process exits within `--grace`
     (10s default), runtime.json shows `status=cancelled`, runlog
     has a kill entry.

5. `start_control_plane.py --no-open`:
   ```bash
   python3 .agents/skills/agent-orchestrator/scripts/start_control_plane.py --no-open
   ```
   Expect: status_wave output printed once, dashboard URL printed,
   dashboard reachable at http://127.0.0.1:8787, no browser launched,
   Ctrl-C cleanly shuts dashboard down.

6. Dashboard snapshot:
   ```bash
   curl -s http://127.0.0.1:8787/api/snapshot |
     jq '.mission.runtime.sessions[] | {id, status, runtime_status, agent_activity}'
   ```
   Expect: every session has the two new derived fields populated.

## Hygiene check

```bash
grep -R "kill_all\|killall" .agents/skills/agent-orchestrator/scripts/
# Should return empty — no mass-write by design.
```

## Worker report contract

`reports/ENG-226-worker-report.md` must include:
- Task id + title (M-3).
- Linear id + URL.
- Branch + worktree.
- Touched files per Task A-H.
- Tests run (commands + counts).
- Smoke transcript covering the 6 cases above.
- Risks + follow-ups.
- Do-not-merge conditions.

## Acceptance recheck

Verifier walks every checkbox in `acceptance.md` against evidence.
Blockers get a `Verification failed:` line in runlog.
