# Decision Log — revenue-intelligence-analytics-v1 (ENG-504)

## 2026-06-17 — New `analytics` DB schema approved (invariant #1 addition)
Operator approved adding a new `analytics` PostgreSQL schema to host
`fact_patient_journey` and future aggregate read-models. This extends hard
architectural invariant #1 (the canonical-DB schema set). Rationale: a fact /
read-model layer should not live inside a transactional domain schema; keeping it
separate makes it an explicitly **rebuildable projection** that can be dropped and
regenerated from canonical domains without touching source-of-truth data. The
`analytics` schema is written only by the fact builder and is never a source of
truth. An ADR should be filed during B0.1 to record this formally.

## 2026-06-17 — Full epic, all 14 pages
Operator chose to deliver the entire `market.md` spec (14 pages + foundation +
export) under one project rather than an MVP-first slice. Delivery is still
phased internally (B0 → B1/B2 → B3) but the scope is the full platform.

## 2026-06-17 — Missing fields: nullable + two fill paths
Fact columns that are not yet derivable from data (caller/coordinator/doctor,
treatment_accepted, surgery_*, marketing_cost) ship **nullable** with per-field
provenance (source, method `auto`/`manual`/`unresolved`, confidence, resolved_at).
They are filled later by either an automatic resolver OR manual operator
enrichment. Proposed precedence: `manual` > `auto` > `unresolved`; a fact rebuild
must never clobber a manual override. UI shows honest "no data" until resolved.
This was an explicit operator instruction ("потом их добавим или в ручном вводе
сделаем пометки или в автоматическом").

## 2026-06-17 — Multi-location is first-class (aggregate + per-location)
Operator requirement: every page works both aggregate (all locations) and
per-location. `location_id` is added to `fact_patient_journey` (not in the spec's
column list) and the shared filter; data already exists (`tenant.location`,
`ops.consultation.location_id`). Default is aggregate; `location_id` filters down.

## 2026-06-17 — Strategy created Linear under explicit operator direction
Per protocol "Strategy proposes, Orchestrator disposes", Linear creation is
normally the Orchestrator's step. The operator explicitly instructed Strategy to
create the full Linear mission ("все таски в линаре по миссии"), so the Strategy
session created project + epic ENG-504 + children ENG-505..ENG-529 and these
mission docs. Strategy did NOT launch workers, create branches/worktrees, or write
product code — those remain gated on Orchestrator acceptance + operator go.
Record the `Handoff: strategy → orchestrator` event in runtime files on acceptance.

## 2026-06-18 — Orchestrator acceptance + B0 foundation worker running
Operator confirmed all decisions (incl. surgery data) and authorized autonomous
overnight execution bounded to **build + draft PR, NO merge** (migrations/contract
merge to main + deploy wait for operator + cross-runtime review).

Operator cleared the dirty-canonical-checkout blocker (tree clean; mission specs
committed to local `main` as `e193203`). A **parallel Codex orchestrator** then
accepted the handoff and launched the B0 foundation worker in background at
07:31Z: session `3f5d89cd5223` (b0-foundation), claude-code, pid 87043, isolated
worktree `…/revenue-intelligence-analytics-v1/worktrees/b0-foundation`, branch
`eng-505-b0-foundation`, running the guardrailed B0 prompt (ENG-505→506→507).

This Claude orchestrator's own `--mode print` created a duplicate phantom session
(`bba68eef0274`) + stray worktree `eng-505-eng-505`; both were cancelled/removed
to avoid a second worker on the same branch (collision/contract-drift risk).
**Coordination note:** two orchestrators (Claude + Codex) are active on this
mission — to avoid duplicate launches, the running B0 worker is left to the
existing launch; no further worker is launched until B0 produces its draft PR and
report. Next wave (B1/B2) is gated on B0 draft PR + operator review + cross-runtime
review; it is NOT auto-launched.

## 2026-06-19 — Operator authorized merge + push of B0/B1/B2 to `main`
The earlier overnight gate ("build + draft PR, NO merge") is **lifted by explicit
operator instruction in-session**. Operator directed integration of the analytics
read-model B0/B1/B2 directly into `main` and a push to `origin`.

Done:
- Local `main` (16 commits, ENG-505/506/507/509/510/513/514/515/521/523/526 plus
  orchestration docs) pushed: `origin/main 1c576c0..5036af8`, then `..5b2a1fc`.
- DRAFT PR #185 (B0, branch `eng-505-b0-foundation`) auto-resolved to **MERGED**
  by GitHub once its 4 commits became contained in `main`.

Verification at integration:
- `ruff check packages/analytics packages/attribution` → clean.
- `cd packages/db && alembic check` → "No new upgrade operations detected"
  (no migration drift; required the env.py root-`.env` load fix, commit
  `5b2a1fc`).
- deploy-drift contract tests (`test_env_reference_matches_settings`,
  `test_traffic_primary_filter`) → 25 passed.
- analytics domain does not import `phi`; `ops` does not import `phi`.

Handoff: integrator/claude-code -> orchestrator/claude-code. This rolls the
mission boundary (large merge landed on `main`). Outstanding before any
**production deploy**: cross-runtime (Codex) review of the contract-changing
read-model, and ENG-512 (marketing-cost allocation) / ENG-508 (export) scope
confirmation. Deploy itself still requires explicit operator approval and
`docs/DEPLOYMENT_RULES.md` preflight. `current` pointer moved from the completed
`analytics-dashboards-v1` (ENG-468) to this mission.

