# Shared Contracts — revenue-intelligence-analytics-v1 (ENG-504)

Task class: **contract_change** (new DB schema, new fact table, new shared filter
contract consumed by 14 pages). Foundation (B0) is a **sequential single-branch
pipeline**; pages (B2) may parallelize once B0 contracts are frozen.

## New durable contracts (additive, coordinate carefully)
- **`analytics` schema** — new 9th-tier read-model schema (operator-approved
  invariant #1 addition). Rebuildable projection only; never written outside the
  fact builder; never a source of truth.
- **`analytics.fact_patient_journey`** — one row per `person_uid`; all spec
  columns + `location_id`; nullable except `person_uid`; per-field provenance
  (source, method `auto`/`manual`/`unresolved`, confidence, resolved_at).
- **`AnalyticsFilters` + `TimeRange` DTO** (ENG-507) — the single shared filter
  contract every page endpoint consumes. Location supports aggregate (default)
  and per-location (`location_id`).
- **Derived-metric functions** (ENG-507) — single definition of cost-per-stage,
  revenue-per-stage, ROI, conversion ratios. No page redefines a metric.
- **Provenance precedence** (ENG-513): `manual` > `auto` > `unresolved`. The fact
  rebuild must never clobber a manual override.

## Shared paths (touched by multiple tickets — additive only, sequence)
- `apps/api/routers/dashboard.py` — each page adds its own `/dashboard/analytics/*`
  endpoint; the shared filter DTO is added once (ENG-507).
- `apps/web/components/layout/AppShell.tsx` — each page adds one nav entry.
- `packages/analytics/**` — shared fact service, filter resolver, derived metrics.
- `packages/db/alembic/versions/**` — new revisions chained in one branch.
- `apps/web/lib/api/schemas/**`, `apps/web/lib/api/hooks/**` — Zod + TanStack.

## Contract rules
- Endpoints live under the existing `/dashboard` router prefix; routes compose,
  logic in `packages/analytics` (invariant #5).
- Typed FastAPI `*Out` ⇄ Zod must match exactly; dates as datetime.
- Read-only. No raw provider payloads in responses or exports. Logs PHI-free.
- Agents never touch the DB (invariant #6). Person spine `identity.person.id`.
- Migrations immutable once shipped; new change → new revision.

## Sequencing decision
ENG-505 → ENG-506 → ENG-507 first and in order (schema, then builder, then the
filter/metric contract). ENG-508 after ENG-507. B1 enablement runs alongside once
the fact contract (ENG-505) is frozen. B2 pages start after ENG-507; each page
also waits on its dimension's B1 ticket for full data (ships "no data" otherwise).
B3 verification last.
