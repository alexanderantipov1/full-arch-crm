import { sql, relations } from "drizzle-orm";
import { pgTable, text, varchar, serial, integer, timestamp, date, boolean, jsonb, decimal } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";

export * from "./models/auth";
export * from "./models/chat";

// Patients table
export const patients = pgTable("patients", {
  id: serial("id").primaryKey(),
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

// Relations
export const patientsRelations = relations(patients, ({ many }) => ({
  medicalHistory: many(medicalHistory),
  dentalInfo: many(dentalInfo),
  facialEvaluation: many(facialEvaluation),
  insurance: many(insurance),
  referrals: many(patientReferrals),
  notes: many(clinicalNotes),
  documents: many(patientDocuments),
  treatmentPlans: many(treatmentPlans),
  appointments: many(appointments),
  surgeryReports: many(surgeryReports),
  billingClaims: many(billingClaims),
}));

// Insert Schemas
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

// Types
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
