import { z } from "zod";
import { MarketingKpiSchema } from "./marketingAnalytics";
import { FullFunnelNotConfiguredSchema } from "./fullFunnel";

/**
 * ENG-471 — Web Analytics / SEO dashboard contract.
 * Mirrors `apps/api/routers/dashboard.py` (SeoAnalyticsOut and its nested
 * `*Out` models) field-for-field. The backend serialises the date window
 * fields as `YYYY-MM-DD` (Pydantic `date`), so use a plain date string here
 * rather than the `Datetime` alias (which expects a full timestamp with
 * offset). KPI cards reuse the marketing `MarketingKpiSchema` (value=null →
 * "—"); the GSC top-pages table reuses the full-funnel not-configured marker.
 */

const DateOnly = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "expected YYYY-MM-DD");

export const SeoGaDailyPointSchema = z.object({
  metric_date: DateOnly,
  sessions: z.number(),
  total_users: z.number(),
  new_users: z.number(),
  screen_page_views: z.number(),
  conversions: z.number(),
});
export type SeoGaDailyPoint = z.infer<typeof SeoGaDailyPointSchema>;

// ENG-478 — GA4 acquisition-channel split (organic / paid / direct / …).
export const SeoGaChannelRowSchema = z.object({
  channel: z.string(),
  sessions: z.number(),
  total_users: z.number(),
  new_users: z.number(),
  screen_page_views: z.number(),
  conversions: z.number(),
});
export type SeoGaChannelRow = z.infer<typeof SeoGaChannelRowSchema>;

// ENG-478 — GA4 top landing pages by sessions.
export const SeoGaPageRowSchema = z.object({
  page_path: z.string(),
  sessions: z.number(),
  total_users: z.number(),
  new_users: z.number(),
  screen_page_views: z.number(),
  conversions: z.number(),
});
export type SeoGaPageRow = z.infer<typeof SeoGaPageRowSchema>;

export const SeoGaSchema = z.object({
  connected: z.boolean(),
  kpis: z.array(MarketingKpiSchema),
  // ENG-478 engagement rollup KPIs (value=null → "—" when not captured).
  engagement_kpis: z.array(MarketingKpiSchema),
  daily: z.array(SeoGaDailyPointSchema),
  channels: z.array(SeoGaChannelRowSchema),
  top_pages: z.array(SeoGaPageRowSchema),
});
export type SeoGa = z.infer<typeof SeoGaSchema>;

export const SeoGscQueryRowSchema = z.object({
  query: z.string(),
  clicks: z.number(),
  impressions: z.number(),
  // Impression-weighted; `null` when the query had zero impressions → "—".
  ctr: z.number().nullable(),
  position: z.number().nullable(),
});
export type SeoGscQueryRow = z.infer<typeof SeoGscQueryRowSchema>;

export const SeoGscSchema = z.object({
  connected: z.boolean(),
  kpis: z.array(MarketingKpiSchema),
  top_queries: z.array(SeoGscQueryRowSchema),
  // Page-level GSC data is not ingested; rendered as a not-connected marker.
  top_pages: FullFunnelNotConfiguredSchema,
});
export type SeoGsc = z.infer<typeof SeoGscSchema>;

export const SeoAnalyticsWindowSchema = z.object({
  start_date: DateOnly,
  end_date: DateOnly,
});
export type SeoAnalyticsWindow = z.infer<typeof SeoAnalyticsWindowSchema>;

export const SeoAnalyticsSchema = z.object({
  window: SeoAnalyticsWindowSchema,
  ga: SeoGaSchema,
  gsc: SeoGscSchema,
  // Web-analytics sources we do not ingest (Semrush / Clarity / PageSpeed /
  // crawler) — the UI renders an explicit placeholder for each.
  not_connected: z.array(z.string()),
});
export type SeoAnalytics = z.infer<typeof SeoAnalyticsSchema>;
