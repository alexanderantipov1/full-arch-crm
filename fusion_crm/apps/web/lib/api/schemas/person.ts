import { z } from "zod";
import { Datetime, ProviderSchema, Uuid } from "./common";

export const LeadStatusSchema = z.enum([
  "new",
  "qualified",
  "contacted",
  "booked",
  "lost",
]);
export type LeadStatus = z.infer<typeof LeadStatusSchema>;

export const ConsultationStatusSchema = z.enum([
  "scheduled",
  "completed",
  "no_show",
  "cancelled",
  "rescheduled",
]);
export type ConsultationStatus = z.infer<typeof ConsultationStatusSchema>;

export const ConsultationKindSchema = z.enum([
  "initial",
  "follow_up",
  "treatment",
  "other",
]);
export type ConsultationKind = z.infer<typeof ConsultationKindSchema>;

export const RelationshipKindSchema = z.enum(["prospect", "patient"]);
export type RelationshipKind = z.infer<typeof RelationshipKindSchema>;

export const RelationshipStatusSchema = z.enum([
  "unknown",
  "consult_scheduled",
  "consult_completed",
  "no_show",
  "cancelled",
]);
export type RelationshipStatus = z.infer<typeof RelationshipStatusSchema>;

export const SourceLinkSchema = z.object({
  provider: ProviderSchema,
  external_id: z.string(),
  entity: z.string(),
  confidence: z.number().min(0).max(1),
  provider_url: z.string().nullable().optional(),
  first_seen_at: Datetime.nullable().optional(),
});
export type SourceLink = z.infer<typeof SourceLinkSchema>;

export const PersonSummarySchema = z.object({
  id: Uuid,
  display_name: z.string(),
  email: z.string().email().nullable(),
  phone: z.string().nullable(),
  /** Aggregate flags driven by ops data (no PHI). */
  has_lead: z.boolean(),
  has_consultation: z.boolean(),
  /** Latest activity timestamp across SF + CareStack. */
  last_activity_at: Datetime.nullable(),
  source_providers: z.array(ProviderSchema),
});
export type PersonSummary = z.infer<typeof PersonSummarySchema>;

export const PersonListSchema = z.object({
  items: z.array(PersonSummarySchema),
  total: z.number().int().nonnegative(),
});
export type PersonList = z.infer<typeof PersonListSchema>;

export const TimelineEventKindSchema = z.enum([
  "lead_created",
  "lead_updated",
  "consultation_scheduled",
  "consultation_completed",
  "consultation_cancelled",
  "merge",
  "note",
]);
export type TimelineEventKind = z.infer<typeof TimelineEventKindSchema>;

export const TimelineEventSchema = z.object({
  id: Uuid,
  kind: TimelineEventKindSchema,
  occurred_at: Datetime,
  provider: ProviderSchema.nullable(),
  /** Short human label — never raw clinical text. */
  summary: z.string(),
  /** Flat key-value bag of safe metadata (lead_status, source_id, etc). */
  details: z.record(z.union([z.string(), z.number(), z.boolean(), z.null()])),
});
export type TimelineEvent = z.infer<typeof TimelineEventSchema>;

// Mirrors backend EVENT_KINDS (packages/interaction/models.py). A kind
// the backend can return but this enum lacks fails the Zod parse and
// silently EMPTIES the whole timeline (the ENG-143 trap) — keep the two
// lists in lockstep.
export const OperationalTimelineEventKindSchema = z.enum([
  "lead_created",
  "lead_updated",
  "consultation_scheduled",
  "consultation_created",
  "consultation_rescheduled",
  "consultation_cancelled",
  "consultation_completed",
  "consultation_no_show",
  "task_created",
  "task_completed",
  "call_logged",
  "call_reference_found",
  "case_opened",
  "case_closed",
  "opportunity_created",
  "opportunity_won",
  "opportunity_lost",
  // ENG-382 funnel segments.
  "opportunity_stage_changed",
  "contact_created",
  "treatment_proposed",
  "treatment_completed",
  "invoice_created",
  // CareStack money events (ENG-283 / ENG-418): backend EventKind emits these;
  // FE enum MUST include them or a payment-bearing timeline fails Zod parse.
  "payment_recorded",
  "payment_refunded",
  "payment_reversed",
  "payment_applied",
]);
export type OperationalTimelineEventKind = z.infer<
  typeof OperationalTimelineEventKindSchema
>;

// Mirrors backend SOURCE_KINDS (packages/interaction/models.py) — same
// lockstep rule as the event-kind enum above.
export const OperationalTimelineSourceKindSchema = z.enum([
  "salesforce_lead",
  "salesforce_event",
  "salesforce_task",
  "salesforce_opportunity",
  "salesforce_case",
  // ENG-382 funnel segments.
  "salesforce_contact",
  "salesforce_account",
  "salesforce_opportunity_history",
  "carestack_appointment",
  "carestack_patient",
  "carestack_treatment_procedure",
  "carestack_invoice",
  // ENG-418: source_kind for the CareStack accounting-transaction ingest path.
  "carestack_accounting_transaction",
]);
export type OperationalTimelineSourceKind = z.infer<
  typeof OperationalTimelineSourceKindSchema
>;

export const OperationalTimelineDataClassSchema = z.enum([
  "public",
  "operational",
  "clinical_summary",
  "phi_protected",
  "call_recording_ref",
  "billing",
]);
export type OperationalTimelineDataClass = z.infer<
  typeof OperationalTimelineDataClassSchema
>;

export const OperationalTimelineReviewStatusSchema = z.enum([
  "auto",
  "pending_review",
  "reviewed",
  "rejected",
]);
export type OperationalTimelineReviewStatus = z.infer<
  typeof OperationalTimelineReviewStatusSchema
>;

export const OperationalTimelineProjectionTypeSchema = z.enum([
  "ops_lead",
  "ops_consultation",
  "ops_followup_task",
]);
export type OperationalTimelineProjectionType = z.infer<
  typeof OperationalTimelineProjectionTypeSchema
>;

export const OperationalTimelineProjectionSchema = z.object({
  type: OperationalTimelineProjectionTypeSchema,
  id: Uuid,
  status: z.string().nullable().optional(),
  scheduled_at: Datetime.nullable().optional(),
  due_at: Datetime.nullable().optional(),
});
export type OperationalTimelineProjection = z.infer<
  typeof OperationalTimelineProjectionSchema
>;

/** ENG-418: funnel responsibility role enumeration. Mirrors
 * ``packages.interaction.models.RESPONSIBILITY_ROLES``. */
export const ResponsibilityRoleSchema = z.enum(["operational", "clinical"]);
export type ResponsibilityRole = z.infer<typeof ResponsibilityRoleSchema>;

/** ENG-418: one responsible-actor row attached to a timeline entry. */
export const PersonTimelineResponsibleSchema = z.object({
  actor_id: Uuid,
  role: ResponsibilityRoleSchema,
  actor_type: z.string(),
  name: z.string(),
});
export type PersonTimelineResponsible = z.infer<
  typeof PersonTimelineResponsibleSchema
>;

/** One curated label/value pair on a timeline node's "what happened"
 * card. Timestamps are already formatted in the company timezone by the
 * backend. */
export const TimelineNodeDetailFieldSchema = z.object({
  label: z.string(),
  value: z.string(),
});
export type TimelineNodeDetailField = z.infer<
  typeof TimelineNodeDetailFieldSchema
>;

/** Curated "what actually happened" card, inlined per timeline node — the
 * verbatim ``ingest.raw_event`` projected into human-readable fields
 * (task Type/Subject/Description, appointment notes/schedule, …). */
export const TimelineNodeDetailSchema = z.object({
  title: z.string().nullable().default(null),
  /** Human status label (e.g. "Completed", "Not Started", "Scheduled"). */
  status: z.string().nullable().default(null),
  /** `true`/`false` only for kinds with done/not-done semantics (SF
   * Tasks); `null` otherwise. Drives the completion badge. */
  is_complete: z.boolean().nullable().default(null),
  fields: z.array(TimelineNodeDetailFieldSchema).default([]),
});
export type TimelineNodeDetail = z.infer<typeof TimelineNodeDetailSchema>;

export const OperationalTimelineEntrySchema = z.object({
  kind: OperationalTimelineEventKindSchema,
  occurred_at: Datetime,
  source_provider: ProviderSchema,
  source_kind: OperationalTimelineSourceKindSchema.nullable(),
  source_external_id: z.string().nullable(),
  /** Link to the backing ``ingest.raw_event``; `null` for derived events
   * with no raw row (e.g. `call_reference_found`). */
  source_event_id: Uuid.nullable().optional(),
  /** Curated "what happened" card, inlined so the whole chain renders at
   * once. `null` for nodes with no raw row to project. */
  detail: TimelineNodeDetailSchema.nullable().optional(),
  data_class: OperationalTimelineDataClassSchema,
  review_status: OperationalTimelineReviewStatusSchema,
  summary: z.string(),
  projection: OperationalTimelineProjectionSchema.nullable(),
  /** ENG-418: operational owner(s) for this node — agent/TC. Empty when
   * the legacy ingest pre-W2 emitted the event with no responsibility
   * row attached. */
  operational_responsibles: z
    .array(PersonTimelineResponsibleSchema)
    .default([]),
  /** ENG-418: clinical owner(s) for this node — typically a doctor on
   * consults / treatments. Empty for pre-consult events and for SF
   * events that carry no clinical actor. */
  clinical_responsibles: z
    .array(PersonTimelineResponsibleSchema)
    .default([]),
});
export type OperationalTimelineEntry = z.infer<
  typeof OperationalTimelineEntrySchema
>;

/** ENG-418: current-owner header for the chain UI. ``stage="lead"``
 * means the person is still in the pre-Opportunity phase and the Lead
 * owner is in charge. ``stage="opportunity"`` means at least one
 * non-closed-lost Opportunity exists; its owner (the TC) is in charge. */
export const PersonTimelineCurrentOwnerSchema = z.object({
  stage: z.enum(["lead", "opportunity"]),
  actor_id: Uuid.nullable(),
  actor_type: z.string().nullable(),
  name: z.string().nullable(),
  source_provider: z.string(),
  external_id: z.string(),
  opportunity_id: Uuid.nullable().optional(),
});
export type PersonTimelineCurrentOwner = z.infer<
  typeof PersonTimelineCurrentOwnerSchema
>;

export const PersonOperationalTimelineSchema = z.object({
  items: z.array(OperationalTimelineEntrySchema),
  total: z.number().int().nonnegative(),
  /** ENG-418: who is currently responsible for this person in the
   * funnel — drives the chain-card header. Lead owner until an
   * Opportunity exists, then the Opportunity owner (TC). `null` when
   * the person has neither a Lead nor an Opportunity row yet. */
  current_owner: PersonTimelineCurrentOwnerSchema.nullable().optional(),
  /** IANA timezone of the company (`tenant.timezone`); the UI renders
   * every timestamp in this zone so "when" is unambiguous. */
  timezone: z.string().default("America/Los_Angeles"),
});
export type PersonOperationalTimeline = z.infer<
  typeof PersonOperationalTimelineSchema
>;

export const OpsConsultationSchema = z.object({
  id: Uuid,
  person_uid: Uuid,
  source_provider: ProviderSchema,
  source_instance: z.string(),
  external_id: z.string(),
  scheduled_at: Datetime,
  duration_minutes: z.number().int().nonnegative().nullable(),
  status: ConsultationStatusSchema,
  consultation_kind: ConsultationKindSchema,
  location_id: Uuid.nullable(),
  provider_clinician_name: z.string().nullable(),
  raw_event_id: Uuid.nullable(),
  created_at: Datetime,
  updated_at: Datetime,
});
export type OpsConsultation = z.infer<typeof OpsConsultationSchema>;

export const PersonLocationProfileSchema = z.object({
  id: Uuid,
  person_uid: Uuid,
  location_id: Uuid,
  relationship_kind: RelationshipKindSchema,
  relationship_status: RelationshipStatusSchema,
  last_evidence_provider: ProviderSchema.nullable(),
  last_evidence_source_instance: z.string().nullable(),
  last_evidence_external_id: z.string().nullable(),
  last_evidence_at: Datetime.nullable(),
  last_consultation_id: Uuid.nullable(),
  last_raw_event_id: Uuid.nullable(),
  created_at: Datetime,
  updated_at: Datetime,
});
export type PersonLocationProfile = z.infer<
  typeof PersonLocationProfileSchema
>;

export const PersonCarestackOriginRowSchema = z.object({
  patient_id: z.string(),
  earliest_activity_at: Datetime.nullable().optional(),
  latest_activity_at: Datetime.nullable().optional(),
  default_location_id: z.number().int().nullable().optional(),
  default_location_name: z.string().nullable().optional(),
  default_provider_id: z.number().int().nullable().optional(),
  default_provider_name: z.string().nullable().optional(),
  city: z.string().nullable().optional(),
  state: z.string().nullable().optional(),
  /** ENG-310: per-pid name (multi-link row label "First Last · pid"). */
  first_name: z.string().nullable().optional(),
  last_name: z.string().nullable().optional(),
  /** ENG-310: patient details panel — click-to-reveal. */
  dob: z.string().nullable().optional(),
  gender: z.string().nullable().optional(),
  marital_status: z.string().nullable().optional(),
  mobile: z.string().nullable().optional(),
  phone_with_ext: z.string().nullable().optional(),
  work_phone_with_ext: z.string().nullable().optional(),
  email: z.string().nullable().optional(),
  address_line1: z.string().nullable().optional(),
  address_line2: z.string().nullable().optional(),
  address_zip: z.string().nullable().optional(),
  patient_identifier: z.string().nullable().optional(),
  account_id: z.string().nullable().optional(),
});
export type PersonCarestackOriginRow = z.infer<
  typeof PersonCarestackOriginRowSchema
>;

/** ENG-310: bidirectional household link — sibling person sharing a
 * normalised phone or email. Household ≠ identity merge: financials and
 * consultations stay on each ``person_uid``. */
export const PersonHouseholdMemberSchema = z.object({
  person_uid: z.string(),
  display_name: z.string().nullable().optional(),
  shared_via: z.enum(["phone", "email", "both"]),
  shared_value_masked: z.string(),
});
export type PersonHouseholdMember = z.infer<
  typeof PersonHouseholdMemberSchema
>;

export const PersonFinancialSummarySchema = z.object({
  /** Σ PROCEDURECOMPLETED debit on the patient's accounting feed
   * (deduped by external_id, latest received_at). */
  billed: z.number(),
  /** Net (debit − credit) Σ PATIENTADJUSTMENT + FEEUPDATION. */
  adjustments: z.number(),
  /** appliedPatientPayment + appliedInsPayments from latest snapshot. */
  paid: z.number(),
  /** balanceDuePatient + balanceDueInsurance from latest snapshot. */
  balance: z.number(),
  /** `null` until a payment-summary snapshot has been captured for this
   * patient. The UI keys off this to render "—" in every slot. */
  snapshot_received_at: Datetime.nullable(),
  /** CareStack patient ids covered by this row (rare: usually 0 or 1). */
  carestack_patient_ids: z.array(z.string()),
  patient_count: z.number().int().nonnegative(),
});
export type PersonFinancialSummary = z.infer<typeof PersonFinancialSummarySchema>;

export const PersonDetailSchema = z.object({
  summary: PersonSummarySchema,
  source_links: z.array(SourceLinkSchema),
  lead: z
    .object({
      status: LeadStatusSchema.nullable(),
      source: z.string().nullable(),
      created_at: Datetime,
      updated_at: Datetime,
      salesforce_status: z.string().nullable().optional(),
      salesforce_created_at: Datetime.nullable().optional(),
      company: z.string().nullable().optional(),
      campaign: z.string().nullable().optional(),
      owner: z.string().nullable().optional(),
      treatment_coordinator: z.string().nullable().optional(),
      is_reactivation: z.boolean().optional(),
    })
    .nullable(),
  consultations: z.array(
    z.object({
      id: Uuid,
      status: ConsultationStatusSchema,
      scheduled_at: Datetime,
      provider: ProviderSchema,
    }),
  ),
  timeline: z.array(TimelineEventSchema),
  /** ENG-306: per-person financial summary. `null` when the backend has
   * not attached one (older mock fixtures); when present the object's
   * `snapshot_received_at` signals empty state. */
  financial_summary: PersonFinancialSummarySchema.nullable().optional(),
  /** ENG-308: per-CareStack-pid origin context. One row per linked
   * CareStack patient_id with the true earliest CareStack-side activity
   * timestamp, resolved provider name (no raw integer), and city/state.
   * Empty array when the person has no CareStack patient links. */
  carestack_origin: z.array(PersonCarestackOriginRowSchema).default([]),
  /** ENG-310: bidirectional navigational links to OTHER persons sharing
   * a normalised phone or email. Empty when no siblings match. The UI
   * surfaces a "different people, financials separate" disclaimer
   * because the resolver intentionally does NOT collapse identities. */
  household_members: z.array(PersonHouseholdMemberSchema).default([]),
});
export type PersonDetail = z.infer<typeof PersonDetailSchema>;
