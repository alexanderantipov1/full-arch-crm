import { sql, relations } from "drizzle-orm";
import { pgTable, text, varchar, serial, integer, timestamp, date, boolean, jsonb, decimal, uuid, uniqueIndex } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";

export * from "./models/auth";
export * from "./models/chat";

// ── Tenants (multi-clinic isolation) ────────────────────────────────────
// Each clinic deployment is one tenant. Every PHI/ops row carries a
// `tenant_id`, and `PhiService` filters by the calling principal's tenant
// so cross-clinic reads are impossible by construction.
//
// Today the system is effectively single-tenant — when this migration
// runs, the backfill puts every existing row under a "default" tenant.
// New clinics get their own tenant row + a separate set of records.
//
// Per fusion_crm doctrine the `tenant` schema is its own domain; here the
// flat-schema CRM puts the table alongside the rest. The shape matches
// fusion_crm's `tenant.tenant` so the conceptual move-out later is rename
// + relocation, not redesign.
export const tenants = pgTable("tenants", {
  id: uuid("id").primaryKey().defaultRandom(),
  slug: text("slug").notNull().unique(), // url-safe key, e.g. "main-clinic"
  name: text("name").notNull(),
  // Optional: per-tenant configuration, branding, billing details. Lives
  // in JSONB so adding a new field doesn't require a migration.
  settings: jsonb("settings"),
  enabled: boolean("enabled").default(true).notNull(),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertTenantSchema = createInsertSchema(tenants).omit({ id: true, createdAt: true });

// ── Persons (canonical identity) ────────────────────────────────────────
// One row per real human, regardless of which domain first met them. Both
// `patients.personUid` and `leads.personUid` point here. The `person_uid`
// UUID is the join key per fusion_crm doctrine ("one global entity:
// identity.person.id is the person_uid referenced by every other domain").
//
// Today this table is additive — `patients` and `leads` keep their
// serial-int primary keys and continue to function. New code resolves
// identity through `IdentityService.resolveOrCreatePerson` and writes
// `personUid` alongside the existing FK. Backfill via
// `scripts/backfill-persons.ts` populates the column for legacy rows.
export const persons = pgTable("persons", {
  id: uuid("id").primaryKey().defaultRandom(),
  // Tenant isolation: nullable until backfill assigns every existing row
  // to a default tenant. New rows get a tenant id from the calling
  // principal (set by IdentityService.resolveOrCreatePerson).
  tenantId: uuid("tenant_id").references(() => tenants.id),
  firstName: text("first_name"),
  lastName: text("last_name"),
  dateOfBirth: date("date_of_birth"),
  // Email/phone are normalized when written via IdentityService:
  // - email: trimmed + lowercased
  // - phone: digits only (no parens, dashes, spaces)
  email: text("email"),
  phone: text("phone"),
  // Provenance: which domain first brought this person into the system.
  firstSeenSource: text("first_seen_source"),
  firstSeenAt: timestamp("first_seen_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  // Merge tracking. When persons A and B are determined to be the same
  // human, the loser gets `mergedIntoId = winner.id` and is no longer
  // returned by resolveOrCreatePerson — callers follow the link to the
  // winner. We don't physically delete rows because PHI/audit history
  // already references the loser's UUID.
  mergedIntoId: uuid("merged_into_id"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// ── Person external IDs (source_link) ───────────────────────────────────
// Maps a canonical person_uid to its identity in external systems
// (Salesforce, CareStack, Stripe, etc.). Per fusion_crm `identity.source_link`.
//
// One row per (external_system, external_id) pair — uniqueness is enforced
// at the DB level so the same external record can't accidentally end up
// linked to two different persons. `external_kind` is optional sub-type
// for systems that have multiple object types (Salesforce: lead/contact;
// CareStack: patient/responsible_party).
//
// When IdentityService.resolveOrCreatePerson is called with externalIds,
// these are checked FIRST — an external ID match is the highest-trust
// signal (the external system has its own dedup). If found, return that
// person. If not, fall through to email/phone/name+DOB matching and link
// the external ID(s) to whatever person ends up resolved/created.
export const personExternalIds = pgTable(
  "person_external_ids",
  {
    id: serial("id").primaryKey(),
    personUid: uuid("person_uid")
      .notNull()
      .references(() => persons.id, { onDelete: "cascade" }),
    externalSystem: text("external_system").notNull(),
    externalId: text("external_id").notNull(),
    externalKind: text("external_kind"),
    linkedAt: timestamp("linked_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
    lastSyncedAt: timestamp("last_synced_at"),
    metadata: jsonb("metadata"),
  },
  (table) => ({
    uniqExternal: uniqueIndex("uniq_person_external_ids_system_id").on(
      table.externalSystem,
      table.externalId,
    ),
  }),
);

// Patients table
export const patients = pgTable("patients", {
  id: serial("id").primaryKey(),
  // Tenant isolation — nullable until backfill, then targets NOT NULL.
  // Every PhiService.getPatient/createPatient/... call resolves the
  // caller's principal.tenantId and filters/sets this column.
  tenantId: uuid("tenant_id").references(() => tenants.id),
  // Canonical identity link. Nullable today because legacy rows haven't
  // been backfilled yet; targets NOT NULL once `scripts/backfill-persons.ts`
  // has run against every environment.
  personUid: uuid("person_uid").references(() => persons.id),
  firstName: text("first_name").notNull(),
  lastName: text("last_name").notNull(),
  dateOfBirth: date("date_of_birth").notNull(),
  gender: text("gender").notNull(),
  email: text("email"),
  phone: text("phone"),
  address: text("address"),
  city: text("city"),
  state: text("state"),
  zipCode: text("zip_code"),
  emergencyContact: text("emergency_contact"),
  emergencyPhone: text("emergency_phone"),
  profilePhotoUrl: text("profile_photo_url"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Medical History
export const medicalHistory = pgTable("medical_history", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  conditions: text("conditions").array(),
  allergies: text("allergies").array(),
  medications: text("medications").array(),
  surgeries: text("surgeries").array(),
  familyHistory: text("family_history"),
  smokingStatus: text("smoking_status"),
  alcoholUse: text("alcohol_use"),
  bloodPressure: text("blood_pressure"),
  heartRate: text("heart_rate"),
  weight: text("weight"),
  height: text("height"),
  notes: text("notes"),
  lastPhysicalExam: date("last_physical_exam"),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Dental Information
export const dentalInfo = pgTable("dental_info", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  chiefComplaint: text("chief_complaint"),
  dentalHistory: text("dental_history"),
  lastDentalVisit: date("last_dental_visit"),
  brushingFrequency: text("brushing_frequency"),
  flossingFrequency: text("flossing_frequency"),
  existingConditions: text("existing_conditions").array(),
  missingTeeth: text("missing_teeth").array(),
  implants: text("implants").array(),
  crowns: text("crowns").array(),
  bridges: text("bridges").array(),
  dentures: text("dentures"),
  orthodonticHistory: text("orthodontic_history"),
  tmjIssues: boolean("tmj_issues").default(false),
  grindingClenching: boolean("grinding_clenching").default(false),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Facial/Airway Evaluation (Arnett & Gunson Protocol)
export const facialEvaluation = pgTable("facial_evaluation", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  facialProfile: text("facial_profile"),
  facialSymmetry: text("facial_symmetry"),
  lipPosition: text("lip_position"),
  chinPosition: text("chin_position"),
  nasalProjection: text("nasal_projection"),
  airwayAssessment: text("airway_assessment"),
  mallampatiScore: text("mallampati_score"),
  tonsilSize: text("tonsil_size"),
  neckCircumference: text("neck_circumference"),
  biteClassification: text("bite_classification"),
  overjet: text("overjet"),
  overbite: text("overbite"),
  midlineDeviation: text("midline_deviation"),
  cephalometricNotes: text("cephalometric_notes"),
  arnettGunsonNotes: text("arnett_gunson_notes"),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Insurance Information
export const insurance = pgTable("insurance", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  insuranceType: text("insurance_type").notNull(),
  providerName: text("provider_name").notNull(),
  policyNumber: text("policy_number").notNull(),
  groupNumber: text("group_number"),
  subscriberName: text("subscriber_name"),
  subscriberDob: date("subscriber_dob"),
  relationship: text("relationship"),
  effectiveDate: date("effective_date"),
  terminationDate: date("termination_date"),
  coveragePercentage: integer("coverage_percentage"),
  annualMaximum: decimal("annual_maximum", { precision: 10, scale: 2 }),
  deductible: decimal("deductible", { precision: 10, scale: 2 }),
  remainingBenefit: decimal("remaining_benefit", { precision: 10, scale: 2 }),
  priorAuthRequired: boolean("prior_auth_required").default(false),
  notes: text("notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Referring Providers
export const referringProviders = pgTable("referring_providers", {
  id: serial("id").primaryKey(),
  providerType: text("provider_type").notNull(),
  firstName: text("first_name").notNull(),
  lastName: text("last_name").notNull(),
  practiceName: text("practice_name"),
  specialty: text("specialty"),
  email: text("email"),
  phone: text("phone"),
  fax: text("fax"),
  address: text("address"),
  npi: text("npi"),
  notes: text("notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Patient-Provider Referral Link
export const patientReferrals = pgTable("patient_referrals", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  providerId: integer("provider_id").notNull().references(() => referringProviders.id, { onDelete: "cascade" }),
  referralDate: date("referral_date"),
  referralReason: text("referral_reason"),
  notes: text("notes"),
});

// Clinical Notes
export const clinicalNotes = pgTable("clinical_notes", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  noteType: text("note_type").notNull(),
  title: text("title").notNull(),
  content: text("content").notNull(),
  authorId: varchar("author_id"),
  authorName: text("author_name"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Patient Photos/Documents
export const patientDocuments = pgTable("patient_documents", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  documentType: text("document_type").notNull(),
  fileName: text("file_name").notNull(),
  fileUrl: text("file_url").notNull(),
  mimeType: text("mime_type"),
  category: text("category"),
  description: text("description"),
  uploadedBy: varchar("uploaded_by"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Treatment Plans
export const treatmentPlans = pgTable("treatment_plans", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  planName: text("plan_name").notNull(),
  status: text("status").notNull().default("draft"),
  diagnosis: text("diagnosis"),
  diagnosisCode: text("diagnosis_code"),
  aiDiagnosis: text("ai_diagnosis"),
  aiRecommendations: jsonb("ai_recommendations"),
  procedures: jsonb("procedures"),
  totalCost: decimal("total_cost", { precision: 10, scale: 2 }),
  insuranceCoverage: decimal("insurance_coverage", { precision: 10, scale: 2 }),
  patientResponsibility: decimal("patient_responsibility", { precision: 10, scale: 2 }),
  cosmeticPackage: boolean("cosmetic_package").default(false),
  notes: text("notes"),
  medicalNecessityLetter: text("medical_necessity_letter"),
  priorAuthStatus: text("prior_auth_status"),
  priorAuthNumber: text("prior_auth_number"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Appointments
export const appointments = pgTable("appointments", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  treatmentPlanId: integer("treatment_plan_id").references(() => treatmentPlans.id),
  appointmentType: text("appointment_type").notNull(),
  title: text("title").notNull(),
  description: text("description"),
  startTime: timestamp("start_time").notNull(),
  endTime: timestamp("end_time").notNull(),
  status: text("status").notNull().default("scheduled"),
  location: text("location"),
  providerId: varchar("provider_id"),
  providerName: text("provider_name"),
  notes: text("notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Surgery Reports (Op Reports)
export const surgeryReports = pgTable("surgery_reports", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  appointmentId: integer("appointment_id").references(() => appointments.id),
  treatmentPlanId: integer("treatment_plan_id").references(() => treatmentPlans.id),
  surgeryDate: date("surgery_date").notNull(),
  surgeryType: text("surgery_type").notNull(),
  surgeon: text("surgeon"),
  assistant: text("assistant"),
  anesthesiaType: text("anesthesia_type"),
  preOpDiagnosis: text("pre_op_diagnosis"),
  postOpDiagnosis: text("post_op_diagnosis"),
  procedureDetails: text("procedure_details"),
  findings: text("findings"),
  implantDetails: jsonb("implant_details"),
  complications: text("complications"),
  bloodLoss: text("blood_loss"),
  specimenSent: text("specimen_sent"),
  postOpInstructions: text("post_op_instructions"),
  followUpPlan: text("follow_up_plan"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Cephalometric Analysis
export const cephalometrics = pgTable("cephalometrics", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  analysisDate: date("analysis_date").notNull(),
  sna: decimal("sna", { precision: 5, scale: 2 }),
  snb: decimal("snb", { precision: 5, scale: 2 }),
  anb: decimal("anb", { precision: 5, scale: 2 }),
  fma: decimal("fma", { precision: 5, scale: 2 }),
  impa: decimal("impa", { precision: 5, scale: 2 }),
  upperLipToEPlane: decimal("upper_lip_e_plane", { precision: 5, scale: 2 }),
  lowerLipToEPlane: decimal("lower_lip_e_plane", { precision: 5, scale: 2 }),
  nasalTipProjection: decimal("nasal_tip_projection", { precision: 5, scale: 2 }),
  upperIncisorToNADegrees: decimal("upper_incisor_na_deg", { precision: 5, scale: 2 }),
  lowerIncisorToNBDegrees: decimal("lower_incisor_nb_deg", { precision: 5, scale: 2 }),
  softTissueAnalysis: text("soft_tissue_analysis"),
  skeletalClassification: text("skeletal_classification"),
  growthPattern: text("growth_pattern"),
  interpretation: text("interpretation"),
  imageUrl: text("image_url"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Prior Authorization Workflow
export const priorAuthorizations = pgTable("prior_authorizations", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  treatmentPlanId: integer("treatment_plan_id").references(() => treatmentPlans.id),
  insuranceId: integer("insurance_id").references(() => insurance.id),
  authType: text("auth_type").notNull(),
  status: text("status").notNull().default("pending"),
  submissionDate: date("submission_date"),
  responseDate: date("response_date"),
  expirationDate: date("expiration_date"),
  authNumber: text("auth_number"),
  requestedProcedures: jsonb("requested_procedures"),
  approvedProcedures: jsonb("approved_procedures"),
  denialReason: text("denial_reason"),
  medicalNecessityLetter: text("medical_necessity_letter"),
  supportingDocuments: text("supporting_documents").array(),
  peerToPeerRequired: boolean("peer_to_peer_required").default(false),
  peerToPeerDate: timestamp("peer_to_peer_date"),
  peerToPeerNotes: text("peer_to_peer_notes"),
  peerToPeerOutcome: text("peer_to_peer_outcome"),
  appealCount: integer("appeal_count").default(0),
  lastAppealDate: date("last_appeal_date"),
  appealLetter: text("appeal_letter"),
  notes: text("notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Medical Consultation Requests
export const medicalConsults = pgTable("medical_consults", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  consultType: text("consult_type").notNull(),
  specialty: text("specialty").notNull(),
  urgency: text("urgency").notNull().default("routine"),
  status: text("status").notNull().default("pending"),
  requestDate: date("request_date").notNull(),
  scheduledDate: date("scheduled_date"),
  completedDate: date("completed_date"),
  referringPhysician: text("referring_physician"),
  consultingPhysician: text("consulting_physician"),
  reason: text("reason").notNull(),
  clinicalQuestion: text("clinical_question"),
  requiredLabs: text("required_labs").array(),
  labResults: jsonb("lab_results"),
  findings: text("findings"),
  recommendations: text("recommendations"),
  clearanceStatus: text("clearance_status"),
  clearanceNotes: text("clearance_notes"),
  surgeryDate: date("surgery_date"),
  notes: text("notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Comprehensive Full Arch Exam
export const fullArchExams = pgTable("full_arch_exams", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  examDate: date("exam_date").notNull(),
  examiner: text("examiner"),
  chiefComplaint: text("chief_complaint"),
  presentIllness: text("present_illness"),
  edentulousArch: text("edentulous_arch"),
  existingProsthesis: text("existing_prosthesis"),
  prosthesisCondition: text("prosthesis_condition"),
  boneQuality: text("bone_quality"),
  boneQuantity: text("bone_quantity"),
  sinusProximity: text("sinus_proximity"),
  nerveCanalProximity: text("nerve_canal_proximity"),
  softTissueAssessment: text("soft_tissue_assessment"),
  keratinizedTissue: text("keratinized_tissue"),
  occlusionAssessment: text("occlusion_assessment"),
  verticalDimension: text("vertical_dimension"),
  interarchSpace: text("interarch_space"),
  estheticAssessment: text("esthetic_assessment"),
  smileLine: text("smile_line"),
  lipSupport: text("lip_support"),
  phoneticsAssessment: text("phonetics_assessment"),
  nutritionalStatus: text("nutritional_status"),
  functionalLimitations: text("functional_limitations"),
  patientExpectations: text("patient_expectations"),
  treatmentGoals: text("treatment_goals"),
  recommendedApproach: text("recommended_approach"),
  implantCount: integer("implant_count"),
  prostheticType: text("prosthetic_type"),
  graftingNeeded: boolean("grafting_needed").default(false),
  graftingType: text("grafting_type"),
  cbctFindings: text("cbct_findings"),
  panorexFindings: text("panorex_findings"),
  photographyComplete: boolean("photography_complete").default(false),
  impressionsComplete: boolean("impressions_complete").default(false),
  notes: text("notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Follow-up Tracking
export const followUps = pgTable("follow_ups", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  treatmentPlanId: integer("treatment_plan_id").references(() => treatmentPlans.id),
  followUpType: text("follow_up_type").notNull(),
  dueDate: date("due_date").notNull(),
  completedDate: date("completed_date"),
  status: text("status").notNull().default("pending"),
  priority: text("priority").notNull().default("normal"),
  assignedTo: text("assigned_to"),
  notes: text("notes"),
  outcome: text("outcome"),
  nextAction: text("next_action"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Continuity of Care Reports
export const careReports = pgTable("care_reports", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  recipientProviderId: integer("recipient_provider_id").references(() => referringProviders.id),
  reportType: text("report_type").notNull(),
  reportDate: date("report_date").notNull(),
  sentDate: date("sent_date"),
  sentMethod: text("sent_method"),
  summary: text("summary"),
  treatmentProvided: text("treatment_provided"),
  currentStatus: text("current_status"),
  recommendedFollowUp: text("recommended_follow_up"),
  attachments: text("attachments").array(),
  acknowledged: boolean("acknowledged").default(false),
  acknowledgedDate: date("acknowledged_date"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Code Cross-Reference (CDT → CPT/ICD-10)
export const codeCrossReference = pgTable("code_cross_reference", {
  id: serial("id").primaryKey(),
  cdtCode: text("cdt_code").notNull(),
  cdtDescription: text("cdt_description").notNull(),
  cptCode: text("cpt_code"),
  cptDescription: text("cpt_description"),
  icd10Codes: text("icd10_codes").array(),
  icd10Descriptions: text("icd10_descriptions").array(),
  medicalNecessityRequired: boolean("medical_necessity_required").default(true),
  medicalNecessityCriteria: text("medical_necessity_criteria"),
  averageFee: decimal("average_fee", { precision: 10, scale: 2 }),
  averageReimbursement: decimal("average_reimbursement", { precision: 10, scale: 2 }),
  approvalRate: decimal("approval_rate", { precision: 5, scale: 2 }),
  procedureCategory: text("procedure_category"),
  notes: text("notes"),
});

// Fee Schedules
export const feeSchedules = pgTable("fee_schedules", {
  id: serial("id").primaryKey(),
  payerName: text("payer_name").notNull(),
  payerType: text("payer_type").notNull(),
  cdtCode: text("cdt_code"),
  cptCode: text("cpt_code"),
  allowedAmount: decimal("allowed_amount", { precision: 10, scale: 2 }),
  percentOfCharge: decimal("percent_of_charge", { precision: 5, scale: 2 }),
  effectiveDate: date("effective_date"),
  expirationDate: date("expiration_date"),
  region: text("region"),
  notes: text("notes"),
});

// Billing/Claims
export const billingClaims = pgTable("billing_claims", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  treatmentPlanId: integer("treatment_plan_id").references(() => treatmentPlans.id),
  claimNumber: text("claim_number"),
  claimStatus: text("claim_status").notNull().default("pending"),
  serviceDate: date("service_date").notNull(),
  procedureCode: text("procedure_code").notNull(),
  icd10Code: text("icd10_code"),
  description: text("description"),
  chargedAmount: decimal("charged_amount", { precision: 10, scale: 2 }).notNull(),
  allowedAmount: decimal("allowed_amount", { precision: 10, scale: 2 }),
  paidAmount: decimal("paid_amount", { precision: 10, scale: 2 }),
  patientPortion: decimal("patient_portion", { precision: 10, scale: 2 }),
  denialReason: text("denial_reason"),
  appealStatus: text("appeal_status"),
  appealNotes: text("appeal_notes"),
  submittedDate: date("submitted_date"),
  paidDate: date("paid_date"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// AI Claim Pre-Flight Check Results
export const claimPreflightResults = pgTable("claim_preflight_results", {
  id: serial("id").primaryKey(),
  claimId: integer("claim_id").notNull().references(() => billingClaims.id, { onDelete: "cascade" }),
  riskScore: integer("risk_score").notNull(),
  approvalProbability: integer("approval_probability").notNull(),
  issues: jsonb("issues").notNull(),
  checklist: jsonb("checklist").notNull(),
  recommendedActions: text("recommended_actions").array(),
  checkedAt: timestamp("checked_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  resolvedAt: timestamp("resolved_at"),
});

export const insertClaimPreflightResultSchema = createInsertSchema(claimPreflightResults).omit({ id: true, checkedAt: true });
export type ClaimPreflightResult = typeof claimPreflightResults.$inferSelect;
export type InsertClaimPreflightResult = z.infer<typeof insertClaimPreflightResultSchema>;

// Patient Portal Access
export const patientPortalAccess = pgTable("patient_portal_access", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }).unique(),
  enabled: boolean("enabled").default(true).notNull(),
  lastAccessedAt: timestamp("last_accessed_at"),
  linkSentAt: timestamp("link_sent_at"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertPatientPortalAccessSchema = createInsertSchema(patientPortalAccess).omit({ id: true, createdAt: true });
export type PatientPortalAccess = typeof patientPortalAccess.$inferSelect;
export type InsertPatientPortalAccess = z.infer<typeof insertPatientPortalAccessSchema>;

// Portal Appointment Requests
export const portalAppointmentRequests = pgTable("portal_appointment_requests", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  preferredDate: date("preferred_date"),
  preferredTime: text("preferred_time"),
  reason: text("reason").notNull(),
  appointmentType: text("appointment_type").default("consultation"),
  status: text("status").default("pending").notNull(),
  staffNotes: text("staff_notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertPortalAppointmentRequestSchema = createInsertSchema(portalAppointmentRequests).omit({ id: true, createdAt: true });
export type PortalAppointmentRequest = typeof portalAppointmentRequests.$inferSelect;
export type InsertPortalAppointmentRequest = z.infer<typeof insertPortalAppointmentRequestSchema>;

// Relations
export const patientsRelations = relations(patients, ({ many }) => ({
  medicalHistory: many(medicalHistory),
  dentalInfo: many(dentalInfo),
  facialEvaluation: many(facialEvaluation),
  cephalometrics: many(cephalometrics),
  insurance: many(insurance),
  referrals: many(patientReferrals),
  notes: many(clinicalNotes),
  documents: many(patientDocuments),
  treatmentPlans: many(treatmentPlans),
  appointments: many(appointments),
  surgeryReports: many(surgeryReports),
  billingClaims: many(billingClaims),
  priorAuthorizations: many(priorAuthorizations),
  medicalConsults: many(medicalConsults),
  fullArchExams: many(fullArchExams),
  followUps: many(followUps),
  careReports: many(careReports),
}));

// Insert Schemas
export const insertPersonSchema = createInsertSchema(persons).omit({ id: true, createdAt: true, updatedAt: true, firstSeenAt: true });
export const insertPersonExternalIdSchema = createInsertSchema(personExternalIds).omit({ id: true, linkedAt: true });
export const insertPatientSchema = createInsertSchema(patients).omit({ id: true, createdAt: true, updatedAt: true });
export const insertMedicalHistorySchema = createInsertSchema(medicalHistory).omit({ id: true, updatedAt: true });
export const insertDentalInfoSchema = createInsertSchema(dentalInfo).omit({ id: true, updatedAt: true });
export const insertFacialEvaluationSchema = createInsertSchema(facialEvaluation).omit({ id: true, updatedAt: true });
export const insertInsuranceSchema = createInsertSchema(insurance).omit({ id: true, createdAt: true });
export const insertReferringProviderSchema = createInsertSchema(referringProviders).omit({ id: true, createdAt: true });
export const insertClinicalNoteSchema = createInsertSchema(clinicalNotes).omit({ id: true, createdAt: true, updatedAt: true });
export const insertPatientDocumentSchema = createInsertSchema(patientDocuments).omit({ id: true, createdAt: true });
export const insertTreatmentPlanSchema = createInsertSchema(treatmentPlans).omit({ id: true, createdAt: true, updatedAt: true });
export const insertAppointmentSchema = createInsertSchema(appointments).omit({ id: true, createdAt: true });
export const insertSurgeryReportSchema = createInsertSchema(surgeryReports).omit({ id: true, createdAt: true });
export const insertBillingClaimSchema = createInsertSchema(billingClaims).omit({ id: true, createdAt: true });
export const insertCephalometricSchema = createInsertSchema(cephalometrics).omit({ id: true, createdAt: true });
export const insertPriorAuthorizationSchema = createInsertSchema(priorAuthorizations).omit({ id: true, createdAt: true, updatedAt: true });
export const insertMedicalConsultSchema = createInsertSchema(medicalConsults).omit({ id: true, createdAt: true });
export const insertFullArchExamSchema = createInsertSchema(fullArchExams).omit({ id: true, createdAt: true });
export const insertFollowUpSchema = createInsertSchema(followUps).omit({ id: true, createdAt: true });
export const insertCareReportSchema = createInsertSchema(careReports).omit({ id: true, createdAt: true });
export const insertCodeCrossReferenceSchema = createInsertSchema(codeCrossReference).omit({ id: true });
export const insertFeeScheduleSchema = createInsertSchema(feeSchedules).omit({ id: true });

// AI Generated Documents
export const generatedDocuments = pgTable("generated_documents", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  documentType: text("document_type").notNull(),
  title: text("title").notNull(),
  content: text("content").notNull(),
  metadata: jsonb("metadata"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Appeals
export const appeals = pgTable("appeals", {
  id: serial("id").primaryKey(),
  claimId: integer("claim_id").references(() => billingClaims.id),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  denialReason: text("denial_reason").notNull(),
  denialCode: text("denial_code"),
  appealLevel: integer("appeal_level").default(1).notNull(),
  appealType: text("appeal_type").notNull(),
  status: text("status").default("draft").notNull(),
  appealLetter: text("appeal_letter"),
  supportingDocs: text("supporting_docs").array(),
  submittedDate: date("submitted_date"),
  responseDate: date("response_date"),
  outcome: text("outcome"),
  successProbability: integer("success_probability"),
  aiRecommendations: jsonb("ai_recommendations"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Insurance Eligibility Checks
export const eligibilityChecks = pgTable("eligibility_checks", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  insuranceId: integer("insurance_id").references(() => insurance.id),
  checkDate: timestamp("check_date").default(sql`CURRENT_TIMESTAMP`).notNull(),
  status: text("status").notNull(),
  eligibilityStatus: text("eligibility_status"),
  coverageDetails: jsonb("coverage_details"),
  benefitsRemaining: decimal("benefits_remaining", { precision: 10, scale: 2 }),
  deductibleMet: decimal("deductible_met", { precision: 10, scale: 2 }),
  effectiveDate: date("effective_date"),
  terminationDate: date("termination_date"),
  rawResponse: jsonb("raw_response"),
});

// ERA/Payment Postings
export const paymentPostings = pgTable("payment_postings", {
  id: serial("id").primaryKey(),
  claimId: integer("claim_id").references(() => billingClaims.id),
  patientId: integer("patient_id").references(() => patients.id),
  paymentDate: date("payment_date").notNull(),
  payerName: text("payer_name").notNull(),
  checkNumber: text("check_number"),
  paymentAmount: decimal("payment_amount", { precision: 10, scale: 2 }).notNull(),
  adjustmentAmount: decimal("adjustment_amount", { precision: 10, scale: 2 }),
  patientResponsibility: decimal("patient_responsibility", { precision: 10, scale: 2 }),
  postingStatus: text("posting_status").default("pending").notNull(),
  varianceFlag: boolean("variance_flag").default(false),
  varianceReason: text("variance_reason"),
  eraData: jsonb("era_data"),
  autoPosted: boolean("auto_posted").default(false),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Training Progress
export const trainingProgress = pgTable("training_progress", {
  id: serial("id").primaryKey(),
  userId: varchar("user_id").notNull(),
  moduleName: text("module_name").notNull(),
  lessonId: text("lesson_id").notNull(),
  completed: boolean("completed").default(false).notNull(),
  score: integer("score"),
  completedAt: timestamp("completed_at"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// ============ PATIENT JOURNEY SYSTEM ============

// Marketing Leads
export const leads = pgTable("leads", {
  id: serial("id").primaryKey(),
  // Tenant isolation — nullable until backfill, then NOT NULL.
  tenantId: uuid("tenant_id").references(() => tenants.id),
  // Canonical identity link — nullable until backfill runs (see persons table).
  // When a lead converts to a patient, BOTH rows point at the same person_uid.
  personUid: uuid("person_uid").references(() => persons.id),
  firstName: text("first_name").notNull(),
  lastName: text("last_name").notNull(),
  email: text("email"),
  phone: text("phone").notNull(),
  source: text("source").notNull(),
  campaign: text("campaign"),
  status: text("status").default("new").notNull(),
  interestedIn: text("interested_in"),
  notes: text("notes"),
  assignedTo: text("assigned_to"),
  convertedToPatientId: integer("converted_to_patient_id").references(() => patients.id),
  leadScore: integer("lead_score").default(0),
  lastContactDate: timestamp("last_contact_date"),
  nextFollowUpDate: timestamp("next_follow_up_date"),
  utmSource: text("utm_source"),
  utmMedium: text("utm_medium"),
  utmCampaign: text("utm_campaign"),
  landingPage: text("landing_page"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Lead Activities/Interactions
export const leadActivities = pgTable("lead_activities", {
  id: serial("id").primaryKey(),
  leadId: integer("lead_id").notNull().references(() => leads.id, { onDelete: "cascade" }),
  activityType: text("activity_type").notNull(),
  description: text("description"),
  outcome: text("outcome"),
  performedBy: text("performed_by"),
  callDuration: integer("call_duration"),
  recordingUrl: text("recording_url"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Appointment Reminders
export const appointmentReminders = pgTable("appointment_reminders", {
  id: serial("id").primaryKey(),
  appointmentId: integer("appointment_id").notNull().references(() => appointments.id, { onDelete: "cascade" }),
  reminderType: text("reminder_type").notNull(),
  scheduledFor: timestamp("scheduled_for").notNull(),
  sentAt: timestamp("sent_at"),
  status: text("status").default("pending").notNull(),
  channel: text("channel").notNull(),
  messageContent: text("message_content"),
  response: text("response"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Treatment Packages (Cookie-cutter plans with pricing)
export const treatmentPackages = pgTable("treatment_packages", {
  id: serial("id").primaryKey(),
  name: text("name").notNull(),
  description: text("description"),
  procedureType: text("procedure_type").notNull(),
  archType: text("arch_type").notNull(),
  prosthesisType: text("prosthesis_type").notNull(),
  materialType: text("material_type").notNull(),
  basePrice: decimal("base_price", { precision: 10, scale: 2 }).notNull(),
  implantCount: integer("implant_count").notNull(),
  includedServices: jsonb("included_services"),
  estimatedDuration: text("estimated_duration"),
  warrantyYears: integer("warranty_years").default(5),
  isActive: boolean("is_active").default(true).notNull(),
  displayOrder: integer("display_order").default(0),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Financing Plans
export const financingPlans = pgTable("financing_plans", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  treatmentPlanId: integer("treatment_plan_id").references(() => treatmentPlans.id),
  provider: text("provider").notNull(),
  applicationStatus: text("application_status").default("pending").notNull(),
  approvedAmount: decimal("approved_amount", { precision: 10, scale: 2 }),
  interestRate: decimal("interest_rate", { precision: 5, scale: 2 }),
  termMonths: integer("term_months"),
  monthlyPayment: decimal("monthly_payment", { precision: 10, scale: 2 }),
  downPayment: decimal("down_payment", { precision: 10, scale: 2 }),
  applicationDate: timestamp("application_date").default(sql`CURRENT_TIMESTAMP`).notNull(),
  approvalDate: timestamp("approval_date"),
  expirationDate: date("expiration_date"),
  accountNumber: text("account_number"),
  notes: text("notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Patient Check-ins (Front Desk)
export const patientCheckIns = pgTable("patient_check_ins", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  appointmentId: integer("appointment_id").references(() => appointments.id),
  checkInTime: timestamp("check_in_time").default(sql`CURRENT_TIMESTAMP`).notNull(),
  checkInMethod: text("check_in_method").default("manual").notNull(),
  recognitionConfidence: decimal("recognition_confidence", { precision: 5, scale: 2 }),
  greeted: boolean("greeted").default(false),
  offeredRefreshment: boolean("offered_refreshment").default(false),
  assignedRoom: text("assigned_room"),
  waitTime: integer("wait_time"),
  notes: text("notes"),
});

// Medical Clearance
export const medicalClearances = pgTable("medical_clearances", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  treatmentPlanId: integer("treatment_plan_id").references(() => treatmentPlans.id),
  requestedDate: timestamp("requested_date").default(sql`CURRENT_TIMESTAMP`).notNull(),
  physicianName: text("physician_name"),
  physicianPhone: text("physician_phone"),
  physicianFax: text("physician_fax"),
  clearanceType: text("clearance_type").notNull(),
  status: text("status").default("pending").notNull(),
  receivedDate: timestamp("received_date"),
  expirationDate: date("expiration_date"),
  clearanceNotes: text("clearance_notes"),
  restrictions: text("restrictions"),
  documentUrl: text("document_url"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Pre-Surgery Tasks
export const preSurgeryTasks = pgTable("pre_surgery_tasks", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  treatmentPlanId: integer("treatment_plan_id").references(() => treatmentPlans.id),
  taskType: text("task_type").notNull(),
  taskName: text("task_name").notNull(),
  description: text("description"),
  dueDate: date("due_date"),
  completedDate: timestamp("completed_date"),
  status: text("status").default("pending").notNull(),
  assignedTo: text("assigned_to"),
  resultNotes: text("result_notes"),
  documentUrl: text("document_url"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Surgery Sessions
export const surgerySessions = pgTable("surgery_sessions", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  treatmentPlanId: integer("treatment_plan_id").references(() => treatmentPlans.id),
  appointmentId: integer("appointment_id").references(() => appointments.id),
  surgeryDate: timestamp("surgery_date").notNull(),
  surgeryType: text("surgery_type").notNull(),
  archTreated: text("arch_treated").notNull(),
  surgeon: text("surgeon").notNull(),
  assistant: text("assistant"),
  anesthesiaType: text("anesthesia_type").notNull(),
  anesthesiologist: text("anesthesiologist"),
  startTime: timestamp("start_time"),
  endTime: timestamp("end_time"),
  implantsPlaced: jsonb("implants_placed"),
  complications: text("complications"),
  bloodLoss: text("blood_loss"),
  vitalSigns: jsonb("vital_signs"),
  aiGeneratedNotes: text("ai_generated_notes"),
  videoRecordingUrl: text("video_recording_url"),
  status: text("status").default("scheduled").notNull(),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Anesthesia Records
export const anesthesiaRecords = pgTable("anesthesia_records", {
  id: serial("id").primaryKey(),
  surgerySessionId: integer("surgery_session_id").notNull().references(() => surgerySessions.id, { onDelete: "cascade" }),
  anesthesiaType: text("anesthesia_type").notNull(),
  medications: jsonb("medications"),
  startTime: timestamp("start_time").notNull(),
  endTime: timestamp("end_time"),
  vitalSignsLog: jsonb("vital_signs_log"),
  complications: text("complications"),
  recoveryNotes: text("recovery_notes"),
  anesthesiologistSignature: text("anesthesiologist_signature"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Lab Cases
export const labCases = pgTable("lab_cases", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  treatmentPlanId: integer("treatment_plan_id").references(() => treatmentPlans.id),
  surgerySessionId: integer("surgery_session_id").references(() => surgerySessions.id),
  caseType: text("case_type").notNull(),
  labName: text("lab_name"),
  prosthesisType: text("prosthesis_type").notNull(),
  materialType: text("material_type").notNull(),
  shade: text("shade"),
  status: text("status").default("pending").notNull(),
  sentToLabDate: timestamp("sent_to_lab_date"),
  expectedReturnDate: date("expected_return_date"),
  receivedDate: timestamp("received_date"),
  designIncluded: integer("design_included").default(2),
  designsUsed: integer("designs_used").default(0),
  additionalDesignFee: decimal("additional_design_fee", { precision: 10, scale: 2 }),
  notes: text("notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Design Revisions
export const designRevisions = pgTable("design_revisions", {
  id: serial("id").primaryKey(),
  labCaseId: integer("lab_case_id").notNull().references(() => labCases.id, { onDelete: "cascade" }),
  revisionNumber: integer("revision_number").notNull(),
  requestedChanges: text("requested_changes").notNull(),
  designFileUrl: text("design_file_url"),
  approvedByPatient: boolean("approved_by_patient").default(false),
  approvedByDoctor: boolean("approved_by_doctor").default(false),
  chargeApplied: boolean("charge_applied").default(false),
  chargeAmount: decimal("charge_amount", { precision: 10, scale: 2 }),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Post-Op Visits
export const postOpVisits = pgTable("post_op_visits", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  surgerySessionId: integer("surgery_session_id").references(() => surgerySessions.id),
  appointmentId: integer("appointment_id").references(() => appointments.id),
  visitType: text("visit_type").notNull(),
  visitDate: timestamp("visit_date").notNull(),
  daysSinceSurgery: integer("days_since_surgery"),
  healingStatus: text("healing_status"),
  suturesRemoved: boolean("sutures_removed").default(false),
  screwsTightened: boolean("screws_tightened").default(false),
  adjustmentsMade: text("adjustments_made"),
  nextVisitScheduled: date("next_visit_scheduled"),
  notes: text("notes"),
  photosUrl: text("photos_url"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Consent Forms
export const consentForms = pgTable("consent_forms", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  treatmentPlanId: integer("treatment_plan_id").references(() => treatmentPlans.id),
  formType: text("form_type").notNull(),
  formTitle: text("form_title"),
  formContent: text("form_content"),
  content: text("content").notNull(),
  status: text("status").default("pending").notNull(),
  aiGenerated: boolean("ai_generated").default(true),
  signedAt: timestamp("signed_at"),
  signatureUrl: text("signature_url"),
  witnessName: text("witness_name"),
  witnessSignature: text("witness_signature"),
  alternativesDiscussed: boolean("alternatives_discussed").default(true),
  patientQuestions: text("patient_questions"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Warranty Records
export const warrantyRecords = pgTable("warranty_records", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  treatmentPlanId: integer("treatment_plan_id").references(() => treatmentPlans.id),
  labCaseId: integer("lab_case_id").references(() => labCases.id),
  warrantyType: text("warranty_type").notNull(),
  startDate: date("start_date").notNull(),
  endDate: date("end_date").notNull(),
  coverageDetails: text("coverage_details"),
  warrantyLetterUrl: text("warranty_letter_url"),
  registrationNumber: text("registration_number"),
  claimHistory: jsonb("claim_history"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Patient Testimonials
export const testimonials = pgTable("testimonials", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  treatmentPlanId: integer("treatment_plan_id").references(() => treatmentPlans.id),
  testimonialType: text("testimonial_type").notNull(),
  content: text("content"),
  videoUrl: text("video_url"),
  photoUrls: jsonb("photo_urls"),
  beforePhotos: jsonb("before_photos"),
  afterPhotos: jsonb("after_photos"),
  rating: integer("rating"),
  consentToPublish: boolean("consent_to_publish").default(false),
  publishedAt: timestamp("published_at"),
  platformsPublished: text("platforms_published").array(),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Maintenance Appointments
export const maintenanceAppointments = pgTable("maintenance_appointments", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  treatmentPlanId: integer("treatment_plan_id").references(() => treatmentPlans.id),
  appointmentId: integer("appointment_id").references(() => appointments.id),
  maintenanceType: text("maintenance_type").notNull(),
  scheduledDate: timestamp("scheduled_date").notNull(),
  completedDate: timestamp("completed_date"),
  durationMinutes: integer("duration_minutes"),
  hourlyRate: decimal("hourly_rate", { precision: 10, scale: 2 }).default("400"),
  totalCharge: decimal("total_charge", { precision: 10, scale: 2 }),
  servicesPerformed: jsonb("services_performed"),
  xraysTaken: boolean("xrays_taken").default(false),
  implantStatus: text("implant_status"),
  prosthesisCondition: text("prosthesis_condition"),
  nextMaintenanceDue: date("next_maintenance_due"),
  notes: text("notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// Patient Journey Status (unified tracking)
export const patientJourneyStatus = pgTable("patient_journey_status", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  currentStage: text("current_stage").notNull(),
  leadCapturedAt: timestamp("lead_captured_at"),
  appointmentScheduledAt: timestamp("appointment_scheduled_at"),
  consultationCompletedAt: timestamp("consultation_completed_at"),
  treatmentPlanAcceptedAt: timestamp("treatment_plan_accepted_at"),
  financingApprovedAt: timestamp("financing_approved_at"),
  medicalClearanceAt: timestamp("medical_clearance_at"),
  surgeryCompletedAt: timestamp("surgery_completed_at"),
  tempsDeliveredAt: timestamp("temps_delivered_at"),
  finalsDeliveredAt: timestamp("finals_delivered_at"),
  warrantyIssuedAt: timestamp("warranty_issued_at"),
  testimonialCollectedAt: timestamp("testimonial_collected_at"),
  lastMaintenanceAt: timestamp("last_maintenance_at"),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// HIPAA Audit Logs - Track all PHI access for compliance
export const auditLogs = pgTable("audit_logs", {
  id: serial("id").primaryKey(),
  userId: text("user_id").notNull(),
  userEmail: text("user_email"),
  action: text("action").notNull(), // view, create, update, delete, export, print
  resourceType: text("resource_type").notNull(), // patient, treatment_plan, billing_claim, etc.
  resourceId: text("resource_id"), // ID of the accessed resource
  patientId: integer("patient_id"), // If action involves patient PHI
  ipAddress: text("ip_address"),
  userAgent: text("user_agent"),
  details: jsonb("details"), // Additional context about the action
  phiAccessed: boolean("phi_accessed").default(false), // Whether PHI was accessed
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertAuditLogSchema = createInsertSchema(auditLogs).omit({ id: true, createdAt: true });

// ── MCP API keys ─────────────────────────────────────────────────────────
// Per-key authentication for AI clients (Claude Code, Codex, internal AI
// agents) reaching the /mcp endpoint. Each key has its own capability
// scope, so a marketing-AI key can be issued with ops-only access while a
// clinical-AI key gets phi.read. Replaces the single shared MCP_API_KEY
// env approach.
//
// `keyHash` stores a SHA-256 hex of the bearer token. The plaintext is
// returned to the operator exactly once at creation time and never stored.
// `capabilities` mirrors the Principal capability list ("phi.read",
// "phi.write", etc.) — same string values, same gate.
export const mcpApiKeys = pgTable("mcp_api_keys", {
  id: serial("id").primaryKey(),
  // Tenant scope: every MCP key is bound to exactly one tenant. The
  // resulting principal can never reach data outside that tenant — keeps
  // a marketing AI for clinic A from accidentally reaching clinic B
  // even with phi.read. Nullable until backfill assigns existing keys to
  // the default tenant.
  tenantId: uuid("tenant_id").references(() => tenants.id),
  label: text("label").notNull(),
  keyHash: text("key_hash").notNull().unique(),
  capabilities: text("capabilities").array().notNull().default(sql`ARRAY[]::text[]`),
  enabled: boolean("enabled").default(true).notNull(),
  createdBy: text("created_by"),
  lastUsedAt: timestamp("last_used_at"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  revokedAt: timestamp("revoked_at"),
});

export const insertMcpApiKeySchema = createInsertSchema(mcpApiKeys).omit({
  id: true,
  createdAt: true,
  lastUsedAt: true,
  revokedAt: true,
});

// ── Workflow durability ──────────────────────────────────────────────────
// Persisted record of every agent loop run (see server/workflow/runner.ts).
// Lets crashed/timed-out runs be inspected, drives the operator UI's
// "in-flight workflows" view, and contributes to the audit story (every
// tool the agent invoked, with input + result + duration).
//
// Per fusion_crm doctrine these would live in the `workflow` schema; in
// the flat-schema CRM they sit alongside the other tables. The shape
// matches what fusion_crm's `workflow.instance` + `workflow.step` would
// hold, so migrating later is rename + relocation, not redesign.

export const workflowInstances = pgTable("workflow_instances", {
  id: uuid("id").primaryKey().defaultRandom(),
  // Who triggered the run. References the principal that ran the agent
  // loop — staff userId from OIDC, or "mcp:<keyId>" for MCP-driven runs.
  principalUserId: text("principal_user_id").notNull(),
  principalEmail: text("principal_email"),
  goal: text("goal").notNull(),
  status: text("status").notNull(), // pending | running | completed | failed | timeout | max_iterations
  endReason: text("end_reason"),
  finalAnswer: text("final_answer"),
  errorMessage: text("error_message"),
  iterationsUsed: integer("iterations_used").default(0).notNull(),
  // Which tool subset the run was allowed to use. null = the full registry.
  // Stored for auditability so reviewers can see what the agent could touch.
  allowedToolNames: text("allowed_tool_names").array(),
  startedAt: timestamp("started_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  completedAt: timestamp("completed_at"),
});

export const workflowSteps = pgTable("workflow_steps", {
  id: uuid("id").primaryKey().defaultRandom(),
  instanceId: uuid("instance_id")
    .notNull()
    .references(() => workflowInstances.id, { onDelete: "cascade" }),
  iteration: integer("iteration").notNull(),
  toolName: text("tool_name").notNull(),
  input: jsonb("input"),
  // Outcome shape: { ok: true, data } | { ok: false, error: { code, message } }
  result: jsonb("result").notNull(),
  durationMs: integer("duration_ms").notNull(),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertWorkflowInstanceSchema = createInsertSchema(workflowInstances).omit({
  id: true,
  startedAt: true,
  completedAt: true,
});
export const insertWorkflowStepSchema = createInsertSchema(workflowSteps).omit({
  id: true,
  createdAt: true,
});

export const insertGeneratedDocumentSchema = createInsertSchema(generatedDocuments).omit({ id: true, createdAt: true });
export const insertAppealSchema = createInsertSchema(appeals).omit({ id: true, createdAt: true, updatedAt: true });
export const insertEligibilityCheckSchema = createInsertSchema(eligibilityChecks).omit({ id: true, checkDate: true });
export const insertPaymentPostingSchema = createInsertSchema(paymentPostings).omit({ id: true, createdAt: true });
export const insertTrainingProgressSchema = createInsertSchema(trainingProgress).omit({ id: true, createdAt: true });

// Patient Journey Insert Schemas
export const insertLeadSchema = createInsertSchema(leads).omit({ id: true, createdAt: true, updatedAt: true });
export const insertLeadActivitySchema = createInsertSchema(leadActivities).omit({ id: true, createdAt: true });
export const insertAppointmentReminderSchema = createInsertSchema(appointmentReminders).omit({ id: true, createdAt: true });
export const insertTreatmentPackageSchema = createInsertSchema(treatmentPackages).omit({ id: true, createdAt: true });
export const insertFinancingPlanSchema = createInsertSchema(financingPlans).omit({ id: true, createdAt: true, applicationDate: true });
export const insertPatientCheckInSchema = createInsertSchema(patientCheckIns).omit({ id: true, checkInTime: true });
export const insertMedicalClearanceSchema = createInsertSchema(medicalClearances).omit({ id: true, createdAt: true, requestedDate: true });
export const insertPreSurgeryTaskSchema = createInsertSchema(preSurgeryTasks).omit({ id: true, createdAt: true });
export const insertSurgerySessionSchema = createInsertSchema(surgerySessions).omit({ id: true, createdAt: true });
export const insertAnesthesiaRecordSchema = createInsertSchema(anesthesiaRecords).omit({ id: true, createdAt: true });
export const insertLabCaseSchema = createInsertSchema(labCases).omit({ id: true, createdAt: true });
export const insertDesignRevisionSchema = createInsertSchema(designRevisions).omit({ id: true, createdAt: true });
export const insertPostOpVisitSchema = createInsertSchema(postOpVisits).omit({ id: true, createdAt: true });
export const insertConsentFormSchema = createInsertSchema(consentForms).omit({ id: true, createdAt: true });
export const insertWarrantyRecordSchema = createInsertSchema(warrantyRecords).omit({ id: true, createdAt: true });
export const insertTestimonialSchema = createInsertSchema(testimonials).omit({ id: true, createdAt: true });
export const insertMaintenanceAppointmentSchema = createInsertSchema(maintenanceAppointments).omit({ id: true, createdAt: true });
export const insertPatientJourneyStatusSchema = createInsertSchema(patientJourneyStatus).omit({ id: true, updatedAt: true });

// Internal Messages
export const internalMessages = pgTable("internal_messages", {
  id: serial("id").primaryKey(),
  senderId: varchar("sender_id").notNull(),
  senderName: text("sender_name").notNull(),
  recipientId: varchar("recipient_id").notNull(),
  recipientName: text("recipient_name").notNull(),
  subject: text("subject").notNull(),
  body: text("body").notNull(),
  priority: text("priority").default("normal"),
  isRead: boolean("is_read").default(false).notNull(),
  category: text("category").default("general"),
  patientId: integer("patient_id"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertInternalMessageSchema = createInsertSchema(internalMessages).omit({ id: true, createdAt: true, isRead: true });

// Practice Settings (Onboarding)
export const practiceSettings = pgTable("practice_settings", {
  id: serial("id").primaryKey(),
  userId: varchar("user_id").notNull(),
  practiceName: text("practice_name").notNull(),
  practiceType: text("practice_type").default("dental_implant"),
  address: text("address"),
  city: text("city"),
  state: text("state"),
  zipCode: text("zip_code"),
  phone: text("phone"),
  email: text("email"),
  website: text("website"),
  npiNumber: text("npi_number"),
  taxId: text("tax_id"),
  providerName: text("provider_name"),
  providerTitle: text("provider_title"),
  providerLicense: text("provider_license"),
  providerSpecialty: text("provider_specialty"),
  providerNpi: text("provider_npi"),
  billingContactName: text("billing_contact_name"),
  billingContactEmail: text("billing_contact_email"),
  billingContactPhone: text("billing_contact_phone"),
  defaultBillingType: text("default_billing_type").default("medical"),
  primaryPayers: text("primary_payers").array(),
  onboardingStep: integer("onboarding_step").default(0),
  onboardingComplete: boolean("onboarding_complete").default(false),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertPracticeSettingsSchema = createInsertSchema(practiceSettings).omit({ id: true, createdAt: true, updatedAt: true });

// Tooth Conditions (per-tooth charting)
export const toothConditions = pgTable("tooth_conditions", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull(),
  toothNumber: integer("tooth_number").notNull(),
  conditionType: text("condition_type").notNull(),
  surface: text("surface"),
  severity: text("severity"),
  status: text("status").default("active").notNull(),
  notes: text("notes"),
  observedDate: timestamp("observed_date").default(sql`CURRENT_TIMESTAMP`),
  resolvedDate: timestamp("resolved_date"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertToothConditionSchema = createInsertSchema(toothConditions).omit({ id: true, createdAt: true });

// Treatment Plan Procedures (line items)
export const treatmentPlanProcedures = pgTable("treatment_plan_procedures", {
  id: serial("id").primaryKey(),
  treatmentPlanId: integer("treatment_plan_id").notNull(),
  patientId: integer("patient_id").notNull(),
  toothNumber: integer("tooth_number"),
  quadrant: text("quadrant"),
  cdtCode: text("cdt_code").notNull(),
  description: text("description").notNull(),
  surface: text("surface"),
  fee: text("fee").notNull(),
  insuranceEstimate: text("insurance_estimate"),
  patientCost: text("patient_cost"),
  status: text("status").default("planned").notNull(),
  priority: integer("priority").default(1),
  notes: text("notes"),
  completedDate: timestamp("completed_date"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertTreatmentPlanProcedureSchema = createInsertSchema(treatmentPlanProcedures).omit({ id: true, createdAt: true });

// Types
export type Tenant = typeof tenants.$inferSelect;
export type InsertTenant = z.infer<typeof insertTenantSchema>;
export type Person = typeof persons.$inferSelect;
export type InsertPerson = z.infer<typeof insertPersonSchema>;
export type PersonExternalId = typeof personExternalIds.$inferSelect;
export type InsertPersonExternalId = z.infer<typeof insertPersonExternalIdSchema>;
export type Patient = typeof patients.$inferSelect;
export type InsertPatient = z.infer<typeof insertPatientSchema>;
export type MedicalHistory = typeof medicalHistory.$inferSelect;
export type InsertMedicalHistory = z.infer<typeof insertMedicalHistorySchema>;
export type DentalInfo = typeof dentalInfo.$inferSelect;
export type InsertDentalInfo = z.infer<typeof insertDentalInfoSchema>;
export type FacialEvaluation = typeof facialEvaluation.$inferSelect;
export type InsertFacialEvaluation = z.infer<typeof insertFacialEvaluationSchema>;
export type Insurance = typeof insurance.$inferSelect;
export type InsertInsurance = z.infer<typeof insertInsuranceSchema>;
export type ReferringProvider = typeof referringProviders.$inferSelect;
export type InsertReferringProvider = z.infer<typeof insertReferringProviderSchema>;
export type ClinicalNote = typeof clinicalNotes.$inferSelect;
export type InsertClinicalNote = z.infer<typeof insertClinicalNoteSchema>;
export type PatientDocument = typeof patientDocuments.$inferSelect;
export type InsertPatientDocument = z.infer<typeof insertPatientDocumentSchema>;
export type TreatmentPlan = typeof treatmentPlans.$inferSelect;
export type InsertTreatmentPlan = z.infer<typeof insertTreatmentPlanSchema>;
export type Appointment = typeof appointments.$inferSelect;
export type InsertAppointment = z.infer<typeof insertAppointmentSchema>;
export type SurgeryReport = typeof surgeryReports.$inferSelect;
export type InsertSurgeryReport = z.infer<typeof insertSurgeryReportSchema>;
export type BillingClaim = typeof billingClaims.$inferSelect;
export type InsertBillingClaim = z.infer<typeof insertBillingClaimSchema>;
export type Cephalometric = typeof cephalometrics.$inferSelect;
export type InsertCephalometric = z.infer<typeof insertCephalometricSchema>;
export type PriorAuthorization = typeof priorAuthorizations.$inferSelect;
export type InsertPriorAuthorization = z.infer<typeof insertPriorAuthorizationSchema>;
export type MedicalConsult = typeof medicalConsults.$inferSelect;
export type InsertMedicalConsult = z.infer<typeof insertMedicalConsultSchema>;
export type FullArchExam = typeof fullArchExams.$inferSelect;
export type InsertFullArchExam = z.infer<typeof insertFullArchExamSchema>;
export type FollowUp = typeof followUps.$inferSelect;
export type InsertFollowUp = z.infer<typeof insertFollowUpSchema>;
export type CareReport = typeof careReports.$inferSelect;
export type InsertCareReport = z.infer<typeof insertCareReportSchema>;
export type CodeCrossReference = typeof codeCrossReference.$inferSelect;
export type InsertCodeCrossReference = z.infer<typeof insertCodeCrossReferenceSchema>;
export type FeeSchedule = typeof feeSchedules.$inferSelect;
export type InsertFeeSchedule = z.infer<typeof insertFeeScheduleSchema>;
export type GeneratedDocument = typeof generatedDocuments.$inferSelect;
export type InsertGeneratedDocument = z.infer<typeof insertGeneratedDocumentSchema>;
export type Appeal = typeof appeals.$inferSelect;
export type InsertAppeal = z.infer<typeof insertAppealSchema>;
export type EligibilityCheck = typeof eligibilityChecks.$inferSelect;
export type InsertEligibilityCheck = z.infer<typeof insertEligibilityCheckSchema>;
export type PaymentPosting = typeof paymentPostings.$inferSelect;
export type InsertPaymentPosting = z.infer<typeof insertPaymentPostingSchema>;
export type TrainingProgress = typeof trainingProgress.$inferSelect;
export type InsertTrainingProgress = z.infer<typeof insertTrainingProgressSchema>;

// Patient Journey Types
export type Lead = typeof leads.$inferSelect;
export type InsertLead = z.infer<typeof insertLeadSchema>;
export type LeadActivity = typeof leadActivities.$inferSelect;
export type InsertLeadActivity = z.infer<typeof insertLeadActivitySchema>;
export type AppointmentReminder = typeof appointmentReminders.$inferSelect;
export type InsertAppointmentReminder = z.infer<typeof insertAppointmentReminderSchema>;
export type TreatmentPackage = typeof treatmentPackages.$inferSelect;
export type InsertTreatmentPackage = z.infer<typeof insertTreatmentPackageSchema>;
export type FinancingPlan = typeof financingPlans.$inferSelect;
export type InsertFinancingPlan = z.infer<typeof insertFinancingPlanSchema>;
export type PatientCheckIn = typeof patientCheckIns.$inferSelect;
export type InsertPatientCheckIn = z.infer<typeof insertPatientCheckInSchema>;
export type MedicalClearance = typeof medicalClearances.$inferSelect;
export type InsertMedicalClearance = z.infer<typeof insertMedicalClearanceSchema>;
export type PreSurgeryTask = typeof preSurgeryTasks.$inferSelect;
export type InsertPreSurgeryTask = z.infer<typeof insertPreSurgeryTaskSchema>;
export type SurgerySession = typeof surgerySessions.$inferSelect;
export type InsertSurgerySession = z.infer<typeof insertSurgerySessionSchema>;
export type AnesthesiaRecord = typeof anesthesiaRecords.$inferSelect;
export type InsertAnesthesiaRecord = z.infer<typeof insertAnesthesiaRecordSchema>;
export type LabCase = typeof labCases.$inferSelect;
export type InsertLabCase = z.infer<typeof insertLabCaseSchema>;
export type DesignRevision = typeof designRevisions.$inferSelect;
export type InsertDesignRevision = z.infer<typeof insertDesignRevisionSchema>;
export type PostOpVisit = typeof postOpVisits.$inferSelect;
export type InsertPostOpVisit = z.infer<typeof insertPostOpVisitSchema>;
export type ConsentForm = typeof consentForms.$inferSelect;
export type InsertConsentForm = z.infer<typeof insertConsentFormSchema>;
export type WarrantyRecord = typeof warrantyRecords.$inferSelect;
export type InsertWarrantyRecord = z.infer<typeof insertWarrantyRecordSchema>;
export type Testimonial = typeof testimonials.$inferSelect;
export type InsertTestimonial = z.infer<typeof insertTestimonialSchema>;
export type MaintenanceAppointment = typeof maintenanceAppointments.$inferSelect;
export type InsertMaintenanceAppointment = z.infer<typeof insertMaintenanceAppointmentSchema>;
export type PatientJourneyStatus = typeof patientJourneyStatus.$inferSelect;
export type InsertPatientJourneyStatus = z.infer<typeof insertPatientJourneyStatusSchema>;
export type AuditLog = typeof auditLogs.$inferSelect;
export type InsertAuditLog = z.infer<typeof insertAuditLogSchema>;
export type McpApiKey = typeof mcpApiKeys.$inferSelect;
export type InsertMcpApiKey = z.infer<typeof insertMcpApiKeySchema>;
export type WorkflowInstance = typeof workflowInstances.$inferSelect;
export type InsertWorkflowInstance = z.infer<typeof insertWorkflowInstanceSchema>;
export type WorkflowStep = typeof workflowSteps.$inferSelect;
export type InsertWorkflowStep = z.infer<typeof insertWorkflowStepSchema>;
export type InternalMessage = typeof internalMessages.$inferSelect;
export type InsertInternalMessage = z.infer<typeof insertInternalMessageSchema>;
export type PracticeSettings = typeof practiceSettings.$inferSelect;
export type InsertPracticeSettings = z.infer<typeof insertPracticeSettingsSchema>;
export type ToothCondition = typeof toothConditions.$inferSelect;
export type InsertToothCondition = z.infer<typeof insertToothConditionSchema>;
export type TreatmentPlanProcedure = typeof treatmentPlanProcedures.$inferSelect;
export type InsertTreatmentPlanProcedure = z.infer<typeof insertTreatmentPlanProcedureSchema>;

// Union Partnerships
export const unionOrganizations = pgTable("union_organizations", {
  id: serial("id").primaryKey(),
  name: text("name").notNull(),
  localNumber: text("local_number"),
  category: text("category").notNull(), // construction, public_sector, healthcare, transportation, retail
  memberCount: integer("member_count"),
  address: text("address"),
  city: text("city"),
  state: text("state"),
  zipCode: text("zip_code"),
  phone: text("phone"),
  fax: text("fax"),
  email: text("email"),
  website: text("website"),
  affiliatedWith: text("affiliated_with"), // AFL-CIO, etc.
  dentalPlan: text("dental_plan"), // Delta Dental, etc.
  pipelineStage: text("pipeline_stage").notNull().default("prospect"), // prospect, contacted, meeting_scheduled, proposal_sent, negotiating, partner, inactive
  priorityScore: integer("priority_score").default(50), // 0-100
  notes: text("notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const unionContacts = pgTable("union_contacts", {
  id: serial("id").primaryKey(),
  unionId: integer("union_id").notNull().references(() => unionOrganizations.id, { onDelete: "cascade" }),
  firstName: text("first_name").notNull(),
  lastName: text("last_name").notNull(),
  title: text("title"), // Business Manager, Business Agent, Benefits Coordinator, etc.
  email: text("email"),
  phone: text("phone"),
  isPrimary: boolean("is_primary").default(false),
  notes: text("notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const unionOutreach = pgTable("union_outreach", {
  id: serial("id").primaryKey(),
  unionId: integer("union_id").notNull().references(() => unionOrganizations.id, { onDelete: "cascade" }),
  contactId: integer("contact_id").references(() => unionContacts.id),
  type: text("type").notNull(), // email, phone, in_person, mail
  subject: text("subject"),
  body: text("body"),
  status: text("status").notNull().default("draft"), // draft, sent, delivered, opened, replied, no_response
  sentAt: timestamp("sent_at"),
  followUpDate: date("follow_up_date"),
  responseNotes: text("response_notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const unionEvents = pgTable("union_events", {
  id: serial("id").primaryKey(),
  unionId: integer("union_id").references(() => unionOrganizations.id),
  title: text("title").notNull(),
  type: text("type").notNull(), // health_fair, lunch_learn, screening, open_enrollment, meeting
  date: date("date").notNull(),
  time: text("time"),
  location: text("location"),
  description: text("description"),
  status: text("status").notNull().default("planned"), // planned, confirmed, completed, cancelled
  attendeeCount: integer("attendee_count"),
  screeningsPerformed: integer("screenings_performed"),
  leadsGenerated: integer("leads_generated"),
  notes: text("notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const unionAgreements = pgTable("union_agreements", {
  id: serial("id").primaryKey(),
  unionId: integer("union_id").notNull().references(() => unionOrganizations.id, { onDelete: "cascade" }),
  type: text("type").notNull(), // preferred_provider, discount_schedule, mou, sponsorship
  title: text("title").notNull(),
  status: text("status").notNull().default("draft"), // draft, pending_review, active, expired, terminated
  startDate: date("start_date"),
  endDate: date("end_date"),
  discountPercentage: decimal("discount_percentage"),
  specialPricing: jsonb("special_pricing"), // e.g., { "full_arch": 14995, "implant": 2000 }
  terms: text("terms"),
  signedBy: text("signed_by"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const unionMemberVisits = pgTable("union_member_visits", {
  id: serial("id").primaryKey(),
  unionId: integer("union_id").notNull().references(() => unionOrganizations.id, { onDelete: "cascade" }),
  patientId: integer("patient_id").references(() => patients.id),
  visitDate: date("visit_date").notNull(),
  serviceType: text("service_type"), // general, implant, ortho, surgery, emergency
  revenueGenerated: decimal("revenue_generated"),
  referralSource: text("referral_source"), // health_fair, direct, referral, website
  notes: text("notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

// ============ ENDODONTICS ============
export const endoCases = pgTable("endo_cases", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  toothNumber: integer("tooth_number").notNull(),
  toothName: text("tooth_name"), // e.g., "Maxillary Left First Molar"
  diagnosis: text("diagnosis").notNull(), // irreversible_pulpitis, pulp_necrosis, previously_treated, etc.
  diagnosisIcd10: text("diagnosis_icd10"),
  procedure: text("procedure").notNull(), // rct, retreatment, pulpotomy, pulpectomy, apicoectomy
  procedureCdt: text("procedure_cdt"), // D3310, D3320, D3330, etc.
  status: text("status").notNull().default("in_progress"), // in_progress, completed, referred_out, failed
  startDate: date("start_date").notNull(),
  completionDate: date("completion_date"),
  referredBy: text("referred_by"),
  referredTo: text("referred_to"),
  providerName: text("provider_name"),
  // Canal data: { mb: { length, file, obturation }, db: { ... }, ml: { ... }, p: { ... } }
  canalData: jsonb("canal_data").default({}),
  // JSONB visit log: [{ date, visit, notes, xray }]
  visitLog: jsonb("visit_log").default([]),
  preOpDiagnosis: text("pre_op_diagnosis"),
  workingLength: text("working_length"), // e.g. "MB:21mm, DB:20mm, ML:21.5mm"
  masterApicalFile: text("master_apical_file"),
  obturationMethod: text("obturation_method"), // lateral_condensation, warm_vertical, single_cone
  irrigant: text("irrigant").default("NaOCl + EDTA"),
  sealer: text("sealer"),
  restorationPlan: text("restoration_plan"), // crown, buildup, composite
  prognosis: text("prognosis"), // excellent, good, fair, poor
  notes: text("notes"),
  totalFee: decimal("total_fee"),
  insuranceFiled: boolean("insurance_filed").default(false),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertEndoCaseSchema = createInsertSchema(endoCases).omit({ id: true, createdAt: true, updatedAt: true });
export type EndoCase = typeof endoCases.$inferSelect;
export type InsertEndoCase = z.infer<typeof insertEndoCaseSchema>;

// ============ PATIENT MESSAGING (2-Way SMS/Email) ============
export const patientMessages = pgTable("patient_messages", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  direction: text("direction").notNull().default("outbound"), // inbound, outbound
  channel: text("channel").notNull().default("sms"), // sms, email, in_app
  subject: text("subject"),
  body: text("body").notNull(),
  status: text("status").notNull().default("sent"), // sent, delivered, failed, read
  sentBy: text("sent_by"),
  fromNumber: text("from_number"),
  toNumber: text("to_number"),
  appointmentId: integer("appointment_id"),
  templateUsed: text("template_used"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertPatientMessageSchema = createInsertSchema(patientMessages).omit({ id: true, createdAt: true });
export type PatientMessage = typeof patientMessages.$inferSelect;
export type InsertPatientMessage = z.infer<typeof insertPatientMessageSchema>;

// ============ MULTI-LOCATION ============
export const practiceLocations = pgTable("practice_locations", {
  id: serial("id").primaryKey(),
  name: text("name").notNull(),
  address: text("address").notNull(),
  city: text("city").notNull(),
  state: text("state").notNull(),
  zip: text("zip"),
  phone: text("phone"),
  email: text("email"),
  npi: text("npi"),
  taxId: text("tax_id"),
  isMain: boolean("is_main").default(false),
  isActive: boolean("is_active").default(true),
  operatories: integer("operatories").default(4),
  providerCount: integer("provider_count").default(1),
  notes: text("notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertPracticeLocationSchema = createInsertSchema(practiceLocations).omit({ id: true, createdAt: true });
export type PracticeLocation = typeof practiceLocations.$inferSelect;
export type InsertPracticeLocation = z.infer<typeof insertPracticeLocationSchema>;

// ============ PEDIATRIC MODULE ============
export const pediatricExams = pgTable("pediatric_exams", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  examDate: date("exam_date").notNull(),
  providerName: text("provider_name"),
  // Primary teeth present (20 teeth): JSON object { A: {present, caries, filling, extracted}, B: {...}, ... }
  primaryTeeth: jsonb("primary_teeth").default({}),
  // Permanent teeth eruption tracking
  permanentEruption: jsonb("permanent_eruption").default({}),
  // Oral habits
  thumbSucking: boolean("thumb_sucking").default(false),
  pacifierUse: boolean("pacifier_use").default(false),
  bruxism: boolean("bruxism").default(false),
  tongueThrustting: boolean("tongue_thrusting").default(false),
  // DMFT scores
  dmft: integer("dmft"), // decayed-missing-filled teeth (primary)
  DMFT: integer("dmft_permanent"), // DMFT permanent
  // Sealants applied
  sealants: text("sealants"), // e.g. "3, 14, 19, 30"
  // Fluoride treatment
  fluorideTreatment: boolean("fluoride_treatment").default(false),
  fluorideType: text("fluoride_type"), // varnish, gel, rinse
  // Radiographs
  bitewingsTaken: boolean("bitewings_taken").default(false),
  // Behavior management
  behaviorRating: text("behavior_rating"), // definitely_positive, positive, negative, definitely_negative
  behaviorMgmtTechnique: text("behavior_mgmt_technique"), // TSD, nitrous, GA
  // Next recall
  nextRecallMonths: integer("next_recall_months").default(6),
  // Clinical notes
  clinicalNotes: text("clinical_notes"),
  treatmentPlan: text("treatment_plan"),
  parentEducation: text("parent_education"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertPediatricExamSchema = createInsertSchema(pediatricExams).omit({ id: true, createdAt: true, updatedAt: true });
export type PediatricExam = typeof pediatricExams.$inferSelect;
export type InsertPediatricExam = z.infer<typeof insertPediatricExamSchema>;

// ============ ORAL SURGERY MODULE ============
export const oralSurgeryCases = pgTable("oral_surgery_cases", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  procedureType: text("procedure_type").notNull(), // simple_extraction, surgical_extraction, wisdom_tooth, implant_placement, bone_graft, biopsy, frenectomy, alveoloplasty, tori_removal, sinus_lift, all_on_4, all_on_6
  teeth: text("teeth"), // affected teeth numbers
  surgeryDate: date("surgery_date").notNull(),
  surgeon: text("surgeon"),
  anesthesia: text("anesthesia").notNull().default("local"), // local, local_sedation, iv_sedation, ga
  anesthesiaDetails: text("anesthesia_details"),
  status: text("status").notNull().default("planned"), // planned, completed, cancelled, follow_up_needed
  // Pre-op
  preOpNotes: text("pre_op_notes"),
  medicalClearance: boolean("medical_clearance").default(false),
  consentSigned: boolean("consent_signed").default(false),
  // Intra-op
  operativeFindings: text("operative_findings"),
  complications: text("complications"),
  implantDetails: jsonb("implant_details").default({}), // { position, brand, size, torque }
  boneGraftDetails: text("bone_graft_details"),
  surgeryDuration: integer("surgery_duration"), // minutes
  // Post-op
  postOpInstructions: text("post_op_instructions"),
  medicationsPrescribed: text("medications_prescribed"),
  followUpDate: date("follow_up_date"),
  healingStatus: text("healing_status"), // normal, delayed, complications
  // Billing
  cdtCode: text("cdt_code"),
  fee: decimal("fee"),
  notes: text("notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertOralSurgeryCaseSchema = createInsertSchema(oralSurgeryCases).omit({ id: true, createdAt: true, updatedAt: true });
export type OralSurgeryCase = typeof oralSurgeryCases.$inferSelect;
export type InsertOralSurgeryCase = z.infer<typeof insertOralSurgeryCaseSchema>;

// ============ PRACTICE PROVIDERS (Multi-Provider Scheduling) ============
export const practiceProviders = pgTable("practice_providers", {
  id: serial("id").primaryKey(),
  name: text("name").notNull(),
  title: text("title").notNull().default("DMD"), // DMD, DDS, RDH, DA, etc.
  specialty: text("specialty").notNull().default("General Dentistry"),
  color: text("color").notNull().default("#0EA5E9"), // hex color for calendar
  npi: text("npi"),
  licenseNumber: text("license_number"),
  email: text("email"),
  phone: text("phone"),
  isActive: boolean("is_active").default(true),
  // Default working hours JSON: { monday: { start: "08:00", end: "17:00" }, ... }
  workingHours: jsonb("working_hours").default({}),
  // Operatory/chair assignment
  operatory: text("operatory"),
  // Production target per day ($)
  dailyProductionTarget: decimal("daily_production_target"),
  notes: text("notes"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertPracticeProviderSchema = createInsertSchema(practiceProviders).omit({ id: true, createdAt: true });
export type PracticeProvider = typeof practiceProviders.$inferSelect;
export type InsertPracticeProvider = z.infer<typeof insertPracticeProviderSchema>;

// ============ RECALL SYSTEM ============
export const recallPatients = pgTable("recall_patients", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  recallType: text("recall_type").notNull(), // hygiene, post_op, implant_check, ortho_check, endo_check, perio_maintenance, new_patient_followup
  intervalMonths: integer("interval_months").notNull().default(6),
  lastVisitDate: date("last_visit_date"),
  nextDueDate: date("next_due_date").notNull(),
  status: text("status").notNull().default("due"), // due, scheduled, completed, overdue, declined
  priority: text("priority").notNull().default("normal"), // high, normal, low
  notes: text("notes"),
  assignedTo: text("assigned_to"),
  contactPreference: text("contact_preference").default("any"), // phone, email, sms, any
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const recallContactLog = pgTable("recall_contact_log", {
  id: serial("id").primaryKey(),
  recallPatientId: integer("recall_patient_id").notNull().references(() => recallPatients.id, { onDelete: "cascade" }),
  contactDate: date("contact_date").notNull(),
  method: text("method").notNull(), // phone, email, sms, mail
  outcome: text("outcome").notNull(), // scheduled, no_answer, left_vm, patient_declined, wrong_number
  scheduledDate: date("scheduled_date"),
  notes: text("notes"),
  contactedBy: text("contacted_by"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertRecallPatientSchema = createInsertSchema(recallPatients).omit({ id: true, createdAt: true, updatedAt: true });
export const insertRecallContactLogSchema = createInsertSchema(recallContactLog).omit({ id: true, createdAt: true });
export type RecallPatient = typeof recallPatients.$inferSelect;
export type InsertRecallPatient = z.infer<typeof insertRecallPatientSchema>;
export type RecallContactLog = typeof recallContactLog.$inferSelect;
export type InsertRecallContactLog = z.infer<typeof insertRecallContactLogSchema>;

// ============ ORTHODONTICS ============
export const orthoCases = pgTable("ortho_cases", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  treatmentType: text("treatment_type").notNull(), // Invisalign Full, Invisalign Lite, Metal Braces, Clear Braces, Lingual Braces, Retainer
  status: text("status").notNull().default("active"), // active, retention, completed, discontinued
  startDate: date("start_date").notNull(),
  estimatedEndDate: date("estimated_end_date"),
  actualEndDate: date("actual_end_date"),
  currentStep: integer("current_step").default(1),
  totalSteps: integer("total_steps"),
  compliance: integer("compliance").default(100), // 0-100 %
  totalFee: decimal("total_fee"),
  amountPaid: decimal("amount_paid").default("0"),
  insuranceCoverage: decimal("insurance_coverage").default("0"),
  archesType: text("arches_type").default("both"), // upper, lower, both
  extractionsRequired: boolean("extractions_required").default(false),
  providerName: text("provider_name"),
  notes: text("notes"),
  // JSONB: [{ phase, date, notes, attachments, xrays, photos }]
  progressLog: jsonb("progress_log").default([]),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertOrthoCaseSchema = createInsertSchema(orthoCases).omit({ id: true, createdAt: true, updatedAt: true });
export type OrthoCase = typeof orthoCases.$inferSelect;
export type InsertOrthoCase = z.infer<typeof insertOrthoCaseSchema>;

// ============ PERIO CHARTING ============
export const perioExams = pgTable("perio_exams", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  providerId: text("provider_id"),
  providerName: text("provider_name"),
  examDate: date("exam_date").notNull(),
  // JSONB: { [toothNum]: { facialProbing:[d,f,m], lingualProbing:[d,l,m], facialBop:[b,b,b], lingualBop:[b,b,b], facialRecession:[n,n,n], lingualRecession:[n,n,n], mobility:0-3, furcation:0-3, missing:bool, implant:bool } }
  probingData: jsonb("probing_data").default({}),
  diagnosisStage: text("diagnosis_stage"),   // I, II, III, IV
  diagnosisGrade: text("diagnosis_grade"),   // A, B, C
  diagnosisExtent: text("diagnosis_extent"), // Localized, Generalized, Molar-incisor
  notes: text("notes"),
  aiAssessment: text("ai_assessment"),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
  updatedAt: timestamp("updated_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertPerioExamSchema = createInsertSchema(perioExams).omit({ id: true, createdAt: true, updatedAt: true });
export type PerioExam = typeof perioExams.$inferSelect;
export type InsertPerioExam = z.infer<typeof insertPerioExamSchema>;

export const insertUnionOrganizationSchema = createInsertSchema(unionOrganizations).omit({ id: true, createdAt: true, updatedAt: true });
export const insertUnionContactSchema = createInsertSchema(unionContacts).omit({ id: true, createdAt: true });
export const insertUnionOutreachSchema = createInsertSchema(unionOutreach).omit({ id: true, createdAt: true });
export const insertUnionEventSchema = createInsertSchema(unionEvents).omit({ id: true, createdAt: true });
export const insertUnionAgreementSchema = createInsertSchema(unionAgreements).omit({ id: true, createdAt: true });
export const insertUnionMemberVisitSchema = createInsertSchema(unionMemberVisits).omit({ id: true, createdAt: true });

export type UnionOrganization = typeof unionOrganizations.$inferSelect;

// ============ STRIPE PAYMENTS ============
export const stripePayments = pgTable("stripe_payments", {
  id: serial("id").primaryKey(),
  patientId: integer("patient_id").notNull().references(() => patients.id, { onDelete: "cascade" }),
  claimId: integer("claim_id").references(() => billingClaims.id),
  stripePaymentIntentId: text("stripe_payment_intent_id").notNull().unique(),
  amount: integer("amount").notNull(), // in cents
  currency: text("currency").default("usd").notNull(),
  status: text("status").notNull(), // succeeded, pending, failed
  description: text("description"),
  patientName: text("patient_name"),
  receiptEmail: text("receipt_email"),
  collectedBy: text("collected_by"),
  testMode: boolean("test_mode").default(true).notNull(),
  createdAt: timestamp("created_at").default(sql`CURRENT_TIMESTAMP`).notNull(),
});

export const insertStripePaymentSchema = createInsertSchema(stripePayments).omit({ id: true, createdAt: true });
export type StripePayment = typeof stripePayments.$inferSelect;
export type InsertStripePayment = z.infer<typeof insertStripePaymentSchema>;
export type InsertUnionOrganization = z.infer<typeof insertUnionOrganizationSchema>;
export type UnionContact = typeof unionContacts.$inferSelect;
export type InsertUnionContact = z.infer<typeof insertUnionContactSchema>;
export type UnionOutreach = typeof unionOutreach.$inferSelect;
export type InsertUnionOutreach = z.infer<typeof insertUnionOutreachSchema>;
export type UnionEvent = typeof unionEvents.$inferSelect;
export type InsertUnionEvent = z.infer<typeof insertUnionEventSchema>;
export type UnionAgreement = typeof unionAgreements.$inferSelect;
export type InsertUnionAgreement = z.infer<typeof insertUnionAgreementSchema>;
export type UnionMemberVisit = typeof unionMemberVisits.$inferSelect;
export type InsertUnionMemberVisit = z.infer<typeof insertUnionMemberVisitSchema>;
