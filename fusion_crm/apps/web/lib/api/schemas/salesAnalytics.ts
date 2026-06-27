import { z } from "zod";
import { Datetime } from "./common";
import { ConsultationStatusSchema } from "./person";
import { MarketingKpiSchema } from "./marketingAnalytics";
import { FullFunnelNotConfiguredSchema } from "./fullFunnel";

/**
 * ENG-473 — Sales Pipeline dashboard contract.
 * Mirrors `apps/api/routers/dashboard.py` (SalesAnalyticsOut and its nested
 * `*Out` models) field-for-field. KPI cards reuse the marketing
 * `MarketingKpiSchema` (value=null → "—"); the follow-up call/text/email split
 * reuses the full-funnel not-configured marker (only `call_logged` events are
 * ingested). `scheduled_at` / `close_date` are full timestamps (Pydantic
 * `datetime`) so use the `Datetime` alias, not a date-only string.
 */

export const SalesPipelineStageSchema = z.object({
  stage: z.string(),
  count: z.number(),
  value: z.number(),
});
export type SalesPipelineStage = z.infer<typeof SalesPipelineStageSchema>;

export const SalesTcLeaderboardRowSchema = z.object({
  tc: z.string(),
  opps: z.number(),
  won: z.number(),
  lost: z.number(),
  // Won ÷ (won + lost); `null` when the TC has no closed opps → "—".
  close_rate: z.number().nullable(),
  value: z.number(),
  won_revenue: z.number(),
  collected: z.number(),
});
export type SalesTcLeaderboardRow = z.infer<typeof SalesTcLeaderboardRowSchema>;

export const SalesConsultationSchema = z.object({
  consultation_id: z.string().uuid(),
  // Identity display name (staff-frontend PHI policy permits it); `null` when
  // identity has no record.
  patient: z.string().nullable(),
  // TC / stage / opp_value / close_date come from the covering opportunity and
  // are `null` when none is linked.
  tc: z.string().nullable(),
  status: ConsultationStatusSchema,
  scheduled_at: Datetime,
  stage: z.string().nullable(),
  opp_value: z.number().nullable(),
  paid: z.number(),
  // `opp_value - paid`; `null` when there is no opportunity value to bill.
  balance: z.number().nullable(),
  close_date: Datetime.nullable(),
});
export type SalesConsultation = z.infer<typeof SalesConsultationSchema>;

export const SalesAnalyticsSchema = z.object({
  kpis: z.array(MarketingKpiSchema),
  pipeline_by_stage: z.array(SalesPipelineStageSchema),
  tc_leaderboard: z.array(SalesTcLeaderboardRowSchema),
  consultations: z.array(SalesConsultationSchema),
  // Patient follow-up calls/texts/emails split is not connected (only
  // call_logged events are ingested) — rendered as a not-configured marker.
  followups: FullFunnelNotConfiguredSchema,
});
export type SalesAnalytics = z.infer<typeof SalesAnalyticsSchema>;
