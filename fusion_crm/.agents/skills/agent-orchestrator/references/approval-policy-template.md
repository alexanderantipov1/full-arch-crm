# Approval Policy

Mission:
Wave:
Approved by:

## Goal

Approve one bounded wave instead of approving routine commands in every worker terminal.

## Pre-Approved Inside This Wave

Workers may:
- Read files inside the repository.
- Edit only their assigned write scope.
- Run focused tests and static checks.
- Start local dev servers on assigned ports.
- Write reports to the assigned report path.
- For `tiny_fix` and low-risk `normal` tasks, create an isolated branch,
  stage only task-owned files, commit, push the task branch, and open a draft
  PR after focused verification passes.
- Preserve unrelated dirty and untracked files.

## Worker Stop Conditions

Workers must stop and report to the orchestrator, not the user, if:
- The task requires files outside the assigned write scope.
- A shared file conflict appears.
- Tests fail for unclear reasons.
- The task requires migration, dependency, env, deploy, secret, or GitHub Actions changes.
- The task requires merge to `main`, release integration, production data,
  deploy, or destructive commands.
- Unrelated changes are in the same files and cannot be separated safely.
- A major merge, large PR boundary, mission direction change, context
  compaction, or budget exhaustion means the next substantial task needs a
  Context Rollover Gate handoff first.

## Always Requires User Approval

- Merge to integration, main, or release branches.
- Production or staging deploy.
- Destructive git commands such as reset, clean, checkout-overwrite, force-push.
- `.env*`, secrets, deploy scripts, GitHub Actions deploy workflow, Cloud Run services/jobs.
- Shipped Alembic revisions.
- Architecture invariants.
- PHI-sensitive decisions.
- Shared contract changes, durable schema changes, migrations, auth/security
  behavior changes, or metric/time-window/read-model semantics changes.
- Deferring Context Rollover Gate after a required rollover trigger.

## Recommended Terminal Modes

Codex worker:

```bash
python3 .agents/skills/agent-orchestrator/scripts/launch_worker.py \
  --runtime codex \
  --codex-sandbox workspace-write \
  --codex-full-auto \
  --workspace worktree \
  --role worker \
  --task-id ENG-000 \
  --linear-id ENG-000 \
  --linear-url https://linear.app/... \
  --linear-title "Short task title" \
  --prompt "Worker instructions..." \
  --mode background
```

Claude worker:

```bash
python3 .agents/skills/agent-orchestrator/scripts/launch_worker.py \
  --runtime claude-code \
  --claude-permission-mode auto \
  --workspace worktree \
  --role worker \
  --task-id ENG-000 \
  --linear-id ENG-000 \
  --linear-url https://linear.app/... \
  --linear-title "Short task title" \
  --prompt "Worker instructions..." \
  --mode background
```

Codex `--codex-full-auto` maps to the installed CLI's
`--dangerously-bypass-approvals-and-sandbox` flag because this Codex version
does not expose `codex exec --full-auto`. Use it only through the Orchestrator
launcher after the task has Linear, ownership card, worktree, forbidden paths,
and verification defined. Do not use Claude `--dangerously-skip-permissions`
for normal workers.

## Unattended Wave Commands

Run workers in the background:

```bash
python3 .agents/skills/agent-orchestrator/scripts/run_wave.py \
  --tasks .agents/orchestration/<mission>/wave.json \
  --mission .agents/orchestration/<mission> \
  --mode background
```

Check status:

```bash
python3 .agents/skills/agent-orchestrator/scripts/status_wave.py \
  --mission .agents/orchestration/<mission>
```

Workers must put questions and blockers in their report files. The orchestrator reviews those reports and escalates only consolidated decisions to the user.
