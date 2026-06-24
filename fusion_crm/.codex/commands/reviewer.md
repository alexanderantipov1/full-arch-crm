---
description: Run an independent production reviewer for Fusion CRM mission state.
---

For the review target: **$ARGUMENTS**

Use this command when the user wants an outside review of where the mission
stands, what is unfinished, whether agents missed anything, or what needs
cleanup before merge/deploy.

## Default: review in the current Codex session

Use `$production-reviewer`.

Read:

- `CLAUDE.md`
- `AGENTS.md`
- `.agents/CLAUDE.md`
- `.agents/AGENTS.md`
- `.agents/orchestration/CLAUDE.md`
- `.agents/orchestration/AGENTS.md`
- `.agents/skills/production-reviewer/SKILL.md`

Then inspect observable state only:

- git branch, status, and diff;
- `.agents/orchestration/current/` spec files;
- runtime files under `FUSION_AGENT_RUNTIME_HOME` or the default runtime root;
- worker reports, incidents, decision log, board, runlog, and Linear sync;
- related Linear issue, GitHub PR, and CI state when available;
- verification evidence, especially `make lint`, `mypy .`, `make test`, and
  `cd packages/db && alembic check` when product code changed.

Return:

1. **State**
2. **Open Work**
3. **Risks**
4. **Coordination Gaps**
5. **Next Actions**

## Launch as a dashboard-visible Codex reviewer

Use the Orchestrator launcher when the user wants a separate tracked reviewer
session. Replace the Linear fields with the real issue.

```bash
python3 .agents/skills/agent-orchestrator/scripts/launch_worker.py \
  --mission .agents/orchestration/current \
  --runtime codex \
  --role reviewer \
  --workspace self \
  --allow-self-execute \
  --scope docs \
  --task-id REVIEW-000 \
  --linear-id ENG-000 \
  --linear-url https://linear.app/... \
  --linear-title "Production review" \
  --prompt "Use $production-reviewer to audit the current mission. Produce State, Open Work, Risks, Coordination Gaps, and Next Actions. Do not edit code." \
  --mode print
```

Use `--mode background` only when the user explicitly asks to launch it.
