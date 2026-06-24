# ENG-361 Worker Report - Documentation, Production Smoke, And Closure

## Linear

- Issue: ENG-361 - LLM-07 Documentation, Production Smoke, And Closure
- URL: https://linear.app/fusion-dental-implants/issue/ENG-361/llm-07-documentation-production-smoke-and-closure
- Status: In Review

## Summary

Closed the LLM Agent Runtime Pilot V1 implementation pass with aligned
workbench documentation, local verification, protected production smoke, and
mission runtime synchronization.

The workbench now explains the LLM planning pilot in plain language in both
English and Russian: it creates a constrained plan, not a final manager answer;
it can allow, clarify, deny/refuse, or require approval; and it stores only safe
metadata/audit posture.

## Changed Files

- `apps/web/app/(staff)/dev/agent-runtime/page.tsx`
- `apps/api/dependencies.py`
- `apps/api/routers/agent_runtime.py`
- `apps/api/routers/auth.py`
- `apps/web/app/(staff)/dev/data-intelligence/page.tsx`
- `packages/integrations/openai/client.py`
- `packages/integrations/openai/schemas.py`
- `tests/api/test_auth_routes.py`
- `tests/api/test_dependencies.py`
- `tests/integrations/openai/test_client.py`
- `.agents/orchestration/llm-agent-runtime-pilot-v1/reports/ENG-361-worker-report.md`

## Documentation Updates

- Added an English `LLM planning pilot` docs section.
- Added the matching Russian `LLM planning pilot` docs section.
- Updated workbench usage guidance to explain that dev prompts should be safe
  and that policy result/run id must be reviewed before treating any answer path
  as ready.
- Extended verification evidence with the ENG-360 LLM eval pack and safe
  request-validation envelope.

## Verification

- `cd apps/web && npm run typecheck`
  - Passed.
- `cd apps/web && npm run lint`
  - Passed.
- `.venv/bin/python -m pytest -q tests/agent_runtime/test_service.py tests/api/test_agent_runtime_routes.py tests/integrations/openai/test_client.py tests/integrations/openai/test_service.py`
  - Passed: 45 tests.
- `.venv/bin/python -m pytest -q tests/api/test_dependencies.py tests/api/test_auth_routes.py tests/api/test_agent_runtime_routes.py tests/integrations/openai/test_client.py tests/agent_runtime/test_service.py`
  - Passed: 50 tests.
- `.venv/bin/ruff check apps/api/dependencies.py apps/api/routers/auth.py packages/integrations/openai/client.py packages/integrations/openai/schemas.py tests/api/test_dependencies.py tests/api/test_auth_routes.py tests/integrations/openai/test_client.py`
  - Passed.
- `.venv/bin/mypy apps/api/dependencies.py apps/api/routers/auth.py packages/integrations/openai/client.py packages/integrations/openai/schemas.py tests/api/test_dependencies.py tests/api/test_auth_routes.py tests/integrations/openai/test_client.py`
  - Passed.
- Local browser docs smoke on `http://127.0.0.1:3000/dev/agent-runtime`
  - Passed: English and Russian docs render the LLM planning pilot section.
- Local configured-key smoke on `http://127.0.0.1:3000/dev/agent-runtime`
  - Passed after post-closure fixes: local sign-in sets `staff_session`, the
    FastAPI local dependency bridge maps that session to an admin principal, all
    Agent Runtime workbench requests avoid 403, and `Run planner` renders a
    `Planner result`.
  - The OpenAI planner now uses Agents SDK structured output with a strict
    key/value argument schema and normalizes it back to the public
    `tool_arguments` object.
  - No API key marker or raw provider payload marker was visible.
- Production-open access gate update
  - `/dev/agent-runtime` is no longer frontend-gated to
    `NEXT_PUBLIC_ENVIRONMENT=local`.
  - `/dev/data-intelligence` is no longer frontend-gated to
    `NEXT_PUBLIC_ENVIRONMENT=local`; its UI posture copy now describes the
    page as internal/IAP protected.
  - `/agent-runtime/*` API routes are no longer hidden by
    `Settings.is_production`; they remain restricted to admin/system
    principals.
  - Google IAP `X-Goog-Authenticated-User-Email` is bridged to the shared
    principal contract as an internal admin principal until the full staff auth
    model lands.
  - Direct local smoke with an IAP-authenticated header returned `200 OK` from
    `/agent-runtime/tools`.
- Production HTTP smoke on `https://fusioncrm.app/dev/agent-runtime`
  - Passed protected-surface check: Google IAP returns 302 to Google sign-in,
    proving the dev workbench is not publicly reachable.
- Production Chrome read-only smoke
  - Confirmed the route lands on Google IAP account selection without selecting
    an account or submitting a production LLM request.

## Production Notes

- I did not run a production LLM planner request because that requires choosing
  an IAP Google account and submitting a request against production. The safe
  production result observed in this pass is the IAP-protected boundary.
- A full production inside-IAP planner smoke remains a manual/operator step:
  sign in as an authorized admin/system principal, open `/dev/agent-runtime`,
  run the safe aggregate prompt, and verify either a safe planner result or a
  safe credential/policy failure.

## Remaining Second-Layer Work

- Final manager-facing answers are not generated by this pilot.
- Tool execution does not happen from the workbench yet.
- Resumable LLM runs and full LLM planner promotion remain deferred.
- Golden replay evals should be added once real manager prompts exist.
- Production inside-IAP live-key smoke should be run by an authorized operator
  before promoting beyond dev/internal use.
