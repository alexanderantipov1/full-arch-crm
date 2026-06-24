# CLAUDE.md — Agent Orchestration Runtime

This directory contains local mission runtime state for parallel agent work.
It is not part of the Fusion CRM product runtime.

## Language

- Repository files in this directory must be written in English.
- Runtime text that should be parsed by the dashboard should use stable English
  markers and field names.

## Live State Is Required

All Orchestrator and Worker sessions must write progress here. A terminal-only
message is not shared state and will not be visible in the dashboard.

Each mission lives in its own named folder:

```text
.agents/orchestration/<mission>/
```

There is no shared `current/` pointer — multiple missions run in parallel, so
the dashboard must always be started with the explicit mission path.

## Required Mission Files

Mission files split between two locations after M-1 (ENG-224):

**Spec dir** (`.agents/orchestration/<mission>/` in repo) — durable decision
artifacts:

```text
goal.md
acceptance.md
verification.md
contract.md
ownership.yaml
incidents.md
lessons.md
decision-log.md
reports/
```

**Runtime dir** (`<FUSION_AGENT_RUNTIME_HOME>/<mission>/` or default
`~/.fusion-agent-orchestrator/<repo-hash>/<mission>/`) — live telemetry:

```text
runtime.json
runlog.md
board.md
linear-sync.md
prompts/
logs/
worktrees/   (M-2 placeholder)
```

The launcher (`launch_worker.py`) writes runtime files via `paths.py`
helpers — never hand-edit them in repo. `.gitignore` blocks accidental
new writes to the runtime paths inside repo; archived/ paths stay
re-included so historical snapshots remain committed.

## Workspace Isolation (M-2 / ENG-225)

Parallel work across Codex, Claude Code, and future Worker runtimes is governed
by `.agents/orchestration/PARALLEL_WORK_POLICY.md`. Read that file before
opening a wave, launching a Worker, approving self-execute, integrating PRs, or
reviewing coordination health.

Ownership is task-scoped and model-agnostic. Do not assign permanent product
directions to a model. Each Worker receives one Linear issue, branch,
workspace, ownership card, owned paths, shared paths, forbidden paths,
verification plan, and integration mode.

Large, high-risk, and contract-changing tasks require read-only cross-runtime
review before ready-for-integration or merge. Focused verification may be
committed and pushed to a draft PR first unless the user, ownership card, or
Orchestrator explicitly requires pre-commit review. If Codex implements the
task, prefer a Claude Code reviewer; if Claude Code implements it, prefer a
Codex reviewer. Human review may replace cross-runtime review only when
explicitly recorded.

`tiny_fix` and low-risk `normal` tasks use autonomous PR prep by default:
after focused verification passes, the agent may stage only its task files,
commit, push the task branch, and open a draft PR without asking the user to
confirm obvious file lists. Merge to `main`, release integration, deploy,
destructive commands, secrets/env/deploy config, migrations, and shared
contract changes still require explicit user approval.

The launcher's `--workspace` flag controls where the worker runs:

- `--workspace worktree` (default for `--role worker`) — provisions an
  isolated `git worktree` under
  `<runtime_root>/<mission_id>/worktrees/<task_id>/` on a fresh branch
  `<linear-id>-<task-id>` (suffix `-<sid>` on branch collisions). The
  canonical checkout is never touched. Pre-flight rejects launch when
  the `--branch-base` working tree is dirty.
- `--workspace self` (default for `--role verifier` /
  `--role integrator`) — runs in the current checkout. Requires three
  explicit acknowledgements:
  1. `--allow-self-execute`
  2. Prompt size ≤ 5000 chars
  3. `--scope tiny|bugfix|docs` (not `none`)

  On a successful self-execute, the launcher appends a `Scope: <value>`
  line to runlog and a structured entry to `decision-log.md` so the
  blast-radius decision is auditable.

Worktree pruning lives in
`.agents/skills/agent-orchestrator/scripts/cleanup_worktrees.py`. It
defaults to dry-run; `--apply` removes eligible worktrees (mission
archived AND branch merged into main) with per-item `y/N` confirmation.
`--force` permits removal of unmerged-branch worktrees with a second
confirmation, gated behind `--apply`.

Self-execute is only for policy-approved `tiny_fix`, `hotfix`, or docs scopes.
If a small task touches a shared contract, reclassify it as `contract_change`
and use an isolated branch plus Integrator review.

## Process Supervision Control Plane (M-3 / ENG-226)

`worker_ctl.py` is the single CLI for live session control:

- `--list` — table of every session in the current mission with
  derived `runtime_status` (alive / exited / missing via
  `os.kill(pid, 0)`) and `agent_activity` heuristic.
- `--status <sid>` — compact block + log tail.
- `--kill <sid>` — SIGTERM with 10s grace, then SIGKILL; marks the
  session `cancelled` in `runtime.json` and appends a runlog line.
  `--grace <seconds>` overrides the default. No `--kill-all` by design.
- `--attach <sid>` — tail the worker log to stdout. Read-only.

`start_control_plane.py` is a convenience wrapper: runs `status_wave`
once, starts the dashboard child, opens the browser (`--no-open`
opt-out), blocks until Ctrl-C, then cleanly shuts the dashboard.

`runtime_status` and `agent_activity` are DERIVED at render time
(status_wave + dashboard snapshot + worker_ctl --list/--status). They
are not persisted by the launcher. The activity heuristic is best-effort
— surfaces label it as such; trust the worker's own `Needs decision:`
or `Blocked:` runlog markers over the heuristic for critical decisions.

Missing files are valid empty state before a mission starts. Once work
starts, `runtime.json`, `runlog.md`, and `board.md` are required (in
the runtime dir).

## Mission Open Order (live-state first)

When opening a new mission folder, write the live-state files BEFORE any
decision artifact. The dashboard's "Active work" widget reads only
`runtime.json.sessions[]`; until that file exists with at least one
session, the dashboard cannot show you any orchestration in flight.

Required order:

1. `runtime.json` with the strategy → orchestrator handoff and at least
   one orchestrator session in `running` state.
2. `board.md` with rows for MISSION-OPEN and the planned tasks.
3. `linear-sync.md` with the task ↔ Linear-issue mapping.
4. `runlog.md` with the opening line and the strategy → orchestrator
   handoff marker.
5. THEN decision artifacts (`goal.md`, `acceptance.md`,
   `verification.md`, `contract.md`, `ownership.yaml`).
6. THEN the worker prompt under `prompts/`.
7. Reports, incidents, decision-log, and lessons populate as work
   happens.

"Meaningful work" includes writing decision artifacts. If you started
writing `goal.md` before `runtime.json`, the dashboard is blind to you
and the human partner cannot see that orchestration began. Batch-writing
all opening files in a single tool call is acceptable; staggered writes
that start anywhere other than `runtime.json` are a protocol violation.

## Context Rollover Gate

Long-running threads must roll over at mission boundaries. After a major PR is
merged, a large or multi-layer PR is opened for review, the user changes the
mission direction, context compaction is detected, or an explicit token/mission
budget is near exhaustion, stop starting new substantial work in the current
thread.

Before the next substantial task starts, write or report a compact handoff with:

- branch, PRs, and relevant commits;
- completed work;
- verification commands and results;
- unfinished work and do-not-merge conditions;
- open risks and data/contract/privacy concerns;
- Linear issues and owners for remaining work;
- recommended next mission objective and starting branch.

If thread-management tools are available, create or recommend a fresh thread
and carry the handoff summary into it. If they are unavailable, ask the user to
start a fresh thread with the handoff summary. The old thread may continue only
for small follow-up questions, handoff review, or explicit approval steps.

## Linear Gate

Every execution task must have a Linear issue before it is assigned to a
Worker. Candidate missions and Strategy handoffs are proposals only; they become
execution work only after the Orchestrator accepts them and creates or links the
corresponding Linear issues.

Required Linear fields:

- `linear_issue_id`
- `linear_issue_url`
- `linear_status`
- `linear_title`

These fields must appear in:

- `runtime.json`
- `board.md`
- `linear-sync.md`
- worker prompts
- worker reports

If Linear is unavailable, the Orchestrator must write `Needs approval:` with the
reason and may only proceed after explicit human approval. Active execution
without a Linear issue must be marked as `Missing Linear:`.

## Handoff Contract

Every role transition must be recorded as a visible handoff. A handoff is
required when work moves from:

- Strategy or Architecture to Orchestrator;
- Orchestrator to Worker;
- Worker to Verifier;
- Verifier to Integrator;
- Integrator back to Orchestrator.

Each handoff must be written to `runtime.json` under `handoffs` and appended to
`runlog.md` with the `Handoff:` marker.

Minimum handoff shape:

```json
{
  "id": "handoff-001",
  "created_at": "2026-05-19T23:00:00Z",
  "task_id": "TASK-001",
  "linear_issue_id": "LIN-123",
  "from_role": "strategy",
  "from_agent": "codex",
  "to_role": "orchestrator",
  "to_agent": "codex",
  "reason": "Candidate mission accepted for execution.",
  "status": "accepted"
}
```

Allowed handoff status values:

- `proposed`
- `accepted`
- `rejected`
- `in-progress`
- `completed`

## Runtime Contract

`runtime.json` is the machine-readable active session snapshot. It should be
updated before meaningful work begins and refreshed during long work.

Minimum shape:

```json
{
  "mission_id": "current",
  "updated_at": "2026-05-19T23:00:00Z",
  "handoffs": [
    {
      "id": "handoff-001",
      "created_at": "2026-05-19T23:00:00Z",
      "task_id": "TASK-001",
      "linear_issue_id": "LIN-123",
      "from_role": "strategy",
      "from_agent": "codex",
      "to_role": "orchestrator",
      "to_agent": "codex",
      "reason": "Candidate mission accepted for execution.",
      "status": "accepted"
    }
  ],
  "sessions": [
    {
      "id": "worker-or-orchestrator-session-id",
      "role": "orchestrator",
      "agent": "codex",
      "task_id": "TASK-001",
      "linear_issue_id": "LIN-123",
      "linear_issue_url": "https://linear.app/example/issue/LIN-123/example-task",
      "linear_status": "In Progress",
      "linear_title": "Example task",
      "status": "running",
      "phase": "inspecting code paths",
      "worktree": ".",
      "branch": "current-branch",
      "last_activity": "2026-05-19T23:00:00Z",
      "needs_human": false,
      "risk": "low",
      "current_note": "Inspecting CareStack and Salesforce ingest paths."
    }
  ]
}
```

Allowed status values:

- `planned`
- `assigned`
- `running`
- `waiting`
- `blocked`
- `report-ready`
- `verification-failed`
- `ready-for-integration`
- `merged`
- `cancelled`

## Runlog Contract

`runlog.md` is the chronological human-readable event stream. Append a line
when a session starts, changes phase, blocks, retries, finishes, or hands off.

Preferred format:

```text
- 2026-05-19T23:00:00Z | orchestrator | TASK-001 | running | Inspecting apps/api/routers/carestack.py and packages/ingest/sf_lead_service.py.
```

Use explicit dashboard markers when human attention is needed:

```text
- 2026-05-19T23:05:00Z | codex | TASK-001 | blocked | Blocked: CareStack persistence owner is unclear.
- 2026-05-19T23:08:00Z | verifier | TASK-001 | failed | Verification failed: acceptance item 2 is not satisfied.
- 2026-05-19T23:10:00Z | orchestrator | TASK-001 | blocked | Missing Linear: active execution session has no linked Linear issue.
- 2026-05-19T23:12:00Z | strategy | TASK-001 | handoff | Handoff: strategy/codex -> orchestrator/codex for LIN-123. Candidate mission accepted.
```

## Board Contract

`board.md` tracks current task state.

Preferred columns:

```text
| Task | Linear | Owner | Agent | Status | Worktree | Branch | Report | Needs human | Updated |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
```

## Linear Sync Contract

`linear-sync.md` records the mapping between mission tasks and Linear issues.

Preferred columns:

```text
| Task | Linear issue | Linear URL | Linear status | Execution status | Owner | Updated |
| --- | --- | --- | --- | --- | --- | --- |
```

## Worker Report Contract

Workers must write a report when they finish, pause, or block:

```text
reports/<task-id>-worker-report.md
```

The report must include:

- task id and title;
- Linear issue id and URL;
- role and agent;
- branch and worktree;
- allowed scope;
- touched files;
- what changed;
- tests run and results;
- verification status;
- risks;
- blockers or questions;
- suggested next task;
- do-not-merge conditions.

## Incident And Decision Markers

Write `incidents.md` for tool failures, repeated errors, retry loops, missing
files, missing permissions, and behavior that should train future runs.

Write `decision-log.md` for direction-changing decisions and their rationale.

Use these exact markers so the dashboard can route attention:

- `Blocked:`
- `Needs decision:`
- `Needs approval:`
- `Verification failed:`
- `Contract drift:`
- `Ownership violation:`
- `Missing Linear:`
- `Handoff:`
