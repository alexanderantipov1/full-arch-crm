# Verification Plan — ENG-225 (M-2)

## Scope check

Touched files must stay under:
- `.agents/skills/agent-orchestrator/scripts/` (launcher edits + new
  `cleanup_worktrees.py`)
- `.agents/skills/agent-orchestrator/tests/`
- `.agents/orchestration/CLAUDE.md`
- `.agents/skills/agent-orchestrator/SKILL.md`
- `.agents/skills/agent-orchestrator/tests/README.md`
- `.agents/orchestration/worktree-as-default/`

Any file outside is an ownership violation.

## Compile + lint + type check

```bash
make verify
```

This runs `ruff check .` + `mypy packages apps` + `pytest` for the
product code. Must be green BEFORE push (M-1 lesson — ruff caught
sha1; CI cycle wasted).

## Skill test suites

```bash
.venv/bin/python -m pytest .agents/skills/agent-orchestrator/tests/ -v
.venv/bin/python -m pytest .agents/dashboard/tests/ -v
```

Both must be green. The integration test in (F) is the load-bearing
proof of isolation.

## Smoke test (manual)

1. Pre-flight rejects dirty tree:
   ```bash
   echo "x" >> some-file.md
   .venv/bin/python .agents/skills/agent-orchestrator/scripts/launch_worker.py \
     --mission .agents/orchestration/worktree-as-default \
     --runtime claude-code --role worker \
     --task-id SMOKE-1 --linear-id ENG-225 \
     --linear-url https://linear.app/.../ENG-225 \
     --linear-title Smoke --prompt "echo ok" --mode print
   ```
   Expect: SystemExit naming `some-file.md`. Revert the dirty change.

2. Worktree created on clean main:
   ```bash
   .venv/bin/python .agents/skills/agent-orchestrator/scripts/launch_worker.py \
     --mission .agents/orchestration/worktree-as-default \
     --runtime claude-code --role worker \
     --task-id SMOKE-2 --linear-id ENG-225 \
     --linear-url https://linear.app/.../ENG-225 \
     --linear-title Smoke --prompt "echo ok" --mode print \
     --branch-base main
   ```
   Expect: a directory under
   `$FUSION_AGENT_RUNTIME_HOME/worktree-as-default/worktrees/SMOKE-2/`
   exists, is on branch `eng-225-SMOKE-2`, contains the working tree.

3. Self-execute refused without `--allow-self-execute`:
   ```bash
   ... --workspace self
   ```
   Expect: SystemExit naming `--allow-self-execute`.

4. Self-execute guardrail catches missing scope:
   ```bash
   ... --workspace self --allow-self-execute
   ```
   Expect: SystemExit naming `--scope`.

5. Self-execute happy path:
   ```bash
   ... --workspace self --allow-self-execute --scope bugfix --note "Tiny: fix typo"
   ```
   Expect: success; `decision-log.md` shows a `Scope: bugfix` line.

6. Cleanup helper dry-run shows the SMOKE worktrees as cleanup
   candidates after they're done:
   ```bash
   .venv/bin/python .agents/skills/agent-orchestrator/scripts/cleanup_worktrees.py --dry-run
   ```

## Worker report contract

`reports/ENG-225-worker-report.md` must include:
- Task id + title.
- Linear id + URL.
- Branch + worktree.
- Touched files per Task A-F.
- Tests run (commands + counts).
- Smoke transcript covering the 6 cases above.
- Risks + follow-ups (especially M-3 readiness).
- Do-not-merge conditions.

## Acceptance recheck

Verifier walks each box in `acceptance.md` against evidence. Blockers
get a `Verification failed:` line in runlog.
