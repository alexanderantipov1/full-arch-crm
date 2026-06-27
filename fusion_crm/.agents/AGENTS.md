# AGENTS.md — Internal Agent Development Layer

Follow the root `CLAUDE.md` and `AGENTS.md` first. This directory adds local
rules for development orchestration assets.

Non-negotiable rules:

- Keep repository files in English.
- Keep the dashboard read-only unless the user explicitly approves a write
  action scope.
- Strategy and Architecture agents may create candidate missions and handoff
  requests, but must not launch workers, assign execution tasks directly, or
  modify product code.
- Production Reviewer agents are independent read-only mission auditors. They
  inspect git, mission files, runtime telemetry, Linear, PRs, CI, and worker
  reports to report state, unfinished work, risks, coordination gaps, and next
  actions. They must not launch workers, assign tasks, edit code, or mutate
  mission state unless explicitly asked.
- Strategy proposes, Orchestrator disposes.
- Treat missing mission, strategy, and runtime files as valid empty state.
- Do not infer live agents, blockers, decisions, or verification results when
  no source file reports them.
- Do not connect this layer to production CRM UI or backend runtime.
- Do not expose the local dashboard outside `127.0.0.1`.
- Make execution work dashboard-visible by writing live state to mission runtime
  files. Terminal-only or chat-only progress does not count as shared state.
- Follow `.agents/orchestration/PARALLEL_WORK_POLICY.md` for parallel Codex,
  Claude Code, and future Worker execution. Task ownership is assigned per
  Linear issue and ownership card, never by model name or product direction.
- Follow the Context Rollover Gate in
  `.agents/orchestration/PARALLEL_WORK_POLICY.md`: after a major merge, large
  PR boundary, mission direction change, detected context compaction, or budget
  exhaustion, write a handoff summary and move the next substantial mission to
  a fresh thread or mission run.

Live state requirements for every Orchestrator and Worker session:

- create or select the active mission folder before execution work starts,
  normally `.agents/orchestration/current/`;
- update `runtime.json` before meaningful work begins and while long work is
  active;
- append progress to `runlog.md` when starting, changing phase, blocking,
  retrying, finishing, or handing off;
- record every role transition as a `Handoff:` event in `runtime.json` and
  `runlog.md`;
- record the Linear issue mapping in `linear-sync.md`;
- update `board.md` when task status changes;
- write `reports/<task-id>-worker-report.md` when a worker finishes or pauses;
- write tool failures, retry loops, and unexpected behavior to `incidents.md`;
- write direction-changing decisions to `decision-log.md`;
- use explicit dashboard markers for human attention: `Blocked:`,
  `Needs decision:`, `Needs approval:`, `Verification failed:`,
  `Contract drift:`, `Ownership violation:`, `Missing Linear:`, and
  `Handoff:`.

Handoff visibility:

- Strategy to Orchestrator, Orchestrator to Worker, Worker to Verifier,
  Verifier to Integrator, and Integrator to Orchestrator transitions must be
  visible in the dashboard;
- each handoff must include source agent, target agent, task id, Linear issue,
  reason, and timestamp;
- a terminal-only role switch is not shared state.

Linear execution gate:

- every execution task must have a Linear issue before a Worker receives it;
- Strategy and Architecture handoffs are proposals, not executable work;
- only the Orchestrator may accept a handoff into execution and create or link
  Linear issues;
- `runtime.json`, `board.md`, prompts, and reports must include Linear issue id
  and URL;
- if Linear is unavailable, the Orchestrator must write `Needs approval:` and
  wait for explicit human approval before proceeding;
- active execution without Linear is a protocol violation.

When a Strategy or Architecture topic is ready for execution, record it in:

- `.agents/strategy/CANDIDATE_MISSIONS.md`
- `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md`

Each handoff must include business goal, why now, expected outcome,
assumptions, architecture constraints, suggested decomposition, risks, human
decisions needed, and readiness status.

Only the Orchestrator validates execution scope, creates mission folders,
creates or syncs Linear issues, defines ownership, assigns workers, runs
verification, and integrates worker output.

Parallel work gate:

- every Worker task must have a task class, branch, workspace, ownership card,
  owned paths, shared paths, forbidden paths, verification plan, and integration
  mode;
- `tiny_fix` and `hotfix` fast paths are allowed only under
  `.agents/orchestration/PARALLEL_WORK_POLICY.md`;
- for `tiny_fix` and low-risk `normal` tasks, agents may autonomously create
  an isolated branch, stage only their own task files, commit, push, and open a
  draft PR after focused verification passes;
- shared contract changes require Integrator review and one-at-a-time merge
  sequencing;
- large, high-risk, or contract-changing tasks require cross-runtime review
  before ready-for-integration or merge. Focused verification may be committed
  and pushed to a draft PR first unless the user, ownership card, or
  Orchestrator explicitly requires pre-commit review;
- merge to `main`, production/staging deploy, destructive commands, secrets,
  `.env*`, deploy config, migrations, and shared contract changes still require
  explicit user approval;
- when `main` advances, affected active Workers must sync before PR or merge.
- after merge, large PR, mission direction change, context compaction, or
  budget exhaustion, do not start new substantial work until the Context
  Rollover Gate handoff is written or explicitly deferred.

When adding a new sub-area under `.agents/`, update both this file and
`CLAUDE.md` if the area needs persistent rules.
