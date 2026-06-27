import { z } from "zod";
import {
  AnalyticsFiltersEchoSchema,
  AnalyticsWindowSchema,
} from "./journeyMetrics";

/**
 * ENG-515 — Funnel Analytics page contract.
 *
 * Mirrors `packages/analytics/schemas.py` (`FunnelStagesOut` / `FunnelStageOut`)
 * field-for-field. Served by `GET /dashboard/analytics/funnel-stages`. The
 * nine-point patient funnel over `fact_patient_journey`, added alongside the
 * existing Full-Funnel v2 (it does not replace it). `conversion` / `cost` are
 * `number | null` → render "—" (entry stage has no conversion; cost is null
 * until an ad-spend source is connected). B1-unresolved stages report count 0.
 */

export const PatientFunnelStageSchema = z.object({
  key: z.string(),
  label: z.string(),
  count: z.number().int(),
  revenue: z.number(),
  collected: z.number(),
  conversion: z.number().nullable().default(null),
  cost: z.number().nullable().default(null),
});
export type PatientFunnelStage = z.infer<typeof PatientFunnelStageSchema>;

export const FunnelStagesSchema = z.object({
  window: AnalyticsWindowSchema,
  filters: AnalyticsFiltersEchoSchema,
  stages: z.array(PatientFunnelStageSchema),
  spend: z.number().nullable().default(null),
  patients: z.number().int(),
  revenue_total: z.number(),
  collected_total: z.number(),
});
export type FunnelStages = z.infer<typeof FunnelStagesSchema>;
