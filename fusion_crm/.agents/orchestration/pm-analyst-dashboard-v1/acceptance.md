# PM/Analyst Dashboard V1 Acceptance

## Acceptance Criteria

1. A dashboard v1 API contract exists for PM/Analyst filters, search, KPIs,
   funnel, breakdowns, risk rows, treatment/payment widgets, sync health, and
   drilldowns.
2. A staff UI dashboard screen or tabbed dashboard implements global filters
   and search.
3. The first data slice uses existing canonical data where possible:
   `identity.person`, `identity.source_link`, `ops.lead`, `ops.consultation`,
   `interaction.event`, and `integrations.sync_run`.
4. Person detail uses `GET /persons/{uid}/operational-timeline` for the safe
   normalized activity view.
5. Salesforce enrichment covers the dashboard fields needed for business unit,
   assigned center, preferred language, UTM fields, owner, and consultation
   scheduled date.
6. CareStack treatment/payment visibility is included as a required read-only
   track. The first implementation must classify the data and expose only the
   smallest safe dashboard slice needed for treatment totals, accepted amounts,
   production/collection/payment totals, first/last payment dates, and AR-like
   risk flags.
7. Dashboard and API outputs contain no raw provider payloads, clinical notes,
   or unreviewed clinical free text.
8. No provider write-back is implemented.
9. Verification is run or explicitly blocked:
   - `make lint`
   - `mypy .`
   - `make test`
   - `cd packages/db && alembic check`

## Human Decisions / Follow-ups

1. Route shape resolved for V1: Project Manager workspace at
   `/project-manager`, with analyst-specific split deferred until requested.
2. Risk thresholds: stale lead, no next action, consult completed with no next
   step, and AR risk. AR-like risk remains a follow-up behind a permissioned
   billing/read model.
3. Whether saved views are v1 or later. Default: later.
4. Which staff roles may see treatment/payment aggregates and whether row-level
   details need an additional permission. V1 exposes aggregate-only dashboard
   fields; row-level invoice/payment drilldowns stay out of scope.

## Current State

All mission-board acceptance work is implemented and verified locally. Linear
children ENG-251 through ENG-259 and integration gate ENG-265 are Done. Parent
ENG-250 is ready to close after pushing the local `main` commits and confirming
remote/CI state.
