# Parallel Work Policy

This policy is the canonical coordination contract for parallel Fusion CRM
agent work. It applies to Codex, Claude Code, and any future worker runtime.
Do not bind ownership to a model or vendor. Bind ownership to the task scope.

## Core Rule

```text
A Worker does not own a product direction. A Worker owns one declared task
scope, in one isolated workspace, on one branch, with one Linear issue.
```

Parallel execution is allowed only when every active task has:

- a Linear issue id and URL;
- an isolated worktree or an explicitly approved self-execute scope;
- a branch name;
- an ownership card;
- a verification plan;
- a worker report path;
- a merge/integration owner;
- a cross-runtime review plan when the task is large, high-risk, or changes a
  shared contract.

## Interactive Sessions (Hand-Opened Terminals)

The rest of this policy governs Workers launched through the Orchestrator
(`launch_worker.py`), which provision an isolated worktree automatically. This
section governs the other failure mode: **interactive Claude Code / Codex
sessions a human opens by hand in several terminals.** These do not pass through
the launcher, are invisible to the dashboard (`runtime.json` tracks only
launched sessions), and historically collide by sharing the one canonical
checkout and its single Git HEAD.

### Mandatory: one worktree per interactive session

A hand-opened interactive session **MUST NOT** do feature work, edits, or
commits in the canonical checkout `~/dev/Fusion_crm` (the primary worktree).
The canonical checkout is reserved for integration and read-only inspection.

Each interactive session that will edit code creates its own worktree first:

```bash
git fetch origin
git worktree add ../fusion_<short-task> -b <eng-id>-<slug> origin/main
cd ../fusion_<short-task>
```

Base off `origin/main` unless the task explicitly builds on another open branch.
One session → one worktree → one branch. Never two sessions in the same checkout.

### Pre-flight (run before the first edit or commit, every session)

1. `git worktree list` and `git branch --show-current` — see who is sitting
   where and confirm no other worktree already holds the branch you intend to
   use.
2. Confirm you are **not** in the canonical checkout before feature edits. If
   you are, create/switch to your own worktree (above) first.
3. Inspect `git status`. If the tree is dirty with files you did not create
   (another session's uncommitted work), **STOP** — do not stage, commit, or
   `git add -A` over it. Report it; let the owning session land it.

### Pre-commit HEAD-race guard (every commit)

Parallel sessions sharing a checkout can switch HEAD between your `git add` and
`git commit`, landing your commit on the wrong branch. Even from your own
worktree, immediately before committing:

1. Re-check `git branch --show-current` equals your task branch.
2. `git add` only your explicit paths — never a bare `git add -A`/`git add .`
   when other sessions may be active.
3. After commit, verify `git log -1 --decorate` shows the commit on your branch.
4. If HEAD raced, recover with `git cherry-pick` onto the correct branch and
   clean the wrong branch with `git reset --hard` / `--force-with-lease` only
   after confirming what you are discarding.

### Cleanup

When the branch is merged or abandoned, remove the worktree with
`git worktree remove <path>` (or `cleanup_worktrees.py`). Do not leave stale
worktrees holding branches other sessions may want.

### The interactive fix-lane (small fixes across the day)

The launcher governs big autonomous Workers; this governs the opposite reality:
hand-opened debugging where you fix a little here, a little there. Spreading
those edits across the canonical checkout (or several terminals on shared HEAD)
is the main source of dirty-tree collisions. Give interactive fixes one isolated
home — the **fix-lane** — instead.

```bash
python3 .agents/skills/agent-orchestrator/scripts/fix_lane.py        # ensure + cd hint
python3 .agents/skills/agent-orchestrator/scripts/fix_lane.py --sync # ff onto latest origin/main
```

One lane per day: branch `fix/<YYYY-MM-DD>` off fresh `origin/main`, in a
worktree beside the canonical checkout. Batch small logical commits there; merge
via the fast path. The helper only manages the worktree/branch — it never
pushes, deletes remote refs, or edits code.

**Linear granularity for fixes — issue = unit of mergeable intent, not unit of
edit.** A whole debugging session is ONE Linear issue — the standing umbrella
**ENG-537** (Maintenance / misc interactive fixes); the micro-edits inside it
are commits, not issues. Forcing a Linear issue per 3-line fix is the friction
that makes sessions skip the discipline — don't.

**Smell test — when a "small fix" is actually a task:** if the change touches
more than one ownership area, alters a shared contract / DTO / API schema / query
id / read-model meaning / metric or date-time semantics / PHI / audit behavior,
or needs a migration or env/deploy/secret change, it is **not** a `tiny_fix`.
Stop, reclassify it as `normal` or `contract_change`, give it its own worktree
and (for contracts) cross-runtime review. Cross-cutting debugging stays in ONE
worktree, sequential — never fanned across terminals.

## Task Classes

Every task must be classified before execution.

### `normal`

Use for ordinary feature, bugfix, UI, data, service, agent, analytics, or test
work.

Rules:

- isolated worktree required for Workers;
- PR required;
- focused verification required;
- Integrator review required before merge when shared paths or contracts are
  touched.

### `tiny_fix`

Use only for a very small correction that should not wait for a full wave.

Allowed only when all conditions are true:

- changes are limited to one or two files;
- no shared contract is changed;
- no migration, env, deploy, secret, OAuth/CORS, or Cloud Run file is changed;
- no active Worker owns the same file or path;
- the change does not alter API schemas, DTOs, tool envelopes, query ids,
  read-model meaning, metric definitions, date/time semantics, PHI policy, or
  audit behavior.

Rules:

- focused verification required;
- PR description must state `Tiny fix: no contract change`;
- agents may use the autonomous PR prep path below when all checks pass;
- if any condition fails, reclassify as `normal` or `contract_change`.

## Autonomous PR Prep

After the user asks an agent to "do it" or otherwise clearly authorizes a
bounded implementation task, the agent should not ask the user to confirm
obvious file lists or routine git steps. The agent owns scope detection.

For `tiny_fix` tasks, and for low-risk `normal` tasks that do not touch shared
contracts, the Worker or Orchestrator may automatically:

- create or switch to an isolated task branch or worktree;
- make the scoped change;
- run focused verification;
- stage only files changed for this task;
- commit with an English commit message;
- push the task branch;
- open a draft PR;
- report the branch, commit, PR URL, checks, and any remaining risks.

For `contract_change` tasks, autonomous PR prep is allowed only as a
review artifact after focused verification passes. The draft PR must stay
blocked for Integrator review and required cross-runtime review before it can
be marked ready for integration, ready for merge, or merged. The required
review gate is normally **post-commit / post-draft-PR and pre-integration**,
not a blanket pre-commit gate.

Use stricter **pre-commit review** only when the user explicitly asks for it,
the ownership card requires it, the Orchestrator marks the task high-risk
enough to inspect the local diff before commit, or the Worker cannot separate
its changes safely from unrelated local state. In that stricter mode, run
focused verification, stop with the local diff and verification results, and
wait for the assigned reviewer or Integrator before commit/push.

This is the default path for small UI, copy, link, display, test, or route
wiring fixes when focused verification passes. Do not stop to ask which files
to stage when the answer is derivable from `git diff`, ownership scope, and the
current task.

The agent must preserve unrelated dirty or untracked files. If the main
checkout is dirty, prefer one of these paths:

- use an isolated worktree from `origin/main` and apply only the task patch;
- stage only the task's touched files with explicit paths;
- leave unrelated dirty/untracked files exactly as they were.

Autonomous PR prep must stop and ask for explicit human approval when:

- focused verification fails and the cause is not obvious;
- the task needs `.env*`, secrets, deploy scripts, GitHub Actions deployment,
  Cloud Run, OAuth/CORS, or production/staging config changes;
- the task needs a migration or touches a shipped Alembic revision;
- the task changes a shared contract, durable schema, PHI/privacy/audit policy,
  auth/security behavior, or metric/time-window/read-model semantics;
- unrelated changes are in the same file and cannot be separated safely;
- the agent would need destructive git commands;
- the next action is merge to `main`, release branch integration, or deploy.

Autonomous PR prep does not authorize merging, production deploy, destructive
commands, or including unrelated files. Those always need explicit user
approval.

## Context Rollover Gate

Long-running agent threads must not become the permanent execution context.
When a mission crosses a natural boundary, the agent must stop starting new
substantial work in the current thread and produce a handoff for a fresh
thread or mission run.

Rollover is required after any of these events:

- a major PR is merged;
- a large or multi-layer PR is opened and ready for review;
- the user changes the product direction or mission goal;
- the agent detects context compaction or receives only a summarized prior
  state;
- the thread mixes unrelated missions enough that ownership, branch, or risk is
  no longer easy to audit;
- an explicit token or mission budget is near exhaustion, when such a budget is
  available to the runtime.

Before rollover, the agent must write or report a compact handoff summary with:

- current branch, PR numbers, and relevant commits;
- what is complete;
- verification commands and results;
- unfinished work and do-not-merge conditions;
- open risks, including data correctness, PHI/audit, deployment, and contract
  risks when applicable;
- Linear issues and owners for remaining work;
- the recommended next mission objective and starting branch.

If thread-management tools are available, the agent should create or recommend
a fresh thread for the next mission and include the handoff summary there. If
those tools are unavailable, the agent must ask the user to start a new thread
with the handoff summary. The old thread may continue only for small follow-up
questions, review of the handoff, or explicit merge/deploy approval.

Rollover does not replace required approvals. Merge to `main`, release
integration, production/staging deploy, destructive commands, shared contract
changes, migrations, `.env*`, secrets, and deployment configuration still need
explicit user approval.

### `hotfix`

Use for urgent fixes to failing CI, broken local dev, or production-visible
defects.

Rules:

- may jump ahead of the integration queue;
- must still use a Linear issue, branch, verification, and PR unless the user
  explicitly approves emergency direct action;
- before merge, check active PRs and ownership cards for path overlap;
- after merge, mark affected active Workers as `sync_required` and record the
  reason in runlog/board/decision-log.

### `contract_change`

Use when the change affects a shared interface or meaning, even if the code diff
is small.

Examples:

- API request or response schema;
- Pydantic/Zod DTO;
- tool params or result envelope;
- query id or read-model id;
- aggregate metric definition;
- time-window semantics;
- audit summary shape;
- migration or durable schema;
- deployment/env contract.

Rules:

- no fast-path merge;
- Integrator review required before ready-for-integration or merge;
- cross-runtime review required before ready-for-integration or merge;
- focused verification may be committed and pushed to a draft PR first unless
  pre-commit review was explicitly requested;
- PR descriptions must state the task class, required reviewers, verification
  results, and `Do not merge before Integrator and cross-runtime review`;
- dependent Workers must either wait for the contract PR or explicitly build on
  its branch;
- if two PRs change the same contract, reconcile before either merge.

## Cross-Runtime Review

Large or risky tasks must be reviewed by a different worker runtime before
integration. This is model-agnostic: if Codex implemented the task, prefer a
Claude Code reviewer; if Claude Code implemented it, prefer a Codex reviewer.
If the original runtime is neither Codex nor Claude Code, use any independent
runtime or a human reviewer.

Cross-runtime review is required when any condition is true:

- task class is `contract_change`;
- the change touches more than one product layer, for example backend +
  frontend, agent runtime + tools, or read model + UI;
- the change touches PHI/privacy policy, audit behavior, auth, security,
  deployment, environment contracts, migrations, or durable data shape;
- the change affects aggregate metric meaning, time-window semantics,
  read-model definitions, tool envelopes, API/Zod/Pydantic schemas, or manager
  answer grounding;
- the diff is large enough that a single reviewer is likely to miss integration
  issues;
- the Orchestrator marks risk as `high`.

Cross-runtime review is recommended, but not required, for ordinary `normal`
tasks that touch only one well-owned module and have focused tests.

Cross-runtime review is not required for `tiny_fix` unless the task was
misclassified and actually changes a contract.

The reviewer's job is read-only by default:

- verify changed files match the ownership card;
- check hidden contract or semantics changes;
- check test coverage and failed/missing verification;
- check interaction with active parallel work;
- write a reviewer report before the Integrator marks the task ready for
  integration or merges.

The reviewer must not rewrite the implementation during review. If fixes are
needed, the reviewer reports findings and the Orchestrator either returns the
task to the original Worker or launches a separate fix task with its own
ownership card.

Required cross-runtime review must be visible in the PR and Linear issue. The
Worker or Orchestrator records the required reviewer runtime, review status,
and any do-not-merge condition in the PR body, Linear comment, worker report,
or mission runtime files. A draft PR without that visible review gate is not
ready for integration.

## Migration Merge Ordering (Concurrent Alembic Heads)

Two PRs that each add a migration off the same parent revision are each a single
alembic head in isolation and pass CI alone. Merging both to `main` produces two
heads, and the prod `alembic upgrade head` job then fails ("Multiple head
revisions are present"). Prod is not touched (alembic fails before DDL), but the
deploy stalls until someone adds a merge revision. This has happened more than
once. See `docs/DEPLOYMENT_RULES.md` §11 for the full three-layer model.

The enforced fix is branch protection "require branch up to date before merging"
(strict), which forces the trailing PR to rebase onto the moved `main` and thus
surface both heads in its own CI before merge. **That server-side gate is not
available on the current GitHub plan (private repo on Free).** Until the repo is
on a plan that supports rulesets (GitHub Team), this is an enforced-by-discipline
rule for the Integrator:

- **Before merging any migration-bearing PR, rebase/sync it onto the current
  `main` and re-run CI.** If a second head appears, `make verify-alembic-heads`
  goes red — resolve it on the branch with
  `cd packages/db && alembic merge heads -m 'merge <a>+<b>'` (after confirming
  the two parents are disjoint or encoding the correct order) before merge.
- **Serialize migration-bearing PRs.** Do not merge two open migration PRs
  back-to-back without re-syncing the second onto `main` first.
- The deploy-time failure (Layer 3) remains the backstop; never resolve it by
  auto-merging heads in the deploy pipeline.

When the repo moves to GitHub Team, apply `infra/scripts/setup_main_ruleset.sh`
to make this (and the rest of the merge gate) server-enforced, and this manual
rule becomes redundant.

## Ownership Card

Every Worker prompt must include an ownership card. The Orchestrator writes it
into mission state and the Worker report repeats it with actual touched files.

Minimum shape:

```yaml
task_id: ENG-000
linear_issue_id: ENG-000
linear_issue_url: https://linear.app/...
task_class: normal
worker_runtime: codex | claude-code | other
branch: codex/eng-000-short-title
workspace: isolated_worktree
owned_paths:
  - packages/example/**
shared_paths:
  - packages/tools/analytics_tools.py
forbidden_paths:
  - .env*
  - shipped alembic revisions
integration_mode: pr_only
requires_integrator_review: true
requires_cross_runtime_review: true
reviewer_runtime: claude-code
if_shared_path_needed: stop_and_report
if_main_advances: sync_before_pr
verification:
  - focused command here
```

## Automatic Worker Launches

Automatic worker launch is allowed only after the ownership card exists.

For Codex, prefer the Orchestrator launch profile `--codex-full-auto` or the
equivalent wave field `codex_full_auto: true`. The current installed Codex CLI
does not expose `codex exec --full-auto`; the launcher maps the profile to
Codex's supported non-interactive bypass flag. Use this only with an isolated
worktree or an explicitly approved self-execute scope.

For Claude Code, use `--claude-permission-mode auto` or the equivalent wave
field `claude_permission_mode: auto`.

Auto-launched workers still obey the same gates:

- no direct DB access from agents;
- no `.env*` or shipped Alembic edits;
- no commits, pushes, merges, deploys, or destructive commands unless the user
  explicitly approved that action class;
- shared contracts require Integrator review;
- if `main` advances, affected workers are marked `sync_required`.

## Ownership Rules

- Workers may edit only declared `owned_paths`.
- Workers may inspect broader repo context when needed.
- Shared paths may be edited only when they are declared before launch or the
  Worker stops and reports `Needs decision: shared path required`.
- Forbidden paths must not be edited without explicit human approval.
- A Worker that discovers its task needs a new shared contract must stop and
  report the proposed contract change rather than silently expanding scope.
- Worker reports must list changed files and whether any shared paths were
  touched.

## Shared Contracts

Shared contracts are files, schemas, or definitions that more than one task may
depend on. Contract changes require explicit integration sequencing.

Common shared contracts include:

- API route contracts and schemas;
- `packages/tools/**` tool envelopes and analytics query definitions;
- `packages/agent_runtime/**` audit, planning, time-window, and answer
  eligibility contracts;
- web schema files under `apps/web/lib/api/schemas/**`;
- read-model aggregate semantics;
- migrations and durable database shape;
- deployment/env/GitHub Actions contracts.

When in doubt, mark the file as shared and require Integrator review.

## Merge And Integration Queue

Merges happen one PR at a time.

Required order:

1. Verify the PR against its task class.
2. Merge one PR.
3. Record the merge SHA and affected paths.
4. Mark affected active Workers as `sync_required`.
5. Update other PR branches from `origin/main` when they touch overlapping or
   shared paths.
6. Re-run focused verification on updated branches.
7. Merge the next PR only after the updated verification is clean.

No Worker should merge a parallel wave "as a batch". The Integrator owns the
merge order and must prefer contract PRs before dependent implementation PRs.

## Main Advanced / Sync Required

When `main` advances, active Workers must decide whether they are affected.

Sync is required when:

- their PR touches the same file or path;
- their PR touches a shared contract;
- their task depends on a contract that changed;
- a hotfix merged ahead of them;
- CI indicates a conflict or outdated base.

Sync action:

```text
git fetch origin
merge or rebase origin/main according to the branch policy
resolve conflicts without reverting unrelated work
run focused verification
update worker report / runlog
```

## Pre-Merge Checks

Minimum checks before any PR merge:

```bash
git status
git ls-files -u
rg "<<<<<<<|=======|>>>>>>>" apps packages tests .agents
git diff --check
```

Then run task-specific focused checks. For larger product changes, use the full
repo verify loop:

```bash
make lint
mypy .
make test
cd packages/db && alembic check
```

## Role Responsibilities

### Strategy / Architecture

Strategy proposes work but does not execute. Handoffs must include
parallel-safety fields:

```yaml
parallel_safety:
  task_class: normal
  expected_owned_paths:
    - packages/example/**
  expected_shared_contracts:
    - packages/tools/analytics_tools.py
  likely_conflicts:
    - "Example schema may overlap with dashboard work."
  recommended_merge_order:
    - contract PR first
    - implementation PR second
```

### Orchestrator

The Orchestrator enforces this policy:

- create or link Linear issues before execution;
- classify each task;
- create ownership cards;
- launch Workers in isolated worktrees unless self-execute is explicitly
  allowed;
- maintain integration queue state;
- record `sync_required`, `Ownership violation:`, `Contract drift:`, and
  `Needs decision:` events in mission runtime files;
- assign Integrator/Reviewer roles when a task touches shared paths.

### Worker

Workers execute only the assigned ownership card:

- stay within owned paths;
- stop and report when shared or forbidden paths are needed;
- update mission-visible state;
- write a report with changed files, tests, risks, and shared path status;
- do not merge parallel work directly unless explicitly assigned as Integrator.

### Production Reviewer

Reviewers audit policy compliance:

- ownership card exists and matches changed files;
- task class is appropriate;
- shared path edits were declared;
- hidden contract changes are identified;
- active PRs were synced after `main` advanced;
- tests match blast radius;
- tiny fixes are truly tiny;
- hotfixes marked affected Workers as `sync_required`.
- context rollover was performed or explicitly deferred after merge, large PR,
  mission direction change, compaction, or budget exhaustion.

### Integrator

Integrator owns merge order:

- verify PR readiness;
- reconcile shared contract changes;
- merge one PR at a time;
- force affected branches to sync with `main`;
- run or confirm post-merge CI/deploy/smoke as required;
- update Linear and mission state with final merge/deploy evidence.
- trigger the Context Rollover Gate after a major merge or large PR boundary
  instead of starting a new substantial mission in the same thread.
