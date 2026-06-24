import { z } from "zod";
import {
  AnalyticsFiltersEchoSchema,
  AnalyticsWindowSchema,
} from "./journeyMetrics";

/**
 * ENG-522 (B2.9) — Cost Intelligence page contract.
 *
 * Mirrors `packages/analytics/schemas.py` (`CostIntelligenceOut`,
 * `CostMetricOut`) field-for-field. Served by
 * `GET /dashboard/analytics/cost`.
 *
 * Marketing cost metrics are computable from window ad spend + funnel stage
 * counts. When no spend source is connected, `spend` is `null` and every
 * spend-derived metric has `value: null` + a `note` explaining why.
 *
 * Operational cost metrics (`cost_per_caller_conversion`,
 * `cost_per_coordinator_conversion`) are always `value: null` — the system
 * does not yet capture staff operational cost inputs. The `note` field
 * explains this honestly so the UI never needs to fabricate a value.
 */

export const CostMetricSchema = z.object({
  label: z.string(),
  /** null = no data (zero denominator, no spend, or inputs not captured). */
  value: z.number().nullable().default(null),
  /** Human-readable explanation of why `value` is null, or null when computed. */
  note: z.string().nullable().default(null),
});
export type CostMetric = z.infer<typeof CostMetricSchema>;

export const CostIntelligenceSchema = z.object({
  window: AnalyticsWindowSchema,
  filters: AnalyticsFiltersEchoSchema,
  /** Ground-truth window ad spend (null when no source connected). */
  spend: z.number().nullable().default(null),
  leads: z.number().int(),
  consults: z.number().int(),
  shows: z.number().int(),
  surgeries: z.number().int(),
  collected: z.number(),
  cost_per_lead: CostMetricSchema,
  cost_per_consult: CostMetricSchema,
  cost_per_show: CostMetricSchema,
  cost_per_surgery: CostMetricSchema,
  cost_per_revenue_dollar: CostMetricSchema,
  /** Always null — operational cost inputs not yet captured. */
  cost_per_caller_conversion: CostMetricSchema,
  /** Always null — operational cost inputs not yet captured. */
  cost_per_coordinator_conversion: CostMetricSchema,
});
export type CostIntelligence = z.infer<typeof CostIntelligenceSchema>;
