import { z } from "zod";
import { Uuid } from "./common";
import {
  AnalyticsFiltersEchoSchema,
  AnalyticsWindowSchema,
} from "./journeyMetrics";

/**
 * ENG-527 — Revenue Influence Matrix page contract (B2.14).
 *
 * Mirrors `packages/analytics/schemas.py` (`RevenueInfluenceMatrixOut`,
 * `InfluenceRowOut`) field-for-field.
 * Served by: GET /dashboard/analytics/revenue-influence
 *
 * DOUBLE-COUNTING CAVEAT (intentional per-spec):
 *   The same patient's collected revenue is counted once per role dimension.
 *   A patient with both a caller and a coordinator assigned contributes their
 *   revenue to the Caller row AND the Coordinator row. This is by design —
 *   "Revenue Influenced" measures each employee's influence on the outcome,
 *   not an additive breakdown. The matrix MUST NOT be summed across roles.
 *
 * Vendor role rows will be empty today (vendor_id 100% NULL — see ENG-517).
 */

export const InfluenceRowSchema = z.object({
  employee_id: Uuid.nullable().default(null),
  /** Short display label: first 8 chars of UUID, or "Unassigned". */
  employee_label: z.string(),
  /** One of: "vendor" | "caller" | "coordinator" | "doctor" */
  role: z.string(),
  revenue_influenced: z.number(),
  case_count: z.number().int(),
});
export type InfluenceRow = z.infer<typeof InfluenceRowSchema>;

export const RevenueInfluenceMatrixSchema = z.object({
  window: AnalyticsWindowSchema,
  filters: AnalyticsFiltersEchoSchema,
  rows: z.array(InfluenceRowSchema),
});
export type RevenueInfluenceMatrix = z.infer<
  typeof RevenueInfluenceMatrixSchema
>;
