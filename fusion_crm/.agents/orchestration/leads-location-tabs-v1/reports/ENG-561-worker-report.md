# ENG-561 — Frontend: 4 location tabs (default Galleria) + unified person card

- **Task:** ENG-561 — Frontend: 4 location tabs (default Galleria) + unified person card
- **Linear:** ENG-561 — https://linear.app/fusion-dental-implants/issue/ENG-561
- **Runtime:** claude-code (Worker)
- **Branch:** `eng-561-eng-561`
- **Base:** `eng-560-eng-560` (backend ENG-560, draft PR #207) — stacks on #207
- **PR:** #208 (draft, targets `eng-560-eng-560`) — https://github.com/alexanderantipov1/fusion_crm/pull/208
- **Task class:** normal, multi-layer (FE depends on backend contract) → Codex cross-runtime review before merge

## Summary
Extended the existing Project Manager → Leads page with four clinic **location
tabs** (`galleria | fusion | el_dorado | cosmo`), made **Galleria the default
active tab**, and added a **unified person card** that merges the Salesforce
lead(s) and the linked CareStack contact/consultation(s) into one
creation-ordered, expandable timeline. No new page was created (operator
decision: extend). The backend `location_tab` query param (ENG-560) is consumed
as a pure request filter — the response row DTO is unchanged.

## Touched files
| File | Change |
|------|--------|
| `apps/web/lib/api/schemas/dashboard.ts` | Added request-side `DashboardPmLeadLocationTabSchema` (4-value Zod enum) + inferred type. No response row schema change. |
| `apps/web/lib/api/hooks/useDashboard.ts` | Added optional `location_tab` to `DashboardPmLeadFilters` (typed by the new enum). Existing URLSearchParams serialization handles it (omitted when absent). |
| `apps/web/app/(staff)/project-manager/leads/page.tsx` | New `LeadTab` union incl. 4 location tabs; default tab → `galleria`; `LOCATION_TABS` config; single `locationQuery` (enabled only on a location tab) with its own offset; tab strip extended via a `TabButton` helper; header total/loading/error account for location tab; new `UnifiedPersonsView` + `UnifiedPersonCard` + `buildPersonTimeline` rendering merged SF→CareStack timeline. Linked tab keeps its existing two-column `LinkedPersonsView`. |
| `apps/web/tests/unit/ProjectManagerLeadsPage.test.tsx` | Updated stale "defaults to Linked" comment; added ENG-561 describe block: default tab = Galleria queries `location_tab=galleria` on first load (no `linked_only` leakage); switching to another location tab issues `location_tab=el_dorado`; unified card shows SF + CareStack together and expands to the merged timeline. |

## What changed (behavior)
1. **Tab strip:** `All leads | Linked SF + CareStack | Galleria | Fusion | El Dorado | Cosmo`.
2. **Default tab = Galleria** (was Linked). First render fires `/dashboard/pm/leads?location_tab=galleria`.
3. **Location tabs** fetch `/pm/leads?location_tab=<tab>` via `useDashboardPmLeads`, person-grouped, with the same `LinkedPagination` pattern as the Linked tab.
4. **Request contract:** `location_tab` added on the request side only (hook filter + Zod enum). `"all"`/`"linked"` ⇒ param absent. Response row DTO untouched.
5. **Unified person card:** one card per `person_uid`; collapsed shows name (links to `/persons/<uid>`), contact, location, and SF/CareStack presence badges; click/expand reveals the full creation-ordered SF→CareStack event path (lead created → events/appointments).

## Tests run + results
- `npm run lint` (next lint / eslint) → **No ESLint warnings or errors**
- `npm run typecheck` (tsc --noEmit, strict) → **clean** (note: `lint` is eslint-only in this repo; typecheck is a separate script — ran both)
- `npm run test -- ProjectManagerLeadsPage` → **5 passed**
- `npm run test` (full suite) → **118 passed / 20 files**

## Verification status
PASS — lint, strict typecheck, targeted + full vitest suite all green.

## Risks
- Unified card timeline is built client-side purely from existing row fields (`created_at`, `consultation_*`, `location_name`). It is presentation only — no business logic; tab semantics stay in the backend classifier (ENG-560).
- `location_name` shown on the card is whatever the row DTO already carries; the tab *bucket* is resolved server-side and not echoed per row (by contract).
- Location tabs do **not** set `linked_only` — they show every person the server buckets into that tab (linked or not), rendered as unified cards.

## Blockers / Needs decision
- None.

## Do-not-merge conditions
- **Draft only.** Stacks on ENG-560 (#207); do NOT merge until #207 merges (the live `location_tab` backend param ships there).
- Multi-layer change → **Codex cross-runtime review required** before merge.
- Merge to `main` auto-deploys prod — operator approval only. Do NOT merge/deploy from this worker.
