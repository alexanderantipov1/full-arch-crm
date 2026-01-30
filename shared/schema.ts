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

export const insertGeneratedDocumentSchema = createInsertSchema(generatedDocuments).omit({ id: true, createdAt: true });
export const insertAppealSchema = createInsertSchema(appeals).omit({ id: true, createdAt: true, updatedAt: true });
export const insertEligibilityCheckSchema = createInsertSchema(eligibilityChecks).omit({ id: true, checkDate: true });
export const insertPaymentPostingSchema = createInsertSchema(paymentPostings).omit({ id: true, createdAt: true });
export const insertTrainingProgressSchema = createInsertSchema(trainingProgress).omit({ id: true, createdAt: true });

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
