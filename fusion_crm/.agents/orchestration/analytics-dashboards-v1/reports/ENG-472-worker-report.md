# Worker Report — ENG-472 (Full Funnel dashboard)

- **Task:** ENG-472 — Analytics: Full Funnel dashboard page
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-472
- **Role/agent:** worker / claude-code (`eng472-funnel`)
- **Branch:** eng-468-analytics-dashboards · commit `f3caccb`
- **Verified by orchestrator** (ruff + mypy + pytest run independently before commit).

## Changed/created files
- `packages/ops/repository.py` — new `count_opportunity_outcomes_by_month()` (closed/won + carryover via correlated EXISTS on `consultation.covering_opportunity_id`, month != close month).
- `packages/ops/service.py` + `schemas.py` — `get_opportunity_outcomes_by_month()` + `OpportunityMonthOutcomeOut`.
- `packages/marketing/repository.py` + `service.py` + `schemas.py` — `aggregate_monthly_by_provider()` / `monthly_spend_by_provider()` + `AdSpendMonthlyPointOut`.
- `apps/api/routers/dashboard.py` — `GET /dashboard/analytics/full-funnel` + FullFunnel* Pydantic models.
- `apps/web/lib/api/schemas/fullFunnel.ts` (+ index export), `hooks/useFullFunnel.ts`, `app/(staff)/analytics/funnel/page.tsx`, `AppShell.tsx` (append Full funnel nav item).
- `tests/integration/test_full_funnel.py` (new, 3 cases).

## Endpoint + DTO
`GET /dashboard/analytics/full-funnel?start_date&end_date` (date-only; default trailing 6 months, capped 24) → `FullFunnelOut { window{start_month,end_month}, channels[], months[FullFunnelMonthOut{month, channels[FullFunnelChannelRowOut{channel,spend?,impressions?,leads,consults_scheduled,consults_attended,closed_won?,revenue}], spend?,impressions?,leads,consults_scheduled,consults_attended,closed,closed_won,carryover,revenue}], center_breakdown:NotConfigured, tc_breakdown:NotConfigured }`. Zod parity confirmed field-for-field.

## Real-data findings (psql, read-only)
- `opportunity.stage` only 3 distinct test values locally (Consultation Completed / Surgery Scheduled / Surgery Completed), 7 rows, all not-won/not-closed → did NOT hardcode a stage ladder; closed/won use `extra.is_closed`/`is_won` JSON booleans (robust to prod stage strings).
- `consultation.status` enum confirmed; `location_id` ~99.97% non-null.
- `covering_opportunity_id` 0% coverage locally → carryover reads 0 locally; logic proven by seeded integration test. Worth a prod spot-check once SF opportunity↔consult linkage lands.

## Decisions
- provider→channel: google_ads→google, meta_ads→facebook, tiktok_ads→other.
- Monthly bucketing: spend by metric_date; leads/consults/revenue by lead.created_at; closed/won/carryover by opportunity.close_date.
- Revenue = net lifetime collected per person folded into the person's lead-created month (matches shipped marketing dashboard), NOT payment month.
- center/TC + per-channel closed_won = "not configured" (ENG-475).

## Verification (orchestrator-run)
- ruff PASS; mypy PASS (11 files); pytest 6 PASS (full-funnel 3 + marketing regression 3). Worker also reported tsc --noEmit clean + eslint clean + 34-test regression.

## Correctness risks for morning review (NOT blockers)
1. Carryover = ANY covering consult in a different calendar month (EXISTS). Confirm vs "primary/latest consult" semantics.
2. Carryover unverifiable on local data (covering_opportunity_id 0%); prod spot-check needed.
3. Revenue buckets by lead-created month, not cash-received month. Decide if payment-month bucketing is preferred for the funnel (needs an occurred-at-windowed collected read).

## Do-not-merge conditions
None for overnight commit; the 3 risks are review items for the morning PR.
