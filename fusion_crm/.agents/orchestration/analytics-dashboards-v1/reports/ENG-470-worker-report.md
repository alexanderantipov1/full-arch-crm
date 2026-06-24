# Worker Report — ENG-470 (Marketing / Ad-spend dashboard)

- **Task:** ENG-470 — Analytics: Marketing / Ad-spend dashboard page
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-470
- **Role/agent:** worker / claude-code (in-session agent `eng470-marketing`)
- **Branch:** eng-468-analytics-dashboards · commit `cc593c0`
- **Verified by orchestrator** (ruff + mypy + pytest run independently before commit).

## Changed files
- `apps/api/routers/dashboard.py` — new `GET /dashboard/analytics/marketing` + Pydantic `MarketingAnalyticsOut` (+ nested KPI/daily/provider/campaign/window models). Thin composer.
- `apps/api/dependencies.py` — added `get_marketing_service` DI provider (idiomatic, mirrors get_enrichment_service). Out of literal owned paths but minimal + correct; accepted.
- `packages/marketing/service.py` — new `spend_breakdown()` read method.
- `packages/marketing/repository.py` — new `aggregate_daily_by_provider()` + `aggregate_provider_totals()` group-bys.
- `packages/marketing/schemas.py` — new aggregate DTOs.
- `apps/web/lib/api/schemas/marketingAnalytics.ts` (new) — Zod, mirrors `MarketingAnalyticsOut` field-for-field; uses date-only strings (window/daily dates are Pydantic `date`, not datetime — documented inline).
- `apps/web/lib/api/schemas/index.ts` — export.
- `apps/web/lib/api/hooks/useMarketingAnalytics.ts` (new) — TanStack + `.parse()`.
- `apps/web/app/(staff)/analytics/marketing/page.tsx` (new) — recharts AreaChart + shadcn Card/Tabs/Skeleton/Badge.
- `apps/web/components/layout/AppShell.tsx` — new "Analytics" nav section (`analyticsItems` array, extensible).
- `tests/integration/test_marketing_spend_breakdown.py` (new) — real-PG test.

## Endpoint + contract
`GET /dashboard/analytics/marketing?start_date&end_date&provider` →
`MarketingAnalyticsOut { window{start_date,end_date}, kpis[{key,label,value:float|null,format,hint}], daily[{metric_date,provider,spend,impressions,clicks,conversions}], providers[...], campaigns[{provider,campaign_external_id,campaign_name?,...}], lead_sources[LeadSourceNodeOut] }`. Zod parity confirmed field-for-field.

## Verification (orchestrator-run)
- ruff: All checks passed.
- mypy: Success, no issues in 7 source files.
- pytest `tests/integration/test_marketing_spend_breakdown.py`: 3 passed.
- FE: imports resolve, parity verified by reading both sides. Live browser render deferred to morning.

## "Not connected" / degraded
- Channels limited to google/facebook/other (shipped resolver). Dima/Implant-Engine/center/TC NOT shown → ENG-475.
- Derived ratios (CTR/CPC/CPM/CPL) render "—" when denominator is 0 (value=null).

## Reuse for next dashboards
- Nav: append to `analyticsItems` in `AppShell.tsx`.
- Endpoint pattern: `/dashboard/analytics/<name>` in dashboard.py, thin composer, `get_principal_with_tenant` + per-domain service DI.
- Zod: mirror the `*Out`; date-only fields use a `YYYY-MM-DD` regex string, datetimes use `Datetime` from common.ts.

## Risks / follow-ups
- Full `tsc` not run (deferred to morning live-render check).
- ENG-475 gates richer channel/center/TC parity.
