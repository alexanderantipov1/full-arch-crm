import { z } from "zod";
import { Datetime } from "./common";

/**
 * ENG-450 (Block D) — Attribution funnel analytics contract.
 * Mirrors `packages/attribution/schemas.py`
 * (AttributionTreeOut / AttributionLeadListOut).
 */

export type AttributionTreeNode = {
  key: string;
  label: string;
  level: string; // "vendor" | "channel" | "campaign"
  leads: number;
  consults_scheduled: number;
  consults_attended: number;
  collected_amount: number;
  // Vendor-level only (ENG-572/ENG-573): colour, and monthly cost + CPL when a
  // period is requested.
  color: string | null;
  monthly_cost: number | null;
  cost_per_lead: number | null;
  children: AttributionTreeNode[];
};

export const AttributionTreeNodeSchema: z.ZodType<AttributionTreeNode> = z.lazy(
  () =>
    z.object({
      key: z.string(),
      label: z.string(),
      level: z.string(),
      leads: z.number(),
      consults_scheduled: z.number(),
      consults_attended: z.number(),
      collected_amount: z.number(),
      color: z.string().nullable(),
      monthly_cost: z.number().nullable(),
      cost_per_lead: z.number().nullable(),
      children: z.array(AttributionTreeNodeSchema),
    }),
);

export const AttributionTreeSchema = z.object({
  total_leads: z.number(),
  needs_review: z.number(),
  consults_scheduled: z.number(),
  consults_attended: z.number(),
  collected_amount: z.number(),
  nodes: z.array(AttributionTreeNodeSchema),
});
export type AttributionTree = z.infer<typeof AttributionTreeSchema>;

export const AttributionLeadItemSchema = z.object({
  person_uid: z.string().uuid(),
  sf_lead_id: z.string().nullable(),
  display_name: z.string().nullable(),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  vendor: z.string().nullable(),
  channel: z.string().nullable(),
  campaign: z.string().nullable(),
  created_by_name: z.string().nullable(),
  method: z.string(),
  source_signal: z.string().nullable(),
  confidence: z.number().nullable(),
  collected_amount: z.number(),
  resolved_at: Datetime,
});
export type AttributionLeadItem = z.infer<typeof AttributionLeadItemSchema>;

export const AttributionLeadListSchema = z.object({
  total: z.number(),
  items: z.array(AttributionLeadItemSchema),
});
export type AttributionLeadList = z.infer<typeof AttributionLeadListSchema>;
