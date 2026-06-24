# Worker Fix-Pass Report — ENG-512 (Phase 1): address Codex review

- **Task id:** eng-512-fix
- **Linear:** ENG-512 — B1.4 — ad-level `marketing_cost_allocated` (cost-per-lead)
  <https://linear.app/fusion-dental-implants/issue/ENG-512/b14-marketing-cost-allocated-spend-lead-attribution-join>
- **Role / agent:** worker / claude-code (Opus 4.8)
- **Branch / worktree:** `eng-512-eng-512` /
  `…/revenue-intelligence-analytics-v1/worktrees/eng-512` (base `main`)
- **Mode:** fix-in-place — **NOT committed/pushed/merged/deployed.**

`Handoff: worker → orchestrator` — requesting **re-review** of the four review
findings below.

---

## TL;DR

All four Codex findings (3 blockers + 1 major) are fixed in place. Each fix has a
dedicated new unit test. **Verification gap:** `ruff` and `pytest` could **not be
executed** in this worker sandbox — the project venv lives at
`/Users/eduardkarionov/dev/Fusion_crm/.venv` (outside the worktree) and the
sandbox denies all code execution (`python3 -c …`, `rm`, even `/usr/bin/python3`
on a file inside the worktree are blocked; read-only `ls`/`which`/`pwd` work).
The worktree path resolves through a symlink to a location the execution gate
blocks, so the prompt's "DB + pytest are available here" did not hold in this
runtime. Logic was verified by close hand-tracing; tests must be run in CI / an
unblocked environment before merge (do-not-merge #1).

---

## Findings → fix → proving test

### Blocker 1 — incremental refresh over-allocation ✅
**Fix:** denominators are now computed over the **full attributed population**,
independent of `only_persons`. `build()` computes `full_lead_dates` for the whole
universe *before* narrowing to `only_persons`, via a new shared
`FactPatientJourneyBuilder._lead_date_for` (single source of the dating rule, so
the written `lead_date` and the allocator denominator never drift).
`_apply_cost_allocation` now takes `full_lead_dates`, builds allocator leads for
every dated person whose day falls in the (in-scope-derived) spend window, runs
`allocate` over that full set, and **writes cost only for the in-scope
`projected` rows** (full-population leads outside scope count toward the
denominator but are skipped on write).
- File: `packages/analytics/fact_builder.py`
- **Test:** `tests/analytics/test_fact_builder.py::test_incremental_refresh_denominator_uses_full_population`
  — 2 leads on ad `23856`/day ($100), `only_persons={p1}` → `p1` cost == **$50**
  (spend/2), and only `p1` is written.

### Blocker 2 — rounding over-allocation ✅
**Fix:** new `cost_allocation._split_cents(amount, shares)` does **cent-exact
largest-remainder** allocation: spend → integer cents → `base = cents // n` with
the first `cents % n` shares getting +1 cent, so the Σ of per-lead rounded
amounts == the group's spend cents **exactly** ($100/6 → 10000¢, never 100.02).
Both tiers (ad + campaign residual) use it. The builder now persists
`cost.amount` **verbatim** (removed the second independent `round(.,2)` at the
former `fact_builder.py:419`).
- Files: `packages/analytics/cost_allocation.py`, `packages/analytics/fact_builder.py`
- **Tests:** `tests/analytics/test_cost_allocation.py::test_cent_exact_indivisible_hundred_over_six`
  (Σ == 10000¢; split `[1666,1666,1667,1667,1667,1667]`; `allocated_total` cents
  == 10000), `::test_cent_exact_penny_over_three` ($0.01/3 → `[0,0,1]`, Σ==1¢),
  `::test_cent_exact_campaign_residual_indivisible` ($100/3 residual → `[3333,3333,3334]`).

### Blocker 3 — slug-collision mis-allocation ✅
**Fix (a):** `_build_slug_index` now detects collisions — a slug that resolves to
**>1 distinct external_id** is marked ambiguous and **dropped** from the index, so
a lead carrying it resolves to `None` → UNMATCHED (coverage reduction /
`spend_without_leads`), never silently assigned to a "last row wins" id.
**Fix (b):** in the allocator ad tier, a lead is ad-covered only when the resolved
ad's **parent campaign == the lead's resolved campaign** (or the lead has no
resolved campaign to contradict). A lead resolved to an ad in a *different*
campaign is dropped from that ad's group → falls back to its own campaign tier;
the ad's spend surfaces as `spend_without_leads`.
- Files: `packages/analytics/fact_builder.py` (a), `packages/analytics/cost_allocation.py` (b)
- **Tests:** `tests/analytics/test_fact_builder.py::test_build_slug_index_collision_is_ambiguous`
  (two ads, identical name-slug → `promo_video` resolves to neither; raw ids still
  resolve) + `::test_build_slug_index_non_colliding_names_resolve` (control);
  `tests/analytics/test_cost_allocation.py::test_ad_in_wrong_campaign_falls_back_to_campaign_tier`
  (+ `::test_ad_with_matching_campaign_is_ad_covered` control).

### Major 4 — D-1 window included today ✅
**Fix:** `import_recent_spend` now sets `end_date = today − 1` (settle on
completed days; today's spend is still accruing) and keeps the rolling lookback
`start = end − (days−1)` → default `days=3` ⇒ `[D-3, D-1]`. Docstring updated.
This is the fix the review prescribed (not a contract question), so applied
directly.
- File: `packages/ingest/meta_ads_ad_service.py`
- **Test:** `tests/ingest/test_meta_ads_ad_service.py::test_recent_window_settles_on_completed_days_d_minus_1`
  — asserts `end_date == today-1`, `start_date == today-3`, 3-day span.

---

## Files touched (this fix pass)

**Modified**
- `packages/analytics/cost_allocation.py` — `_split_cents` (cent-exact); ad-tier
  parent-campaign match filter; campaign-tier cent-exact; docstring.
- `packages/analytics/fact_builder.py` — `_build_slug_index` collision→ambiguous;
  `build()` full-population `full_lead_dates`; `_apply_cost_allocation(full_lead_dates)`
  full-denominator + write-only-in-scope + no second round; new `_lead_date_for`;
  `_project_person` uses it.
- `packages/ingest/meta_ads_ad_service.py` — D-1 window + docstring.
- `tests/analytics/test_cost_allocation.py` — +6 tests (cent-exact ×3, parent-campaign ×2 plus control).
- `tests/analytics/test_fact_builder.py` — +3 tests (incremental denominator, slug collision ×2) + import.
- `tests/ingest/test_meta_ads_ad_service.py` — +1 test (D-1 window) + `timedelta` import.

**Untracked temp files to delete before commit** (could not `rm` — execution gated):
- `_verify_alloc.py` — standalone logic mirror I wrote to self-check (this pass).
- `.find_head.py` — leftover from the prior build pass.
Both are untracked; they will not land unless `git add -A`.

---

## Verification

| Check | Status | Notes |
|---|---|---|
| `ruff check` (touched packages + tests) | ⛔ **could not run** | execution gated in sandbox (venv outside worktree; python denied) |
| Unit: allocator — cent-exact, parent-campaign, + existing | ⛔ not executed | logic hand-traced against `tests/analytics/test_cost_allocation.py` |
| Unit: builder — incremental denominator, slug collision, + existing | ⛔ not executed | hand-traced; existing tests confirmed still satisfied (see below) |
| Unit: ad ingest — D-1 window + existing | ⛔ not executed | `import_window` integration test unaffected (uses explicit window) |
| Integration / `alembic` | ⛔ not executed | unchanged this pass; still required pre-merge |
| No `phi` import / no spend mutation / `analytics` written only by builder | ✅ | nothing added imports `phi`; allocator is pure & read-only; builder writes only its own schema |

**Hand-trace of existing tests (confirmed still green):** `test_marketing_cost_allocated_auto_when_marketing_wired`
(LEAD_P → $100 single lead; DIRECT_P dated-but-unattributed → $0; EMPTY_P
unresolved; `spend_without_leads == 0.0`), `test_marketing_cost_unresolved_without_marketing_service`
(no-op), `test_manual_marketing_cost_survives_rebuild` (manual $4242 preserved),
and all allocator reconciliation/zero-lead/fallback/day-isolation tests
(cent-exact keeps the same totals for divisible cases; reconciliation now *exact*
not approx). `_split_cents` edge: amount 0.0 → all-zero shares (ad spent $0 still
covers its lead at $0); `zip(..., strict=True)` is safe (shares len == group len).

---

## Risks / residual
1. **Tests not executed here** — primary residual risk; the four fixes are
   logic-verified by trace only. CI / unblocked run required.
2. **Join match rate still unverified on real DB** (carried over from the
   original report) — the slug↔spend bridge coverage is unknown; fixes here make
   mismatches *fail safe more strictly* (ambiguous/cross-campaign → coverage
   reduction), so a low match rate now shows as more `spend_without_leads`, never
   wrong cost.
3. **Spend-window widening under incremental refresh:** the window is derived
   from in-scope lead days, so a refresh spanning a wide date range pulls a wider
   `ad_daily_spend`/`campaign_daily_spend` query. Bounded by the refresh set's
   own min/max day; acceptable at current volume (consistent with the builder's
   existing full-scan read posture).

## Do-not-merge conditions
1. **Run `ruff` + the full pytest suite (incl. the 10 new tests) + the
   integration test against the test Postgres** — green required (could not run
   in this sandbox).
2. Run `alembic upgrade head` + `alembic check` (no drift) + downgrade of
   `c5e7a9b1d3f2`; if the dev DB is upgraded, **downgrade back to `a1b2c3d4e5f6`**.
3. **Delete untracked temp files** `_verify_alloc.py` and `.find_head.py`.
4. Carried over: verify the real-DB spend↔attribution match rate before trusting
   `marketing_cost_allocated` as `auto` on the dashboard.
5. Not committed/pushed by the worker.

## Runtime telemetry note
The mission runtime dir (`~/.fusion-agent-orchestrator/<hash>/…runtime`) is
outside this worker's writable working directory (same symlink/sandbox boundary
that blocks execution), so I could not update `runtime.json` / `runlog.md`. This
report is the durable record; orchestrator should reflect the fix-pass handoff in
the runtime files.

`Handoff: worker → orchestrator` — fix pass complete, pending re-review +
unblocked verification run.
