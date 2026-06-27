# ENG-349 Worker Report — DIA And Semantic Catalog Linkage V1

## Linear

- Issue: ENG-349
- URL: https://linear.app/fusion-dental-implants/issue/ENG-349/ar-06-dia-and-semantic-catalog-linkage-v1
- Status at report time: In Progress

## Summary

Implemented a safe Agent Runtime linkage projection from Data Intelligence
Agent outputs to Semantic Catalog review. The workbench now shows how review-only
DIA mapping proposals and gap briefs move through the path:

`agent run -> proposal -> approval -> catalog review -> approved version`

The projection keeps downstream catalog consumption approved-version-only and
does not auto-approve catalog meaning.

## Changed Files

- `packages/agent_runtime/schemas.py`
- `packages/agent_runtime/service.py`
- `packages/agent_runtime/CLAUDE.md`
- `apps/api/routers/agent_runtime.py`
- `apps/web/lib/api/schemas/agentRuntime.ts`
- `apps/web/lib/api/hooks/useAgentRuntime.ts`
- `apps/web/lib/msw/handlers.ts`
- `apps/web/app/(staff)/dev/agent-runtime/page.tsx`
- `tests/agent_runtime/test_service.py`
- `tests/api/test_agent_runtime_routes.py`
- `apps/web/tests/unit/schemas.test.ts`

## Backend

- Added safe linkage DTOs for:
  - impact surfaces with `known`, `likely`, or `unknown` confidence
  - review path steps with readiness status
  - DIA/Catalog linkage records
- Added `AgentRuntimeService.list_dia_catalog_linkages()`.
- Added API endpoint:
  - `GET /agent-runtime/dia-catalog-linkages`
- Linkage contract uses `downstream_consumption = approved_version_only`.

## Frontend

- Added Zod contracts and React Query hook for DIA/Catalog linkages.
- Added `/dev/agent-runtime` card: `DIA / Semantic Catalog linkage`.
- UI shows:
  - runtime run id
  - approval request id
  - catalog proposal ref
  - approved version ref
  - data classes and evidence refs
  - impact surfaces
  - review path steps and owners
  - approved-version-only downstream posture
- Added MSW endpoint with mapping proposal and gap brief examples.

## Safety Notes

- This is a read-only projection.
- Agent suggestions are review-only and never become catalog truth by
  themselves.
- Semantic Catalog approved versions remain the only downstream catalog source.
- No secrets, PHI, raw provider payloads, raw SQL, prompt bodies, or unmasked
  rows are exposed in linkage DTOs or UI.

## Verification

- `.venv/bin/python -m pytest -q tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/api/test_tenant_credential_routes.py`
  - Result: 23 passed
- `ruff check packages/agent_runtime apps/api/routers/agent_runtime.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
  - Result: passed
- `mypy packages/agent_runtime apps/api/routers/agent_runtime.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
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
  - Result: linkage card rendered with `approved_version_only`, known/likely/
    unknown impact surfaces, review path, and the note that agent suggestions
    are never approved catalog truth by themselves.

## Risks And Follow-Ups

- V1 linkage is a projection, not a persisted handoff table.
- Real DIA runner ingestion into approval requests and catalog review handoff
  still need implementation when the DIA runtime runner lands.
- Registry/read-model impact preview remains a stronger future layer for
  production dependencies.

## Do Not Merge Conditions

- Do not merge if the product expects this slice to mutate Semantic Catalog
  proposals automatically.
- Do not merge if downstream consumers are allowed to read draft proposals or
  documentation as catalog truth.
