import { z } from "zod";

/**
 * ENG-482 — Full Funnel v2 (person-anchored) report contract.
 *
 * Mirrors `packages/analytics/schemas.py` (`FullFunnelV2Out` and its nested
 * `*Out` models) field-for-field. The funnel is anchored on
 * `identity.person`: each stage is counted as distinct persons and windowed on
 * its own system-of-truth timestamp (Salesforce lead created-at, CareStack
 * consultation scheduled-at, CareStack payment occurred-at).
 *
 * Month and month-window fields are `YYYY-MM` strings (not full timestamps), so
 * they use a plain month-string regex rather than the `Datetime` alias.
 *
 * Rendering rule: `spend` is `null` (render "—") for the `other` channel and
 * for any month with no ingested ad spend. Stage counts are real distinct-person
 * integers — a genuine `0` stays `0`, only `null` renders "—". `closed_won` is
 * "money received" (CareStack collected cash > 0), NOT the Salesforce
 * `is_won` flag, and is reported at the headline + month level only
 * (opportunity→channel attribution is deferred).
 */

const MonthOnly = z.string().regex(/^\d{4}-\d{2}$/, "expected YYYY-MM");

export const FullFunnelAudienceSchema = z.enum(["all", "marketing"]);
export type FullFunnelAudience = z.infer<typeof FullFunnelAudienceSchema>;

export const FullFunnelChannelSchema = z.enum(["google", "facebook", "other"]);
export type FullFunnelChannel = z.infer<typeof FullFunnelChannelSchema>;

export const FullFunnelWindowSchema = z.object({
  start_month: MonthOnly,
  end_month: MonthOnly,
});
export type FullFunnelWindow = z.infer<typeof FullFunnelWindowSchema>;

export const FullFunnelHeadlineSchema = z.object({
  leads: z.number(),
  // Consult stages are APPOINTMENT counts (one per consultation row, not
  // distinct persons), so they balance:
  //   consults_scheduled = showed + no_show + cancelled + rescheduled + pending
  consults_scheduled: z.number(),
  showed: z.number(),
  no_show: z.number(),
  cancelled: z.number(),
  rescheduled: z.number(),
  pending: z.number(),
  // Money-based closure: distinct paying persons (Net Collected > 0), not SF
  // is_won.
  closed_won: z.number(),
  revenue: z.number(),
});
export type FullFunnelHeadline = z.infer<typeof FullFunnelHeadlineSchema>;

export const FullFunnelMonthSchema = z.object({
  month: MonthOnly,
  // `null` when no ad spend was ingested for the month; the UI renders "—".
  spend: z.number().nullable(),
  leads: z.number(),
  // Consult stages are APPOINTMENT counts and balance:
  //   consults_scheduled = showed + no_show + cancelled + rescheduled + pending
  consults_scheduled: z.number(),
  showed: z.number(),
  no_show: z.number(),
  cancelled: z.number(),
  rescheduled: z.number(),
  pending: z.number(),
  closed_won: z.number(),
  revenue: z.number(),
});
export type FullFunnelMonth = z.infer<typeof FullFunnelMonthSchema>;

export const FullFunnelChannelRowSchema = z.object({
  month: MonthOnly,
  channel: FullFunnelChannelSchema,
  // `null` for the `other` channel and for months with no ingested spend.
  spend: z.number().nullable(),
  leads: z.number(),
  // Consult stages are APPOINTMENT counts and balance:
  //   consults_scheduled = showed + no_show + cancelled + rescheduled + pending
  consults_scheduled: z.number(),
  showed: z.number(),
  no_show: z.number(),
  cancelled: z.number(),
  rescheduled: z.number(),
  pending: z.number(),
  // No per-channel `closed_won`: it stays month-level only.
  revenue: z.number(),
});
export type FullFunnelChannelRow = z.infer<typeof FullFunnelChannelRowSchema>;

/**
 * Shared "not configured / not connected" marker. Reused by the Sales and SEO
 * analytics contracts (backend `FullFunnelNotConfiguredOut`) for tiles whose
 * source is not yet wired. The Full Funnel v2 report itself no longer embeds
 * these (its center/TC breakdowns were dropped in v2), but the shape stays here
 * because it is the canonical home other analytics schemas import from.
 */
export const FullFunnelNotConfiguredSchema = z.object({
  configured: z.literal(false),
  reason: z.string(),
  ticket: z.string(),
});
export type FullFunnelNotConfigured = z.infer<
  typeof FullFunnelNotConfiguredSchema
>;

export const FullFunnelSchema = z.object({
  audience: FullFunnelAudienceSchema,
  window: FullFunnelWindowSchema,
  channels: z.array(z.string()),
  headline: FullFunnelHeadlineSchema,
  by_month: z.array(FullFunnelMonthSchema),
  by_channel: z.array(FullFunnelChannelRowSchema),
});
export type FullFunnel = z.infer<typeof FullFunnelSchema>;
