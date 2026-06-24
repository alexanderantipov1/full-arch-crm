# Decision Log — analytics-dashboards-v1 (ENG-468)

## 2026-06-16 — Base branch = marketing branch, not main
`marketing.*` (ad_metric_daily / ga_metric_daily / gsc_query_daily + migration
c1a2b3d4e5f6) is NOT on `origin/main` — it lives only on
`origin/eng-464-marketing-ad-spend` and `origin/eng-465-marketing-web-analytics`
(PRs #160/#161, unmerged). The dashboards depend on those tables, so the epic
branch `eng-468-analytics-dashboards` is based on `eng-465-marketing-web-analytics`.
The eventual epic PR will carry the marketing commits until #160/#161 merge
(acceptable per solo-dev bundling pref). Confirmed via `git branch -r --contains`.

## 2026-06-16 — Sequential single-branch pipeline, not parallel worktrees
All 5 dashboards touch the same shared paths (`dashboard.py`, `AppShell.tsx`,
analytics read layer, web API client). Parallel worktrees would guarantee
conflicts on nav + router. For an unattended overnight run we want zero manual
conflict resolution, so workers run sequentially on one accumulating epic branch.
Task class = contract_change (multi-layer + read-model semantics).

## 2026-06-16 — In-session agents, orchestrator commits between tickets
Owner chose in-session subagents (not detached launch_worker.py CLIs): more
observable, orchestrator reviews each diff and commits between tickets. Commits
local yes; push + PR deferred to the morning for human review. ScheduleWakeup
keeps the orchestration loop alive overnight.

## 2026-06-16 — Verification split: automated overnight, live render morning
Owner chose ruff+mypy+pytest (real PG) overnight; live browser render + Replit
number cross-check + Codex cross-runtime review in the morning before push/PR.

## 2026-06-16 — Build order: 469 -> 470 -> 472 -> 471 -> 473 -> 474
ENG-469 (doc) blocks all. ENG-470 (Marketing) second because it extends the
existing MarketingService and establishes the analytics read layer + "Analytics"
nav section + endpoint pattern. Then the high-priority headline ENG-472 (Funnel),
then ENG-471 (SEO), ENG-473 (Sales), ENG-474 (Calls shell, lowest, partial).

## 2026-06-16 — Channel/center/TC gap: ship google/facebook/Other + defer parity (ENG-475)
ENG-469 §6 surfaced that our `_channel_of_source()` only classifies google/facebook,
while legacy needs 5 channels + center bucketing + TC→center→per-arch pricing
(business config we don't have). Orchestrator decision: overnight dashboards ship
with google/facebook/Other and render center/TC/Dima/Implant-Engine as
"not configured" (degrade gracefully, epic's no-fake-zeros mandate). Resolver
extension + config table deferred to ENG-475 (needs the doctor's business facts:
channel list, TC→center map, per-arch pricing). Canonical resolver left untouched.

## 2026-06-16 — NO packages/analytics domain; compose in apps/api (overrides ENG-469 rec)
ENG-469 recommended a new `packages/analytics/` package composing
MarketingService/OpsService/InteractionService. Rejected on invariant #3 grounds:
the import matrix (packages/CLAUDE.md) grants broad cross-domain imports only to
`tools`/`agent_runtime`; a new analytics domain importing 3 domains would breach
strict domain separation (a hard invariant, needs explicit approval to change).
The established invariant-safe pattern is already in dashboard.py: the API layer
is the composition root (imports Ops/Interaction/Identity/Integration services and
assembles in the route), and `OpsService.get_lead_source_tree` deliberately does
NOT import interaction — revenue is attributed at the API layer by person_uid.
Decision: new aggregation READS go in the owning domain service (Marketing/Ops/
Interaction); cross-domain COMPOSITION stays in apps/api (router `/dashboard/
analytics/*`, mirroring `/dashboard/pm/*`; a thin apps/api-local helper if a route
gets heavy). No new packages/ domain. This keeps routes thin (aggregation in
services) while respecting the import matrix.

## 2026-06-16 — Messenger WIP parked
Uncommitted ENG-459 messenger edits (chat_inbound*.py, chat/base.py,
chat/mattermost.py) were stashed (`git stash` msg "ENG-459 messenger WIP parked
by orchestrator for ENG-468 epic") to give the epic branch a clean base. Restore
with `git stash pop stash@{0}` on the eng-459 branch later.
