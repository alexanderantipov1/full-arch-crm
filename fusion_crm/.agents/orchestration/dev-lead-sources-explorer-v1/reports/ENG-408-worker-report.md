# Worker report — ENG-408

- **Task:** ENG-408 — PM Payments: auto-apply filters + lead-source filter + Source/Owner columns
- **Linear:** ENG-408 — https://linear.app/fusion-dental-implants/issue/ENG-408/pm-payments-auto-apply-filters-lead-source-filter-sourceowner-columns
- **Role / agent:** worker / claude-code (self-execute, canonical checkout)
- **Branch:** `eng-408-pm-payments-source-filter` (forked from `origin/main` @ 0ce1d87)
- **Worktree:** `.`
- **Allowed scope:** feature — `apps/web` payments page, `apps/api` dashboard router, `packages/ops` + `packages/interaction` read paths, `packages/ingest` SF lead projection; no migration, no deploy changes.

## What changed

1. **Auto-apply filters** (`apps/web/app/(staff)/project-manager/payments/page.tsx`)
   — the Apply/Filter button is gone; every control applies on change.
   `baseFilters` is now derived (`useMemo`) from the draft; free-text search
   debounces 400 ms; pagination resets to page 1 on any filter change. Reset
   stays.
2. **Lead-source resource filter** — new "Source" dropdown composed exactly
   like the Lead Sources explorer hierarchy (channel → source → medium →
   campaign, indented options with lead counts, fetched from
   `GET /ops/analytics/lead-sources/tree` unwindowed). Selecting a node sends
   `lead_channel` / `lead_source` / `lead_medium` / `lead_campaign` to BOTH
   `GET /dashboard/pm/payments` and `/summary`. Semantics: the period applies
   to the PAYMENT date; the node decides WHO (persons of the node's leads,
   regardless of lead age) — i.e. "cash by resource over the window".
   - ops: `OpsRepository.person_uids_for_source_node` +
     `OpsService.person_uids_for_lead_source_node` (no lead-creation window
     by design).
   - interaction: `person_uids` filter on list/count/summarize, bound as ONE
     PG array param (`= ANY(:ids)`) — no expanding IN (asyncpg param-limit
     safe for tens of thousands of ids); empty list = matches nothing.
   - route: `_resolve_lead_source_node_persons` composes the two domains;
     no cross-domain imports.
3. **Source + Owner columns replace Stage** — each row carries
   `lead_source_label` (explorer last-touch label via new public helper
   `explorer_source_label_for_lead`, also reused by the explorer drill-down)
   and `lead_owner` (`owner_name` → `owner_id` fallback via
   `owner_label_for_lead`).
4. **SF projection captures `Owner.Name`** (`packages/ingest/sf_lead_service.py`)
   — `owner_name` mirrors into `Lead.extra` on pull; the ENG-255 merge path
   backfills existing rows on the next re-pull/backfill. Until a prod lead
   backfill runs, the Owner column shows raw SF OwnerIds.

## Touched files

- apps/api/routers/dashboard.py
- packages/ops/repository.py, packages/ops/service.py
- packages/interaction/repository.py, packages/interaction/service.py
- packages/ingest/sf_lead_service.py
- apps/web/app/(staff)/project-manager/payments/page.tsx
- apps/web/lib/api/schemas/dashboard.ts, apps/web/lib/api/hooks/useDashboard.ts
- tests/api/test_dashboard_pm_payments.py (+ node-scope test)
- tests/integration/test_lead_source_explorer.py (+ node→persons→payments DB test)
- apps/web/tests/unit/PaymentsPage.test.tsx (auto-apply + resource-filter tests)

## Tests & verification

- `make lint` (ruff) — clean
- `mypy .` — clean (370 files)
- `make test` — 1491 passed (incl. new API + integration tests)
- `cd packages/db && alembic check` — no new operations (read-only feature)
- `npx tsc --noEmit`, `next lint` — clean
- `npx vitest run` — 108 passed (incl. 2 new payments-page tests)
- Live smoke on local API: all-time $6,066,435.67 / 2,945 payments /
  1,914 patients; facebook node $132,854 (33), google $244,855 (79);
  facebook last-30d $26,254 (11) — the requested "which resources produced
  cash this period" cut. Ghost node → 0 rows. Heavy nodes (facebook,
  unknown/unknown) ≈ 0.4 s — no ENG-400-style correlated-subquery regression.

## Risks

- Owner column shows SF OwnerId (`005…`) until leads are re-pulled with the
  new projection; a prod `fusion-job-backfill --entities sf_leads` re-run
  after deploy populates names dataset-wide.
- The Source dropdown renders the full explorer hierarchy as a flat native
  select (hundreds of options); acceptable for the PM tool, a searchable
  combobox is a possible follow-up.
- `lead_source` param name on payments endpoints means the EXPLORER label
  (lowercase, last-touch), unlike `/dashboard/pm/leads` where it is the
  PM-label chain — documented in route docstring and hook types.

## Blockers / questions

- None. Commit pending owner approval (repo rule: never commit unless asked).

## Suggested next task

- Prod deploy + SF lead backfill re-run to populate `owner_name`, then
  visual check of /project-manager/payments in prod.

## Do-not-merge conditions

- None known; feature is read-only aggregation, no migration.
