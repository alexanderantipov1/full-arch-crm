import { z } from "zod";
import { Datetime, Uuid } from "./common";

/**
 * ENG-507 — Revenue Intelligence foundation metrics contract.
 *
 * Mirrors `packages/analytics/schemas.py` (`JourneyMetricsOut` and its nested
 * `*Out` models) field-for-field. This is the shared filter + time-range +
 * derived-metric layer every Revenue-Intelligence page composes onto — not a
 * page itself. Served by `GET /dashboard/analytics/journey-metrics`.
 *
 * Rendering rule: every derived metric is `number | null`. A `null` means the
 * denominator was 0 (divide-by-zero) and renders "—", never a fabricated 0.
 * `spend` is `null` when no ad-spend source is connected for the window.
 * `location_id` omitted (`null`) means the aggregate over all locations; a
 * value scopes the window + counts to that one clinic.
 */

export const AnalyticsTimeRangePresetSchema = z.enum([
  "today",
  "yesterday",
  "last_7_days",
  "last_30_days",
  "last_90_days",
  "this_month",
  "this_quarter",
  "this_year",
  "custom",
]);
export type AnalyticsTimeRangePreset = z.infer<
  typeof AnalyticsTimeRangePresetSchema
>;

export const AnalyticsWindowSchema = z.object({
  preset: AnalyticsTimeRangePresetSchema,
  start: Datetime,
  end: Datetime,
  tz: z.string(),
});
export type AnalyticsWindow = z.infer<typeof AnalyticsWindowSchema>;

export const AnalyticsFiltersEchoSchema = z.object({
  time_range: AnalyticsTimeRangePresetSchema,
  location_id: Uuid.nullable().default(null),
  campaign_id: Uuid.nullable().default(null),
  source: z.string().nullable().default(null),
  vendor_id: Uuid.nullable().default(null),
  caller_id: Uuid.nullable().default(null),
  coordinator_id: Uuid.nullable().default(null),
  doctor_id: Uuid.nullable().default(null),
});
export type AnalyticsFiltersEcho = z.infer<typeof AnalyticsFiltersEchoSchema>;

export const FactAggregateSchema = z.object({
  leads: z.number().int(),
  contacts: z.number().int(),
  consults: z.number().int(),
  shows: z.number().int(),
  surgeries: z.number().int(),
  patients: z.number().int(),
  revenue: z.number(),
  collected: z.number(),
  spend: z.number().nullable().default(null),
});
export type FactAggregate = z.infer<typeof FactAggregateSchema>;

export const DerivedMetricsSchema = z.object({
  cost_per_lead: z.number().nullable().default(null),
  cost_per_consult: z.number().nullable().default(null),
  cost_per_show: z.number().nullable().default(null),
  cost_per_surgery: z.number().nullable().default(null),
  revenue_per_lead: z.number().nullable().default(null),
  revenue_per_show: z.number().nullable().default(null),
  roi: z.number().nullable().default(null),
  lead_to_contact: z.number().nullable().default(null),
  contact_to_consult: z.number().nullable().default(null),
  consult_to_show: z.number().nullable().default(null),
  show_to_surgery: z.number().nullable().default(null),
  surgery_to_revenue: z.number().nullable().default(null),
});
export type DerivedMetrics = z.infer<typeof DerivedMetricsSchema>;

export const JourneyMetricsSchema = z.object({
  window: AnalyticsWindowSchema,
  filters: AnalyticsFiltersEchoSchema,
  aggregate: FactAggregateSchema,
  derived: DerivedMetricsSchema,
});
export type JourneyMetrics = z.infer<typeof JourneyMetricsSchema>;
