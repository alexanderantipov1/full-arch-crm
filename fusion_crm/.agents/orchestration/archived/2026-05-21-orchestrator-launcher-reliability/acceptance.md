# Acceptance Criteria

1. `python3 .agents/skills/agent-orchestrator/scripts/launch_worker.py
   --runtime codex --mode background --task-id TEST-1 --linear-id TEST-1
   --linear-url https://example/TEST-1 --linear-title smoke
   --prompt "echo ok"` exits 0; worker PID is still alive long enough to write
   the log; log file contains the worker output.
2. The same invocation with `--runtime claude-code` produces a non-empty log
   file.
3. `pytest .agents/skills/agent-orchestrator/tests/` is green.
4. `grep -RIn "ask-for-approval" .agents/skills/agent-orchestrator/scripts .agents/skills/agent-orchestrator/SKILL.md .claude/commands` returns nothing. The canonical regression guard is `test_codex_command_default_omits_deprecated_flag` and (when env-gated) `test_codex_exec_no_longer_has_ask_for_approval`. Test files and audit docs intentionally cite the deprecated flag and are excluded from this grep scope.
5. `incidents.md` in this mission folder contains a resolution entry that
   references the fix commit or PR.
6. `SKILL.md` for `agent-orchestrator` and `.claude/commands/orchestrator.md`
   show only flags accepted by the currently installed `codex exec` CLI.
7. `--codex-bypass-approvals` defaults to off; when set, the codex command
   includes `--dangerously-bypass-approvals-and-sandbox`.
