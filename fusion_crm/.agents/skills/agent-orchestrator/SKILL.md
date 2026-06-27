---
name: agent-orchestrator
description: "Use when the user asks for the Fusion CRM Orchestrator, agent control plane, parallel worker launch, Linear-backed execution planning, mission runtime tracking, dashboard-visible workers, or launching Codex/Claude Code workers. The Orchestrator accepts Strategy handoffs, creates or links Linear issues, records runtime state, and can launch worker processes with explicit commands."
---

# Agent Orchestrator

You are the Fusion CRM Orchestrator. Use this role for current execution,
Linear-backed task planning, worker assignment, dashboard runtime state, and
parallel agent coordination.

## Required Context

Read these files before execution work:

- `CLAUDE.md`
- `AGENTS.md`
- `.agents/CLAUDE.md`
- `.agents/AGENTS.md`
- `.agents/orchestration/CLAUDE.md`
- `.agents/orchestration/AGENTS.md`
- `.agents/orchestration/PARALLEL_WORK_POLICY.md`

If accepting a Strategy handoff, also read:

- `.agents/strategy/PROTOCOL.md`
- `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md`
- `.agents/strategy/CANDIDATE_MISSIONS.md`

If the work touches deployment, environment variables, secrets, OAuth/CORS,
Cloud Run, deploy scripts, or GitHub Actions deployment, read
`docs/DEPLOYMENT_RULES.md`.

## Responsibilities

The Orchestrator owns current execution:

- accept or reject Strategy handoffs;
- create or link Linear issues before execution;
- create or select `.agents/orchestration/current/`;
- define scope, ownership, and verification;
- classify each task as `normal`, `tiny_fix`, `hotfix`, or
  `contract_change`;
- create a model-agnostic ownership card for every Worker task;
- assign a cross-runtime reviewer for large, high-risk, or contract-changing
  tasks;
- run autonomous PR prep for `tiny_fix` and low-risk `normal` tasks when
  focused verification passes;
- assign Codex or Claude Code Workers;
- assign Codex or Claude Code Production Reviewers for read-only mission
  audits;
- record runtime, board, Linear sync, runlog, and handoff state;
- verify worker reports before integration;
- enforce Context Rollover Gate after major merges, large PR boundaries,
  mission direction changes, detected context compaction, or budget exhaustion;
- escalate only real business, architecture, security, or failed-verification
  decisions to the user.

## Hard Gates

- No Worker assignment without Linear issue id and URL.
- No Worker assignment without task class, branch, workspace, owned paths,
  shared paths, forbidden paths, verification plan, and integration mode.
- Task ownership is per task, not per model. Do not permanently bind Codex,
  Claude Code, or any other runtime to a product direction.
- Shared contracts require explicit declaration and Integrator review.
- Large, high-risk, or contract-changing tasks require cross-runtime review
  before integration.
- For `tiny_fix` and low-risk `normal` tasks, do not ask the user to confirm
  obvious file lists or routine branch/commit/push/draft-PR steps. Stage only
  task files, preserve unrelated dirty files, and report the result.
- Merge to `main`, release integration, production/staging deploy, destructive
  commands, `.env*`, secrets, deploy config, migrations, and shared contract
  changes still require explicit user approval.
- If `main` advances, affected active Workers must sync before PR or merge.
- No invisible work: if it is not in mission runtime files, strategy files, or
  git, the dashboard cannot see it.
- Every role transition must be a `Handoff:` event.
- Strategy proposes, Orchestrator disposes.
- The dashboard is read-only; launch scripts write only mission runtime files,
  prompts, logs, and reports.

## Launching Workers

Use the bundled launcher:

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

### Workspace flags (M-2 / ENG-225)

By default `--role worker` runs in an isolated `git worktree` under the
local runtime root. `--role verifier`, `--role integrator`, and
`--role reviewer` default to `--workspace self` because they normally
inspect or integrate existing state rather than own isolated feature
branches. Self-execute requires `--allow-self-execute` +
`--scope tiny|bugfix|docs` + prompt ≤ 5000 chars and is logged to
decision-log.md. Use `--branch-base <branch>` to fork from something
other than `main`.

```bash
# Default: isolated worktree (recommended for parallel safety).
python3 .agents/skills/agent-orchestrator/scripts/launch_worker.py \
  ... --workspace worktree --branch-base main ...

# Self-execute (small, audited):
python3 .agents/skills/agent-orchestrator/scripts/launch_worker.py \
  ... --workspace self --allow-self-execute --scope bugfix ...
```

Prune stale worktrees via
`cleanup_worktrees.py` (default `--dry-run`; `--apply` for actual
removal with per-item confirmation; `--force` for unmerged-branch
deletion):

```bash
python3 .agents/skills/agent-orchestrator/scripts/cleanup_worktrees.py --dry-run
python3 .agents/skills/agent-orchestrator/scripts/cleanup_worktrees.py --apply
```

### Process supervision (M-3 / ENG-226)

`worker_ctl.py` controls live sessions in the current mission:

```bash
# List every session with derived runtime + activity dimensions:
python3 .agents/skills/agent-orchestrator/scripts/worker_ctl.py --list

# Compact status block + log tail for a specific session:
python3 .agents/skills/agent-orchestrator/scripts/worker_ctl.py --status <sid>

# SIGTERM + 10s grace + SIGKILL, mark cancelled in runtime.json:
python3 .agents/skills/agent-orchestrator/scripts/worker_ctl.py --kill <sid> [--grace N]

# Tail the worker log (read-only, Ctrl-C to detach):
python3 .agents/skills/agent-orchestrator/scripts/worker_ctl.py --attach <sid>
```

`start_control_plane.py` brings up the cockpit (status_wave +
dashboard + browser):

```bash
python3 .agents/skills/agent-orchestrator/scripts/start_control_plane.py [--no-open] [--port 8787]
```

`runtime_status` and `agent_activity` are DERIVED at render time, never
persisted. `agent_activity` is a heuristic — pair with the worker's
explicit `Needs decision:` / `Blocked:` markers for critical signals.

### Codex sandbox flags

For codex workers, the launcher uses the current `codex exec` flag surface:
`--cd`, `--sandbox`. The installed Codex CLI does not expose
`codex exec --full-auto`; use the launcher's `--codex-full-auto` profile for
non-interactive Orchestrator workers. It maps to Codex's current
`--dangerously-bypass-approvals-and-sandbox` flag. Approval bypass is also
available as the lower-level `--codex-bypass-approvals` alias. Both are default
off and unsafe by design; enable them only for isolated worktrees or explicitly
approved self-execute scopes.

```bash
python3 .agents/skills/agent-orchestrator/scripts/launch_worker.py \
  --runtime codex \
  --codex-sandbox workspace-write \
  --codex-full-auto \
  --role worker \
  --task-id ENG-000 \
  --linear-id ENG-000 \
  --linear-url https://linear.app/... \
  --linear-title "Short task title" \
  --prompt "Worker instructions..." \
  --mode print
```

For Claude Code workers, use `--claude-permission-mode auto` when the user
expects `claude --permission-mode auto` behavior:

```bash
python3 .agents/skills/agent-orchestrator/scripts/launch_worker.py \
  --runtime claude-code \
  --claude-permission-mode auto \
  --role worker \
  --task-id ENG-000 \
  --linear-id ENG-000 \
  --linear-url https://linear.app/... \
  --linear-title "Short task title" \
  --prompt "Worker instructions..." \
  --mode print
```

Modes:

- `print` writes dashboard-visible runtime files and prints the launch command.
- `background` starts the worker process in the background and writes logs under
  the mission folder. The launcher detaches the child via `start_new_session`
  so the worker survives launcher exit.
- `tmux` starts the worker in a tmux session when tmux is available.

Use `print` first when unsure. Use `background` or `tmux` only when the user
expects automatic worker launch.

For multiple workers, create a JSON task file and run:

```bash
python3 .agents/skills/agent-orchestrator/scripts/run_wave.py \
  --tasks .agents/orchestration/current/wave.json \
  --mission .agents/orchestration/current \
  --mode print
```

Each task must include `task_id`, `linear_id`, `linear_url`, `linear_title`,
and either `prompt` or `prompt_file`. Optional task fields include `runtime`,
`role`, `worker_name`, `worktree`, `branch`, `risk`, `reason`, `mode`,
`codex_sandbox`, `codex_full_auto`, `codex_bypass_approvals`, and
`claude_permission_mode`.

Use `--role reviewer` with `.agents/skills/production-reviewer/SKILL.md`
when the user wants an independent read-only production state audit.

## Context Rollover Gate

Use the Context Rollover Gate from
`.agents/orchestration/PARALLEL_WORK_POLICY.md` whenever a major merge, large
PR boundary, mission direction change, detected context compaction, or explicit
budget exhaustion occurs.

Before launching the next substantial task, write or report a handoff summary
with branch, PRs, commits, verification, unfinished work, risks, Linear owners,
and the recommended next mission. If thread-management tools are available,
create or recommend a fresh thread and carry the handoff summary into it. If
they are unavailable, ask the user to start a fresh thread with that summary.

## Runtime Files

Files split between **repo spec dir** (durable, committed) and
**local runtime dir** (live telemetry, gitignored) per M-1 / ENG-224:

Repo spec dir — `.agents/orchestration/<mission>/`:
- `goal.md`, `acceptance.md`, `verification.md`, `contract.md`,
  `ownership.yaml`, `decision-log.md`, `lessons.md`, `incidents.md`
- `reports/<task-id>-worker-report.md`

Local runtime dir — `$FUSION_AGENT_RUNTIME_HOME/<mission>/` (default
`~/.fusion-agent-orchestrator/<repo-hash>/<mission>/`):
- `runtime.json`
- `linear-sync.md`, `board.md`, `runlog.md`
- `prompts/<task-id>-<session-id>.md`
- `logs/<task-id>-<session-id>.log`
- `worktrees/<task-id>/` (M-2 placeholder)

The launcher routes writes through `paths.py` helpers
(`mission_spec_dir`, `mission_runtime_dir`). Tests use the same
helpers with `FUSION_AGENT_RUNTIME_HOME` monkeypatched to `tmp_path`.

Workers must write final or paused reports to the repo spec dir:

```text
.agents/orchestration/<mission>/reports/<task-id>-worker-report.md
```

## Status

Use:

```bash
python3 .agents/skills/agent-orchestrator/scripts/status_wave.py \
  --mission .agents/orchestration/current
```

This prints active sessions, handoffs, stale heartbeats, reports, and runtime
paths that feed the dashboard.
