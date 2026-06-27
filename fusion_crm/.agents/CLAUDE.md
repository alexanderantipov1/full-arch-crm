# CLAUDE.md — Internal Agent Development Layer

This directory contains local development orchestration assets. It is not part
of the Fusion CRM product runtime.

## Scope

- `.agents/dashboard/` is a localhost-only development cockpit.
- `.agents/orchestration/` contains mission decision artifacts (goal,
  acceptance, contract, ownership, decision-log, lessons, incidents,
  reports). Live runtime telemetry (runtime.json, runlog.md, board.md,
  linear-sync.md, prompts/, logs/) lives outside the repo under
  `FUSION_AGENT_RUNTIME_HOME` (default `~/.fusion-agent-orchestrator/
  <repo-hash>/<mission-id>/`). See ENG-224 / M-1.
- `.agents/strategy/` contains optional strategic planning artifacts.
- `.agents/skills/` contains local agent skills and helpers, including
  Orchestrator, Strategy, and Production Reviewer roles.

## Language

- Repository files in this directory must be written in English.
- User-facing runtime localization may be added later through external config
  or generated local state, but source files stay English.

## Safety Rules

- The dashboard is read-only by default.
- Do not add write actions, process kill controls, git mutation controls,
  Linear writes, PR creation, or deployment actions without explicit approval.
- Do not read or write `.env*` files.
- Do not expose this dashboard beyond localhost.
- Do not make `.agents/` a dependency of product code.

## Architecture

The dashboard must treat existing files and git state as the source of truth.
It should tolerate missing orchestration, strategy, mission, worktree, and
provider files. Empty state is preferable to inferred state.

## Live State Protocol

All Orchestrator and Worker sessions must make their progress visible through
mission runtime files. A message that only exists in a terminal, chat thread, or
agent transcript is not dashboard-visible state.

Parallel Codex, Claude Code, and future Worker execution is governed by the
canonical policy in:

```text
.agents/orchestration/PARALLEL_WORK_POLICY.md
```

That policy is model-agnostic: agents do not own product directions. Each
Worker owns only the declared task scope, branch, workspace, paths, shared
contracts, and verification plan assigned by the Orchestrator.

Before execution work starts, the Orchestrator must create or select a named
mission folder and reference it explicitly:

```text
.agents/orchestration/<mission>/
```

There is no shared default pointer — several missions run in parallel, so each
session names its own mission path. The dashboard is started with that path.

Every active execution session must update these files:

- `runtime.json` for machine-readable active session state;
- `runlog.md` for chronological human-readable progress;
- `board.md` for task status;
- `linear-sync.md` for the Linear issue mapping that authorizes execution;
- `reports/<task-id>-worker-report.md` when a worker finishes or pauses;
- `incidents.md` when a failure, retry loop, tool error, or unexpected behavior
  occurs;
- `decision-log.md` when a human or Orchestrator decision changes direction.

Agent handoff visibility:

- every role transition must be recorded as a `Handoff:` event;
- this includes Strategy to Orchestrator, Orchestrator to Worker, Worker to
  Verifier, Verifier to Integrator, and Integrator back to Orchestrator;
- write handoffs into `runtime.json` under `handoffs`;
- append the same transition to `runlog.md` with the `Handoff:` marker;
- include source agent, target agent, task id, Linear issue, reason, and
  timestamp.

Linear execution gate:

- every execution task must have a Linear issue before it is assigned to a
  Worker;
- Strategy and Architecture handoffs are not execution tasks until the
  Orchestrator accepts them and creates or links Linear issues;
- `runtime.json`, `board.md`, worker prompts, and worker reports must include
  the Linear issue id and URL;
- if Linear is unavailable, the Orchestrator must write `Needs approval:` with
  the reason and may only proceed after explicit human approval;
- dashboard-visible task state without a Linear issue is a protocol violation.

Minimum live update rules:

- write a `runtime.json` entry before starting meaningful work;
- append a `runlog.md` line when starting, changing phase, blocking, retrying,
  finishing, or handing off;
- refresh the session heartbeat at least every few minutes during long work;
- write blockers and approvals with explicit markers: `Blocked:`,
  `Needs decision:`, `Needs approval:`, `Verification failed:`,
  `Contract drift:`, `Ownership violation:`, `Missing Linear:`, or
  `Handoff:`;
- write `Missing Linear:` when an active execution session has no Linear issue;
- do not claim a task is done unless the report lists changed files, tests run,
  verification status, risks, and remaining questions.

Dashboard rule:

```text
If it is not in mission runtime files, strategy files, or git, the dashboard
cannot see it.
```

## Context Rollover Gate

After a major merge, large PR boundary, mission direction change, detected
context compaction, or budget exhaustion, do not start new substantial work in
the same thread. Write a compact handoff summary with branch, PRs, commits,
verification, unfinished work, risks, Linear owners, and the recommended next
mission. Then create or recommend a fresh thread or mission run for the next
substantial task.

Small follow-up questions, handoff review, and explicit merge/deploy approval
may stay in the old thread. Required approvals from the parallel work policy
still apply.

## Strategy / Architecture Protocol

Strategy and Architecture agents may create candidate missions and handoff
requests for the Orchestrator. They must not launch workers, assign execution
tasks directly, or modify product code.

Strategy and Architecture agents are responsible for:

- discussing business logic and future architecture;
- clarifying assumptions and risks;
- creating roadmap themes and candidate missions;
- preparing structured handoff for the Orchestrator;
- marking whether a candidate mission is ready for execution.

Handoff rule:

```text
Strategy proposes, Orchestrator disposes.
```

When a topic is ready for execution, record it in:

- `.agents/strategy/CANDIDATE_MISSIONS.md`
- `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md`

Each handoff must include:

- business goal;
- why now;
- expected outcome;
- assumptions;
- architecture constraints;
- suggested decomposition;
- risks;
- human decisions needed;
- readiness status: `draft`, `needs decision`, or `ready for orchestrator`.

The Orchestrator is responsible for:

- validating scope;
- creating the mission folder;
- creating or syncing Linear issues before assigning Workers;
- defining ownership;
- assigning workers;
- assigning cross-runtime review for large, high-risk, or contract-changing
  tasks before ready-for-integration or merge. Focused verification may be
  committed and pushed to a draft PR first unless the user, ownership card, or
  Orchestrator explicitly requires pre-commit review;
- allowing autonomous branch, commit, push, and draft PR prep for `tiny_fix`
  and low-risk `normal` tasks after focused verification passes;
- running verification;
- integration and handoff.

## Production Reviewer Protocol

Production Reviewer agents are independent, read-only mission auditors. They
inspect actual state across git, mission files, runtime telemetry, Linear,
GitHub PRs, CI, and worker reports, then report where the mission stands and
what remains.

Production Reviewer agents are responsible for:

- summarizing observable completion state;
- finding unfinished work, missing reports, stale handoffs, and verification
  gaps;
- checking coordination drift between Codex, Claude Code, Linear, PRs,
  branches, and mission files;
- surfacing production risks, including architecture invariant drift,
  missing tests, migration safety concerns, deployment/env risks, and PHI or
  audit issues;
- recommending ordered next actions.

Production Reviewer agents must not:

- redesign the product unless explicitly asked;
- launch workers or assign execution tasks;
- modify product code or mission state by default;
- commit, push, deploy, or run destructive commands;
- infer live progress from terminal-only or chat-only claims.

Reviewer output should use this order:

1. State
2. Open Work
3. Risks
4. Coordination Gaps
5. Next Actions

Expected optional mission files:

- `goal.md`
- `acceptance.md`
- `verification.md`
- `contract.md`
- `ownership.yaml`
- `board.md`
- `linear-sync.md`
- `runtime.json`
- `runlog.md`
- `reports/`
- `incidents.md`
- `lessons.md`
- `decision-log.md`

Expected optional strategy areas:

- `inbox/`
- `discussions/`
- `candidate-missions/`
- `CANDIDATE_MISSIONS.md`
- `HANDOFF_TO_ORCHESTRATOR.md`
- `architecture-radar.md`
- `roadmap.md`
- `business-assumptions.md`
- `strategic-decisions.md`

## Verification

For dashboard-only changes, prefer focused checks:

- `python3 -m py_compile .agents/dashboard/server.py`
- API smoke test against `/api/snapshot`
- static file load through the local server

For orchestrator launcher / skill changes, run the skill-local test suite:

```bash
.venv/bin/python -m pytest .agents/skills/agent-orchestrator/tests/ -v
```

The suite covers `launch_worker.py`, `run_wave.py`, and `status_wave.py` with
unit, integration, SIGHUP-regression, runtime.json schema, and env-gated
contract-drift tests. See
`.agents/skills/agent-orchestrator/tests/README.md` for details.

The full project verification loop remains required when changes touch product
code, architecture invariants, database behavior, deployment, or shared
packages.
