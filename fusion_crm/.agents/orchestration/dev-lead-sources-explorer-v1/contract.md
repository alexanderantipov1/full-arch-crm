# Contract — ENG-391

API (FastAPI, `apps/api/routers/`):

- `GET /ops/analytics/lead-sources/tree`
  - query: `created_from?`, `created_to?` (ISO dates over lead created_at),
    `search?` (case-insensitive substring over node labels)
  - response: `{ total_leads, generated_at, sources: [SourceNode] }`
  - `SourceNode`: `{ key, label, leads, consults_scheduled,
    consults_attended, children: [SourceNode] }` (levels: source →
    medium → campaign; empty dimension values collapse into label
    "unknown")
- `GET /ops/analytics/lead-sources/leads`
  - query: `source` (required, effective-source label), `medium?`,
    `campaign?`, `created_from?`, `created_to?`, `limit?` (default 50,
    max 200), `offset?`
  - response: `{ total, items: [LeadListItem] }`
  - `LeadListItem`: `{ id, person_uid, status, source_label, utm_medium,
    utm_campaign, created_at, sf_created_at, extra_attribution }` where
    `extra_attribution` is the whitelisted attribution subset of
    `Lead.extra` (no PHI, no free-text notes)

Semantics:

- effective source label = existing `_lead_source_label()` coalesce chain;
- consults_scheduled = `ops.consultation.status == SCHEDULED` for persons
  of the node's leads; consults_attended = `status == COMPLETED`;
  NO_SHOW / CANCELLED / RESCHEDULED excluded from both;
- all queries tenant-scoped via `for_tenant`.

Frontend:

- Zod schemas `apps/web/lib/api/schemas/leadSources.ts`;
- hooks `apps/web/lib/api/hooks/useLeadSources.ts` (TanStack Query);
- page `apps/web/app/(staff)/dev/lead-sources/page.tsx`;
- nav entry in `apps/web/components/layout/AppShell.tsx`.

Out of scope:

- writes of any kind to providers or DB;
- chair/treatment stage of the funnel (future iteration);
- per-clinic (assigned_center / location) breakdown — future filter.
