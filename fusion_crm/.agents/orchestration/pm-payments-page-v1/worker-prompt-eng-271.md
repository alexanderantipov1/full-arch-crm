You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: ENG-271
(https://linear.app/fusion-dental-implants/issue/ENG-271). Isolated git worktree.
Implement → verify → write a report. Do NOT touch `main`, do NOT push, do NOT open
a PR. Commit to YOUR worktree branch only once green; the Orchestrator integrates.

## Mission
Add a **Payments** page under Project Manager → Leads: a date/location-filterable
list of CareStack payment transactions (person + pipeline stage + amount + type +
date + location), each row drilling down to the full verbatim raw payload (like
/dev/inspector). Mirror the existing PM Leads page end-to-end.

## Read first (mirror these)
- Backend leads endpoint: `apps/api/routers/dashboard.py` → `GET /dashboard/pm/leads`
  (`pm_leads`, `DashboardPmLeadListOut`, `DashboardPmLeadOut`). Copy its shape,
  filter handling, tenant scoping, person+stage lookups.
- Inspector list: `apps/api/routers/ingest.py` → `GET /dev/inspector/raw-events`
  (`list_inspector_raw_events`, `_InspectorEventOut`). Add a single-by-id sibling.
- Frontend leads page: `apps/web/app/(staff)/project-manager/leads/page.tsx`,
  hook `apps/web/lib/api/hooks/useDashboard.ts` (`useDashboardPmLeads`), schema
  `apps/web/lib/api/schemas/dashboard.ts`, MSW `apps/web/lib/msw/handlers.ts`.
- Sidebar: `apps/web/components/layout/AppShell.tsx` — the Project Manager group
  with the existing `/project-manager/leads` child (add Payments under it).
- Event model: `interaction.event` has kind, source_provider, source_kind,
  source_external_id, occurred_at, person_uid, payload (has `amount`,
  `transaction_type`, `location_id` from ENG-267/270), and `source_event_id` (FK
  → ingest.raw_event.id) for the raw drilldown.

## Task

### Backend
1. `GET /dashboard/pm/payments` (mirror `pm_leads`): rows from `interaction.event`
   where kind in (`payment_recorded`,`payment_refunded`,`payment_reversed`),
   tenant-scoped. Per-row SAFE fields: person_uid, display_name, lead_status,
   consultation_status (the person's pipeline stage — reuse the same lookups the
   leads/dashboard code uses), amount (from payload), kind, transaction_type
   (from payload), occurred_at, location_id + location_name (resolve via the
   existing location lookup), source_external_id, raw_event_id (= source_event_id).
   Filters: `from`/`to` (occurred_at window), `location_id`
   (payload.location_id match), `source_provider`, `q` (name / external id),
   `limit`. New DTOs `DashboardPmPaymentOut` / `DashboardPmPaymentListOut`.
   Business logic in a service/read-model method, not the route.
2. `GET /ingest/dev/inspector/raw-events/{event_id}` — single tenant-scoped
   raw_event by id with verbatim payload (mirror `list_inspector_raw_events`;
   add an `IngestService.get_raw_event(tenant_id, event_id)` if missing).

### Frontend (apps/web)
3. Sidebar: add a **Payments** child under Leads in the Project Manager group
   (`/project-manager/payments`). Active-state handling like the Leads item.
4. Page `apps/web/app/(staff)/project-manager/payments/page.tsx`: filter bar (date
   window default last 30 days, location select, provider, search) + table
   (person name → link to `/persons/{uid}`, stage badge, amount, type badge, date,
   location) + a per-row **View raw** button → drawer/modal that fetches
   `/ingest/dev/inspector/raw-events/{raw_event_id}` and renders the payload as
   pretty JSON (borrow the inspector's payload rendering).
5. Zod schemas (`lib/api/schemas/dashboard.ts`), hook (`lib/api/hooks/useDashboard.ts`),
   MSW handlers + fixtures. Use the `Datetime` alias for datetime fields.

### Tests
- Backend: payments list shape + each filter (window, location, provider, q),
  tenant scoping, and a no-PHI assertion (list JSON has no clinical free text /
  no fields beyond the safe set). raw-event-by-id returns tenant's row, not
  another tenant's.
- Frontend: page renders loading + rows; applying a filter refetches; View raw
  opens with the payload. Keep MSW ↔ Zod in sync.

## Hard constraints
- The LIST is dashboard-safe (person/stage/amount/location only — NO clinical
  free text). The raw drilldown reuses the EXISTING inspector carve-out — do NOT
  invent new PHI exposure beyond what `/dev/inspector/raw-events` already returns.
- Read-only. No new schema/migration. No PHI in logs. `except Exception` only.
  Cross-domain rules per `packages/CLAUDE.md`. English only. Strict TS.

## Definition of done
1. `make lint` ; `mypy .` ; `make test` ; `cd packages/db && alembic check` green.
2. `cd apps/web && npm run lint && npx tsc --noEmit && npm run test` green.
3. Commit to your worktree branch only once green.
4. Write `.agents/orchestration/pm-payments-page-v1/reports/ENG-271-worker-report.md`
   (changed files, endpoints, safe-field list, tests, verification, risks, do-not-merge).
5. If a needed lookup (stage, location_name) isn't readily available, reuse the
   leads/dashboard approach; if truly blocked, write `Needs decision:`.
