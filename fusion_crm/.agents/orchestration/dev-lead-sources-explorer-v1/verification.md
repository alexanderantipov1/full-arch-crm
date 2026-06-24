# Verification — ENG-391

Backend:

- `make lint`
- `mypy .`
- `make test` (full pytest; new tests for tree aggregation + drill-down
  list, real PostgreSQL test DB per repo policy)
- `cd packages/db && alembic check`

Frontend (apps/web):

- `npx tsc --noEmit`
- `npm run lint`
- `npx vitest run`

Live check (local stack, 127.0.0.1):

- `GET /api/ops/analytics/lead-sources/tree` returns hierarchical buckets
  with non-zero counts on dev data;
- counts spot-checked against direct SQL for one source and one period;
- `/dev/lead-sources` renders the tree, filters, search, and drill-down.
