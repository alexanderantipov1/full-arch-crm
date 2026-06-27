# Lead Source Attribution — Session Handoff (continue at Block D)

Read this first when resuming. It carries the full understanding so a fresh
session can continue without re-deriving anything.

## Two parallel workstreams (both mine, both on their own branches)

### 1. Full-Fidelity Ingestion Framework — ENG-425 — DONE, in PR
- Branch `eng-425-full-fidelity-ingestion-v1`, **PR #148** to main. Blocks A–F
  all done + real-SF verified (8/8 objects). Linear ENG-425..431 In Review.
- Captures 100% of every external object's fields into `ingest.raw_event`
  (SF: 45→240 fields on Lead). Schema registry `ingest.source_object_field`,
  dynamic describe projection, Tooling FLS-gap, daily drift cron, CareStack
  observed-key snapshot, SF backfill script. ADR-0005.
- **CreatedBy.Name** is now captured + backfilled for 2026 Lead (14,427 rows).
  This is what makes attribution possible.

### 2. Lead Source Attribution — ENG-446 — A/B/C done, D pending (THIS work)
- Branch `eng-447-lead-attribution-v1`, developed in a **git worktree** at
  `/Users/eduardkarionov/Desktop/fusion_crm_attribution` (the main checkout was
  on `eng-433-interactive-messenger-layer` with uncommitted other-feature work,
  so I could not branch from main there). Commits: 433be3a, 55acb1a, cec0fa9,
  44ce061. Not yet PR'd.
- Linear: epic **ENG-446**; A **ENG-447**, B **ENG-448**, C **ENG-449** all In
  Review; **D ENG-450** = Todo (the remaining work).
- Design: `.agents/strategy/LEAD_SOURCE_ATTRIBUTION_DESIGN.md`.

## What attribution does (the model)

Source is a hierarchical **chain** we slice analytics by at every level:
```
vendor → channel → campaign → ad_set → ad → form     (+ created_by_name axis)
```
- **A (ENG-447)** — `attribution` domain/schema: `source_node` (chain via
  parent_id), `lead_attribution` (resolved chain per person, denormalized
  levels + `created_by_name` + method + confidence + source_signal),
  `mapping_rule` (editable pattern→node). Migration `f6a7b8c9d0e1`.
- **B (ENG-448)** — `waterfall.py` (pure resolver) + `signals.py` (extract from
  SF payload) + `AttributionService.resolve_person/resolve_and_store/load_rules`.
  Ladder: digital → phone(CallRail/direct-line) → campaign → manual(staff
  CreatedBy) → reactivation(CareStack-before-SF) → created_by(any creator) →
  needs_review. **created_by_name captured for ALL leads** (staff = source for
  manual; integration account = fallback when utm missing).
- **C (ENG-449)** — mapping-rule CRUD + per-lead override (`set_override`,
  method=manual sticky) + batch `resolve_many` + API router
  `apps/api/routers/attribution.py` + `infra/scripts/resolve_attribution.py`.

## Locked design decisions (do not relitigate)

1. Manually-entered leads → `channel=manual`, `created_by_name` = the staff
   person. "manual + who" is the attribution. Manual wins over reactivation.
2. `created_by_name` (renamed from agent_name) is captured for **every** lead,
   not just manual — so we always know who/what created it. `needs_review` only
   when truly nothing.
3. Manual override is sticky across auto/rule re-resolution.
4. Vendor is NOT in the source data → learned via mapping rules
   (`utm_campaign ILIKE 'Dima%' → vendor=Dima`).
5. Never written back to Salesforce (read-only pull guard-rail).

## Real-data findings (so you have the numbers)

- 64,345 distinct leads. utm_source filled ~30%, LeadSource dead (0.1%),
  Business_Unit__c 99.5%, Assigned_Center__c 52%.
- 2026 wide leads: 14,355; **100% have a known creator** after the CreatedBy
  backfill. No-utm leads' creators: staff (Artem Myalik 269, Tomas Zajfert 141,
  Breana Brand 100, …) + integration accounts (Fusion Marketing, Daniel
  Creatives).
- The known "unknown" example lead `a3feb750-fa81-4eaf-b7b9-f1ee5b704d14`
  (Vladyslav Romanchuk) resolves to channel=manual, created_by=Olga Kolomyza.
- Campaign NAMES live in `utm_campaign__c` ("Roseville Lead Gen Fusion"); FORM
  names in `Hubspot_Lead_Source__c` ("…Lead Capturing Form FB", "CallRail",
  "ApiX-Drive"); ad/creative in `utm_content__c`.

## Migration apply — NOT actually blocked (local artifact only)

Earlier I thought `alembic upgrade head` was blocked by a missing revision
`b69bce1e2195`. INVESTIGATED: that is a **local-environment artifact, not a real
chain break**. `b69bce1e2195` is a migration that exists only on branch
`eng-433-interactive-messenger-layer`; it is NOT referenced by main/attribution
scripts. `alembic heads` is clean (single head `f6a7b8c9d0e1`), and an offline
`alembic upgrade head --sql` render walks the whole chain and reaches the
`attribution` tables fine. The b69 error came only from the shared dev DB being
in a multi-branch state.

So: on a **clean standalone checkout of `eng-447-lead-attribution-v1` + a fresh
DB** (`infra/docker/init-schemas.sql` then `alembic upgrade head`), the
attribution migration applies normally — then run `resolve_attribution.py` and
build analytics. Don't try to "repair" b69bce1e2195. (See memory
`blocker_alembic_broken_chain_main`.)

Still true: attribution `f6a7b8c9d0e1` and ingest `e6f7a8b9c0d1` are siblings off
`d5e6f7a8b9c0` → need an Alembic merge revision when both land on main.

## Block D (ENG-450) — what to build next

Funnel analytics by attribution chain level.
1. Backend: funnel aggregate joins `attribution.lead_attribution`; a `dimension`
   param = chain level (vendor|channel|campaign|ad_set|ad|form) + optional parent
   filter for drill-down. Group manual leads by `created_by_name`. Mirror the
   existing funnel/lead-sources-explorer patterns
   (`apps/api/routers/funnel.py`, `packages/interaction/repository.py`,
   `packages/ops/repository.py::_explorer_source_label`).
2. Frontend: hierarchical explorer (vendor → channels → campaigns → …) replacing
   the dashboard "unknown" bucket with the resolved breakdown; show the
   `needs_review` count explicitly (target ~0).
3. Pre-req: run `resolve_attribution.py --all` (after the migration applies) to
   populate `lead_attribution`, then measure needs_review%.

## First steps for the resuming session

1. `cd` into the worktree `/Users/eduardkarionov/Desktop/fusion_crm_attribution`
   (branch `eng-447-lead-attribution-v1`) OR recreate it from `eng-447-...`.
2. Decide: clear the alembic blocker, or proceed to write Block D backend +
   tests against the schema (offline) and defer the live run.
3. Build ENG-450 per the spec above.
