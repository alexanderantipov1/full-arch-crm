# PR115 Production Review Follow-Ups

- Created at: 2026-06-06T04:47:20Z
- Source role: production-reviewer
- Target role: orchestrator
- PR: https://github.com/alexanderantipov1/fusion_crm/pull/115
- Parent Linear issue: ENG-343
- Current Linear state: ENG-343 through ENG-350 are Done
- Execution gate: Needs Linear before worker assignment

## State

Production review found that PR #115 is structurally close but should not be
treated as ready-to-merge until the follow-ups below are either fixed or
converted into explicit accepted product decisions.

The PR is currently draft. GitHub checks are green for the remote head, and the
branch merge state is clean. The local checkout contains an additional merge
from `origin/main`; CI evidence applies to the remote PR head.

## Orchestrator Tasks

### AR-PR115-FIX-001 — Local-only gate for `/dev/agent-runtime`

- Linear: Needs Linear
- Suggested priority: High
- Owner: frontend worker
- Evidence:
  - `apps/web/CLAUDE.md` requires `/dev/*` pages to check
    `NEXT_PUBLIC_ENVIRONMENT === "local"` and 404 otherwise.
  - `apps/web/app/(staff)/dev/data-intelligence/page.tsx` follows that rule.
  - `apps/web/app/(staff)/dev/agent-runtime/page.tsx` renders without the gate.
- Acceptance:
  - If the page remains under `/dev/*`, add the same local-only 404 guard.
  - If it should be production-facing, move/rename the route and record the
    decision in mission artifacts.
  - Add or update a focused test where practical.

### AR-PR115-FIX-002 — Backend authorization/environment gate

- Linear: Needs Linear
- Suggested priority: High
- Owner: backend worker
- Evidence:
  - `apps/api/routers/agent_runtime.py` mounts provider health check, run
    history, approval creation, and approval decision routes without a role or
    environment guard.
  - `apps/api/dependencies.py:get_principal` returns `ANONYMOUS` when no auth
    middleware populated the request principal.
- Acceptance:
  - Anonymous callers cannot run OpenAI health checks or mutate approval
    requests.
  - Read-only projections are either explicitly allowed or protected by the
    same staff/admin contract.
  - Tests cover unauthorized access and the allowed staff/admin path.

### AR-PR115-FIX-003 — Safe failure run-history semantics

- Linear: Needs Linear
- Suggested priority: Medium
- Owner: backend worker
- Evidence:
  - `AgentRuntimeService.test_openai_connection` records a run only after the
    OpenAI integration call returns.
  - The recorded run status is always `success`, even if the safe provider
    result has `ok=False`.
  - Exceptions from credential/provider failures do not create a safe failure
    run summary.
- Acceptance:
  - `ok=False` records a non-success status with safe metadata.
  - Credential and provider exceptions create safe failure/blocked summaries
    without secrets, prompts, raw provider payloads, PHI, or raw SQL.
  - Tests cover success, `ok=False`, invalid credential, and provider failure.

### AR-PR115-FIX-004 — Mission state synchronization

- Linear: Needs Linear
- Suggested priority: Medium
- Owner: orchestrator/integrator
- Evidence:
  - `ownership.yaml` still marks ENG-345/ENG-346 as `in_review` and
    ENG-347 through ENG-350 as `planned`, while runtime/board/Linear state
    reports them Done/completed.
  - `.agents/orchestration/current/` describes an older ENG-312 mission while
    the named mission for PR #115 is
    `.agents/orchestration/agent-runtime-control-plane-v1/`.
- Acceptance:
  - Repo mission ownership, runtime telemetry, Linear state, PR draft/readiness,
    and worker reports agree.
  - The active mission path expected by the dashboard is explicit.
  - Any remaining deferred work is listed as second-layer work, not hidden in
    completed claims.

## Next Orchestrator Actions

1. Create or link active Linear issues for the four tasks above.
2. Update `board.md`, `linear-sync.md`, `runtime.json`, and `runlog.md` in the
   mission runtime directory after Linear issue ids are available.
3. Assign workers only after the Linear gate is satisfied.
4. Re-run focused verification and then the repo verify loop required by the
   mission verification contract where practical.

## Orchestrator Execution — 2026-06-06

The user approved Orchestrator execution after the review handoff. The current
Linear toolset available in this session could not create new issues, so the
Orchestrator executed the fixes directly in the current checkout and preserved
the `Missing Linear` marker in runtime telemetry.

### Changes Made

- Added the local-only `/dev/*` guard to
  `apps/web/app/(staff)/dev/agent-runtime/page.tsx`.
- Added route-level Agent Runtime API protection in
  `apps/api/routers/agent_runtime.py`:
  - hidden in production via 404;
  - admin/system-only in non-production.
- Updated OpenAI provider health-check run history in
  `packages/agent_runtime/service.py`:
  - `ok=False` records a safe `failure` run summary;
  - platform/provider failures record safe failure summaries before re-raising;
  - no secrets, PHI, raw provider payloads, raw SQL, or prompt bodies are
    written.
- Added focused tests for the new authorization and run-history behavior.
- Extended the tenant-isolation integration sweep resolver for the new
  Agent Runtime repositories.
- Updated pytest config so canonical `make test` uses importlib mode and the
  required `pythonpath`, avoiding duplicate `test_service.py` import mismatch.
- Synchronized `ownership.yaml` with completed ENG-345 through ENG-350 state
  and the active PR #115 review follow-up execution.

### Verification

- `.venv/bin/python -m pytest -q tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/api/test_tenant_credential_routes.py`
  - Result: 27 passed.
- `ruff check packages/agent_runtime apps/api/routers/agent_runtime.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
  - Result: passed.
- `mypy packages/agent_runtime apps/api/routers/agent_runtime.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
  - Result: passed.
- `npm run typecheck` in `apps/web`
  - Result: passed.
- `npm run test -- tests/unit/schemas.test.ts` in `apps/web`
  - Result: 17 passed.
- `npm run lint -- --file 'app/(staff)/dev/agent-runtime/page.tsx' --file lib/api/hooks/useAgentRuntime.ts --file lib/api/schemas/agentRuntime.ts --file lib/msw/handlers.ts --file tests/unit/schemas.test.ts`
  - Result: passed.
- `PATH=.venv/bin:$PATH make test`
  - Result: 1358 passed.
- `make lint`
  - Result: passed.
- `mypy .`
  - Result: no issues in 353 source files.
- `cd packages/db && SECRET_KEY=dev-secret DATABASE_URL=postgresql+asyncpg://fusion:fusion@127.0.0.1:5434/fusion REDIS_URL=redis://127.0.0.1:6380/0 ../../.venv/bin/alembic check`
  - Result: `No new upgrade operations detected.`

### Remaining Coordination Note

The product fixes are complete and verified. Linear still lacks separate active
follow-up issues because the current session's Linear toolset could not create
issues. If the project requires one issue per executed fix for audit hygiene,
create/link them after the fact and point them to this report.
