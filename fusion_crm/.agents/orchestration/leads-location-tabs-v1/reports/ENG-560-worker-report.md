# ENG-560 — Backend: location-tab classifier + `location_tab` param on `/pm/leads`

- **Task:** ENG-560 — Backend: location-tab classifier + `location_tab` param on `/pm/leads`
- **Linear:** ENG-560 — https://linear.app/fusion-dental-implants/issue/ENG-560
- **Mission:** leads-location-tabs-v1
- **Runtime:** claude-code (Worker)
- **Branch:** `eng-560-eng-560` (isolated worktree off origin/main)
- **Task class:** contract_change → **draft PR only, blocked for Codex cross-runtime review before merge**
- **Status:** ✅ Implemented + verified. Do not merge until Codex review + operator deploy approval.

## Shared contract — READ THIS (for ENG-561 frontend)

**The response row DTO `DashboardPmLeadOut` is UNCHANGED.** `location_tab` is a
**pure server-side request filter**, not a new response field.

- **New request query param only:** `GET /pm/leads?location_tab=<galleria|fusion|el_dorado|cosmo>`.
  Optional; when omitted the endpoint behaves exactly as before (no regression to All/Linked).
- **No Zod *response* schema change needed.** The rows returned have the same shape as today.
- **ENG-561 must:** add `location_tab` to the request/query builder (and the request-side
  Zod input if one exists) with the 4-value enum + "all" (omit param). It must NOT expect a
  per-row `location_tab` field — the tab is a filter, not surfaced per row.

Rationale for keeping the DTO unchanged: the frontend need is "show only persons in tab X",
which a filter satisfies. Adding a per-row field would have been a response-contract change
requiring lockstep Zod edits with no consumer. Decided: pure filter.

## What changed

### `packages/ops/service.py`
- Added `OpsService.classify_location_tabs(tenant_id, person_uids, *, latest_consultations=None)
  -> dict[UUID, LocationTab]` — the classifier (business logic lives here).
- Added private `OpsService._location_tab_by_id(tenant_id)` — resolves `tenant.location.id →
  tab` via `short_name` using the existing `LocationService.list_locations` (no hardcoded UUIDs).
- Added module constants `LocationTab` (Literal), `_TAB_BY_LOCATION_SHORT_NAME`
  (GALLERIA→galleria, FUSION-ROS→fusion, FUSION-EDH→el_dorado, COSMO→cosmo),
  `_DEFAULT_LOCATION_TAB="galleria"`, and helper `_assigned_center_tab(center)`.
- New import: `from packages.tenant.service import LocationService` (ops→tenant is allowed per
  the `packages/CLAUDE.md` import matrix). Added `Literal` to the typing import.

**Precedence implemented exactly as the operator-fixed contract:**
1. Person with ≥1 consultation → **latest consultation by `scheduled_at`** (reuses
   `latest_consultations_for_persons`, which already applies the cancelled/provider_created_at/id
   tie-break). Its `location_id` → `short_name` → tab.
2. Else SF `Assigned_Center__c` (`ops.lead.extra->>'assigned_center'`, NBSP-normalized via the
   existing `_center_matches` mirror of `repository._lead_assigned_center_predicate`):
   "El Dorado Hills" → el_dorado; Roseville / Galleria OMS / empty / NULL / anything else →
   galleria default.

`fusion` and `cosmo` are reachable only via rule 1; `galleria` is the default; buckets are
mutually exclusive (1 person = 1 tab).

**Documented edge case (not in the spec, made explicit + tested):** a latest consultation whose
`location_id` is NULL or maps to no recognised short_name does NOT decide a tab — the person
falls through to rule 2, so every person still lands in exactly one bucket.

### `packages/ops/repository.py`
- **No change.** The classifier reuses existing data-only methods
  (`list_latest_consultations_for_persons` via `latest_consultations_for_persons`, and
  `list_leads_for_persons` via `latest_leads_for_persons`). No new repository method was needed;
  no business logic was added to the repository.

### `apps/api/routers/dashboard.py` (`pm_leads` handler)
- Added query param `location_tab: Literal["galleria","fusion","el_dorado","cosmo"] | None = None`.
- When set, the handler calls `ops.classify_location_tabs(...)` once (reusing the
  `latest_consultations` it already fetches) and drops any row whose person's resolved tab ≠
  `location_tab`. Applied in both the Salesforce-lead loop and the CareStack-link loop.
- `light_page` (page-sized fetch + `total_override`) is disabled when `location_tab` is set —
  same as the existing `q`/`status` filters — so the post-filter total/pagination stay correct.
- The route stays thin: validate → service → filter → DTO. No new business logic in the route.

### `tests/integration/test_dashboard_pm_leads_location_tab.py` (new, real Postgres)
Mirrors the `test_lead_source_explorer.py` style (fresh tenant, rolled back). 8 tests:
- latest-consultation-wins across two locations (EDH older + ROS newer → fusion);
- consultation overrides assigned_center (Roseville lead + FUSION-ROS consult → fusion);
- El Dorado raw path, plain space **and** the U+00A0 NBSP variant, no consult → el_dorado;
- null / empty / Roseville / Galleria OMS / no-lead, no consult → galleria;
- fusion/cosmo never hold a no-consultation raw lead (rule 2 only ever yields el_dorado/galleria);
- cosmo reachable only via a Cosmo consultation;
- consultation with null location_id falls through to assigned_center;
- empty person list → empty map.

## Tests run
- `ruff check packages/ops apps/api/routers/dashboard.py tests/integration/test_dashboard_pm_leads_location_tab.py` → **All checks passed.**
- `mypy packages/ops apps/api/routers/dashboard.py` → **Success: no issues found in 6 source files.**
- `pytest tests/integration/test_dashboard_pm_leads_location_tab.py -v` → **8 passed** (real Postgres on :5434).
- Regression: `pytest tests/integration/test_lead_source_explorer.py tests/ops -q` → 85 passed,
  **2 failed**. The 2 failures (`tests/ops/test_covering_opportunity.py`) are **pre-existing on
  clean HEAD** (verified via `git stash`): a mock-based test that doesn't populate the ENG-543
  `ConsultationOut.provider_carestack_id` / `source_status` fields. **Not caused by this change.**

## Verification status
✅ Lint, typecheck, and the new integration suite all green. Implementation matches the
operator-fixed precedence contract.

## Risks
- The classifier resolves `short_name → tab` per request via `LocationService.list_locations`
  (one extra query per `/pm/leads` call, only when `location_tab` is set). Locations are few
  (4); negligible cost.
- Tab correctness depends on `tenant.location.short_name` being exactly GALLERIA / FUSION-ROS /
  FUSION-EDH / COSMO. If a short_name drifts, that location's consults fall through to rule 2
  (→ galleria). Resolve-by-short_name (not UUID) is per the spec.
- `assigned_center` matching is substring + NBSP-normalized (reused contract); "El Dorado Hills"
  is the only non-default needle, consistent with the existing explorer behavior.

## Blockers / Needs decision
- None. Stayed inside owned paths (`apps/api/routers/dashboard.py`,
  `packages/ops/service.py`, `tests/integration/...`). `repository.py` and `schemas.py` were in
  scope but needed no change. No forbidden paths touched (`.env*`, alembic, `apps/web/**`,
  `packages/**` outside ops).

## Do-not-merge conditions
- **Contract change → draft PR only.** Requires Codex cross-runtime review before merge.
- **Do NOT merge / deploy without operator approval** — merge to main auto-deploys prod.
- ENG-561 (frontend) should land the `location_tab` query param in lockstep; this backend is
  backward-compatible (param optional) so it can merge first, but coordinate the tab UI.
