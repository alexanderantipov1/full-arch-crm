# Worker Report — ENG-471 (Web Analytics / SEO dashboard)

- **Task:** ENG-471 — Analytics: Web Analytics / SEO dashboard (GA4 + GSC)
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-471
- **Role/agent:** worker / claude-code (`eng471-seo`)
- **Branch:** eng-468-analytics-dashboards · commit `b4c53bc`
- **Verified by orchestrator** (ruff + mypy + pytest + parity, independently).

## Changed/created files
- `packages/marketing/repository.py` + `service.py` + `schemas.py` — new GA window aggregation + GSC window aggregation reads (sums, impression-weighted ctr/position, distinct query count, top queries).
- `apps/api/routers/dashboard.py` — `GET /dashboard/analytics/seo` + Seo* Pydantic models (reuses MarketingKpiOut + FullFunnelNotConfiguredOut).
- `apps/web/lib/api/schemas/seoAnalytics.ts` (+ index export), `hooks/useSeoAnalytics.ts`, `app/(staff)/analytics/seo/page.tsx` (Tabs GA4|GSC + recharts + not-connected cards), `AppShell.tsx` (SEO nav item).
- `tests/integration/test_marketing_seo_aggregations.py` (new).

## Endpoint + DTO
`GET /dashboard/analytics/seo?start_date&end_date` → `SeoAnalyticsOut { window{start_date,end_date}, ga:SeoGaOut{connected,kpis[MarketingKpiOut],daily[{metric_date,sessions,total_users,new_users,screen_page_views,conversions}]}, gsc:SeoGscOut{connected,kpis[],top_queries[{query,clicks,impressions,ctr?,position?}], top_pages:NotConfigured}, not_connected:[str] }`. Zod parity confirmed field-for-field (incl. metric_date, top_pages marker).

## "Not connected"
- GSC top-pages (page-level not ingested), Semrush, Clarity, PageSpeed, crawler/backlinks → explicit markers, never zeros.
- GA bounce/engagement/avg-duration/top-pages not surfaced (not ingested).

## Verification (orchestrator-run)
- ruff PASS; mypy PASS (6 files); pytest 9 PASS (seo 3 + marketing 3 + funnel 3 regression).

## Risks
- None blocking. Live render + real GA/GSC number eyeball deferred to morning.
