import { z } from "zod";
import { MarketingKpiSchema } from "./marketingAnalytics";

/**
 * ENG-474 — Calls dashboard contract.
 * Mirrors `apps/api/routers/dashboard.py` (CallsAnalyticsOut and its nested
 * `*Out` models) field-for-field. The backend serialises the date window
 * fields as `YYYY-MM-DD` (Pydantic `date`), so use a plain date string here
 * rather than the `Datetime` alias. KPI cards reuse `MarketingKpiSchema`
 * (value=null → "—"). `pending` lists the legacy call-center sections that
 * depend on the unbuilt Phase-3 telephony ingest — the UI renders an explicit
 * "pending Phase 3 comms ingest" card for each, never a fake zero.
 */

const DateOnly = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "expected YYYY-MM-DD");

export const CallsAnalyticsWindowSchema = z.object({
  start_date: DateOnly,
  end_date: DateOnly,
});
export type CallsAnalyticsWindow = z.infer<typeof CallsAnalyticsWindowSchema>;

export const CallsAnalyticsSchema = z.object({
  window: CallsAnalyticsWindowSchema,
  // True once any call event exists in the window → render KPIs; otherwise the
  // page shows a "no call events yet" empty state instead of fake numbers.
  connected: z.boolean(),
  kpis: z.array(MarketingKpiSchema),
  // Legacy call-center sections gated on Phase-3 comms ingest.
  pending: z.array(z.string()),
});
export type CallsAnalytics = z.infer<typeof CallsAnalyticsSchema>;
