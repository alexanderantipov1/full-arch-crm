# Agent Orchestrator

Use this command when the user wants current execution orchestration, Linear
task planning, dashboard-visible runtime state, or launching Codex / Claude
Code workers.

Read:

- `CLAUDE.md`
- `AGENTS.md`
- `.agents/CLAUDE.md`
- `.agents/AGENTS.md`
- `.agents/orchestration/CLAUDE.md`
- `.agents/orchestration/AGENTS.md`
- `.agents/skills/agent-orchestrator/SKILL.md`

Responsibilities:

- accept or reject Strategy handoffs;
- create or link Linear issues before execution;
- update `.agents/orchestration/current/`;
- record `runtime.json`, `linear-sync.md`, `board.md`, and `runlog.md`;
- launch Workers only with dashboard-visible state;
- launch Production Reviewers for read-only mission audits when requested;
- record every role transition as `Handoff:`;
- require Linear issue id and URL before assigning Workers.

Use the launcher when a worker should be started:

```bash
python3 .agents/skills/agent-orchestrator/scripts/launch_worker.py \
  --mission .agents/orchestration/current \
  --runtime claude-code \
  --role worker \
  --task-id ENG-000 \
  --linear-id ENG-000 \
  --linear-url https://linear.app/... \
  --linear-title "Short task title" \
  --prompt "Worker instructions..." \
  --mode print
```

For codex workers, the launcher uses the current `codex exec` flag surface
(`--cd`, `--sandbox`). Approval bypass is opt-in via `--codex-bypass-approvals`
(default off, unsafe — only enable when the worker explicitly needs it):

```bash
python3 .agents/skills/agent-orchestrator/scripts/launch_worker.py \
  --runtime codex \
  --codex-sandbox workspace-write \
  --codex-bypass-approvals \
  --role worker \
  --task-id ENG-000 \
  --linear-id ENG-000 \
  --linear-url https://linear.app/... \
  --linear-title "Short task title" \
  --prompt "Worker instructions..." \
  --mode print
```

Use `--mode print` when planning, `--mode background` or `--mode tmux` only
when the user expects automatic launch. Background launches detach the child
process via `start_new_session` so the worker survives launcher exit.
