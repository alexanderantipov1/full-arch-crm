# Verification Plan — ENG-224 (M-1)

## Scope check

Touched files must stay under:
- `.agents/skills/agent-orchestrator/scripts/` (paths.py + edits to
  launch_worker.py, run_wave.py, status_wave.py)
- `.agents/skills/agent-orchestrator/tests/`
- `.agents/dashboard/server.py` (snapshot/log endpoints only — no UI
  changes required)
- `.agents/CLAUDE.md`, `.agents/orchestration/CLAUDE.md`,
  `.agents/orchestration/AGENTS.md`,
  `.agents/skills/agent-orchestrator/SKILL.md`,
  `.agents/skills/agent-orchestrator/tests/README.md`
- `.gitignore`
- `.agents/orchestration/runtime-state-out-of-repo/`

Anything outside this set is an ownership violation.

## Compile + lint

```bash
python3 -m py_compile .agents/dashboard/server.py
python3 -m py_compile .agents/skills/agent-orchestrator/scripts/paths.py
python3 -m py_compile .agents/skills/agent-orchestrator/scripts/launch_worker.py
python3 -m py_compile .agents/skills/agent-orchestrator/scripts/run_wave.py
python3 -m py_compile .agents/skills/agent-orchestrator/scripts/status_wave.py
```

## Tests

```bash
.venv/bin/python -m pytest .agents/skills/agent-orchestrator/tests/ -v
.venv/bin/python -m pytest .agents/dashboard/tests/ -v
```

Required: all tests green. New `paths.py` unit tests must be present.

## Smoke test (manual)

1. Verify the local runtime path is honored:
   ```bash
   FUSION_AGENT_RUNTIME_HOME=/tmp/fusion-agent-runtime \
     python3 .agents/skills/agent-orchestrator/scripts/launch_worker.py \
       --mission .agents/orchestration/runtime-state-out-of-repo \
       --runtime claude-code --role worker \
       --task-id SMOKE-1 --linear-id ENG-224 \
       --linear-url https://linear.app/.../ENG-224 \
       --linear-title "Smoke" --prompt "echo ok" --mode print
   ```
   Expect: `runtime.json`, `runlog.md`, `board.md`, `linear-sync.md`,
   `prompts/SMOKE-1-*.md` appear under
   `/tmp/fusion-agent-runtime/<repo-hash>/runtime-state-out-of-repo/`.
   Decision artifacts (`goal.md` etc.) and `reports/` stay in repo.

2. Verify dashboard merges both views:
   ```bash
   FUSION_AGENT_RUNTIME_HOME=/tmp/fusion-agent-runtime \
     python3 .agents/dashboard/server.py &
   curl -s http://127.0.0.1:8787/api/snapshot | jq '.mission'
   ```
   Expect: `active_mission_name=runtime-state-out-of-repo`,
   `resolution_reason` includes the branch match,
   `mission.files.goal.md.exists=True` (repo),
   `mission.runtime.sessions[0].id=SMOKE-1-...` (local path).

3. Verify the env precedence:
   - With `FUSION_AGENT_RUNTIME_HOME` unset, the runtime root must
     resolve to `~/.fusion-agent-orchestrator/<repo-hash>/`.
   - With the env var set, that wins.
   - With `--runtime-root <path>` CLI override (if added), that wins
     even over env. Document the precedence in SKILL.md.

4. Verify .gitignore catches accidental writes:
   ```bash
   touch .agents/orchestration/runtime-state-out-of-repo/runtime.json
   git status --short | grep "runtime.json" && echo "LEAK"
   ```
   Expect: no `LEAK` line. (After fix lands; right now there's a
   committed runtime.json — the rule covers FUTURE writes only.)

## Hygiene check

```bash
grep -R "args.mission" .agents/dashboard .agents/skills/agent-orchestrator/scripts
# Should show no eager .resolve() at startup for runtime path; only
# spec path uses repo-relative resolution.
```

## Worker report contract

`reports/ENG-224-worker-report.md` must include:
- Task id + title (ENG-224 M-1).
- Linear id + URL.
- Branch + worktree.
- Touched files (paths) per Task A-G.
- Tests run (commands + green/red counts).
- Smoke-test transcript.
- Risks + follow-ups (especially M-2/M-3 readiness).
- Explicit do-not-merge conditions if any.

## Acceptance recheck

The verifier walks every checkbox in `acceptance.md` against evidence
and marks done/blocked. Any blocker → `Verification failed:` in runlog.
