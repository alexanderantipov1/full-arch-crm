# Acceptance — ENG-391

1. New "Lead sources" tab appears in the DEV menu (`AppShell.tsx`
   devToolItems) and renders real data from FastAPI.
2. Tree groups leads by effective source (coalesce `Lead.source` →
   `extra.lead_source` → `extra.hubspot_lead_source` → `extra.utm_source`,
   fallback "unknown"), expandable into `utm_medium` → `utm_campaign`.
3. Every node shows three counts: leads, consults_scheduled (status
   SCHEDULED), consults_attended (status COMPLETED), joined via
   `person_uid`.
4. Period filter (lead `created_at` from/to) and node-label search are
   applied server-side and change the counts.
5. Clicking a node opens the lead list for that node: status, source and
   attribution fields, person_uid, created_at; sorted by created_at desc;
   paginated.
6. Endpoints live in `apps/api/routers/` (prod routing split). No Next.js
   route handlers, no MSW fallback left behind.
7. Route → service → repository layering respected; queries tenant-scoped.
8. `make lint`, `mypy .`, `make test` green; `alembic check` clean (no new
   migration expected — read-only aggregation).
9. Frontend `tsc --noEmit`, lint, and existing vitest suite green.
