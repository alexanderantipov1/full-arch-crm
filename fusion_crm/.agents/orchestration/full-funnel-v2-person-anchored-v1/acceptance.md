# Acceptance — Full Funnel v2

## ENG-481 (backend)
- `GET /dashboard/analytics/full-funnel?audience=all|marketing` returns
  person-anchored stages: `leads`, `consults_scheduled`, `showed`,
  `no_show`, `closed_won` (money-based), `revenue`, plus by-month and
  by-channel breakdowns.
- Person universe = `ops.lead` ∪ `identity.source_link(carestack/patient)`.
- `all` revenue reconciles to ~$6.2M lifetime locally; `all` consults reflect
  CareStack truth (not the ~576 lead-anchored slice).
- `marketing ⊆ all` for every stage.
- Per-stage time window on the stage's own timestamp (lead created-at /
  consultation scheduled-at / payment occurred-at).
- No new DB tables. Cross-domain access via services only; no `event.payload`
  JSON in the router. Thin composer in the route.

## ENG-482 (frontend)
- Marketing/All toggle drives `audience`; default All; visibly changes every
  stage.
- KPIs: Leads · Consults scheduled · Showed · No-show · Closed won (money) ·
  Revenue.
- No-show rendered as its own stage/column; Show + No-show from CareStack
  statuses.
- Closed won presented as money received, not 0.
- `—` for null/unconnected sources (never fake zero). Zod schema + hook match
  the new contract; no zombie MSW handler.

## ENG-483 (verify)
- v2 numbers reconcile to raw DB counts (leads / consult statuses / Net
  Collected) within tolerance.
- `marketing ⊆ all` asserted per stage and month.
- Integration tests on a real PostgreSQL test DB (no mocks), mirroring package
  layout under `tests/`.
