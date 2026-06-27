import { z } from "zod";
import { Uuid } from "./common";
import {
  AnalyticsFiltersEchoSchema,
  AnalyticsWindowSchema,
} from "./journeyMetrics";

/**
 * ENG-525 — Attribution Analytics page contract (B2.12).
 *
 * Mirrors `packages/analytics/schemas.py` (`AttributionAnalyticsOut`,
 * `AttributionDimensionOut`, `RevenueGroupOut`) field-for-field.
 * Served by: GET /dashboard/analytics/attribution
 *
 * Dimensions: campaign (good data), vendor (resolved=false, 100% NULL today),
 * caller/coordinator/doctor (partial coverage; NULL = "Unassigned").
 *
 * `RevenueGroupOut` is shared with Revenue Intelligence; imported inline here
 * to avoid a circular dependency (schemas/revenueIntelligence.ts also exports
 * it, so consumers should prefer importing from there or from the barrel).
 */

export const AttributionRevenueGroupSchema = z.object({
  group_id: Uuid.nullable().default(null),
  group_label: z.string().nullable().default(null),
  gross: z.number(),
  collected: z.number(),
  outstanding: z.number(),
  case_count: z.number().int(),
  avg_case_value: z.number().nullable().default(null),
});
export type AttributionRevenueGroup = z.infer<
  typeof AttributionRevenueGroupSchema
>;

export const AttributionDimensionSchema = z.object({
  dimension: z.string(),
  /** True when the fact column is populated (campaign/caller/coordinator/doctor).
   *  False for vendor (100% NULL today — see ENG-569). */
  resolved: z.boolean(),
  /** Human-readable reason when resolved=false. */
  note: z.string().nullable().default(null),
  groups: z.array(AttributionRevenueGroupSchema),
});
export type AttributionDimension = z.infer<typeof AttributionDimensionSchema>;

export const AttributionAnalyticsSchema = z.object({
  window: AnalyticsWindowSchema,
  filters: AnalyticsFiltersEchoSchema,
  collected_total: z.number(),
  case_count: z.number().int(),
  dimensions: z.array(AttributionDimensionSchema),
});
export type AttributionAnalytics = z.infer<typeof AttributionAnalyticsSchema>;
