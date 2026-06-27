import { z } from "zod";
import { Datetime, Uuid } from "./common";

export const CatalogProposalStatusSchema = z.enum([
  "proposed",
  "approved",
  "rejected",
  "unresolved",
]);
export type CatalogProposalStatus = z.infer<typeof CatalogProposalStatusSchema>;

export const CatalogProposalSourceTypeSchema = z.enum([
  "agent",
  "manual",
  "import",
]);
export type CatalogProposalSourceType = z.infer<
  typeof CatalogProposalSourceTypeSchema
>;

const CatalogProposalBaseSchema = z.object({
  raw_value: z.string().min(1).max(512),
  source_system: z.string().min(1).max(128),
  source_field: z.string().min(1).max(256),
  suggested_term: z.string().min(1).max(256),
  definition: z.string().min(1).max(2000),
  synonyms: z.array(z.string()).default([]),
  confidence: z.number().min(0).max(1),
  reason: z.string().min(1).max(2000),
  reviewer_note: z.string().max(2000).default(""),
  affected_questions: z.array(z.string()).default([]),
  affected_read_models: z.array(z.string()).default([]),
});

export const CatalogProposalSchema = CatalogProposalBaseSchema.extend({
  id: Uuid,
  tenant_id: Uuid,
  status: CatalogProposalStatusSchema,
  source_type: CatalogProposalSourceTypeSchema,
  source_reference_id: z.string().nullable().default(null),
  created_by_actor_id: Uuid.nullable().default(null),
  reviewed_by_actor_id: Uuid.nullable().default(null),
  reviewed_at: Datetime.nullable().default(null),
  created_at: Datetime,
  updated_at: Datetime,
});
export type CatalogProposal = z.infer<typeof CatalogProposalSchema>;

export const CatalogProposalListSchema = z.object({
  items: z.array(CatalogProposalSchema),
});
export type CatalogProposalList = z.infer<typeof CatalogProposalListSchema>;

export const CatalogProposalCreateInputSchema =
  CatalogProposalBaseSchema.extend({
    source_type: CatalogProposalSourceTypeSchema.default("manual"),
    source_reference_id: z.string().max(256).nullable().optional(),
  });
export type CatalogProposalCreateInput = z.infer<
  typeof CatalogProposalCreateInputSchema
>;

export const CatalogProposalUpdateInputSchema = CatalogProposalBaseSchema.partial();
export type CatalogProposalUpdateInput = z.infer<
  typeof CatalogProposalUpdateInputSchema
>;

export const CatalogProposalReviewInputSchema = z.object({
  status: CatalogProposalStatusSchema,
  reviewer_note: z.string().max(2000).default(""),
  reason: z.string().min(1).max(2000),
});
export type CatalogProposalReviewInput = z.infer<
  typeof CatalogProposalReviewInputSchema
>;

export const CatalogProposalImpactSchema = z.object({
  affected_questions: z.array(z.string()).default([]),
  affected_reports: z.array(z.string()).default([]),
  affected_read_models: z.array(z.string()).default([]),
  affected_dashboard_panels: z.array(z.string()).default([]),
  affected_chat_answers: z.array(z.string()).default([]),
  affected_agent_briefs: z.array(z.string()).default([]),
});
export type CatalogProposalImpact = z.infer<
  typeof CatalogProposalImpactSchema
>;

export const CatalogProposalImpactPreviewSchema = z.object({
  proposal_id: Uuid,
  impact: CatalogProposalImpactSchema,
  can_approve: z.boolean(),
  blockers: z.array(z.string()).default([]),
});
export type CatalogProposalImpactPreview = z.infer<
  typeof CatalogProposalImpactPreviewSchema
>;

export const CatalogProposalReviewResponseSchema = z.object({
  proposal: CatalogProposalSchema,
  impact: CatalogProposalImpactSchema,
  catalog_version_id: Uuid.nullable().default(null),
});
export type CatalogProposalReviewResponse = z.infer<
  typeof CatalogProposalReviewResponseSchema
>;

export const CatalogProposalHistoryEventSchema = z.object({
  action: z.string(),
  status: CatalogProposalStatusSchema,
  actor_id: Uuid.nullable().default(null),
  occurred_at: Datetime,
  reason: z.string().nullable().default(null),
  reviewer_note: z.string().nullable().default(null),
  catalog_version_id: Uuid.nullable().default(null),
});
export type CatalogProposalHistoryEvent = z.infer<
  typeof CatalogProposalHistoryEventSchema
>;

export const CatalogProposalHistorySchema = z.object({
  proposal_id: Uuid,
  items: z.array(CatalogProposalHistoryEventSchema),
});
export type CatalogProposalHistory = z.infer<
  typeof CatalogProposalHistorySchema
>;

export const CatalogVersionHistoryEntrySchema = z.object({
  id: Uuid,
  tenant_id: Uuid,
  term: z.string(),
  version: z.number().int(),
  review_status: z.string(),
  definition: z.string(),
  synonyms: z.array(z.string()).default([]),
  allowed_data_sources: z.array(z.string()).default([]),
  data_classes: z.array(z.string()).default([]),
  allowed_outputs: z.array(z.string()).default([]),
  canonical_fields: z.array(z.string()).default([]),
  row_level_fields: z.array(z.string()).default([]),
  aggregate_metrics: z.array(z.string()).default([]),
  used_by: z.array(z.string()).default([]),
  source_references: z.array(z.record(z.unknown())).default([]),
  previous_version_id: Uuid.nullable().default(null),
  proposal_id: Uuid.nullable().default(null),
  previous_value: z.record(z.unknown()).nullable().default(null),
  new_value: z.record(z.unknown()),
  reason: z.string(),
  affected_questions: z.array(z.string()).default([]),
  affected_read_models: z.array(z.string()).default([]),
  affected_reports: z.array(z.string()).default([]),
  affected_dashboard_panels: z.array(z.string()).default([]),
  affected_chat_answers: z.array(z.string()).default([]),
  affected_agent_briefs: z.array(z.string()).default([]),
  approved_by_actor_id: Uuid.nullable().default(null),
  approved_at: Datetime,
  created_at: Datetime,
  updated_at: Datetime,
});
export type CatalogVersionHistoryEntry = z.infer<
  typeof CatalogVersionHistoryEntrySchema
>;

export const CatalogVersionHistorySchema = z.object({
  term: z.string(),
  items: z.array(CatalogVersionHistoryEntrySchema),
});
export type CatalogVersionHistory = z.infer<
  typeof CatalogVersionHistorySchema
>;

export const CatalogDraftPatchInputSchema = z.object({
  proposal_ids: z.array(Uuid).default([]),
});
export type CatalogDraftPatchInput = z.infer<
  typeof CatalogDraftPatchInputSchema
>;

export const CatalogDraftPatchSchema = z.object({
  proposal_ids: z.array(Uuid),
  patch: z.array(z.record(z.unknown())),
  catalog_version_id: Uuid.nullable().default(null),
});
export type CatalogDraftPatch = z.infer<typeof CatalogDraftPatchSchema>;
