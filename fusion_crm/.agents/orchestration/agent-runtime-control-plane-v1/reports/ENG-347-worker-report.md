# ENG-347 Worker Report — Human Approval Requests V1

## Linear

- Issue: ENG-347
- URL: https://linear.app/fusion-dental-implants/issue/ENG-347/ar-04-human-approval-requests-v1
- Status at report time: In Progress

## Summary

Implemented Agent Runtime human approval request V1 as a safe review boundary
for agent-proposed actions. Approval requests can be listed, created, and
decided through the backend/API, and the Agent Runtime workbench now renders
pending approvals with human actions.

This does not auto-approve or mutate Semantic Catalog business meaning.
Semantic Catalog review remains the downstream source of truth.

## Changed Files

- `packages/agent_runtime/models.py`
- `packages/agent_runtime/repository.py`
- `packages/agent_runtime/schemas.py`
- `packages/agent_runtime/service.py`
- `apps/api/routers/agent_runtime.py`
- `packages/db/alembic/versions/20260605_1000_e4f5a6b7c8d9_add_agent_runtime_approval_requests.py`
- `apps/web/lib/api/schemas/agentRuntime.ts`
- `apps/web/lib/api/hooks/useAgentRuntime.ts`
- `apps/web/lib/msw/handlers.ts`
- `apps/web/app/(staff)/dev/agent-runtime/page.tsx`
- `tests/agent_runtime/test_service.py`
- `tests/api/test_agent_runtime_routes.py`
- `apps/web/tests/unit/schemas.test.ts`
- `packages/agent_runtime/CLAUDE.md`
- `packages/audit/CLAUDE.md`

## Backend

- Added `audit.agent_runtime_approval_request` for safe approval request
  summaries.
- Added repository/service methods for create, list, and decision.
- Added API endpoints:
  - `GET /agent-runtime/approvals`
  - `POST /agent-runtime/approvals`
  - `POST /agent-runtime/approvals/{approval_id}/decision`
- Added safe status/target/decision contracts:
  - statuses: `pending`, `approved`, `rejected`, `needs_edit`, `unresolved`
  - target kinds: semantic catalog mapping proposal, impact preview, large
    analysis run, export request, write tool execution
  - decisions: approve, reject, request edit, mark unresolved

## Frontend

- Added Zod contracts and React Query hooks for approvals.
- Added `Approval requests` section to `/dev/agent-runtime`.
- Added mock approval fixtures and decision mutation in MSW.
- UI shows reason, evidence summary, requested action, data classes, affected
  surfaces, risk flags, posture, and human action buttons.

## Safety Notes

- Approval requests are safe summaries only.
- No secrets, API keys, raw provider payloads, raw SQL, prompt bodies, PHI, or
  unmasked row-level values are stored or exposed by the V1 DTOs.
- Lightweight marker validation rejects obvious unsafe approval details before
  persistence.
- Approved approval request status does not execute downstream action or change
  catalog truth.

## Verification

- `.venv/bin/python -m pytest -q tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/api/test_tenant_credential_routes.py`
  - Result: 20 passed
- `ruff check packages/agent_runtime packages/db/registry.py apps/api/routers/agent_runtime.py apps/api/routers/tenant.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/api/test_tenant_credential_routes.py packages/db/alembic/versions/20260605_0900_d3e4f5a6b7c8_add_agent_runtime_run_history.py packages/db/alembic/versions/20260605_1000_e4f5a6b7c8d9_add_agent_runtime_approval_requests.py`
  - Result: passed
- `mypy packages/agent_runtime packages/db/registry.py apps/api/routers/agent_runtime.py apps/api/routers/tenant.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/api/test_tenant_credential_routes.py`
  - Result: passed
- `npm run typecheck`
  - Result: passed
- `npm run test -- tests/unit/schemas.test.ts`
  - Result: 16 passed
- `npm run lint -- --file 'app/(staff)/dev/agent-runtime/page.tsx' --file lib/api/hooks/useAgentRuntime.ts --file lib/api/schemas/agentRuntime.ts --file lib/msw/handlers.ts --file tests/unit/schemas.test.ts`
  - Result: passed
- `cd packages/db && alembic heads`
  - Result: `e4f5a6b7c8d9 (head)`
- `cd packages/db && alembic check`
  - Result: `No new upgrade operations detected.`
- Browser smoke on `http://127.0.0.1:3000/dev/agent-runtime`
  - Result: approval section rendered, pending request displayed, Approve
    mutation changed status to approved with no error.

## Local DB Note

Applied local dev DB upgrade to head for verification:

- `c2d3e4f5a6b7 -> d3e4f5a6b7c8`
- `d3e4f5a6b7c8 -> e4f5a6b7c8d9`

## Risks And Follow-Ups

- V1 approval decisions are status records only; downstream execution adapters
  are intentionally not wired yet.
- Real DIA-generated approval request creation remains for ENG-349 linkage.
- Full audit summaries across approvals/runs remain for ENG-348.
- Stronger sensitive-data classification should replace marker validation when
  the policy engine owns approval payload validation.

## Do Not Merge Conditions

- Do not merge if product wants approval status to execute downstream actions in
  this slice.
- Do not merge if `alembic check` reports new drift after rebasing.
