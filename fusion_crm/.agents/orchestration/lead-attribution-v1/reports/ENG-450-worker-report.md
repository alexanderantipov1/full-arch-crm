# Worker Report — ENG-450 (Block D: Funnel analytics by attribution chain level)

- **Task:** D — Funnel analytics by attribution chain level
- **Linear:** ENG-450 — https://linear.app/fusion-dental-implants/issue/ENG-450 (parent epic ENG-446)
- **Role / agent:** worker / claude-code
- **Branch / worktree:** `eng-447-lead-attribution-v1` / `~/Desktop/fusion_crm_attribution`
- **Task class:** contract_change (new `attribution` schema already shipped in A; D adds read-only analytics endpoints — no new tables)
- **Integration mode:** part of the single epic PR (A–D), Sync → D → one PR.

## What changed

### Pre-req: branch sync (ENG-446 housekeeping)
- Merged `origin/main` (25 commits ahead: ENG-425 ingestion + ENG-433 messenger + ENG-439 enrichment) into the branch. Commit `a24a6ee`.
- Resolved 3 additive conflicts (init-schemas.sql, packages/CLAUDE.md, alembic env.py) by keeping BOTH the new `enrichment` (main) and `attribution` (ours) schemas.
- Alembic merge revision `4c1fe01ca169` (Revises `b69bce1e2195` + `f6a7b8c9d0e1`) → single head restored.

### Block D backend (commit `e6e6e05`)
- `GET /attribution/analytics/tree` — hierarchical lead→consult funnel sliced by the resolved vendor → channel → campaign chain; parents aggregate children; siblings leads-desc; `needs_review` reported separately as the explicit gap.
- `GET /attribution/analytics/leads` — drill-down of leads behind one node (`__none__` sentinel slug = NULL/unassigned bucket).
- `AttributionRepository`: `count_leads_by_chain`, `count_needs_review`, `map_persons_to_chain`, `list_lead_attributions_for_node` (single GROUP BY; labels resolved in the service from the node vocabulary — no self-joins).
- `OpsService.consult_counts_by_person` (+ repo `count_consultations_by_person_status`) — per-person (scheduled, attended) so the route attributes consults without importing `ops.Consultation` into attribution.
- Cash (interaction) + consults (ops) passed per-person by the route; attribution attributes them to each person's resolved node — mirrors the lead-source explorer's cross-domain discipline.

### Block D frontend (commit `ccd82a5`)
- `lib/api/schemas/attribution.ts` — Zod contract mirroring the Python DTOs.
- `lib/api/hooks/useAttribution.ts` — `useAttributionTree` + `useAttributionNodeLeads`.
- `app/(staff)/project-manager/attribution/page.tsx` — expandable funnel tree + drill-down dialog; `needs_review` as a prominent badge. Replaces the dashboard "unknown" bucket.
- `AppShell`: "Attribution" link under Project Manager.
- No MSW handlers (real endpoints exist — per feedback_msw_delete_on_landing).

### Tests (commit `d7ea433`)
- `tests/attribution/test_tree.py` — tree rollups/sort, cash+consult attribution, drill-down slug→id + `__none__`, unknown-slug → NULL bucket, identity+cash enrichment, empty-tree.

## Tests run & results
- Backend: `tests/attribution/` **31 passed**; `tests/ops/` (service/consult/source_tree) **45 passed**. ruff clean.
- Real-DB smoke against a fresh `attr_verify` DB: rollups, needs_review exclusion, cash/consult attribution, drill-down + NULL bucket all correct (smoke script deleted after).
- Migrations: `init-schemas.sql` + `alembic upgrade head` walk the full chain on a fresh DB and converge at `4c1fe01ca169`; attribution tables created.
- Frontend: `tsc --noEmit` clean; `next lint` clean on new files.

## Verification status
- Code-complete and locally verified. **Not yet run against real production-scale data** (needs `resolve_attribution.py --all` on a DB with the real lead set to measure the live `needs_review%`). Recommended before merge per feedback_verify_with_real_data_before_merge.

## Risks
- The tree v1 nests vendor → channel → campaign only (ad_set/ad/form/agent depth deferred — documented follow-up); deeper levels exist in the schema and resolver.
- The tree is unwindowed (no date filter v1) — shows the full resolved population, which is the "0% unknown" intent. A period filter is a follow-up.
- `needs_review%` against real data unknown until the resolver runs at scale.

## Blockers / questions
- None blocking. Open decision: run the resolver on real data to measure needs_review% before or after merging the PR.

## Suggested next task
- Open the single epic PR (A–D) and assign a **Codex cross-runtime review** (contract_change gate: new schema + cross-domain wiring).
- Then run `resolve_attribution.py --all` on real data, measure needs_review%, iterate mapping rules.

## Do-not-merge conditions
- Do not merge before the Codex cross-runtime review (contract_change gate).
- Do not merge before the alembic merge revision is confirmed on the PR's CI (single head + clean upgrade).
