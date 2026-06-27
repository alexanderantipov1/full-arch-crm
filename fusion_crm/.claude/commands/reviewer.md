---
description: Run an independent production reviewer for Fusion CRM mission state.
---

For the review target: **$ARGUMENTS**

Use this command when the user wants an outside review of where the mission
stands, what is unfinished, whether agents missed anything, or what needs
cleanup before merge/deploy.

## Default: review in the current Claude Code session

Read:

- `CLAUDE.md`
- `AGENTS.md`
- `.agents/CLAUDE.md`
- `.agents/AGENTS.md`
- `.agents/orchestration/CLAUDE.md`
- `.agents/orchestration/AGENTS.md`
- `.agents/skills/production-reviewer/SKILL.md`

Then follow the Production Reviewer role exactly:

- read-only by default;
- audit observable state only;
- do not launch workers;
- do not edit code;
- do not commit, push, deploy, or run destructive commands.

Return:

1. **State**
2. **Open Work**
3. **Risks**
4. **Coordination Gaps**
5. **Next Actions**

## Launch as a dashboard-visible Claude Code reviewer

Use the Orchestrator launcher when the user wants a separate tracked reviewer
session. Replace the Linear fields with the real issue.

```bash
python3 .agents/skills/agent-orchestrator/scripts/launch_worker.py \
  --mission .agents/orchestration/current \
  --runtime claude-code \
  --role reviewer \
  --workspace self \
  --allow-self-execute \
  --scope docs \
  --task-id REVIEW-000 \
  --linear-id ENG-000 \
  --linear-url https://linear.app/... \
  --linear-title "Production review" \
  --prompt "Read .agents/skills/production-reviewer/SKILL.md and audit the current mission. Produce State, Open Work, Risks, Coordination Gaps, and Next Actions. Do not edit code." \
  --mode print
```

Use `--mode background` only when the user explicitly asks to launch it.
