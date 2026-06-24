# ENG-271 — Worker Report

- **Task:** ENG-271 — PM Payments page — transaction list + raw drilldown
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-271/pm-payments-page-transaction-list-with-personstage-raw-payload
- **Role / agent:** worker / claude-code
- **Worktree:** `/Users/eduardkarionov/.fusion-agent-orchestrator/c2db50910d08/pm-payments-page-v1/worktrees/ENG-271`
- **Branch:** `eng-271-eng-271`
- **Allowed scope:** Read-only PM Payments dashboard surface, no schema/migration.
- **Status:** report-ready — verification green, no commit/push performed.

## What changed

### Backend
- `apps/api/routers/dashboard.py`
  - New DTOs: `DashboardPmPaymentOut`, `DashboardPmPaymentListOut`.
  - New route: `GET /dashboard/pm/payments` — mirrors `pm_leads` in spirit
    (route composes events + identity + ops + LocationService; business
    logic lives in service/read-model methods, not the handler). Filters:
    `from`, `to`, `location_id`, `source_provider`, `q`, `limit`.
    Returns SAFE row shape and a tenant-scoped page.
  - Local helpers `_float_or_none` and `_uuid_or_none` to coerce payload
    values defensively (the `interaction.event.payload` dict is no-PII
    structured, but the JSONB column is `dict[str, object]`).
- `apps/api/routers/ingest.py`
  - New route: `GET /ingest/dev/inspector/raw-events/{event_id}` —
    sibling of the existing list endpoint; returns one tenant-scoped
    `raw_event` with verbatim payload; 404 on miss via `NotFoundError`.
- `packages/ingest/service.py`
  - `IngestService.get_raw_event(tenant_id, event_id)` — thin wrapper
    over the existing `IngestRepository.get(...)` tenant filter.
- `packages/interaction/repository.py`
  - `InteractionRepository.list_payment_events_for_dashboard(...)` —
    filters by payment kinds + `data_class='billing'` + occurred window +
    `Event.payload['location_id']` exact match + optional provider + `q`
    on `summary` / `source_external_id`; tenant-scoped via `for_tenant`.
- `packages/interaction/service.py`
  - `InteractionService.list_payment_events_for_dashboard(...)` — the
    public service surface; cleans `q`, enforces limit bounds, returns
    raw ORM events (mirrors how `pm_leads` consumes ops DTOs in the
    route).
- `packages/ops/repository.py`
  - `OpsRepository.list_leads_for_persons(tenant_id, person_uids)` —
    batch lookup so the payments page does not N+1 over `Lead`.
- `packages/ops/service.py`
  - `OpsService.latest_leads_for_persons(tenant_id, person_uids)` —
    mirrors the existing `latest_consultations_for_persons` shape and
    returns `dict[UUID, LeadOut]`.

### Frontend (`apps/web`)
- `apps/web/lib/api/schemas/dashboard.ts`
  - `DashboardPmPaymentSchema`, `DashboardPmPaymentListSchema`,
    `DashboardPmPaymentKindSchema`. `Datetime` alias used for
    timestamps; `Uuid` for `location_id` / `raw_event_id`.
- `apps/web/lib/api/hooks/useDashboard.ts`
  - `useDashboardPmPayments(filters)` + `DashboardPmPaymentFilters`
    type — TanStack Query hook that parses the response through Zod.
- `apps/web/lib/api/hooks/useInspector.ts`
  - `useRawEvent(eventId)` — single-by-id fetch parsed with
    `RawEventSchema`. Used by the View raw drawer.
- `apps/web/lib/msw/handlers.ts`
  - MSW handler for `/api/dashboard/pm/payments` — filters the
    in-memory fixture on the same query-string contract as FastAPI so
    UI tests and `npm run dev` both work without the backend.
  - MSW handler for `/api/ingest/dev/inspector/raw-events/:eventId` —
    returns either a payment-fixture raw event or one from the existing
    inspector fixture.
- `apps/web/lib/msw/fixtures/payments.ts` (new) — three payment rows +
  three raw event payloads.
- `apps/web/components/layout/AppShell.tsx`
  - Added a **Payments** child link under the existing Leads item in
    the Project Manager group, with the same active-state handling.
- `apps/web/app/(staff)/project-manager/payments/page.tsx` (new) —
  filter bar (default last-30-day window, location id, provider,
  search), table (person link → `/persons/{uid}`, stage badge, amount,
  type badge, date, location), per-row **View raw** button that opens
  a `Dialog` rendering the verbatim payload as pretty JSON.

### Tests
- `tests/api/test_dashboard_pm_payments.py` (new, 4 tests):
  - SAFE row shape + no-PHI assertion (no `given_name` / `email` /
    `phone` keys; no provider payload keys like `patientId`, `notes`).
  - Window + location + provider + q + limit filter forwarding into the
    service (tenant id in the first positional arg).
  - Tenant-scope smoke (route hands `principal.require_tenant()` to
    every service call).
  - Empty payload edge case (amount/type/location/lead/consult fields
    all nullable in the row).
- `tests/api/test_ingest_inspector_raw_event.py` (new, 2 tests):
  - Verbatim payload round-trips, tenant id passed to
    `IngestService.get_raw_event`.
  - 404 with the PlatformError envelope when the tenant-scoped lookup
    misses (covers "another tenant's row is not readable" path).
- `tests/integration/test_tenant_isolation.py`
  - Added argument resolvers for the two new repository read methods so
    the Phase B cross-tenant safety net keeps covering them.
- `apps/web/tests/unit/PaymentsPage.test.tsx` (new, 3 tests):
  - Loading → rows render (assert person name, external id, currency,
    stage, location).
  - Filter refetch (selecting `carestack` in provider + clicking
    Filter issues a `/api/dashboard/pm/payments?...source_provider=carestack`
    request and the row swaps).
  - "View raw" opens the dialog and renders payload fields (`CS-TX-9001`,
    `PATIENTCREDIT`).

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/dashboard/pm/payments` | PM Payments list (tenant-scoped, SAFE fields) |
| GET | `/ingest/dev/inspector/raw-events/{event_id}` | Single raw event for drilldown |

## Safe-field set returned by the list

`id`, `person_uid`, `display_name`, `lead_status`, `consultation_status`,
`amount`, `kind`, `transaction_type`, `occurred_at`, `source_provider`,
`source_external_id`, `location_id`, `location_name`, `raw_event_id`.

No clinical free text, no patient identifiers beyond the resolved person
display name + `person_uid` (same safety level as `pm_leads`). The
raw-payload drilldown reuses the existing local-dev Inspector carve-out
(`packages/ingest/CLAUDE.md`) — no new PHI exposure surface.

## Verification

All green on the worktree:

| Check | Result |
| --- | --- |
| `make lint` | ✓ ruff clean |
| `mypy .` | ✓ 276 source files, no issues |
| `make test` | ✓ 944 passed |
| `cd packages/db && alembic check` (with env loaded) | ✓ no upgrade operations detected |
| `cd apps/web && npm run lint` | ✓ no warnings/errors |
| `cd apps/web && npx tsc --noEmit` | ✓ clean |
| `cd apps/web && npm run test` | ✓ 51 passed across 11 files |

`alembic check` needs the env loaded; ran via
`set -a; source <worktree>/.env; set +a; alembic check` (the worktree
ships without a copy of `.env`). The symlink I added during local
verification was removed before commit — the working tree has no
`.env*` changes (per the no-edit-.env rule).

## Risks

- Lead status lookup is Phase 1 1:1 (`OpsRepository.find_lead_by_person`)
  in the existing code; my batch `list_leads_for_persons` returns the
  newest row per person if multiple ever exist for one `person_uid`.
  Matches the same assumption as `OpsService.latest_consultations_for_persons`.
- `_location_name` swallows `Exception` (mirrors `pm_leads`) so a missing
  / different-tenant `location_id` reads as "Unknown" instead of 500.
- Row count is capped by `limit` (default 100, max 200) and unsorted by
  identity service caller order — output is newest-first by `occurred_at`
  from the repo; no pagination cursor (matches inspector list, not
  `pm_leads`). If the page grows past 200 we'll add offset/total.
- MSW handler does not implement every backend filter exhaustively; it
  covers what the FE test exercises. Real backend wins for prod.

## Do-not-merge conditions

- Do NOT merge if the `IntegrationCredentialService` env contract or
  any auth middleware lands an incompatible Principal type before this
  PR — re-run `mypy .` and `make test` against the latest main first.
- Do NOT merge while CI cannot run `alembic check` end-to-end on a
  branch without a checked-in `.env` (orchestrator should re-verify the
  drift step inside the canonical checkout if its CI image differs).

## Blockers / questions

None. All work is inside scope, no new schema/migration, no
destructive ops, no `.env*` edits.

## Suggested next task

After the orchestrator merges ENG-271, drop the Payments MSW handlers
(`apps/web/lib/msw/handlers.ts` + `apps/web/lib/msw/fixtures/payments.ts`)
once the FE is wired against the real `/dashboard/pm/payments` in
production builds — per `apps/web/CLAUDE.md` ("one handler per endpoint,
no zombies").
