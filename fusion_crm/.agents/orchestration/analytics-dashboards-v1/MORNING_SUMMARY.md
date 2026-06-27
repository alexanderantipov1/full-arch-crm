# Morning Summary — analytics-dashboards-v1 (ENG-468)

**Status: all 6 child tickets complete on branch `eng-468-analytics-dashboards`
(local commits, not pushed).** Push + PR + live browser render + Codex
cross-runtime review are left for you (per your overnight instructions).

## What got built (5 dashboards + the mapping doc)

| Ticket | Page | Commit | Verify |
|---|---|---|---|
| ENG-469 | `docs/analytics/dashboards-mapping.md` | `1666c57` | doc |
| ENG-470 | `/analytics/marketing` | `cc593c0` | ruff+mypy+pytest 3 |
| ENG-472 | `/analytics/funnel` | `f3caccb` | ruff+mypy+pytest 3 |
| ENG-471 | `/analytics/seo` | `b4c53bc` | ruff+mypy+pytest 3 |
| ENG-473 | `/analytics/sales` | `3a00c8e` | ruff+mypy+pytest 4 |
| ENG-474 | `/analytics/calls` (shell) | `85387dc` | ruff+mypy+pytest 3 |
| ENG-473 fix | tenant-isolation sweep resolver | `02a48f3` | isolation green |

All five pages are in a new **"Analytics"** left-nav section. Endpoints live
under `/dashboard/analytics/*` (thin composers in `apps/api/routers/dashboard.py`).
New aggregation reads went into the owning domain services (marketing / ops /
interaction); cross-domain composition stays in `apps/api` — **no new
`packages/analytics/` domain** (would breach invariant #3). No new migrations
(zero model/column changes).

## Verification status
- **Epic-touched files: ruff clean, mypy clean (all), every per-ticket
  integration test green on real Postgres.** Zod⇄Pydantic parity verified
  field-for-field for all 5 endpoints.
- `make lint` / `make test` on the whole branch show failures that are **100%
  pre-existing on the base marketing branch (`eng-465`, PR #161)** — NOT
  introduced by this epic. Verified by running the same tests on `eng-465`:
  - 9 ruff errors in 8 files (funnel.py, persons.py, actor/service.py,
    responsibility_resolver.py, a backfill script, 3 test files).
  - 10 pytest failures: 3 `workflow_ready` redaction/e2e + 7 tenant-isolation
    (RecordAnnotation, Ingest×2, Marketing get_×4 — all missing Phase-B
    resolvers on the base).
  - **The epic adds zero new failures** once `list_sales_consultations` was
    registered (`02a48f3`).
- `alembic check` errors with "Can't locate revision 4c1fe01ca169" — the known
  **local multi-branch dev-DB artifact** (the dev DB is stamped at the
  lead-attribution merge revision, which isn't on this branch). The epic adds
  no migrations, so there is no real drift. See
  `blocker_alembic_broken_chain_main`.

## Decisions made overnight (see decision-log.md)
1. **Base = `eng-465-marketing-web-analytics`** — `marketing.*` is not on `main`
   yet (PRs #160/#161 unmerged); the dashboards need those tables. The epic PR
   will carry the marketing commits until #160/#161 merge.
2. **ENG-475 filed** (channel/center/TC parity) — needs YOUR business config
   (canonical channel list, TC→center map, per-arch pricing). Overnight the
   dashboards ship google/facebook/other channels and render center/TC as
   explicit "not configured" cards (no fake zeros). **This is the main product
   gap vs the legacy Replit funnel.**
3. **No `packages/analytics/` domain** (invariant #3) — compose in `apps/api`.

## Needs your attention (morning)
1. **Push + open PR(s)** for `eng-468-analytics-dashboards`. Note the base-branch
   dependency: it sits on top of `eng-465` (marketing). Either merge #160/#161
   first, or PR this against the marketing branch.
2. **Live render check** — run the dev stack (127.0.0.1, ports 5434/6380) and
   open each `/analytics/*` page; eyeball spend / sessions / funnel / pipeline
   numbers vs the Replit dashboards for one month.
3. **Codex cross-runtime review** of the bundled diff (contract_change gate:
   multi-layer FE+BE + read-model semantics).
4. **3 Full-Funnel semantic review items** (ENG-472, not blockers): carryover =
   "any covering consult in a different month" (EXISTS); revenue buckets by
   lead-created month (matches the marketing dashboard), not payment month;
   carryover unverifiable locally (`covering_opportunity_id` 0% coverage).
5. **ENG-475** — provide the business config when ready to unlock full
   channel/center/TC funnel parity.
6. (Optional) the 10 pre-existing base-branch test failures + 9 ruff errors
   belong to the marketing PR #161 — fix there, or absorb into this branch if
   you prefer one green PR.

## Parked
- ENG-459 messenger WIP is in `git stash` ("ENG-459 messenger WIP parked by
  orchestrator for ENG-468 epic"). Restore on the eng-459 branch:
  `git stash pop` (it's `stash@{0}`).
