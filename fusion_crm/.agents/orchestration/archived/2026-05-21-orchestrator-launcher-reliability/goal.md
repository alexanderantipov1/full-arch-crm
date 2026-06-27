# Mission Goal — Orchestrator Launcher Reliability And Test Harness

Restore trust in the agent orchestration runtime so the human partner can launch
parallel Codex and Claude Code workers without silent failures.

## Source

- Strategy candidate: `.agents/strategy/CANDIDATE_MISSIONS.md` →
  "Orchestrator Launcher Reliability And Test Harness".
- Strategy handoff: `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md` →
  "Orchestrator Launcher Reliability And Test Harness".

## Root cause summary (from prior wave incidents)

1. `.agents/skills/agent-orchestrator/scripts/launch_worker.py` runs
   `subprocess.Popen` for `--mode background` without `start_new_session=True`
   and without `stdin=subprocess.DEVNULL`. The spawned worker inherits the
   launcher's controlling terminal and process group; when the launcher exits,
   the worker receives SIGHUP and dies before writing any output. Both
   `codex` and `claude-code` runtimes fail with empty 0-byte logs for this
   reason.
2. The codex command builder passes `--ask-for-approval <value>`, which the
   currently installed `codex exec` CLI no longer accepts. The flag should be
   removed; full bypass should be expressed via an opt-in
   `--codex-bypass-approvals` argparse flag that appends
   `--dangerously-bypass-approvals-and-sandbox` to the command when set.

## What a successful mission looks like

- Background-mode worker survives launcher exit for both runtimes.
- Background log is non-empty after a real launch.
- Launcher emits only flags accepted by the current `codex exec` CLI.
- A focused `pytest` suite under
  `.agents/skills/agent-orchestrator/tests/` covers unit, integration, SIGHUP,
  contract, schema, and wave-wrapper behavior.
- Mission `incidents.md` carries a resolution entry.
- `SKILL.md` and `.claude/commands/orchestrator.md` show only valid flags.
