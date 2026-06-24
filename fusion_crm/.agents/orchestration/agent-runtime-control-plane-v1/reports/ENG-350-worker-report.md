# ENG-350 Worker Report — Workbench Documentation And Verification

## Linear

- Issue: ENG-350
- URL: https://linear.app/fusion-dental-implants/issue/ENG-350/ar-07-workbench-documentation-and-verification
- Status at report time: In Progress

## Summary

Updated `/dev/agent-runtime` so it is the visible mission plan for Agent Runtime
Control Plane V1. The workbench now shows child Linear tasks, business logic,
V1 outcomes, remaining second-layer work, verification evidence, and aligned
English/Russian documentation.

## Changed Files

- `apps/web/app/(staff)/dev/agent-runtime/page.tsx`
- `.agents/orchestration/agent-runtime-control-plane-v1/reports/ENG-350-worker-report.md`

## Workbench Updates

- Added `Mission status` card with ENG-344 through ENG-350.
- Each mission row shows:
  - Linear id
  - status
  - business reason
  - V1 result
  - next-layer remaining work
- Added `Verification evidence` block.
- Updated English docs to describe the actual V1 state.
- Updated Russian docs to match the English content.
- Kept docs explicit that:
  - Agent Runtime is the control plane
  - agents do not get direct database access
  - approvals are required for risky or business-changing proposals
  - Semantic Catalog approved versions remain the source of truth
  - remaining work is tracked as second-layer work

## Verification

- `.venv/bin/python -m pytest -q tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/api/test_tenant_credential_routes.py`
  - Result: 23 passed
- `ruff check packages/agent_runtime packages/db/registry.py apps/api/routers/agent_runtime.py apps/api/routers/tenant.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/api/test_tenant_credential_routes.py packages/db/alembic/versions/20260605_0900_d3e4f5a6b7c8_add_agent_runtime_run_history.py packages/db/alembic/versions/20260605_1000_e4f5a6b7c8d9_add_agent_runtime_approval_requests.py`
  - Result: passed
- `mypy packages/agent_runtime packages/db/registry.py apps/api/routers/agent_runtime.py apps/api/routers/tenant.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/api/test_tenant_credential_routes.py`
  - Result: passed
- `npm run typecheck`
  - Result: passed
- `npm run test -- tests/unit/schemas.test.ts`
  - Result: 17 passed
- `npm run lint -- --file 'app/(staff)/dev/agent-runtime/page.tsx' --file lib/api/hooks/useAgentRuntime.ts --file lib/api/schemas/agentRuntime.ts --file lib/msw/handlers.ts --file tests/unit/schemas.test.ts`
  - Result: passed
- `cd packages/db && alembic check`
  - Result: `No new upgrade operations detected.`
- Browser smoke on `http://127.0.0.1:3000/dev/agent-runtime`
  - Result: mission status, ENG-350, verification evidence, and Russian docs
    rendered with no internal server error or application error.

## Remaining Second-Layer Work

- Create approval requests automatically from real DIA/agent runs.
- Persist approved request handoff into Semantic Catalog proposal review.
- Add registry/read-model impact preview backed by production dependency
  metadata.
- Connect full runner executions and resumable state.
- Link safe run summaries to detailed append-only audit events.
- Add production smoke after deployment for `/dev/agent-runtime` docs and
  controls.

## Risks

- The workbench is a documentation and control-plane surface, not a production
  planner by itself.
- Several sections are projections until the full DIA runner and catalog
  handoff are implemented.
- Production verification still needs a deployed URL check after commit/push/
  deploy.

## Do Not Merge Conditions

- Do not merge if English and Russian docs drift.
- Do not merge if the workbench loses visible Linear task memory or deferred
  second-layer notes.
- Do not merge if verification evidence is removed or no longer matches the
  implemented contracts.
