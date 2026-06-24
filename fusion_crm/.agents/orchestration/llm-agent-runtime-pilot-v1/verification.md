# Verification

## Focused Backend Checks

- Agent Runtime service tests for LLM planning validation.
- API route tests for success, deny, clarify, credential failure, and schema
  failure.
- ENG-362 service/API tests for approved aggregate tool execution, no-match
  behavior, and pre-execution stop paths.
- Sensitive-field exclusion tests for prompts, run history, audit summary, and
  API responses.
- OpenAI integration tests using mocked provider responses.

## Focused Frontend Checks

- Typecheck for new API hooks and schemas.
- Schema/unit tests for workbench DTOs.
- UI smoke for success, executed aggregate result, denial, missing credential,
  clarification, and validation states.

## Database Checks

- If models or migrations change, run Alembic check.
- If new audit tables are added, run migration upgrade locally before claiming
  the DB path is verified.

## Live-Key Smoke

When tenant OpenAI credentials are configured:

- run one safe aggregate/internal test prompt;
- verify run history is written;
- verify audit summary is safe;
- verify the UI displays the result without raw provider payloads.

If credentials are missing or invalid, the smoke must show a safe credential
failure rather than a crash.

## 2026-06-07 Local Live-Key Result

- Local real-backend smoke passed on
  `http://127.0.0.1:3000/dev/agent-runtime`.
- Local `/api/auth/login` sets a non-production `staff_session` cookie and
  FastAPI maps it to a local admin principal for Agent Runtime workbench access.
- `Run planner` returned a visible `Planner result`.
- No 403, 500, API key marker, or raw provider payload marker was visible.

## 2026-06-07 Production-Open Access Gate

- Agent Runtime workbench route is no longer restricted to
  `NEXT_PUBLIC_ENVIRONMENT=local`.
- Data Intelligence workbench route is no longer restricted to
  `NEXT_PUBLIC_ENVIRONMENT=local`.
- Agent Runtime API routes are no longer hidden by `APP_ENV=production`.
- API access remains guarded by admin/system principal checks.
- Google IAP authenticated email headers are bridged to the shared principal
  contract for internal production workbench access until full staff auth lands.
- Direct local API smoke with an IAP-authenticated header returned `200 OK` from
  `/agent-runtime/tools`.
