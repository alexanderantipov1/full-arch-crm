# Worker Report — ENG-469 (discovery + data-mapping doc)

- **Task:** ENG-469 — Analytics: discovery + data-mapping doc
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-469
- **Role/agent:** worker / claude-code (in-session agent `eng469-discovery`)
- **Branch:** eng-468-analytics-dashboards · **Workspace:** shared epic branch
- **Scope:** doc-only (one new file, no code touched)

## Touched files
- `docs/analytics/dashboards-mapping.md` (new)

## What changed
Full discovery doc mapping every legacy Replit dashboard metric → our
source-of-truth tables, verified against real models on the epic branch.
Per-dashboard tables with OK/PARTIAL/BLOCKED status, a "cannot compute yet"
section, build recommendations, the channel-classification gap (§6), and a
verify-before-build checklist (§7).

## Key recommendations (accepted by orchestrator)
- Endpoint prefix: extend `/dashboard` with an `/analytics` sub-tree
  (`/dashboard/analytics/{marketing,seo,full-funnel,sales,calls}`).
- Read layer: NEW `packages/analytics/` (`AnalyticsService`, service-only
  composition over MarketingService/OpsService/InteractionService). Do NOT
  extend `insight`. New aggregation reads go in the owning domain service.
- Full Funnel: reuse `OpsService.get_lead_source_tree()` + `_channel_of_source()`;
  do not re-port `classifyLeadSource()`.

## Tests run
None (doc-only).

## Verification status
N/A (doc). Content cross-checked against actual models.

## Risks / blockers
- **Channel/center/TC gap (§6):** our `_channel_of_source()` only classifies
  google/facebook; legacy needs 5 channels + center bucketing + TC→center→pricing
  (business config we don't have). **Orchestrator decision: ship google/facebook/
  Other + render center/TC as "not configured"; resolver extension deferred to a
  follow-up ticket needing the doctor's config.**
- §7 checklist: dashboard workers must verify distinct opportunity.stage strings,
  GSC page / GA engagement `extra` fields, call_logged duration, consultation
  location_id coverage against real prod data before hardcoding.

## Suggested next task
ENG-470 (Marketing dashboard) — establishes `packages/analytics/` + the
"Analytics" nav section + `/dashboard/analytics/marketing` endpoint pattern.

## Do-not-merge conditions
None for the doc itself.
