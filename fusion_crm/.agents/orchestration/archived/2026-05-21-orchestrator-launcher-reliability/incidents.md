# Incidents

## Carryover from `.agents/orchestration/archived/2026-05-19-integration-foundation/`

- 2026-05-20T04:33:18Z | ENG-190 | Blocked: codex background launch pid 79820 exited immediately and wrote an empty log. Retrying through claude-code runtime.
- 2026-05-20T04:34:44Z | ENG-190 | Blocked: claude-code background launch pid 83411 exited immediately and wrote an empty log. Manual codex exec recovery started with pid 86139.
- 2026-05-20T04:34:44Z | ENG-190 | Contract drift: launch_worker.py uses deprecated `codex exec --ask-for-approval`; current codex CLI rejected that flag. Needs follow-up launcher fix.
- 2026-05-20T04:35:25Z | ENG-190 | Blocked: manual background codex exec pid 86139 exited immediately with empty log. Foreground codex exec session 12920 is running.

Root cause identified: launcher does not detach child process from the
controlling terminal; SIGHUP from the parent shell kills the worker before
any output is written. Independent: `--ask-for-approval` flag is deprecated in
the current `codex exec` CLI. Both are tracked in this mission as TASK-A.

## Resolution

- 2026-05-20T17:45:00Z | TASK-A | Resolved: launcher detach + codex flag drift
  fixed in `.agents/skills/agent-orchestrator/scripts/launch_worker.py`.
  Background-mode `subprocess.Popen` now sets `start_new_session=True` and
  `stdin=subprocess.DEVNULL` so the worker detaches from the launcher's
  controlling terminal and survives launcher exit. The deprecated
  `--ask-for-approval` flag was removed from the codex command builder and from
  argparse; opt-in `--codex-bypass-approvals` was added that appends
  `--dangerously-bypass-approvals-and-sandbox` to the codex command when set.
  Verified via fake-codex/fake-claude PATH-shim smoke against
  `--mode background`: worker pid 77200 (codex) and pid 77438 (claude-code)
  both survived launcher exit, wrote full FAKE_*_START/FAKE_*_END markers
  to the log, and runtime.json captured pid + status=running + launch_mode=
  background. Print-mode emits expected command shape for codex
  (with and without bypass) and for claude-code. SKILL.md and
  `.claude/commands/orchestrator.md` snippets updated to current flag set.
