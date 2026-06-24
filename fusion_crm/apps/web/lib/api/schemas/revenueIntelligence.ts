import { z } from "zod";
import { Uuid } from "./common";
import {
  AnalyticsFiltersEchoSchema,
  AnalyticsWindowSchema,
} from "./journeyMetrics";

/**
 * ENG-521 — Revenue Intelligence page contract.
 *
 * Mirrors `packages/analytics/schemas.py` (`RevenueIntelligenceOut` and nested
 * `*Out`) field-for-field. Served by `GET /dashboard/analytics/revenue`. Revenue
 * (cohort by lead_date, so totals reconcile with the funnel) broken down by the
 * seven dimensions. `resolved === false` dimensions (vendor/caller/coordinator/
 * doctor) collapse to a single "Unattributed" bucket until B1. `avg_case_value`
 * is `number | null` → renders "—" when a group has no cases.
 */

export const RevenueGroupSchema = z.object({
  group_id: Uuid.nullable().default(null),
  group_label: z.string().nullable().default(null),
  gross: z.number(),
  collected: z.number(),
  outstanding: z.number(),
  case_count: z.number().int(),
  avg_case_value: z.number().nullable().default(null),
});
export type RevenueGroup = z.infer<typeof RevenueGroupSchema>;

export const RevenueDimensionSchema = z.object({
  dimension: z.string(),
  resolved: z.boolean(),
  groups: z.array(RevenueGroupSchema),
});
export type RevenueDimension = z.infer<typeof RevenueDimensionSchema>;

export const RevenueIntelligenceSchema = z.object({
  window: AnalyticsWindowSchema,
  filters: AnalyticsFiltersEchoSchema,
  gross_total: z.number(),
  collected_total: z.number(),
  outstanding_total: z.number(),
  avg_case_value: z.number().nullable().default(null),
  case_count: z.number().int(),
  dimensions: z.array(RevenueDimensionSchema),
});
export type RevenueIntelligence = z.infer<typeof RevenueIntelligenceSchema>;
