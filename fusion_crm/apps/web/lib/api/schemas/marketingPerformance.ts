import { z } from "zod";
import { Uuid } from "./common";
import {
  AnalyticsFiltersEchoSchema,
  AnalyticsWindowSchema,
} from "./journeyMetrics";

/**
 * ENG-516 (B2.3) — Marketing Performance page contract.
 *
 * Mirrors `packages/analytics/schemas.py` (`MarketingPerformanceOut` and nested
 * `*Out`) field-for-field. Served by
 * `GET /dashboard/analytics/marketing-performance`. Ad spend ⇄ outcomes by
 * Campaign and Source over the shared fact; each group carries Spend, Leads,
 * Consultations, Shows, Surgeries, Revenue + derived ROI / cost-per-stage.
 *
 * `spend` and every spend-derived metric are `number | null` → render "—" when
 * no ad-spend source is connected (never a fabricated 0). `Ad Set` / `Ad` come
 * back `resolved === false` ("no data"): the fact has no ad-set/ad dimension, so
 * outcomes can't be tied to them — `spend_without_leads` instead surfaces the
 * ad spend that produced no attributed leads.
 */

export const MarketingGroupSchema = z.object({
  group_id: Uuid.nullable().default(null),
  group_label: z.string().nullable().default(null),
  spend: z.number().nullable().default(null),
  leads: z.number().int(),
  consults: z.number().int(),
  shows: z.number().int(),
  surgeries: z.number().int(),
  revenue: z.number(),
  collected: z.number(),
  roi: z.number().nullable().default(null),
  cost_per_lead: z.number().nullable().default(null),
  cost_per_consult: z.number().nullable().default(null),
  cost_per_show: z.number().nullable().default(null),
  cost_per_surgery: z.number().nullable().default(null),
});
export type MarketingGroup = z.infer<typeof MarketingGroupSchema>;

export const MarketingBreakdownSchema = z.object({
  dimension: z.string(),
  resolved: z.boolean(),
  groups: z.array(MarketingGroupSchema),
  note: z.string().nullable().default(null),
});
export type MarketingBreakdown = z.infer<typeof MarketingBreakdownSchema>;

export const MarketingPerformanceSchema = z.object({
  window: AnalyticsWindowSchema,
  filters: AnalyticsFiltersEchoSchema,
  total_spend: z.number().nullable().default(null),
  allocated_spend: z.number().nullable().default(null),
  spend_without_leads: z.number().nullable().default(null),
  leads: z.number().int(),
  consults: z.number().int(),
  shows: z.number().int(),
  surgeries: z.number().int(),
  revenue_total: z.number(),
  collected_total: z.number(),
  roi: z.number().nullable().default(null),
  breakdowns: z.array(MarketingBreakdownSchema),
});
export type MarketingPerformance = z.infer<typeof MarketingPerformanceSchema>;
