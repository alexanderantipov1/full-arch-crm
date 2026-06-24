# ENG-348 Worker Report — Agent Audit Summaries V1

## Linear

- Issue: ENG-348
- URL: https://linear.app/fusion-dental-implants/issue/ENG-348/ar-05-agent-audit-summaries-v1
- Status at report time: In Progress

## Summary

Implemented safe Agent Runtime audit summaries for visible run history. Run
summaries now expose data level, policy gate, policy reason, final outcome,
policy decisions, safe evidence references, approval links, and compliance
notes without exposing detailed audit payloads.

This is a summary layer only. Append-only detailed audit architecture remains
intact and is not replaced by the workbench view.

## Changed Files

- `packages/agent_runtime/schemas.py`
- `packages/agent_runtime/service.py`
- `packages/agent_runtime/CLAUDE.md`
- `apps/web/lib/api/schemas/agentRuntime.ts`
- `apps/web/lib/msw/handlers.ts`
- `apps/web/app/(staff)/dev/agent-runtime/page.tsx`
- `tests/agent_runtime/test_service.py`
- `tests/api/test_agent_runtime_routes.py`
- `apps/web/tests/unit/schemas.test.ts`

## Backend

- Extended `AgentRuntimeAuditSummaryOut` with:
  - `data_level`
  - `policy_gate`
  - `policy_reason`
  - `final_outcome`
  - `policy_decisions`
  - `evidence_refs`
  - `compliance_notes`
  - `linked_approval_request_ids`
- Added safe nested policy decision summaries.
- Normalized audit summaries through the Pydantic contract before storing new
  run rows.
- Added validation that rejects obvious unsafe markers such as raw provider
  payloads, raw SQL markers, prompt markers, API-key prefixes, and PHI-like
  marker fields in safe summary text.

## Frontend

- Extended Zod contracts to match backend audit summaries.
- Added a visible `Audit summary` block inside each run history card.
- Workbench now marks:
  - metadata-only, aggregate-only, and row-level posture
  - PHI, billing, export, masked, and approval-required posture
  - policy gates and policy decisions
  - denied/blocked outcomes with safe reasons
  - safe evidence refs and linked approval ids
- Added MSW examples for provider health check, approval-required semantic
  proposal, and denied row-level export preflight.

## Safety Notes

- No secrets, prompt bodies, provider payloads, raw SQL, PHI, or unmasked row
  values are exposed in DTOs or UI.
- Denied/blocked summaries explain the policy gate at a safe level only.
- Detailed append-only audit remains outside this UI summary.

## Verification

- `.venv/bin/python -m pytest -q tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/api/test_tenant_credential_routes.py`
  - Result: 21 passed
- `ruff check packages/agent_runtime packages/db/registry.py apps/api/routers/agent_runtime.py apps/api/routers/tenant.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/api/test_tenant_credential_routes.py packages/db/alembic/versions/20260605_0900_d3e4f5a6b7c8_add_agent_runtime_run_history.py packages/db/alembic/versions/20260605_1000_e4f5a6b7c8d9_add_agent_runtime_approval_requests.py`
  - Result: passed
- `mypy packages/agent_runtime apps/api/routers/agent_runtime.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
  - Result: passed
- `npm run typecheck`
  - Result: passed
- `npm run test -- tests/unit/schemas.test.ts`
  - Result: 16 passed
- `npm run lint -- --file 'app/(staff)/dev/agent-runtime/page.tsx' --file lib/api/hooks/useAgentRuntime.ts --file lib/api/schemas/agentRuntime.ts --file lib/msw/handlers.ts --file tests/unit/schemas.test.ts`
  - Result: passed
- `cd packages/db && alembic check`
  - Result: `No new upgrade operations detected.`
- Browser smoke on `http://127.0.0.1:3000/dev/agent-runtime`
  - Result: audit summary section rendered; denied row-level export run showed
    `row_level_export_policy`, `row_level_field_allowlist`, `blocked`, and
    `evidence: export_preflight`.

## Risks And Follow-Ups

- This does not yet join to detailed `audit.access_log` records; ENG-348 V1 is
  safe summary projection only.
- Future audit work should add stronger structured policy taxonomies and
  trace/evidence identifiers when the detailed audit architecture is connected.
- Real denied/blocked agent runner paths still need to populate these summary
  fields consistently when full agent execution lands.

## Do Not Merge Conditions

- Do not merge if any run summary starts exposing sensitive request bodies,
  provider payloads, prompt text, raw SQL, PHI, or unmasked row-level data.
- Do not merge if downstream expectations require detailed audit log browsing
  inside this V1 workbench.
