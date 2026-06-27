# Contract — Full Funnel v2

## Shared contract: `GET /dashboard/analytics/full-funnel` response shape
This endpoint already exists (ENG-472). v2 changes its **response shape** and
adds an `audience` query param. This is a **contract change** between backend
(ENG-481) and frontend (ENG-482).

### Request
- `audience`: `all` | `marketing` (default `all`)
- `start_date`, `end_date`: optional `YYYY-MM-DD`

### Response (additive / revised)
- headline: `leads`, `consults_scheduled`, `showed`, `no_show`,
  `closed_won` (money-based count), `revenue`
- `by_month[]`: `{ month, spend|null, leads, consults_scheduled, showed,
  no_show, closed_won, revenue }`
- `by_channel[]`: `{ month, channel(google|facebook|other), spend|null,
  leads, consults_scheduled, showed, no_show, revenue }`
  (`closed_won` stays month-level)

### Rules
- Null (`—`) for unconnected sources; never fabricate `0`.
- Backend owns the canonical shape; frontend Zod schema must mirror it exactly.
- ENG-482 must not start the schema until ENG-481 publishes the final field
  names (or they are agreed here first).

## Ownership boundary
- Backend owns: `packages/analytics/*` (if created), `packages/ops/*` reads,
  `packages/interaction/*` reads, `packages/identity/*` reads,
  `apps/api/routers/dashboard.py` (the funnel route only).
- Frontend owns: `apps/web/app/(staff)/analytics/funnel/*`,
  `apps/web/lib/api/schemas/fullFunnel.ts`, `apps/web/lib/api/hooks/useFullFunnel.ts`.
- Forbidden for both: new Alembic migrations, `.env*`, deploy config, any
  schema/table creation.
