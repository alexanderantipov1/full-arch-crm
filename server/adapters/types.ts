/**
 * full-arch-crm — Universal DatabaseAdapter Platform
 *
 * CANONICAL INTERNAL SCHEMA
 * ─────────────────────────
 * These types are the single source of truth for all AI modules, simulation,
 * wiki, and UI. Every third-party database (fusion_crm, Western Dental,
 * ClearChoice, Novvia, etc.) maps INTO these types via their adapter.
 *
 * Core rule: AI modules NEVER import from external adapter code.
 * They only ever see these canonical types.
 *
 * HIPAA note: Any field marked @phi must be redacted before logging,
 * excluded from wiki intelligence ingest, and anonymized before
 * cross-clinic sharing.
 */

// ─── Tenant / Client identity ────────────────────────────────────────────────

export interface CanonicalTenant {
  tenantId: string;           // UUID — stable across all systems
  slug: string;               // url-safe name e.g. "fusion-dental", "western-dental"
  displayName: string;
  adapterType: AdapterType;   // which adapter class handles this tenant
  adapterConfig: AdapterConfig;
  hipaaConfig: HipaaConfig;
  createdAt: Date;
  enabled: boolean;
}

export type AdapterType =
  | "fusion_crm"       // Fusion Dental Corp — our first client
  | "western_dental"   // Western Dental adapter (future)
  | "clearchoice"      // ClearChoice adapter (future)
  | "novvia"           // Novvia adapter (future)
  | "generic_rest"     // Any REST API with standard mapping
  | "mock";            // Dev / testing

export interface AdapterConfig {
  baseUrl?: string;
  apiKey?: string;           // encrypted at rest
  tenantId?: string;         // remote tenant identifier
  customHeaders?: Record<string, string>;
  timeoutMs?: number;
  retryAttempts?: number;
  [key: string]: unknown;    // adapter-specific overrides
}

export interface HipaaConfig {
  baaSignedAt?: Date;         // Business Associate Agreement date
  baaCounterparty?: string;
  phiAccessLogEnabled: boolean;
  auditRetentionDays: number; // HIPAA minimum 6 years = 2190 days
  encryptionAtRest: boolean;
  encryptionInTransit: boolean;
  allowedPurposes: PhiAccessPurpose[];
}

// ─── PHI Access Control ──────────────────────────────────────────────────────

/**
 * Every PHI access must declare a purpose. This is logged to the HIPAA
 * audit trail. Purposes map to allowed operations — e.g. "marketing" cannot
 * access clinical notes.
 */
export type PhiAccessPurpose =
  | "treatment"              // Direct patient care
  | "payment"                // Billing and claims
  | "operations"             // Practice management, scheduling
  | "ai_scribe"              // AI documentation during/after visit
  | "insurance_verification" // Eligibility and prior auth
  | "quality_improvement"    // Internal analytics (de-identified)
  | "audit"                  // Compliance review
  | "patient_request"        // Patient asking for their own records
  | "emergency";             // Break-glass override (always alerts)

export interface PhiAccessContext {
  purpose: PhiAccessPurpose;
  requestedBy: string;       // userId or system process name
  tenantId: string;
  patientId?: string;        // person_uid being accessed
  reason?: string;           // human-readable justification
  traceId: string;           // links to request chain
}

export interface PhiAuditEntry {
  id: string;
  timestamp: Date;
  tenantId: string;
  patientId: string;         // @phi — hashed in cross-clinic analytics
  accessedBy: string;
  purpose: PhiAccessPurpose;
  fieldsAccessed: string[];  // which PHI fields were returned
  sourceAdapter: AdapterType;
  traceId: string;
  ipAddress?: string;
}

// ─── Canonical Patient ───────────────────────────────────────────────────────

/**
 * Full PHI record. Only returned when purpose === "treatment" | "patient_request" | "emergency".
 * All other purposes get CanonicalPatientSummary (non-PHI).
 */
export interface CanonicalPatient {
  // Identity
  personUid: string;           // @phi — stable UUID, our canonical ID
  tenantId: string;
  externalIds: ExternalId[];   // IDs in the source system

  // Demographics — all @phi
  firstName: string;           // @phi
  lastName: string;            // @phi
  dateOfBirth: Date;           // @phi
  gender: "Male" | "Female" | "NonBinary" | "Unknown";
  email?: string;              // @phi
  phone?: string;              // @phi
  address?: CanonicalAddress;  // @phi

  // Emergency contact — @phi
  emergencyContact?: {
    name: string;              // @phi
    phone: string;             // @phi
    relationship: string;
  };

  // Clinical summary (non-PHI aggregates OK for ops)
  riskScore?: number;          // 0–100, AI-derived
  patientStage: PatientStage;
  lastVisitDate?: Date;
  nextAppointmentDate?: Date;
  activeTreatmentPlan: boolean;
  insuranceType?: InsuranceType;

  // Metadata
  createdAt: Date;
  updatedAt: Date;
  sourceAdapter: AdapterType;
  dataFreshness: Date;         // when adapter last refreshed this record
}

/**
 * Non-PHI summary — safe for ops analytics, wiki ingest, cross-clinic sharing.
 */
export interface CanonicalPatientSummary {
  personUid: string;           // pseudonymized in cross-clinic context
  tenantId: string;
  displayName: string;         // "John D." — first name + last initial only
  ageBand: AgeBand;            // "35-44" — never exact DOB
  gender: "Male" | "Female" | "NonBinary" | "Unknown";
  insuranceType?: InsuranceType;
  patientStage: PatientStage;
  lastVisitDate?: Date;
  activeTreatmentPlan: boolean;
  riskScore?: number;
  scenarioTags: string[];      // e.g. ["recall_overdue", "implant_candidate"]
  sourceAdapter: AdapterType;
}

export interface ExternalId {
  system: string;              // e.g. "fusion_crm", "carestack", "dentrix"
  id: string;
  kind?: string;               // sub-type if system has multiple object types
}

export interface CanonicalAddress {
  line1: string;               // @phi
  line2?: string;              // @phi
  city: string;                // @phi (less sensitive, used in ops)
  state: string;
  zip: string;
  country: string;
}

export type PatientStage =
  | "lead"
  | "consultation_scheduled"
  | "consultation_completed"
  | "treatment_plan_accepted"
  | "financing_approved"
  | "prior_auth_pending"
  | "surgery_scheduled"
  | "post_op"
  | "maintenance"
  | "inactive";

export type AgeBand =
  | "18-24" | "25-34" | "35-44" | "45-54" | "55-64" | "65-74" | "75+";

export type InsuranceType = "ppo" | "hmo" | "medicaid" | "medicare" | "self_pay" | "other";

// ─── Canonical Medical History ───────────────────────────────────────────────

export interface CanonicalMedicalHistory {
  personUid: string;
  tenantId: string;
  conditions: string[];        // @phi
  allergies: string[];         // @phi — critical for scribe/surgery
  medications: string[];       // @phi
  surgeries: string[];         // @phi
  smokingStatus?: string;
  alcoholUse?: string;
  bloodPressure?: string;
  weight?: string;
  height?: string;
  lastPhysicalExam?: Date;
  notes?: string;              // @phi
  updatedAt: Date;
}

// ─── Canonical Insurance ─────────────────────────────────────────────────────

export interface CanonicalInsurance {
  personUid: string;           // @phi
  tenantId: string;
  insuranceType: "primary" | "secondary" | "tertiary";
  providerName: string;
  payerId?: string;            // payer EDI ID for electronic claims
  policyNumber: string;        // @phi
  groupNumber?: string;
  subscriberName?: string;     // @phi
  subscriberDob?: Date;        // @phi
  relationship: "self" | "spouse" | "child" | "other";
  effectiveDate?: Date;
  terminationDate?: Date;
  coveragePercentage?: number;
  annualMaximum?: number;
  deductible?: number;
  remainingBenefit?: number;
  deductibleMet?: number;
  priorAuthRequired: boolean;
  notes?: string;
}

export interface CanonicalEligibilityResult {
  personUid: string;
  tenantId: string;
  checkedAt: Date;
  status: "active" | "inactive" | "unknown";
  remainingBenefit: number;
  deductibleMet: number;
  coverageDetails: Record<string, unknown>;
  procedureCoverageMap: Record<string, ProcedureCoverage>;
}

export interface ProcedureCoverage {
  cdtCode: string;
  covered: boolean;
  coveragePercent: number;
  requiresPriorAuth: boolean;
  limitations?: string;
}

// ─── Canonical Appointment ───────────────────────────────────────────────────

export interface CanonicalAppointment {
  appointmentId: string;
  tenantId: string;
  personUid: string;           // @phi
  treatmentPlanId?: string;
  title: string;
  appointmentType: AppointmentType;
  startTime: Date;
  endTime: Date;
  durationMinutes: number;
  status: AppointmentStatus;
  providerId?: string;
  providerName?: string;
  locationId?: string;
  locationName?: string;
  chair?: number;
  procedureCodes: string[];    // CDT codes planned
  insuranceVerified: boolean;
  notes?: string;
  patientDisplay?: string;     // "John D." — non-PHI display name
  createdAt: Date;
  updatedAt: Date;
  sourceAdapter: AdapterType;
}

export type AppointmentType =
  | "consultation" | "pre_op" | "surgery" | "post_op"
  | "maintenance" | "emergency" | "new_patient" | "recall" | "other";

export type AppointmentStatus =
  | "scheduled" | "confirmed" | "checked_in" | "in_progress"
  | "completed" | "cancelled" | "no_show" | "rescheduled";

// ─── Canonical Treatment Plan ────────────────────────────────────────────────

export interface CanonicalTreatmentPlan {
  planId: string;
  tenantId: string;
  personUid: string;           // @phi
  planName: string;
  status: TreatmentPlanStatus;
  diagnosis?: string;
  diagnosisCode?: string;      // ICD-10
  aiDiagnosis?: string;        // AI-generated clinical assessment
  aiRecommendations?: TreatmentRecommendation[];
  procedures: PlannedProcedure[];
  totalCost: number;
  insuranceCoverage: number;
  patientResponsibility: number;
  priorAuthStatus?: string;
  priorAuthNumber?: string;
  medicalNecessityLetter?: string;
  notes?: string;
  createdAt: Date;
  updatedAt: Date;
  sourceAdapter: AdapterType;
}

export type TreatmentPlanStatus =
  | "draft" | "presented" | "active" | "completed" | "declined" | "expired";

export interface PlannedProcedure {
  cdtCode: string;
  description: string;
  quantity: number;
  unitFee: number;
  totalFee: number;
  toothNumbers?: number[];
  status?: string;
}

export interface TreatmentRecommendation {
  recommendation: string;
  priority: "high" | "medium" | "low";
  rationale?: string;
}

// ─── Canonical Clinical Note (SOAP) ──────────────────────────────────────────

export interface CanonicalClinicalNote {
  noteId: string;
  tenantId: string;
  personUid: string;           // @phi
  appointmentId?: string;
  noteType: "soap_note" | "consultation" | "progress" | "surgery" | "post_op" | "other";
  title: string;

  // SOAP structure — all @phi
  soapSubjective?: string;     // @phi — patient's reported symptoms
  soapObjective?: string;      // @phi — clinical findings
  soapAssessment?: string;     // @phi — diagnosis
  soapPlan?: string;           // @phi — treatment plan

  cdtCodes?: string[];
  icd10Codes?: string[];
  authorId?: string;
  authorName?: string;
  aiGenerated: boolean;
  aiConfidenceScore?: number;  // 0–100
  createdAt: Date;
  updatedAt: Date;
  sourceAdapter: AdapterType;
}

// ─── Canonical Billing Claim ─────────────────────────────────────────────────

export interface CanonicalClaim {
  claimId: string;
  tenantId: string;
  personUid: string;           // @phi
  treatmentPlanId?: string;
  claimNumber: string;
  claimStatus: ClaimStatus;
  serviceDate: Date;
  cdtCode: string;
  icd10Code?: string;
  description: string;
  chargedAmount: number;
  allowedAmount?: number;
  paidAmount?: number;
  patientPortion?: number;
  denialReason?: string;
  appealStatus?: string;
  submittedDate?: Date;
  paidDate?: Date;
  createdAt: Date;
  updatedAt: Date;
  sourceAdapter: AdapterType;
}

export type ClaimStatus =
  | "draft" | "pending" | "submitted" | "acknowledged"
  | "approved" | "denied" | "appealed" | "paid" | "written_off";

// ─── Canonical Prior Authorization ───────────────────────────────────────────

export interface CanonicalPriorAuth {
  authId: string;
  tenantId: string;
  personUid: string;           // @phi
  treatmentPlanId?: string;
  authType: string;
  status: "submitted" | "approved" | "denied" | "expired" | "not_required";
  submissionDate?: Date;
  responseDate?: Date;
  expirationDate?: Date;
  authNumber?: string;
  requestedProcedures: Record<string, unknown>;
  approvedProcedures?: Record<string, unknown>;
  denialReason?: string;
  medicalNecessityLetter?: string;
  notes?: string;
}

// ─── Canonical Financing Plan ────────────────────────────────────────────────

export interface CanonicalFinancingPlan {
  planId: string;
  tenantId: string;
  personUid: string;           // @phi
  treatmentPlanId?: string;
  provider: string;
  applicationStatus: "pending" | "approved" | "denied" | "expired";
  approvedAmount?: number;
  interestRate?: number;
  termMonths?: number;
  monthlyPayment?: number;
  downPayment?: number;
  approvalDate?: Date;
  expirationDate?: Date;
  accountNumber?: string;      // @phi
  notes?: string;
}

// ─── Intelligence (anonymized, cross-clinic safe) ────────────────────────────

/**
 * Anonymized pattern that can be safely stored in the Karpathy wiki
 * and shared across clinics. Contains ZERO PHI.
 */
export interface AnonymizedIntelligencePattern {
  patternType: IntelligencePatternType;
  tenantId: string;           // hashed/pseudonymized for cross-clinic context
  sourceAdapter: AdapterType;
  observedAt: Date;
  confidence: number;         // 0–1
  sampleSize: number;         // k-anonymity: minimum 10 before sharing
  payload: Record<string, unknown>; // pattern-specific data, all non-PHI
  wikiTargetPath: string;     // which wiki page this updates
}

export type IntelligencePatternType =
  | "insurance_approval_pattern"     // which payers approve which codes
  | "denial_pattern"                 // common denial reasons by payer
  | "appeal_success_pattern"         // what makes appeals succeed
  | "treatment_outcome_pattern"      // procedure success rates
  | "scheduling_pattern"             // booking/no-show patterns
  | "collection_pattern"             // payment collection rates
  | "dso_performance_pattern";       // multi-location benchmarks

// ─── Adapter Query Options ───────────────────────────────────────────────────

export interface PatientListOptions {
  cursor?: string;
  limit?: number;              // default 50, max 200
  search?: string;
  stage?: PatientStage;
  insuranceType?: InsuranceType;
  lastVisitBefore?: Date;
  lastVisitAfter?: Date;
  activeTreatmentPlan?: boolean;
}

export interface PatientListResult {
  items: CanonicalPatientSummary[];
  total: number;
  nextCursor?: string;
  hasMore: boolean;
}

export interface AppointmentListOptions {
  date?: Date;
  dateFrom?: Date;
  dateTo?: Date;
  locationId?: string;
  providerId?: string;
  personUid?: string;
  status?: AppointmentStatus;
  limit?: number;
}

export interface ClaimListOptions {
  personUid?: string;
  status?: ClaimStatus;
  dateFrom?: Date;
  dateTo?: Date;
  cdtCode?: string;
  limit?: number;
}

// ─── Adapter health ──────────────────────────────────────────────────────────

export interface AdapterHealthStatus {
  adapterType: AdapterType;
  tenantId: string;
  healthy: boolean;
  latencyMs?: number;
  lastCheckedAt: Date;
  errorMessage?: string;
  rateLimitRemaining?: number;
}

// ─── Mapping spec (onboarding config) ───────────────────────────────────────

/**
 * When onboarding a new DSO, you define a MappingSpec that describes how
 * their source fields map to canonical fields. The schema translation layer
 * uses this spec — no custom adapter code needed for standard mappings.
 *
 * Only non-standard transformations require a custom adapter method.
 */
export interface MappingSpec {
  adapterType: AdapterType;
  version: string;
  description: string;

  patient: FieldMappingGroup;
  appointment: FieldMappingGroup;
  treatmentPlan: FieldMappingGroup;
  clinicalNote: FieldMappingGroup;
  insurance: FieldMappingGroup;
  claim: FieldMappingGroup;

  // Value transformations for enums that differ across systems
  enumMaps: {
    patientStage?: Record<string, PatientStage>;
    appointmentType?: Record<string, AppointmentType>;
    appointmentStatus?: Record<string, AppointmentStatus>;
    claimStatus?: Record<string, ClaimStatus>;
    insuranceType?: Record<string, InsuranceType>;
  };
}

export interface FieldMappingGroup {
  // key = canonical field name, value = source field path (dot-notation)
  // e.g. { "firstName": "patient.first_name", "dateOfBirth": "patient.dob" }
  direct: Record<string, string>;

  // Fields that need transformation beyond simple rename
  // key = canonical field name, value = transformer function name
  computed: Record<string, string>;

  // Source fields to ignore (don't map to canonical)
  ignored: string[];
}
