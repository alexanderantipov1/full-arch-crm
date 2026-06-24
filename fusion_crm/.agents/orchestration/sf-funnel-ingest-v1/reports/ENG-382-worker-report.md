# ENG-382 Worker Report — SF funnel provenance

- **Task:** ENG-382 — SF funnel provenance: conversion fields, UTM
  attribution, opportunity person link, stage history
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-382/sf-funnel-provenance-conversion-fields-utm-attribution-opportunity
- **Role / agent:** worker / claude-code (self-execute)
- **Branch:** codex/eng-371-manager-answer-layer-v1 (restored tip 2dfd07e)

## What changed (all 7 scope items)

1. **Lead conversion fields** — `IsConverted`, `ConvertedDate`,
   `ConvertedContactId/AccountId/OpportunityId` in the Lead SOQL
   projection, projected into `Lead.extra` via `_funnel_extra` (shared
   map so upsert metadata and the DTO extra view cannot drift).
2. **Attribution fields** — full set (first/last touch, gclid, fbclid,
   landing page, placement, referral source, ad network, remaining
   utm_*) on Lead (extra) and Opportunity (raw payload). Field API
   names verified against live SF records before SOQL changes.
3. **Opportunity person link** — `_resolve_person` falls back to
   `OpsService.find_lead_person_by_converted_opportunity`; opportunity
   events now land on person timelines. Real-PG test proves the path.
4. **Effective source** — `_lead_source_label` coalesce extends to
   `hubspot_lead_source` and `utm_source` mirrors; PM leads DTO
   materialises the same chain per row. Attribution coverage 83 →
   ~18k leads.
5. **Contact pull** — `sf_contact_service.py`: ENG-185 hint pipeline,
   converted leads reuse their person via email/phone tiers; emits
   `contact_created` events.
6. **Account pull** — `sf_account_service.py`: populates `ops.account`
   + identity source_link `kind="account"` via ConvertedAccountId.
7. **OpportunityHistory pull** — `sf_opportunity_history_service.py`:
   CreatedDate watermark over immutable stage rows; emits
   `opportunity_stage_changed` (no amounts in summaries/payloads).

Plumbing: EVENT_KINDS/SOURCE_KINDS/identity kinds extended through the
full documented checklist (tuples, Literals, `_KIND_VERB`, three
CLAUDE.md tables) + migration `f5a6b7c8d9e0` (CHECK widening; applied
locally; `alembic check` clean). Scheduler runs contacts + accounts
BEFORE opportunity history each tick; `_salesforce_counters`
generalised over eight summaries.

## Tests / verification

- 7 new mock tests (`test_sf_funnel_services.py`) + real-PG funnel-glue
  test; full suite 1443 passed; ruff + mypy (365 files) clean;
  `alembic check` clean.

## Incidents (see incidents.md)

Disk-full event (volume at 98%) truncated 13 git packfiles mid-mission,
plus the ruff binary and mypy cache. Recovery: object salvage +
quarantine + origin-pack import + tree rebuild from the intact index.
Content loss zero; commits ENG-371..382 squashed into restore commit
2dfd07e. Lesson: push mission branches at every checkpoint.

## Risks

- Attribution backfill for existing leads rides on re-imports (upsert
  extra merge). A one-shot `pull_all_since` re-run can force it.
- Restored branch is local-only; until pushed, a repeat disk event
  loses history again. PUSH RECOMMENDED.

## Suggested next

Open PR for the bundle branch (ENG-371..382) once Codex's frontend WIP
lands; production deploy activates the watermark pullers in
fusion-job-sf-pull/cs-pull.
