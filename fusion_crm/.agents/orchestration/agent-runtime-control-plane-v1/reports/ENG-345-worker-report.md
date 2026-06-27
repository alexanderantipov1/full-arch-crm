# ENG-345 Worker Report — Tools Registry Projection V1

## Status

Implemented and ready for review.

## Changed Files

- `packages/agent_runtime/schemas.py`
- `packages/agent_runtime/service.py`
- `apps/api/routers/agent_runtime.py`
- `tests/agent_runtime/test_service.py`
- `tests/api/test_agent_runtime_routes.py`
- `apps/web/lib/api/schemas/agentRuntime.ts`
- `apps/web/lib/api/hooks/useAgentRuntime.ts`
- `apps/web/lib/msw/handlers.ts`
- `apps/web/app/(staff)/dev/agent-runtime/page.tsx`
- `apps/web/tests/unit/schemas.test.ts`

## Delivered

- Added backend `GET /agent-runtime/tools`.
- Added safe Pydantic DTOs for Agent Runtime tool projection.
- Projected registered tools from `packages.tools.registry`.
- Added planned Semantic Catalog helper tools as non-callable planned entries.
- Added frontend Zod schema and React Query hook.
- Added MSW local mock response.
- Added `/dev/agent-runtime` Tools registry panel showing status, data classes,
  output posture, policy posture, limits, and approval/not-callable flags.

## Safety

- The endpoint is discovery-only.
- It does not execute tools.
- It does not expose tool functions, provider credentials, raw SQL, PHI, raw
  provider payloads, or unmasked rows.
- Planned Semantic Catalog tools are visible as `planned` and `callable=false`.

## Verification

- `ruff check packages/agent_runtime apps/api/routers/agent_runtime.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
- `mypy packages/agent_runtime apps/api/routers/agent_runtime.py tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
- `.venv/bin/python -m pytest -q tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py`
- `npm run typecheck`
- `npm run test -- tests/unit/schemas.test.ts`
- `npm run lint -- --file 'app/(staff)/dev/agent-runtime/page.tsx' --file lib/api/hooks/useAgentRuntime.ts --file lib/api/schemas/agentRuntime.ts --file lib/msw/handlers.ts --file tests/unit/schemas.test.ts`
- Browser smoke: `/dev/agent-runtime` rendered Tools registry, `Data Intelligence Profile Field`, and planned `Semantic Catalog Create Review Proposal`.

## Risks

- The current checkout is dirty with prior Agent Runtime/OpenAI base changes, so
  the Orchestrator self-executed this slice instead of launching an isolated
  worker worktree.
- Full repository verification was not run yet.

## Remaining Work

- Review and optionally close ENG-345.
- Continue with ENG-346 Agent Run History V1 after review.
