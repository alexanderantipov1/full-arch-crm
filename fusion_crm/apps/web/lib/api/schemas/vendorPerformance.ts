import { z } from "zod";
import { Uuid } from "./common";
import {
  AnalyticsFiltersEchoSchema,
  AnalyticsWindowSchema,
} from "./journeyMetrics";

/**
 * ENG-517 — Vendor Performance page contract (B2.4).
 *
 * Mirrors `packages/analytics/schemas.py` (`VendorPerformanceOut`,
 * `VendorGroupOut`) field-for-field.
 * Served by: GET /dashboard/analytics/vendor
 *
 * REAL-DATA NOTE: `vendor_id` is 100% NULL on the fact today (verified
 * 2026-06-23: 0 of 115,715 rows). `vendor_attribution_wired` will be
 * `false` and `note` will carry the honest reason. The query is stable —
 * once ENG-569 populates vendor_id the page lights up automatically.
 *
 * `spend_managed` and `roi` are always `null` (no vendor→spend column on
 * the fact; vendor costs live in a separate data layer).
 */

export const VendorGroupSchema = z.object({
  vendor_id: Uuid.nullable().default(null),
  leads: z.number().int(),
  consults: z.number().int(),
  shows: z.number().int(),
  surgeries: z.number().int(),
  revenue: z.number(),
  collected: z.number(),
  /** Always null: no vendor→spend mapping on the analytics fact yet. */
  spend_managed: z.null().default(null),
  /** Always null without spend data. */
  roi: z.null().default(null),
});
export type VendorGroup = z.infer<typeof VendorGroupSchema>;

export const VendorPerformanceSchema = z.object({
  window: AnalyticsWindowSchema,
  filters: AnalyticsFiltersEchoSchema,
  /** False today: vendor_id is 100% NULL on the fact (ENG-569 wires this). */
  vendor_attribution_wired: z.boolean(),
  /** Human-readable reason when vendor_attribution_wired is false. */
  note: z.string().nullable().default(null),
  vendors: z.array(VendorGroupSchema),
});
export type VendorPerformance = z.infer<typeof VendorPerformanceSchema>;
