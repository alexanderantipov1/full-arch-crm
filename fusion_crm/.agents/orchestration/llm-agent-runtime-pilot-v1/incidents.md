# Incidents

## 2026-06-07 - ENG-360 Request Validation Echo

- Task: ENG-360 - LLM-06 Evaluation, Audit, And Safety Tests V1
- Severity: Medium
- Status: Resolved
- Summary: The first LLM planner safety test pack found that FastAPI's default
  request validation response echoed the invalid `body.input` value. For unsafe
  prompts, that could reflect blocked markers back to the caller even though the
  domain service and run history stayed safe.
- Fix: Added a global `RequestValidationError` handler that returns the platform
  error envelope without echoing request input. Extended LLM prompt validators to
  reject raw SQL markers before provider calls.
- Verification: Focused API route tests now assert blocked prompt markers are
  absent from 422 responses; backend focused tests passed.
