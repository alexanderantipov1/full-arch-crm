import { z } from "zod";
import { Uuid } from "./common";
import {
  AnalyticsFiltersEchoSchema,
  AnalyticsWindowSchema,
} from "./journeyMetrics";

/**
 * ENG-518/519/520 — Actor Performance page contracts.
 *
 * Mirrors `packages/analytics/schemas.py` (`CallerPerformanceOut`,
 * `CoordinatorPerformanceOut`, `DoctorPerformanceOut` and their nested types)
 * field-for-field. Served by:
 *   GET /dashboard/analytics/caller       (ENG-518)
 *   GET /dashboard/analytics/coordinator  (ENG-519)
 *   GET /dashboard/analytics/doctor       (ENG-520)
 *
 * Rendering rule: every derived ratio is `number | null`. `null` means the
 * denominator was 0 → renders "—", never a fabricated 0. `caller_id`,
 * `coordinator_id`, `doctor_id` are `null` for the "Unassigned" bucket.
 *
 * `calls_made` is `null` on every CallerGroupOut row (honest no-data: the
 * fact table has no per-call-attempt count column).
 */

// ---------------------------------------------------------------------------
// ENG-518 — Caller Performance
// ---------------------------------------------------------------------------

export const CallerGroupSchema = z.object({
  caller_id: Uuid.nullable().default(null),
  leads: z.number().int(),
  reached: z.number().int(),
  consults: z.number().int(),
  /** Always null: the fact has no dialer call-count column. */
  calls_made: z.null().default(null),
  lead_to_contact: z.number().nullable().default(null),
  lead_to_consult: z.number().nullable().default(null),
  collected: z.number(),
  revenue_per_lead: z.number().nullable().default(null),
  revenue_per_consult: z.number().nullable().default(null),
});
export type CallerGroup = z.infer<typeof CallerGroupSchema>;

export const CallerPerformanceSchema = z.object({
  window: AnalyticsWindowSchema,
  filters: AnalyticsFiltersEchoSchema,
  callers: z.array(CallerGroupSchema),
});
export type CallerPerformance = z.infer<typeof CallerPerformanceSchema>;

// ---------------------------------------------------------------------------
// ENG-519 — Coordinator Performance
// ---------------------------------------------------------------------------

export const CoordinatorGroupSchema = z.object({
  coordinator_id: Uuid.nullable().default(null),
  consults_assigned: z.number().int(),
  shows: z.number().int(),
  treatment_presented: z.number().int(),
  surgery_scheduled: z.number().int(),
  surgery_completed: z.number().int(),
  collected: z.number(),
  scheduled_to_show: z.number().nullable().default(null),
  show_to_surgery: z.number().nullable().default(null),
  revenue_per_consult: z.number().nullable().default(null),
});
export type CoordinatorGroup = z.infer<typeof CoordinatorGroupSchema>;

export const CoordinatorPerformanceSchema = z.object({
  window: AnalyticsWindowSchema,
  filters: AnalyticsFiltersEchoSchema,
  coordinators: z.array(CoordinatorGroupSchema),
});
export type CoordinatorPerformance = z.infer<typeof CoordinatorPerformanceSchema>;

// ---------------------------------------------------------------------------
// ENG-520 — Doctor Performance
// ---------------------------------------------------------------------------

export const DoctorGroupSchema = z.object({
  doctor_id: Uuid.nullable().default(null),
  consults: z.number().int(),
  treatment_presented: z.number().int(),
  treatment_accepted: z.number().int(),
  surgery_completed: z.number().int(),
  collected: z.number(),
  consult_to_accepted: z.number().nullable().default(null),
  accepted_to_surgery: z.number().nullable().default(null),
  revenue_per_consult: z.number().nullable().default(null),
  revenue_per_surgery: z.number().nullable().default(null),
});
export type DoctorGroup = z.infer<typeof DoctorGroupSchema>;

export const DoctorPerformanceSchema = z.object({
  window: AnalyticsWindowSchema,
  filters: AnalyticsFiltersEchoSchema,
  doctors: z.array(DoctorGroupSchema),
});
export type DoctorPerformance = z.infer<typeof DoctorPerformanceSchema>;
