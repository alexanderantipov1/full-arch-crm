import { z } from "zod";
import {
  AnalyticsFiltersEchoSchema,
  AnalyticsWindowSchema,
} from "./journeyMetrics";

/**
 * ENG-526 — Cohort Analytics page contract.
 *
 * Mirrors `packages/analytics/schemas.py` (`CohortAnalyticsOut` and nested
 * `*Out`) field-for-field. Served by `GET /dashboard/analytics/cohort`. Cohorts
 * are months of `lead_date` (person-anchored, so bulk-import patients don't
 * distort the curve); each cell is cumulative collected revenue for persons
 * whose `first_payment_date` lands within N days of their lead date.
 */

export const CohortRevenueSchema = z.object({
  d30: z.number(),
  d60: z.number(),
  d90: z.number(),
  d180: z.number(),
  d365: z.number(),
});
export type CohortRevenue = z.infer<typeof CohortRevenueSchema>;

export const CohortRowSchema = z.object({
  cohort_month: z.string(),
  lead_count: z.number().int(),
  revenue: CohortRevenueSchema,
  collected_total: z.number(),
});
export type CohortRow = z.infer<typeof CohortRowSchema>;

export const CohortAnalyticsSchema = z.object({
  window: AnalyticsWindowSchema,
  filters: AnalyticsFiltersEchoSchema,
  horizons: z.array(z.number().int()),
  cohorts: z.array(CohortRowSchema),
});
export type CohortAnalytics = z.infer<typeof CohortAnalyticsSchema>;
