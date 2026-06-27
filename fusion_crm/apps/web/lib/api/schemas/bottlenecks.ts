import { z } from "zod";
import { Uuid } from "./common";
import {
  AnalyticsFiltersEchoSchema,
  AnalyticsWindowSchema,
} from "./journeyMetrics";

/**
 * ENG-524 (B2.11) — Bottleneck Detection page contract.
 *
 * Mirrors `packages/analytics/schemas.py` (`BottlenecksOut`, `BottleneckOut`,
 * `BottleneckEntityOut`) field-for-field. Served by
 * `GET /dashboard/analytics/bottlenecks`.
 *
 * Rule-based detector over `fact_patient_journey`. Four rule categories:
 * - `campaign_low_show`: campaign with many leads but poor show rate
 * - `coordinator_low_surgery_conversion`: coordinator show→surgery below median
 * - `doctor_low_acceptance`: doctor consult→acceptance below median
 * - `caller_low_booking`: caller lead→consult booking below median
 *
 * `findings` is empty when the cohort is too sparse to detect reliably (all
 * entities below minimum sample thresholds). No findings are invented from
 * noise. `estimated_revenue_loss` is null when the estimate is not computable
 * (zero denominator or no cohort data).
 */

export const BottleneckCategorySchema = z.enum([
  "campaign_low_show",
  "coordinator_low_surgery_conversion",
  "doctor_low_acceptance",
  "caller_low_booking",
]);
export type BottleneckCategory = z.infer<typeof BottleneckCategorySchema>;

export const BottleneckSeveritySchema = z.enum(["low", "medium", "high"]);
export type BottleneckSeverity = z.infer<typeof BottleneckSeveritySchema>;

export const BottleneckEntitySchema = z.object({
  /** UUID of the entity (null for the Unassigned bucket — never flagged). */
  id: Uuid.nullable().default(null),
  label: z.string(),
});
export type BottleneckEntity = z.infer<typeof BottleneckEntitySchema>;

export const BottleneckSchema = z.object({
  category: BottleneckCategorySchema,
  description: z.string(),
  severity: BottleneckSeveritySchema,
  /** Estimated revenue foregone vs. median performer; null when not computable. */
  estimated_revenue_loss: z.number().nullable().default(null),
  suggested_action: z.string(),
  entity: BottleneckEntitySchema,
});
export type Bottleneck = z.infer<typeof BottleneckSchema>;

export const BottlenecksSchema = z.object({
  window: AnalyticsWindowSchema,
  filters: AnalyticsFiltersEchoSchema,
  /** Sorted: high severity first, then by estimated_revenue_loss desc. */
  findings: z.array(BottleneckSchema),
});
export type Bottlenecks = z.infer<typeof BottlenecksSchema>;
