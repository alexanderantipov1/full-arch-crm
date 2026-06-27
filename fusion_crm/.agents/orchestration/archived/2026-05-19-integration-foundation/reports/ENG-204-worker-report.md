# ENG-204 Worker Report

## Summary

Reviewed the existing ENG-204 source-data WIP for the local dev Salesforce and CareStack source data table. The endpoint, ingest service projection, Zod schema, React Query hook, page, nav link, and focused tests are present and aligned with the requested scope. No implementation changes were needed in the source-data code during this pass.

## Touched Files

- `apps/api/routers/dev.py`
- `apps/api/main.py`
- `apps/web/app/(staff)/dev/source-data/page.tsx`
- `apps/web/components/layout/AppShell.tsx`
- `apps/web/lib/api/hooks/useSourceData.ts`
- `apps/web/lib/api/schemas/sourceData.ts`
- `apps/web/lib/api/schemas/index.ts`
- `packages/ingest/repository.py`
- `packages/ingest/schemas.py`
- `packages/ingest/service.py`
- `tests/api/test_dev_source_data.py`
- `tests/ingest/test_dev_source_data_service.py`
- `.agents/orchestration/current/reports/ENG-204-worker-report.md`

## Verification

- PASS: `uv run pytest tests/api/test_dev_source_data.py tests/ingest/test_dev_source_data_service.py -q`
  - Result: `3 passed in 0.43s`
- PASS: `cd apps/web && npm run lint`
  - Result: `No ESLint warnings or errors`
- PASS: `cd apps/web && npm run typecheck`
  - Result: `tsc --noEmit` completed successfully

## Notes

- A bare `pytest tests/api/test_dev_source_data.py tests/ingest/test_dev_source_data_service.py -q` failed before collection because the shell resolved an older Python 3.11 editable install pointing at `.claude/worktrees/...` and that environment lacked `structlog`. Running through `uv run` used the current repo `.venv` and passed.
- The backend route is production-gated through `require_dev_surface()`.
- The frontend route and AppShell nav are local-dev gated with `NEXT_PUBLIC_ENVIRONMENT === "local"`.
- The service returns an allow-listed payload projection instead of verbatim `ingest.raw_event.payload`.

## Risks

- The source-data UI currently trusts the source-data endpoint contract and has no component test. TypeScript and schema validation pass, but UI behavior was not browser-smoked in this pass.
- Full repository verification was not run because this worker was scoped to ENG-204 focused checks and the worktree contains many unrelated concurrent changes.
- Related source links can include providers outside the page's primary Salesforce/CareStack table context if identity data has broader source links; current tests cover the CareStack relation path only.

## Blockers

- None for the focused ENG-204 implementation.

## Suggested Next Task

- Add a small web component/page test or browser smoke for `/dev/source-data` once the orchestration wave settles, ideally with a mocked successful source-data response and an empty-state response.

## Do Not Merge Conditions

- Do not merge if the dev source-data endpoint becomes reachable in production.
- Do not merge if `payload` is changed to return raw provider payloads instead of the allow-listed projection.
- Do not merge if full wave verification later fails on ENG-204 files or route wiring.
