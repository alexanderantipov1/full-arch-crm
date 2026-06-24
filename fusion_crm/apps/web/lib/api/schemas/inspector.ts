import { z } from "zod";
import { Datetime, ProviderSchema, Uuid } from "./common";

export const RawEventSchema = z.object({
  id: Uuid,
  provider: ProviderSchema,
  external_id: z.string(),
  /** External entity kind (Lead, Patient, Appointment, ...). */
  kind: z.string(),
  fetched_at: Datetime,
  /** ID of the SyncRun that produced this row, if any. */
  sync_run_id: Uuid.nullable(),
  /** Verbatim raw payload — local dev only (env-gated server-side). */
  payload: z.record(z.unknown()),
  /** Optional resolved person_uid once normalizer ran. */
  resolved_person_uid: Uuid.nullable(),
});
export type RawEvent = z.infer<typeof RawEventSchema>;

export const RawEventListSchema = z.object({
  items: z.array(RawEventSchema),
  total: z.number().int().nonnegative(),
});
export type RawEventList = z.infer<typeof RawEventListSchema>;
