# Shared Contracts — analytics-dashboards-v1 (ENG-468)

Task class: **contract_change** (multi-layer FE+BE + read-model semantics).
This is why the mission runs as a **sequential single-branch pipeline**, not
parallel worktrees — every dashboard touches the same shared paths.

## Shared paths (touched by multiple tickets — coordinate, additive only)
- `apps/api/routers/dashboard.py` — each dashboard adds its own endpoint(s).
- `apps/web/components/layout/AppShell.tsx` — each dashboard adds one nav entry
  to the new "Analytics" section + `allDevHrefs`.
- `apps/web/lib/api/` (client) — shared API client.
- Analytics read layer (new) — `packages/analytics/` (or extend `insight`).
  ENG-470 establishes it; later tickets extend it.

## Contract rules
- New endpoints live under the existing `/dashboard` router prefix
  (e.g. `/dashboard/analytics/marketing`) OR a new `/analytics` prefix — the
  ENG-469 doc + ENG-470 foundation decides; later tickets follow the precedent.
- Typed FastAPI `*Out` ⇄ Zod schema must match exactly (names + optionality);
  dates use `Datetime` from `apps/web/lib/api/schemas/common.ts`.
- Read-only. Aggregate metric definitions are a shared contract: keep metric
  meaning consistent with the ENG-469 mapping doc across all dashboards.

## Sequencing decision
ENG-470 (Marketing) goes first after ENG-469 because it extends the existing
`MarketingService` and naturally establishes: the analytics read-layer package,
the "Analytics" nav section, and the dashboard endpoint pattern. Subsequent
tickets build additively on the accumulated epic branch.
