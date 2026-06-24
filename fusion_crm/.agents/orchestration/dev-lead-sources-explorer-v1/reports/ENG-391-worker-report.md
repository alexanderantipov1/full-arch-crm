# ENG-391 Worker Report — DEV Lead Sources explorer

- **Task:** ENG-391 — DEV Lead Sources explorer: hierarchical source tree with
  funnel counts and lead drill-down
- **Linear:** ENG-391 —
  https://linear.app/fusion-dental-implants/issue/ENG-391/dev-lead-sources-explorer-hierarchical-source-tree-with-funnel-counts
- **Role / agent:** worker / claude-code (self-execute, ENG-381/382/384 precedent)
- **Branch / worktree:** `codex/eng-371-manager-answer-layer-v1` / canonical checkout
- **Allowed scope:** packages/ops, packages/interaction, apps/api/routers/ops.py,
  apps/web (schemas, hooks, page, nav), tests

## What changed

Backend:

- `packages/ops/repository.py` — `_lead_medium_label()` / `_lead_campaign_label()`
  label expressions; `count_lead_funnel_by_source_tree` (leads grouped by
  source → utm_medium → utm_campaign with period + search filters);
  `count_consultation_funnel_by_source_tree` (consultations joined to leads via
  `person_uid`, grouped by node + status); `map_persons_to_source_nodes`
  (person → node attribution for revenue); `list_leads_for_source_node`
  (paginated drill-down matching the same coalesced labels).
- `packages/ops/schemas.py` — `LeadSourceNodeOut` (recursive),
  `LeadSourceTreeOut`, `LeadSourceLeadItemOut` (attribution allowlist, notes
  excluded), `LeadSourceLeadListOut`. Node/tree carry `collected_amount`.
- `packages/ops/service.py` — `get_lead_source_tree` (tree builder, rolls
  children up, leads-desc ordering; accepts `collected_by_person` dict so ops
  never imports interaction), `list_leads_for_source_node`,
  `_LEAD_ATTRIBUTION_EXTRA_KEYS` allowlist, SF ISO parser.
- `packages/interaction/repository.py` + `service.py` —
  `sum_collected_by_person` / `collected_by_person`: net Collected per person
  (recorded − refunded/reversed, `payment_applied` excluded — same formula as
  `get_treatment_payment_aggregate`; no classification change, paymentsDoc
  untouched).
- `apps/api/routers/ops.py` — `GET /ops/analytics/lead-sources/tree` (wires
  interaction collected dict into ops service) and
  `GET /ops/analytics/lead-sources/leads`. Prod-routable FastAPI routes; no
  Next route handlers.

Frontend:

- `apps/web/lib/api/schemas/leadSources.ts` (+ index export) — Zod contract.
- `apps/web/lib/api/hooks/useLeadSources.ts` — TanStack Query hooks.
- `apps/web/app/(staff)/dev/lead-sources/page.tsx` — DEV tab: expandable tree
  (source › medium › campaign), debounced search, period presets, per-node
  Leads / Scheduled / Attended / Collected / Conv. columns, drill-down dialog
  with paginated lead list (created time, status, person link, attribution
  details).
- `apps/web/components/layout/AppShell.tsx` — "Lead sources" DEV menu item.
- No MSW handler created (real endpoint shipped in the same change).

Tests:

- `tests/ops/test_service.py` — 6 new unit tests (tree build/roll-up/sort,
  consult-only nodes, attribution allowlist, provider-time fallback,
  collected attribution, empty-cash skip).
- `tests/integration/test_lead_source_explorer.py` — 4 DB-backed tests
  (grouping + person_uid join, search/period filters, drill-down pagination +
  unknown bucket, Collected per person + node mapping with payment_applied
  exclusion).
- `tests/integration/test_tenant_isolation.py` — Phase B resolver for
  `list_leads_for_source_node` (auto-discovered by the isolation sweep).
- `apps/web/tests/unit/LeadSourcesPage.test.tsx` — tree render + expand,
  totals incl. Collected, drill-down dialog + query params.

## Verification

- `ruff check` — clean; `mypy` — clean (ops, interaction, router).
- Full backend pytest: **1476 passed** (incl. 204 tenant-isolation params).
- `alembic check` — no drift (read-only feature, no migration).
- Web: `tsc --noEmit` clean, `next lint` clean, vitest **103 passed (18 files)**.
- Live smoke on local stack (127.0.0.1:8000): tree returns real funnel —
  e.g. Google: 4,334 leads / 149 scheduled / 302 attended / $233,709 collected,
  campaign level populated; drill-down returns 2,928 cpc leads with full
  attribution (gclid, utm_term, sf_lead_id).

## Risks

- Tree/leads endpoints aggregate tenant-wide on demand; collected-by-person is
  one grouped query (~persons-with-payments rows in memory). Fine for the DEV
  tab; add caching if it graduates to the manager dashboard.
- Phase 1 person↔lead is 1:1; if that ever fans out, consultation counts and
  collected attribution can double-count (documented in repository docstrings).
- Consultation counts are not period-filtered themselves — the period scopes
  the LEAD side (node membership), revenue/consults follow the person. This is
  the agreed semantic ("сколько за ними закреплено сейчас").

## Blockers / questions

- None technical. Commit + Linear Done pending owner approval.

## Suggested next task

- Optional: location/clinic filter (assigned_center) and chair/treatment stage
  as a fourth funnel column when the marketing dashboard graduates from DEV.

## Do-not-merge conditions

- None known; feature is additive and read-only.
