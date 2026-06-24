import { z } from "zod";
import { Datetime } from "./common";

/**
 * ENG-391 — DEV Lead Sources explorer contract.
 * Mirrors `packages/ops/schemas.py` (LeadSourceTreeOut / LeadSourceLeadListOut).
 */

export type LeadSourceNode = {
  key: string;
  label: string;
  level: string;
  leads: number;
  consults_scheduled: number;
  consults_attended: number;
  collected_amount: number;
  children: LeadSourceNode[];
};

export const LeadSourceNodeSchema: z.ZodType<LeadSourceNode> = z.lazy(() =>
  z.object({
    key: z.string(),
    label: z.string(),
    level: z.string(),
    leads: z.number(),
    consults_scheduled: z.number(),
    consults_attended: z.number(),
    collected_amount: z.number(),
    children: z.array(LeadSourceNodeSchema),
  }),
);

export const LeadSourceTreeSchema = z.object({
  total_leads: z.number(),
  consults_scheduled: z.number(),
  consults_attended: z.number(),
  collected_amount: z.number(),
  sources: z.array(LeadSourceNodeSchema),
});
export type LeadSourceTree = z.infer<typeof LeadSourceTreeSchema>;

export const LeadSourceLeadItemSchema = z.object({
  id: z.string().uuid(),
  person_uid: z.string().uuid(),
  display_name: z.string().nullable(),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  collected_amount: z.number(),
  assigned_center: z.string().nullable(),
  location_mismatch: z.boolean(),
  status: z.string(),
  source_label: z.string(),
  utm_medium: z.string().nullable(),
  utm_campaign: z.string().nullable(),
  created_at: Datetime,
  provider_created_at: Datetime.nullable(),
  attribution: z.record(z.unknown()),
});
export type LeadSourceLeadItem = z.infer<typeof LeadSourceLeadItemSchema>;

export const LeadSourceLeadListSchema = z.object({
  total: z.number(),
  items: z.array(LeadSourceLeadItemSchema),
});
export type LeadSourceLeadList = z.infer<typeof LeadSourceLeadListSchema>;
