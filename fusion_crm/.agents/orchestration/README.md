# Agent Orchestration Runtime

Optional mission runtime folders live here.

Expected mission shape:

```text
.agents/orchestration/<mission>/
  goal.md
  acceptance.md
  verification.md
  contract.md
  ownership.yaml
  board.md
  linear-sync.md
  runtime.json
  runlog.md
  reports/
  incidents.md
  lessons.md
  decision-log.md
```

Mission files are the source of truth for the local dashboard. Missing files
are valid empty state.

## Parallel Work Policy

Parallel Codex, Claude Code, and future Worker execution is governed by:

```text
.agents/orchestration/PARALLEL_WORK_POLICY.md
```

The policy is model-agnostic. Assign ownership by task, Linear issue, branch,
workspace, owned paths, shared paths, forbidden paths, verification plan, and
integration mode. Do not permanently bind a model to a product direction.
Large, high-risk, and contract-changing tasks require read-only cross-runtime
review before integration unless a human reviewer exception is recorded.

## Live Visibility Contract

Orchestrator and Worker sessions must write progress into mission runtime files.
Terminal-only or chat-only progress is not visible to the dashboard.

Before execution starts, create or select a named mission folder and reference
it explicitly:

```text
.agents/orchestration/<mission>/
```

There is no shared default pointer — multiple missions run in parallel, so each
session names its own mission path.

Minimum files once work starts:

- `runtime.json` — machine-readable active session state and heartbeat.
- `runlog.md` — chronological progress stream.
- `board.md` — task status table.
- `linear-sync.md` — mapping between mission tasks and Linear issues.
- `reports/<task-id>-worker-report.md` — worker output and evidence.
- `incidents.md` — failures, retries, missing context, and lessons to learn.
- `decision-log.md` — direction-changing decisions.

## Handoff Visibility

Every transition from one role or agent to another must be visible in the
dashboard. Record it in `runtime.json` under `handoffs` and append it to
`runlog.md` with the `Handoff:` marker.

Examples:

- Strategy to Orchestrator;
- Orchestrator to Worker;
- Worker to Verifier;
- Verifier to Integrator;
- Integrator to Orchestrator.

Each handoff must include source agent, target agent, task id, Linear issue,
reason, status, and timestamp.

## Linear Gate

Every execution task must have a Linear issue before a Worker receives it.
Strategy and Architecture handoffs are proposals only. The Orchestrator accepts
a handoff into execution by creating or linking Linear issues, writing
`linear-sync.md`, and adding Linear fields to `runtime.json` and `board.md`.

If Linear is unavailable, write `Needs approval:` with the reason and wait for
explicit human approval before proceeding. Active execution without Linear must
be marked as `Missing Linear:`.

Dashboard attention markers must be written exactly:

- `Blocked:`
- `Needs decision:`
- `Needs approval:`
- `Verification failed:`
- `Contract drift:`
- `Ownership violation:`
- `Missing Linear:`
- `Handoff:`

Example runlog event:

```text
- 2026-05-19T23:00:00Z | orchestrator | TASK-001 | running | Inspecting apps/api/routers/carestack.py and packages/ingest/sf_lead_service.py.
```

Example runtime entry:

```json
{
  "mission_id": "current",
  "updated_at": "2026-05-19T23:00:00Z",
  "sessions": [
    {
      "id": "019e433f-ed5b-7453-9881-03bfde74d6eb",
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
      "current_note": "Inspecting CareStack live-read and Salesforce persist paths."
    }
  ]
}
```
