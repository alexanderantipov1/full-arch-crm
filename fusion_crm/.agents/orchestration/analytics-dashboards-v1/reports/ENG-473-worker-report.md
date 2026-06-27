# Worker Report — ENG-473 (Sales Pipeline dashboard)

- **Task:** ENG-473 — Analytics: Sales Pipeline dashboard page
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-473
- **Role/agent:** worker / claude-code (`eng473-sales`)
- **Branch:** eng-468-analytics-dashboards · commit `3a00c8e`
- **Verified by orchestrator** (ruff + mypy + pytest + parity, independently).

## Changed/created files
- `packages/ops/repository.py` + `service.py` + `schemas.py` — new sales aggregations (pipeline by stage, TC leaderboard by extra.owner_name, KPI helpers, consultations join).
- `apps/api/routers/dashboard.py` — `GET /dashboard/analytics/sales` + Sales* Pydantic models (reuses MarketingKpiOut + FullFunnelNotConfiguredOut).
- `apps/web/lib/api/schemas/salesAnalytics.ts` (+ index export), `hooks/useSalesAnalytics.ts`, `app/(staff)/analytics/sales/page.tsx`, `AppShell.tsx` (Sales nav item).
- `tests/integration/test_sales_analytics.py` (new).

## Endpoint + DTO
`GET /dashboard/analytics/sales` → `SalesAnalyticsOut { kpis[MarketingKpiOut], pipeline_by_stage[{stage,count,value}], tc_leaderboard[{tc,opps,won,lost,close_rate?,value,won_revenue,collected}], consultations[{consultation_id,patient?,tc?,status,scheduled_at,stage?,opp_value?,paid,balance?,close_date?}], followups:NotConfigured }`. Zod parity confirmed (Datetime for scheduled_at/close_date; reuses ConsultationStatusSchema).

## Decisions / not-connected
- Won/closed via `extra.is_won`/`is_closed` booleans; pipeline grouped by raw `stage` (no hardcoded ladder).
- Follow-up call/text/email split = not-configured (only `call_logged` ingested).

## Verification (orchestrator-run)
- ruff PASS; mypy PASS (6 files); pytest 13 PASS (sales 4 + funnel + seo + marketing regression).

## Risks
- None blocking. Live render + real numbers eyeball deferred to morning.
