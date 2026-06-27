# Manager Answer Layer V1 Eval Matrix

## Scope

These evals cover constrained LLM planning, approved aggregate tool execution,
final manager answer generation, answer audit metadata, and workbench rendering.

## Eval Cases

| Case | Expected outcome | Evidence |
| --- | --- | --- |
| Allowed aggregate answer | Planner selects `ask_manager_analytics`, execution matches an approved query/read model, `manager_answer.status` is `generated`, and the workbench renders summary/key numbers/source refs. | `tests/agent_runtime/test_service.py`, browser smoke |
| Clarification required | Ambiguous prompt returns `clarification_required`, no tool execution, no generated answer. | `tests/agent_runtime/test_service.py`, browser smoke |
| No approved match | Safe but unsupported analytics question returns no-match metadata and answer audit status `not_generated`. | `tests/agent_runtime/test_service.py` |
| Denied PHI-bearing tool | PHI-bearing tool plan is denied before execution and answer generation. | `tests/agent_runtime/test_service.py` |
| Denied row-level/export request | Row-level/export prompt is refused or denied and no answer is generated. | browser smoke, API validation tests |
| Raw SQL prompt | Raw SQL markers fail safe prompt validation and are not echoed in persisted run history. | `tests/agent_runtime/test_service.py`, `tests/api/test_agent_runtime_routes.py` |
| Approval-required request | Export/catalog/write-capable plans create approval posture and do not execute automatically. | `tests/agent_runtime/test_service.py` |
| Missing credential | Missing OpenAI credential returns safe failure without exposing secret state. | browser smoke expected `424` |
| Run-history answer audit | `audit_summary.answer` includes status, eligibility, model, confidence, source refs, caveats, safety notes, and validation errors only. | `tests/agent_runtime/test_service.py`, workbench run history |
| Frontend schema compatibility | Zod schemas parse planner answer, answer eligibility, manager answer, and run-history answer audit. | `apps/web/tests/unit/schemas.test.ts` |

## Safety Expectations

- No API key, prompt body, raw provider payload, raw SQL, PHI, row-level rows,
  unmasked samples, or export payload is persisted in run history.
- Generated answers require source refs, caveats, confidence, and safety notes.
- Answer generation is called only after approved aggregate execution.
- Persisted answer audit metadata is intentionally smaller than the response
  body. Summary, explanation, and key numbers are not stored in
  `audit.agent_runtime_run.audit_summary`.

## Browser Smoke Evidence

Local smoke was run against `http://127.0.0.1:3000/dev/agent-runtime` after mock
login.

- Allowed aggregate: passed; final manager answer visible.
- Clarification: passed; clarification text visible.
- Denied row-level/export: passed; safe refusal visible.
- Missing credential: passed; expected `424 Failed Dependency` surfaced safely.
- Run history: passed; answer audit visible.
- Console errors: only expected `424 Failed Dependency` for missing credential.

## Production Route Smoke

Unauthenticated production route smoke:

- `https://fusioncrm.app/dev/agent-runtime` returns `302` to Google IAP auth.
- `https://fusioncrm.app/dev/data-intelligence` returns `302` to Google IAP auth.

This proves the dev routes are present on production and protected by IAP, not
missing with `404`.
