# Worker report — ENG-410

- **Task:** ENG-410 — PM Payments: group same-day payments per person with expandable legs
- **Linear:** ENG-410 — https://linear.app/fusion-dental-implants/issue/ENG-410/pm-payments-group-same-day-payments-per-person-with-expandable-legs
- **Role / agent:** worker / claude-code (self-execute, canonical checkout)
- **Branch:** `eng-410-pm-payments-day-groups` (forked from `origin/main` @ cc6084c)
- **Worktree:** `.`
- **Allowed scope:** feature — `apps/api` dashboard router, `packages/interaction` read paths, `apps/web` payments page/schemas/hooks; no migration.

## What changed

1. **Server-side same-day grouping** — new
   `GET /dashboard/pm/payments/groups`: rows collapse by
   `(person_uid, kind, clinic-local day)`; CareStack splits one
   real-world payment into per-invoice legs minutes apart. Group key uses
   `America/Los_Angeles` calendar day (constant `_CLINIC_TZ` with a
   tenant-tz follow-up note), so evening legs crossing UTC midnight stay
   in one group. Kinds never merge (a same-day refund is its own row).
   Pagination counts GROUPS; groups order newest-first by latest leg.
2. **Legs embedded, byte-identical to flat rows** — the row-building
   pipeline was extracted into `_build_payment_items` and shared by both
   endpoints; each group carries full leg DTOs (invoice, time, raw
   drill-down) plus person-level enrichment (lead source/owner ENG-408,
   balance ENG-306) on the head.
3. **Frontend** — grouped view is the DEFAULT with a "Group by day"
   toggle back to flat. Multi-leg groups render one row (summed amount,
   `Payment ×N` badge, "N legs · same day", invoice/location roll-ups)
   with chevron expansion into the leg rows; single-leg groups render as
   plain rows. Flat и grouped queries are gated TanStack hooks.
4. **Repository** — `list/count_payment_event_groups_for_dashboard`
   share `_payment_events_dashboard_filter` (window, provider, location,
   search, include_applied, ENG-408 person scope), so a filtered page
   never shows legs the filter excluded; tenant-isolation sweep resolver
   added.

## Touched files

- packages/interaction/repository.py, packages/interaction/service.py
- apps/api/routers/dashboard.py (row-builder extraction + groups endpoint + DTOs)
- apps/web/lib/api/schemas/dashboard.ts, apps/web/lib/api/hooks/useDashboard.ts
- apps/web/app/(staff)/project-manager/payments/page.tsx
- tests/api/test_dashboard_pm_payments.py (+ groups test)
- tests/integration/test_pm_payments_pagination.py (+ real-PG grouping test incl. UTC-midnight crossing)
- tests/integration/test_tenant_isolation.py (resolver for the new read method)
- apps/web/tests/unit/PaymentsPage.test.tsx (grouped default + expansion test; flat tests opt out)

## Tests & verification

- ruff, mypy (372 files) — clean
- `make test` — 1496 passed (tenant-isolation sweep covers the new method)
- `alembic check` — clean (read-only)
- tsc, eslint — clean; vitest — 109 passed
- Live smoke (local): since Jun 10 — 57 groups, 6 multi-leg; the owner's
  example collapses correctly: Christopher Bustos Jun 11 → ONE row
  $1,294 ×3 ($344 #10855 + $450 #10854 + $500 #10852); Sophia Bezuglov →
  $648.20 ×2; Nadezhda Rotkina → $4,200 ×2.

## Risks

- Clinic-local day is a hardcoded `America/Los_Angeles` constant —
  fine single-region; needs a tenant timezone setting if a second
  region onboards.
- Summary bar still counts individual recorded payments ("Payments"
  tile = legs, not groups) — intentional (cash math unchanged), noted
  for the owner.

## Blockers / questions

- None. Commit pending owner approval.

## Suggested next task

- Owner visual check locally, then commit → PR → deploy (same path as ENG-408).

## Do-not-merge conditions

- None known; read-only aggregation, no migration.
