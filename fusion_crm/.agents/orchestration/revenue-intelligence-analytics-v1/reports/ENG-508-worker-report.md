# ENG-508 (B0.4) — CSV/Excel export + metric→patient drill-down — Worker Report

- **Linear:** ENG-508 — B0.4 CSV/Excel export + drill-down
- **Mission:** revenue-intelligence-analytics-v1
- **Branch / worktree:** `eng-508-eng-508` (isolated worktree off `main` @ `9b2e485`)
- **Task class:** `normal` (new service + routes + `openpyxl` dep; **no** schema/migration)
- **Status:** ✅ Build complete, review-ready. **NOT committed / pushed / merged** (build-only mandate).

---

## TL;DR

Implemented CSV + XLSX export for the four fact-backed analytics pages
(executive / funnel / revenue / cohort) and a metric→`person_uid` drill-down
endpoint, all honoring the shared `AnalyticsFilters` (incl. `location`). Export
wraps `AnalyticsPagesService` so a file is byte-for-byte the on-screen page's
numbers. `ruff` + `mypy` clean; new unit tests pass; integration tests are
structurally complete and skip cleanly (no DB settings in the sandbox). **No
migration added** (verified — no `models.py` / `versions/` change).

---

## ⚠️ Important deviation from the task brief (read first)

The brief said two artifacts were "in the repo" and to port them:
`ENG-508-recovery-worker-report.md` and `ENG-508-carryover.patch`.

**Neither exists.** They are not in this worktree, and `git log --all` shows
they were **never committed to any branch**. The uncommitted carryover work
lives only in the working tree of a *separate* worktree
(`…/worktrees/ENG-508-recovery`, branch `eng-508-eng-508-recovery` @ `e0ac851`),
which is outside this session's sandbox **and** is another session's dirty tree
— per `PARALLEL_WORK_POLICY.md` I must not reach into it.

**Decision:** reconstructed ENG-508 from scratch against current `main`,
following the design described in the brief and the established `packages/analytics`
patterns. The result satisfies the same acceptance criteria and is reconciled
to the *current* page DTOs (not the stale `e0ac851` base). If the orchestrator
intended a literal patch-port, the carryover patch needs to be surfaced into the
repo first; otherwise this reconstruction supersedes it.

---

## Changed / new files

**New (4):**
- `packages/analytics/exporters.py` — pure, format-only serializers
  (`ExportTable` → CSV / XLSX bytes). `openpyxl` imported **lazily** inside
  `to_xlsx`; CSV path never imports it. `EXPORT_MAX_ROWS = 50_000` defensive cap
  (raises `ValidationError`, never silently truncates a financial export).
- `packages/analytics/export_service.py` — `AnalyticsExportService`, wraps
  `AnalyticsPagesService` and shapes each page DTO into tables. No independent
  query → export == on-screen numbers. Returns `ExportResult(filename,
  media_type, content)`.
- `tests/analytics/test_exporters.py` — 6 pure unit tests.
- `tests/integration/test_analytics_export.py` — 6 real-PG tests (skip-clean).

**Modified (6):**
- `packages/analytics/queries.py` — added `FactAnalyticsQueries.metric_person_uids(...)`
  (drill-down query: cohort + shared dimension filters + metric predicate,
  ordered by `person_uid`, hard-capped, returns `(uids, total)`) plus the
  `DRILLDOWN_METRICS` registry / `_drilldown_predicate` helper.
- `packages/analytics/metrics_service.py` — added
  `AnalyticsPagesService.metric_drilldown(...)` (resolves window/tz, clamps to
  `DRILLDOWN_HARD_CAP`, builds `MetricDrilldownOut`) + the
  `DRILLDOWN_DEFAULT_LIMIT=500` / `DRILLDOWN_HARD_CAP=1000` constants.
- `packages/analytics/schemas.py` — added `AnalyticsExportPage`,
  `AnalyticsExportFormat`, `DrilldownMetric`, `MetricDrilldownOut`.
- `apps/api/dependencies.py` — `get_analytics_export_service` (wraps the pages
  service) + import.
- `apps/api/routers/dashboard.py` — two endpoints (below) + imports.
- `pyproject.toml` — added `openpyxl>=3.1` (lazy XLSX dependency).
- `uv.lock` — `uv lock` regenerated: added `openpyxl 3.1.5` + `et-xmlfile 2.0.0`
  only (25 insertions, no other churn).

---

## Endpoints added

- `GET /dashboard/analytics/export/{page}` — `page ∈ {executive,funnel,revenue,cohort}`,
  `?format=csv|xlsx` (default `csv`) + the full shared filter bar. Returns the
  bytes with `Content-Disposition: attachment`. Thin route: maps query params →
  `AnalyticsFilters` → `AnalyticsExportService` (no logic in the route).
- `GET /dashboard/analytics/drilldown?metric=<metric>` — shared filter bar +
  `limit` (`ge=1, le=1000`, default 500). Returns `MetricDrilldownOut`
  (`metric, window, filters, total, returned, truncated, person_uids`). Route
  delegates to `AnalyticsPagesService.metric_drilldown`.

Drill-down metrics: the 8 funnel-stage keys + `patients` (whole cohort) + `paid`
(non-null `revenue_amount`, mirrors the revenue page's `case_count`). All anchor
on the same `lead_date` cohort as the pages, so a drill-down list reconciles
with the on-screen count.

---

## Reconciliation against current `main`

- Export wraps `AnalyticsPagesService` (the live page service) — it does **not**
  re-query, so it automatically tracks any page-DTO evolution. Verified the
  current page DTOs: `ExecutiveOverviewOut`, `FunnelStagesOut`,
  `RevenueIntelligenceOut`, `CohortAnalyticsOut` are all covered.
- `fact_patient_journey` gained `case_type` / `marketing_cost_allocated` /
  `surgery_*` since the patch base. These are **not** surfaced as new *page-level*
  columns on the four exported page DTOs today (they are a revenue *dimension* /
  per-row enrichment / honest-zero funnel stages, all already represented). The
  surgery stages (`surgery_scheduled` / `surgery_completed`) **are** exported as
  funnel rows and are drillable metrics. No page DTO column was dropped from any
  export.
- The self-describing `Report` header table in each export echoes the exact
  applied filters + resolved window (incl. `location_id`), so an exported file
  records the filter selection it came from.

---

## Invariants honored

- **No business logic in routes** — routes map params → `AnalyticsFilters` →
  service; all shaping/serialization in service/exporters.
- **Services only, read-only over the fact** — drill-down adds one read query;
  the builder stays the only writer. No model/schema change.
- **No PHI / no raw payloads** — exports carry aggregates + reference ids + dates
  + money; drill-down carries only `person_uid`. No names/clinical text.
- **PHI-free logs** — no logging of row content was added.
- **Lazy `openpyxl`** — CSV works without it; XLSX without the dep raises a clean
  `PlatformError` (unit-tested by blocking the import).
- **Bounded output** — drill-down hard cap 1000 (service clamps regardless of
  query param); export defensive row cap 50k.

---

## Tests + results

| Suite | Result |
|---|---|
| `ruff check` (touched packages + tests) | ✅ All checks passed |
| `mypy packages/analytics apps/api/routers/dashboard.py apps/api/dependencies.py` | ✅ Success, no issues (20 files) |
| `pytest tests/analytics/test_exporters.py` | ✅ 6 passed |
| `pytest tests/analytics` (regression) | ✅ 145 passed |
| `pytest tests/integration/test_analytics_export.py` | ⏭️ 6 skipped — "database settings unavailable" (no `.env`/PG in sandbox) |
| `cd packages/db && alembic check` | ⏭️ Could not run — needs DB Settings; **but no migration/model change exists** (drift provably clean via `git status`) |

Unit tests cover: CSV value formatting + multi-section layout, XLSX one-sheet-per-table
round-trip, the row-cap raise, CSV-works-without-openpyxl + XLSX-degrades, and
service filter pass-through. Integration tests cover: export carries exact page
numbers, **location filter pass-through** (numbers change + echoed in header),
revenue/cohort/executive exports, valid XLSX workbook, and drill-down
filtering / deterministic order / location scoping / size bound + `truncated`.

---

## Verification gaps / risks

1. **Integration tests not executed** — the sandboxed worktree has no `.env`, so
   `Settings` (SECRET_KEY/DATABASE_URL/REDIS_URL) won't construct and the real-PG
   tests skip. They mirror the proven `tests/integration/test_analytics_pages.py`
   fixtures (same seed shape), so confidence is high, but they should be **run
   against the dev DB before integration**.
2. **`alembic check` not executed** for the same reason. Mitigated: zero files
   under `packages/db/.../versions/`, `packages/analytics/models.py` untouched
   (`git status` confirms) — no drift is possible from this change set.
3. **Route registration not smoke-tested at runtime** (app startup needs
   Settings). `mypy` validates the router imports/types; the `{page}` path param
   uses a `Literal` (FastAPI ≥0.115 supports Literal path/query validation) and
   `format` is aliased to avoid shadowing the builtin.
4. **Runtime telemetry** (`runtime.json` / `runlog.md` / `board.md`) lives one
   directory above `worktrees/`, **outside this session's sandbox** — could not
   be updated from here. Orchestrator should reflect this completion.

---

## Documented gap (by design)

**Marketing-page export** is intentionally **not** built — its page does not exist
yet (ENG-516 builds it). When that page ships, add a `"marketing"` literal to
`AnalyticsExportPage` + a `_marketing_tables(...)` shaper. No other change needed.

---

## Do-not-merge / handoff conditions

- **Build-only.** No commit / push / PR / merge / deploy performed (per mandate).
- **Run the integration tests + `alembic check` against the dev DB** before
  integration (they only skipped here for lack of env).
- **Cross-runtime (Codex) review required** before integration.
- Merge to `main` == **prod deploy + prod migration path** → **operator-gated**.
  This change adds no migration, but the merge-gate policy still applies.
- New runtime dependency `openpyxl>=3.1` — already added to `uv.lock`; ensure the
  deployed image rebuilds against the updated lock before the XLSX path is
  exercised in prod. CSV path is unaffected if it's missing.
