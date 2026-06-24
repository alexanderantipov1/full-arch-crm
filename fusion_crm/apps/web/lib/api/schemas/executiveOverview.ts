import { z } from "zod";
import {
  AnalyticsFiltersEchoSchema,
  AnalyticsTimeRangePresetSchema,
  AnalyticsWindowSchema,
  DerivedMetricsSchema,
} from "./journeyMetrics";
import { PatientFunnelStageSchema } from "./funnelStages";

/**
 * ENG-514 — Executive Overview page contract.
 *
 * Mirrors `packages/analytics/schemas.py` (`ExecutiveOverviewOut` and nested
 * `*Out`) field-for-field. Served by `GET /dashboard/analytics/executive`.
 * `funnel` is the eight-stage patient funnel over the selected window; `derived`
 * is the shared cost/ROI/conversion layer (null until ad spend connects);
 * `revenue_widgets` are the seven realized-cash cards (Today…YTD), anchored on
 * payment date and independent of the page's time range.
 */

export const RevenueWidgetSchema = z.object({
  preset: AnalyticsTimeRangePresetSchema,
  label: z.string(),
  gross: z.number(),
  collected: z.number(),
  payers: z.number().int(),
});
export type RevenueWidget = z.infer<typeof RevenueWidgetSchema>;

export const ExecutiveOverviewSchema = z.object({
  window: AnalyticsWindowSchema,
  filters: AnalyticsFiltersEchoSchema,
  funnel: z.array(PatientFunnelStageSchema),
  derived: DerivedMetricsSchema,
  spend: z.number().nullable().default(null),
  revenue_total: z.number(),
  collected_total: z.number(),
  outstanding_total: z.number(),
  patients: z.number().int(),
  revenue_widgets: z.array(RevenueWidgetSchema),
});
export type ExecutiveOverview = z.infer<typeof ExecutiveOverviewSchema>;
