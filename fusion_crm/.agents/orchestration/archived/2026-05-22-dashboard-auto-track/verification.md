# Verification Plan — ENG-223

## Scope check

- Touched files must stay under `.agents/dashboard/` plus new tests
  under `.agents/skills/agent-orchestrator/tests/` (or a co-located
  `.agents/dashboard/tests/` if the worker prefers). Any file outside
  this scope is an ownership violation.

## Compile + lint

```bash
python3 -m py_compile .agents/dashboard/server.py
```

## Tests

```bash
.venv/bin/python -m pytest .agents/skills/agent-orchestrator/tests/ -v
```

Plus the new ENG-223-specific unit tests added by the worker.

## Smoke test (manual)

1. Stop any running dashboard.
2. Start dashboard with no `--mission`:
   ```bash
   python3 .agents/dashboard/server.py
   ```
3. From another shell:
   ```bash
   curl -s http://127.0.0.1:8787/api/snapshot | jq '.mission | {active_mission_name, resolution_reason}'
   ```
   Expect a real folder name and a non-`no-mission` reason that matches
   the current git branch (or mtime if branch has no `ENG-\d+`).
4. Switch git branch to a different `ENG-\d+` (or simulate by setting
   up two mission folders with matching `runtime.json`); re-curl
   without restarting the dashboard; expect the snapshot to reflect
   the new mission.
5. Start dashboard with `--mission .agents/orchestration/archived/...`;
   confirm it stays pinned even when branch changes.

## Hygiene check

```bash
grep -R "ENG-128" .agents .claude 2>/dev/null || true   # stale refs
grep -R "args.mission.resolve()" .agents                # should be gone or moved
```

## Worker report contract

The worker report (`reports/ENG-223-worker-report.md`) must include:

- Task id and title.
- Linear id + URL.
- Branch + worktree.
- Touched files (paths).
- Tests run (commands + green/red counts).
- Smoke-test transcript or screenshots.
- Risks and follow-ups.
- Explicit do-not-merge conditions if any.

## Acceptance recheck

The verifier walks each item in `acceptance.md` and marks it
done/blocked with evidence. If any item is blocked, the verifier writes
`Verification failed:` in `runlog.md`.
