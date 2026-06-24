# Agent Mission Control Dashboard

Read-only localhost dashboard for development orchestration state.

Run:

```bash
python3 .agents/dashboard/server.py \
  --mission .agents/orchestration/<mission> \
  --port 8787
```

Open:

```text
http://127.0.0.1:8787
```

The dashboard reads files from `.agents/orchestration/`, `.agents/strategy/`,
and the current git repository. It does not mutate files, git, processes,
Linear issues, or product runtime state.

If a configured layer does not exist yet, the UI shows an empty state instead
of inventing data.

## Live Data Contract

The dashboard does not inspect terminal buffers, Codex threads, Claude Code
sessions, or hidden agent transcripts. It only shows state that has been
materialized into files or git.

For live execution visibility, Orchestrator and Worker agents must write to the
configured mission folder:

- `runtime.json` for active sessions, status, heartbeat, phase, worktree, and
  current note, plus `handoffs` for role transitions;
- `runlog.md` for chronological progress events;
- `board.md` for task state;
- `linear-sync.md` for task-to-Linear mapping;
- `reports/<task-id>-worker-report.md` for completed, paused, or blocked work;
- `incidents.md` for failures and repeated mistakes;
- `decision-log.md` for direction-changing decisions.

Execution tasks must have Linear issue id and URL before Workers receive them.
The dashboard treats active runtime sessions without Linear fields as protocol
violations.

Every transition between Strategy, Orchestrator, Worker, Verifier, and
Integrator must be recorded as a `Handoff:` event so the dashboard can show when
work leaves one role and enters another.

Use these exact markers when human attention is required, because the dashboard
routes them into the decision inbox:

- `Blocked:`
- `Needs decision:`
- `Needs approval:`
- `Verification failed:`
- `Contract drift:`
- `Ownership violation:`
- `Missing Linear:`
- `Handoff:`

Visibility rule:

```text
If it is not in mission runtime files, strategy files, or git, the dashboard
cannot see it.
```
