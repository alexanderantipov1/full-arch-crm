# AGENTS.md — Agent Orchestration Runtime

Follow the root `CLAUDE.md` and `.agents/CLAUDE.md` first. This directory adds
runtime visibility rules for mission execution.

Non-negotiable rules:

- Keep repository files in English.
- Do not write product secrets or `.env*` content into mission files.
- Do not record PHI in mission files, runlogs, reports, incidents, or decisions.
- Do not claim live progress unless it is written to mission runtime files.
- Reference each mission by its own named path
  (`.agents/orchestration/<mission>/`); there is no shared default pointer,
  since several missions run in parallel.
- Follow `.agents/orchestration/PARALLEL_WORK_POLICY.md` for all parallel
  execution. The policy applies equally to Codex, Claude Code, and future
  Worker runtimes. Task ownership is declared per task, not per model or
  product direction.
- Follow the Context Rollover Gate from the same policy. After a major merge,
  large PR boundary, mission direction change, context compaction, or budget
  exhaustion, write a handoff summary and use a fresh thread or mission run for
  the next substantial task.

Every active Orchestrator or Worker session must:

- create or select the active mission folder before execution work starts;
- create or link the Linear issue before assigning execution work to a Worker;
- classify the task as `normal`, `tiny_fix`, `hotfix`, or `contract_change`;
- record the ownership card with branch, workspace, owned paths, shared paths,
  forbidden paths, verification plan, and integration mode;
- update `runtime.json` **first** when opening a mission — before any
  decision artifact (`goal.md`, `acceptance.md`, etc.). The dashboard's
  "Active work" widget reads only `runtime.json.sessions[]`; without
  that file it cannot see the session even though planning is in flight.
  Batch-write opening files in a single tool call when possible;
  staggered writes that start with anything other than `runtime.json`
  are a protocol violation. See "Mission Open Order" in
  `.agents/orchestration/CLAUDE.md`;
- append progress to `runlog.md` on start, phase change, retry, block, finish,
  and handoff;
- record every role transition as a handoff in `runtime.json` and `runlog.md`;
- refresh heartbeat fields in `runtime.json` during long work;
- update `linear-sync.md` with the task-to-Linear mapping;
- update `board.md` when task status changes;
- write a worker report under `reports/` when finishing, pausing, or blocking;
- write failures and repeated mistakes to `incidents.md`;
- write direction-changing decisions to `decision-log.md`.

Parallel merge safety:

- Workers must stay inside declared owned paths;
- shared paths require prior declaration or a `Needs decision:` stop;
- forbidden paths require explicit human approval;
- `tiny_fix` and low-risk `normal` tasks may use autonomous PR prep: isolated
  branch/worktree, focused verification, stage only task files, commit, push,
  and draft PR without asking the user to confirm obvious file lists;
- shared contract changes require Integrator review;
- large, high-risk, or contract-changing tasks require read-only
  cross-runtime review before ready-for-integration or merge. Focused
  verification may be committed and pushed to a draft PR first unless the user,
  ownership card, or Orchestrator explicitly requires pre-commit review;
- merges happen one PR at a time;
- merge to `main`, release integration, production/staging deploy, destructive
  commands, `.env*`, secrets, deploy config, migrations, and shared contract
  changes still require explicit user approval;
- when `main` advances, affected active Workers must sync before PR or merge.
- after merge, large PR, mission direction change, context compaction, or
  budget exhaustion, the next substantial task must pass through Context
  Rollover Gate instead of continuing invisibly in the old thread.

Linear gate:

- Strategy and Architecture handoffs are proposals only;
- execution starts only after the Orchestrator creates or links Linear issues;
- `runtime.json`, `board.md`, worker prompts, and worker reports must include
  Linear issue id and URL;
- if Linear is unavailable, write `Needs approval:` and wait for explicit human
  approval before proceeding;
- active execution without Linear must be marked as `Missing Linear:`.

Handoff visibility:

- Strategy or Architecture to Orchestrator transitions must be recorded;
- Orchestrator to Worker assignments must be recorded;
- Worker to Verifier, Verifier to Integrator, and Integrator to Orchestrator
  transitions must be recorded;
- every handoff must include source agent, target agent, task id, Linear issue,
  reason, status, and timestamp.

Use exact dashboard markers for human attention:

- `Blocked:`
- `Needs decision:`
- `Needs approval:`
- `Verification failed:`
- `Contract drift:`
- `Ownership violation:`
- `Missing Linear:`
- `Handoff:`

Dashboard visibility rule:

```text
If it is not in mission runtime files, strategy files, or git, the dashboard
cannot see it.
```
