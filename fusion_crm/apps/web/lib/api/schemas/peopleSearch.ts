import { z } from "zod";
import { Datetime, Uuid } from "./common";

/**
 * Unified people search across Salesforce + CareStack + local identity.
 *
 * Phase 1 contract: the frontend issues a single GET to `/people/search/live`
 * with `phone` and/or `email` query params. The backend (ENG-120) fans out
 * to SF and CareStack, normalises identifiers, and returns matches per
 * provider plus any already-linked `identity.person.id` UUIDs.
 *
 * No PHI is ever surfaced — only ops-level identifiers (id, name, phone,
 * email, status, last_appointment date, location). No clinical fields.
 */

export const SfObjectTypeSchema = z.enum(["Lead", "Contact"]);
export type SfObjectType = z.infer<typeof SfObjectTypeSchema>;

export const SfPersonMatchSchema = z.object({
  id: z.string(),
  object_type: SfObjectTypeSchema,
  name: z.string().nullable(),
  phone: z.string().nullable(),
  email: z.string().nullable(),
  /** SF Lead.Status or Contact lifecycle stage; free-form per org config. */
  status: z.string().nullable(),
  last_modified: Datetime,
  /** Optional already-linked person_uid — server-side identity merge result. */
  linked_person_uid: Uuid.nullable(),
});
export type SfPersonMatch = z.infer<typeof SfPersonMatchSchema>;

export const CsPatientMatchSchema = z.object({
  /** CareStack Patient.id is a numeric int; keep as number. */
  id: z.number().int(),
  name: z.string().nullable(),
  phone: z.string().nullable(),
  email: z.string().nullable(),
  /** ISO timestamp of the most recent appointment; null if no appointments. */
  last_appointment: Datetime.nullable(),
  location_name: z.string().nullable(),
  /** Optional already-linked person_uid — server-side identity merge result. */
  linked_person_uid: Uuid.nullable(),
});
export type CsPatientMatch = z.infer<typeof CsPatientMatchSchema>;

export const PeopleSearchQuerySchema = z.object({
  phone_normalised: z.string().optional(),
  email_normalised: z.string().optional(),
});
export type PeopleSearchQuery = z.infer<typeof PeopleSearchQuerySchema>;

export const PeopleSearchWarningSchema = z.object({
  provider: z.enum(["salesforce", "carestack"]),
  code: z.enum(["not_connected", "search_failed"]),
  message: z.string(),
});
export type PeopleSearchWarning = z.infer<typeof PeopleSearchWarningSchema>;

export const PeopleSearchOutSchema = z.object({
  query: PeopleSearchQuerySchema,
  salesforce: z.object({
    matches: z.array(SfPersonMatchSchema),
  }),
  carestack: z.object({
    matches: z.array(CsPatientMatchSchema),
  }),
  /** UUIDs of identity.person rows that already aggregate any of the matches. */
  linked_person_uids: z.array(Uuid),
  /**
   * Non-fatal provider failures. Unified search must still return matches
   * from other sources when one integration is disconnected or temporarily
   * unavailable.
   */
  warnings: z.array(PeopleSearchWarningSchema).default([]),
});
export type PeopleSearchOut = z.infer<typeof PeopleSearchOutSchema>;

/** Frontend-only input shape — what the search bar sends to the hook. */
export interface PeopleSearchInput {
  phone?: string;
  email?: string;
}
