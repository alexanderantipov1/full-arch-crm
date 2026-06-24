# Contract

## Scope

- Edits limited to:
  - `.agents/skills/agent-orchestrator/scripts/launch_worker.py`
  - `.agents/skills/agent-orchestrator/scripts/launch_commands.py` (only if
    needed to thread the new flag through; default expectation: no change).
  - `.agents/skills/agent-orchestrator/SKILL.md` (flag examples).
  - `.claude/commands/orchestrator.md` (flag examples).
  - New tests under `.agents/skills/agent-orchestrator/tests/`.
  - `.agents/orchestration/orchestrator-launcher-reliability/incidents.md`
    (resolution entry).
- Out of scope (separate candidate missions if needed):
  - Product code under `apps/`, `packages/`, `infra/`.
  - Dashboard server.
  - Strategy and handoff files (`.agents/strategy/*`) other than the
    readiness-status note.

## Boundaries

- No secrets or `.env*` reads.
- No PHI or clinical data anywhere in tests or fixtures.
- No commits, pushes, or destructive git operations.
- No worktree creation.
- No Linear writes by the Worker (Orchestrator owns Linear state for this
  mission).

## CLI surface delta

- Remove `--codex-approval` argparse flag (and `--ask-for-approval` from the
  emitted command).
- Add `--codex-bypass-approvals` boolean argparse flag, default `False`. When
  truthy, the codex command list includes
  `--dangerously-bypass-approvals-and-sandbox`.
- All other flags unchanged.

## Subprocess.Popen delta (background mode only)

```python
process = subprocess.Popen(
    command,
    cwd=args.worktree,
    stdout=log_handle,
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
    start_new_session=True,
)
```
