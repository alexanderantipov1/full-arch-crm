# Manager Answer Layer V1 Closure

## Closed Scope

Manager Answer Layer V1 is implemented through ENG-376 and closure-verified in
ENG-377.

The mission now provides:

- mission and Linear runtime tracking;
- manager answer backend/frontend contracts;
- OpenAI `gpt-4.1` manager answer generation after approved aggregate execution;
- safe answer prompt envelope from approved aggregate execution output only;
- answer audit metadata in run history;
- `/dev/agent-runtime` UI for final manager answer and answer audit metadata;
- local mock fixtures for frontend testing;
- eval matrix and smoke evidence.

## Verification Summary

| Check | Result | Notes |
| --- | --- | --- |
| `make lint` | PASS | `ruff check .` passed. |
| `mypy .` | PASS | 357 source files passed. |
| `make test` with default `python` | FAIL | Default shell `python` lacks project dependencies such as `structlog`, `respx`, `agents`, `chevron`, and `arq`. |
| `PATH=.venv/bin:$PATH make test` | FAIL | 1398 passed, 3 failed in `tests/api/test_dashboard_pm.py`, outside Agent Runtime scope. |
| Mission-focused backend tests | PASS | 48 tests passed for Agent Runtime service, schemas, and API routes. |
| Mission-focused backend ruff | PASS | Changed backend/test modules passed. |
| Mission-focused backend mypy | PASS | Changed backend/test modules passed. |
| Frontend schema tests | PASS | 19 tests passed. |
| Frontend lint | PASS | Changed Agent Runtime page/schema/MSW/tests passed. |
| Frontend typecheck | PASS | `tsc --noEmit` passed. |
| Alembic check | PASS | No new upgrade operations detected. |
| Local browser smoke | PASS | Answer UI, eligibility, key numbers, run-history answer audit, clarification, denied, and missing-credential states verified. |
| Production route smoke | PASS | `/dev/agent-runtime` returns IAP `302`, proving route exists and is protected. |

## Known External Failure

Full test suite under `.venv` currently has three failures in
`tests/api/test_dashboard_pm.py`:

- `test_pm_leads_includes_carestack_patient_source_rows`
- `test_pm_leads_paginates_combined_rows`
- `test_pm_leads_searches_identity_and_returns_both_provider_rows`

The mission branch has no diff in `apps/api/routers/dashboard.py` or
`tests/api/test_dashboard_pm.py`, so these failures are recorded as outside
Manager Answer Layer V1 scope.

## Not Done Yet

- Final manager answers are not promoted into production Manager AI Chat.
- Broader approved tool execution adapters remain future work.
- DIA proposal ingestion into Semantic Catalog review remains future work.
- Full autonomous planner promotion remains deferred until policy, catalog,
  eval, and approved query coverage are stronger.
- Detailed append-only trace storage remains deferred until an audited trace
  policy exists.

## Closure Decision

ENG-377 closes the Manager Answer Layer V1 mission with focused verification,
browser smoke, production route smoke, Linear sync, and Orchestrator runtime
sync complete. The only remaining verification concern is the unrelated Project
Manager dashboard test failure recorded above.
