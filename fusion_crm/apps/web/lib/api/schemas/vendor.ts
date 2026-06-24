import { z } from "zod";

/**
 * ENG-570 — Vendor entity contract. Mirrors `packages/attribution/schemas.py`
 * (VendorOut / VendorIn / VendorUpdateIn). A vendor is WHO manages the traffic:
 * an external agency or our own in-house team.
 */

export const VENDOR_KINDS = ["agency", "in_house"] as const;
export type VendorKind = (typeof VENDOR_KINDS)[number];

export const VENDOR_KIND_LABELS: Record<VendorKind, string> = {
  agency: "Agency",
  in_house: "In-house",
};

export const VendorSchema = z.object({
  id: z.string().uuid(),
  slug: z.string(),
  name: z.string(),
  kind: z.string(),
  active: z.boolean(),
  color: z.string().nullable(),
  notes: z.string().nullable(),
  // Monthly spend (ENG-573). flat_monthly_fee=true → monthly_fee is the amount
  // for every month; false → per-month amounts live in vendor costs.
  monthly_fee: z.number().nullable(),
  flat_monthly_fee: z.boolean(),
  fee_currency: z.string(),
  source_node_id: z.string().uuid().nullable(),
});
export type Vendor = z.infer<typeof VendorSchema>;

export const VendorListSchema = z.array(VendorSchema);

export type VendorCreate = {
  name: string;
  kind: VendorKind;
  slug?: string;
  color?: string | null;
  notes?: string | null;
  active?: boolean;
  monthly_fee?: number | null;
  flat_monthly_fee?: boolean;
  fee_currency?: string;
};

export type VendorUpdate = {
  name?: string;
  kind?: VendorKind;
  color?: string | null;
  notes?: string | null;
  active?: boolean;
  monthly_fee?: number | null;
  flat_monthly_fee?: boolean;
  fee_currency?: string;
};

// Per-month fee row (ENG-573), used when a vendor's fee is not flat.
export const VendorCostSchema = z.object({
  id: z.string().uuid(),
  vendor_id: z.string().uuid(),
  period_month: z.string(), // YYYY-MM
  amount: z.number(),
  note: z.string().nullable(),
});
export type VendorCost = z.infer<typeof VendorCostSchema>;

export const VendorCostListSchema = z.array(VendorCostSchema);

export type VendorCostInput = {
  period_month: string;
  amount: number;
  note?: string | null;
};

// Vendor claim — bind matching traffic to a vendor (ENG-571).
export const VendorClaimSchema = z.object({
  id: z.string().uuid(),
  vendor_id: z.string().uuid(),
  match_field: z.string(),
  match_op: z.string(),
  match_value: z.string(),
  priority: z.number(),
  active: z.boolean(),
  origin: z.string(),
});
export type VendorClaim = z.infer<typeof VendorClaimSchema>;

export const VendorClaimListSchema = z.array(VendorClaimSchema);

export type VendorClaimInput = {
  match_field: string;
  match_op?: string;
  match_value: string;
  priority?: number;
  origin?: string; // "manual" | "agent" (ENG-574)
};

// Distinct traffic signatures behind the Unassigned (no-vendor) leads.
export const SignatureValueSchema = z.object({
  match_field: z.string(),
  value: z.string(),
  lead_count: z.number(),
});
export type SignatureValue = z.infer<typeof SignatureValueSchema>;

export const UnassignedSignaturesSchema = z.object({
  items: z.array(SignatureValueSchema),
  scanned: z.number(),
  capped: z.boolean(),
});
export type UnassignedSignatures = z.infer<typeof UnassignedSignaturesSchema>;

// Agent-proposed bindings for a vendor (ENG-574).
export const ClaimSuggestionSchema = z.object({
  match_field: z.string(),
  value: z.string(),
  lead_count: z.number(),
  rationale: z.string(),
});
export type ClaimSuggestion = z.infer<typeof ClaimSuggestionSchema>;

export const ClaimSuggestionsSchema = z.object({
  items: z.array(ClaimSuggestionSchema),
  scanned: z.number(),
  capped: z.boolean(),
});
export type ClaimSuggestions = z.infer<typeof ClaimSuggestionsSchema>;
