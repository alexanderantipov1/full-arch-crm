import { z } from "zod";
import { LeadSourceNodeSchema } from "./leadSources";

/**
 * ENG-470 — Marketing / Ad-spend analytics dashboard contract.
 * Mirrors `apps/api/routers/dashboard.py` (MarketingAnalyticsOut and its
 * nested `*Out` models) field-for-field. The backend serialises the date
 * window fields as `YYYY-MM-DD` (Pydantic `date`), so use a plain date
 * string here rather than the `Datetime` alias (which expects a full
 * timestamp with offset).
 */

const DateOnly = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "expected YYYY-MM-DD");

export const MarketingKpiSchema = z.object({
  key: z.string(),
  label: z.string(),
  // `null` when the metric has no source (e.g. a ratio with a zero base);
  // the UI renders "—" rather than a fabricated 0.
  value: z.number().nullable(),
  format: z.enum(["currency", "integer", "percent", "ratio"]),
  hint: z.string().nullable(),
});
export type MarketingKpi = z.infer<typeof MarketingKpiSchema>;

export const MarketingDailyPointSchema = z.object({
  metric_date: DateOnly,
  provider: z.string(),
  spend: z.number(),
  impressions: z.number(),
  clicks: z.number(),
  conversions: z.number(),
});
export type MarketingDailyPoint = z.infer<typeof MarketingDailyPointSchema>;

export const MarketingProviderSplitSchema = z.object({
  provider: z.string(),
  spend: z.number(),
  impressions: z.number(),
  clicks: z.number(),
  conversions: z.number(),
});
export type MarketingProviderSplit = z.infer<typeof MarketingProviderSplitSchema>;

export const MarketingCampaignRowSchema = z.object({
  provider: z.string(),
  campaign_external_id: z.string(),
  campaign_name: z.string().nullable(),
  spend: z.number(),
  impressions: z.number(),
  clicks: z.number(),
  conversions: z.number(),
});
export type MarketingCampaignRow = z.infer<typeof MarketingCampaignRowSchema>;

export const MarketingAnalyticsWindowSchema = z.object({
  start_date: DateOnly,
  end_date: DateOnly,
});
export type MarketingAnalyticsWindow = z.infer<
  typeof MarketingAnalyticsWindowSchema
>;

export const MarketingAnalyticsSchema = z.object({
  window: MarketingAnalyticsWindowSchema,
  kpis: z.array(MarketingKpiSchema),
  daily: z.array(MarketingDailyPointSchema),
  providers: z.array(MarketingProviderSplitSchema),
  campaigns: z.array(MarketingCampaignRowSchema),
  // Raw-UTM lead-source tree reused from the ops explorer contract.
  lead_sources: z.array(LeadSourceNodeSchema),
});
export type MarketingAnalytics = z.infer<typeof MarketingAnalyticsSchema>;
