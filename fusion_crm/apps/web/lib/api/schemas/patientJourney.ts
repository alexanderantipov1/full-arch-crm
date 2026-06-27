import { z } from "zod";
import { Datetime, Uuid } from "./common";

/**
 * ENG-523 — Patient Journey page contract.
 *
 * Mirrors `packages/analytics/schemas.py` (`PatientJourneyOut` / `JourneyStepOut`)
 * field-for-field. Served by
 * `GET /dashboard/analytics/patient-journey/{person_uid}`. One person's
 * fact-derived stage timeline; `found === false` when the person has no fact
 * row. `occurred_at` is null for stages never reached; `responsible_employee`
 * stays null until B1.1/B1.2; `revenue` is populated only on the payment step.
 * The granular operational-timeline (ENG-235) is fetched separately and merged
 * on the page.
 */

export const JourneyStepSchema = z.object({
  key: z.string(),
  label: z.string(),
  occurred_at: Datetime.nullable().default(null),
  responsible_employee: z.string().nullable().default(null),
  revenue: z.number().nullable().default(null),
});
export type JourneyStep = z.infer<typeof JourneyStepSchema>;

export const PatientJourneySchema = z.object({
  person_uid: Uuid,
  found: z.boolean(),
  campaign_id: Uuid.nullable().default(null),
  campaign_name: z.string().nullable().default(null),
  source: z.string().nullable().default(null),
  location_id: Uuid.nullable().default(null),
  revenue_amount: z.number().nullable().default(null),
  collected_amount: z.number().nullable().default(null),
  steps: z.array(JourneyStepSchema),
});
export type PatientJourney = z.infer<typeof PatientJourneySchema>;
