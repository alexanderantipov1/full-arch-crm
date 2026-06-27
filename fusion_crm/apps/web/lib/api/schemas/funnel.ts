import { z } from "zod";
import { Datetime, Uuid } from "./common";
import { ResponsibilityRoleSchema } from "./person";

/** ENG-419: stable funnel-stage axis. Order matters — the FE renders
 * the dashboard in this order, and drop-off attribution walks the axis
 * left-to-right per person to pick "highest reached stage". */
export const FunnelStageSchema = z.enum([
  "lead_new",
  "lead_contacted",
  "consult_scheduled",
  "consult_no_show",
  "consult_completed",
  "opportunity_open",
  "opportunity_won",
  "opportunity_lost",
]);
export type FunnelStage = z.infer<typeof FunnelStageSchema>;

export const FunnelActorSchema = z.object({
  actor_id: Uuid,
  actor_type: z.string(),
  name: z.string(),
  role: ResponsibilityRoleSchema,
});
export type FunnelActor = z.infer<typeof FunnelActorSchema>;

export const FunnelStageActorBucketSchema = z.object({
  actor: FunnelActorSchema,
  event_count: z.number().int().nonnegative(),
  person_count: z.number().int().nonnegative(),
});
export type FunnelStageActorBucket = z.infer<
  typeof FunnelStageActorBucketSchema
>;

export const FunnelStageAggregateSchema = z.object({
  stage: FunnelStageSchema,
  event_count: z.number().int().nonnegative(),
  person_count: z.number().int().nonnegative(),
  by_actor: z.array(FunnelStageActorBucketSchema),
});
export type FunnelStageAggregate = z.infer<typeof FunnelStageAggregateSchema>;

export const FunnelAppliedFiltersSchema = z.object({
  from: Datetime.nullable().optional(),
  to: Datetime.nullable().optional(),
  source_provider: z.enum(["salesforce", "carestack"]).nullable().optional(),
  location_id: Uuid.nullable().optional(),
  role: ResponsibilityRoleSchema.nullable().optional(),
});
export type FunnelAppliedFilters = z.infer<typeof FunnelAppliedFiltersSchema>;

export const FunnelAggregateSchema = z.object({
  stages: z.array(FunnelStageAggregateSchema),
  filters: FunnelAppliedFiltersSchema,
});
export type FunnelAggregate = z.infer<typeof FunnelAggregateSchema>;

export const FunnelDropoffActorBucketSchema = z.object({
  /** ``null`` for persons whose drop-off event carried no operational
   * responsibility row (legacy events emitted before W2 ingest wire-up). */
  actor: FunnelActorSchema.nullable(),
  person_count: z.number().int().nonnegative(),
  dollar_total: z.number(),
});
export type FunnelDropoffActorBucket = z.infer<
  typeof FunnelDropoffActorBucketSchema
>;

export const FunnelDropoffStageSchema = z.object({
  stage: FunnelStageSchema,
  person_count: z.number().int().nonnegative(),
  dollar_total: z.number(),
  by_operational_actor: z.array(FunnelDropoffActorBucketSchema),
});
export type FunnelDropoffStage = z.infer<typeof FunnelDropoffStageSchema>;

export const FunnelDropoffSchema = z.object({
  stages: z.array(FunnelDropoffStageSchema),
  filters: FunnelAppliedFiltersSchema,
});
export type FunnelDropoff = z.infer<typeof FunnelDropoffSchema>;

export const FunnelRevenueByActorRowSchema = z.object({
  actor: FunnelActorSchema,
  collected_total: z.number(),
  payment_count: z.number().int().nonnegative(),
});
export type FunnelRevenueByActorRow = z.infer<
  typeof FunnelRevenueByActorRowSchema
>;

export const FunnelRevenueByActorSchema = z.object({
  items: z.array(FunnelRevenueByActorRowSchema),
  filters: FunnelAppliedFiltersSchema,
});
export type FunnelRevenueByActor = z.infer<typeof FunnelRevenueByActorSchema>;

export const FunnelOwnersSchema = z.object({
  items: z.array(FunnelActorSchema),
});
export type FunnelOwners = z.infer<typeof FunnelOwnersSchema>;
