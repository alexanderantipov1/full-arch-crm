/**
 * full-arch-crm — DatabaseAdapter Interface
 * ──────────────────────────────────────────
 * The single contract every database backend must implement.
 *
 * ONBOARDING A NEW DSO (e.g. Western Dental, ClearChoice, Novvia):
 * ────────────────────────────────────────────────────────────────
 * Step 1 — Define a MappingSpec (mapping.config.ts) for their field names
 * Step 2 — Implement this interface (can extend BaseAdapter for free translation)
 * Step 3 — Register in AdapterRegistry with their tenantId
 * Step 4 — Set env vars: ADAPTER_TYPE, ADAPTER_URL, ADAPTER_API_KEY
 *
 * That's it. All AI modules (scribe, insurance AI, simulation, wiki)
 * work immediately — they only ever call this interface.
 *
 * AI modules MUST NEVER import from adapter implementations directly.
 * Always resolve via: `registry.getAdapter(tenantId)`
 */

import type {
  PhiAccessContext,
  PhiAuditEntry,
  CanonicalPatient,
  CanonicalPatientSummary,
  CanonicalMedicalHistory,
  CanonicalInsurance,
  CanonicalEligibilityResult,
  CanonicalAppointment,
  CanonicalTreatmentPlan,
  CanonicalClinicalNote,
  CanonicalClaim,
  CanonicalPriorAuth,
  CanonicalFinancingPlan,
  AnonymizedIntelligencePattern,
  AdapterHealthStatus,
  PatientListOptions,
  PatientListResult,
  AppointmentListOptions,
  ClaimListOptions,
} from "./types";

// ─── Core Interface ──────────────────────────────────────────────────────────

export interface DatabaseAdapter {
  /** Adapter identity */
  readonly adapterType: string;
  readonly tenantId: string;

  // ── Health ────────────────────────────────────────────────────────────────

  /**
   * Ping the backend. Called every 5 minutes by the health monitor.
   * Returns healthy=false instead of throwing — callers degrade gracefully.
   */
  healthCheck(): Promise<AdapterHealthStatus>;

  // ── Patients ──────────────────────────────────────────────────────────────

  /**
   * List patients — returns NON-PHI summaries only.
   * Safe for ops analytics, wiki ingest, DSO dashboard.
   */
  listPatients(options?: PatientListOptions): Promise<PatientListResult>;

  /**
   * Full PHI record. REQUIRES phiContext with a declared purpose.
   * Every call is written to the HIPAA audit log.
   * Returns null if patient not found (never throws 404).
   */
  getPatient(personUid: string, phiContext: PhiAccessContext): Promise<CanonicalPatient | null>;

  /**
   * Search patients by name, email, or phone.
   * Returns non-PHI summaries — use getPatient() if you need PHI.
   */
  searchPatients(query: string, limit?: number): Promise<CanonicalPatientSummary[]>;

  /**
   * Create a new patient record. Returns the canonical form with assigned personUid.
   */
  createPatient(
    data: Omit<CanonicalPatient, "personUid" | "createdAt" | "updatedAt" | "sourceAdapter" | "dataFreshness">,
    phiContext: PhiAccessContext
  ): Promise<CanonicalPatient>;

  /**
   * Update patient demographics. Returns updated canonical record.
   */
  updatePatient(
    personUid: string,
    updates: Partial<Pick<CanonicalPatient, "firstName" | "lastName" | "email" | "phone" | "address" | "emergencyContact">>,
    phiContext: PhiAccessContext
  ): Promise<CanonicalPatient>;

  // ── Medical History ───────────────────────────────────────────────────────

  getMedicalHistory(personUid: string, phiContext: PhiAccessContext): Promise<CanonicalMedicalHistory | null>;
  upsertMedicalHistory(data: CanonicalMedicalHistory, phiContext: PhiAccessContext): Promise<CanonicalMedicalHistory>;

  // ── Insurance ─────────────────────────────────────────────────────────────

  getInsurance(personUid: string, phiContext: PhiAccessContext): Promise<CanonicalInsurance[]>;

  /**
   * Real-time eligibility check against the payer.
   * Results cached for 24h to avoid repeat payer hits.
   */
  checkEligibility(
    personUid: string,
    procedureCodes: string[],
    phiContext: PhiAccessContext
  ): Promise<CanonicalEligibilityResult>;

  // ── Appointments ──────────────────────────────────────────────────────────

  listAppointments(options: AppointmentListOptions): Promise<CanonicalAppointment[]>;

  getAppointment(appointmentId: string): Promise<CanonicalAppointment | null>;

  /**
   * Book appointment. Returns the created appointment with assigned appointmentId.
   */
  createAppointment(
    data: Omit<CanonicalAppointment, "appointmentId" | "createdAt" | "updatedAt" | "sourceAdapter">
  ): Promise<CanonicalAppointment>;

  updateAppointment(
    appointmentId: string,
    updates: Partial<Pick<CanonicalAppointment, "startTime" | "endTime" | "status" | "notes" | "providerId" | "chair">>
  ): Promise<CanonicalAppointment>;

  cancelAppointment(appointmentId: string, reason?: string): Promise<void>;

  // ── Treatment Plans ───────────────────────────────────────────────────────

  getTreatmentPlans(personUid: string, phiContext: PhiAccessContext): Promise<CanonicalTreatmentPlan[]>;

  getTreatmentPlan(planId: string, phiContext: PhiAccessContext): Promise<CanonicalTreatmentPlan | null>;

  createTreatmentPlan(
    data: Omit<CanonicalTreatmentPlan, "planId" | "createdAt" | "updatedAt" | "sourceAdapter">,
    phiContext: PhiAccessContext
  ): Promise<CanonicalTreatmentPlan>;

  updateTreatmentPlan(
    planId: string,
    updates: Partial<CanonicalTreatmentPlan>,
    phiContext: PhiAccessContext
  ): Promise<CanonicalTreatmentPlan>;

  // ── Clinical Notes (AI Scribe output) ────────────────────────────────────

  getClinicalNotes(personUid: string, phiContext: PhiAccessContext): Promise<CanonicalClinicalNote[]>;

  /**
   * Save AI Scribe output. Called after every completed scribe session.
   * Automatically triggers wiki ingest for the clinical pattern.
   */
  saveClinicalNote(
    data: Omit<CanonicalClinicalNote, "noteId" | "createdAt" | "updatedAt" | "sourceAdapter">,
    phiContext: PhiAccessContext
  ): Promise<CanonicalClinicalNote>;

  // ── CDT Code lookup ───────────────────────────────────────────────────────

  /**
   * Search CDT codes by code or description text.
   * Used by AI Scribe to suggest codes from dictation.
   */
  searchCdtCodes(query: string, limit?: number): Promise<CdtCodeResult[]>;

  // ── Billing / Claims ──────────────────────────────────────────────────────

  listClaims(options: ClaimListOptions): Promise<CanonicalClaim[]>;

  getClaim(claimId: string): Promise<CanonicalClaim | null>;

  createClaim(
    data: Omit<CanonicalClaim, "claimId" | "createdAt" | "updatedAt" | "sourceAdapter">,
    phiContext: PhiAccessContext
  ): Promise<CanonicalClaim>;

  updateClaim(
    claimId: string,
    updates: Partial<Pick<CanonicalClaim, "claimStatus" | "allowedAmount" | "paidAmount" | "patientPortion" | "denialReason" | "appealStatus" | "paidDate">>
  ): Promise<CanonicalClaim>;

  /**
   * Post EOB (Explanation of Benefits) from insurance.
   * Updates claim with payment, triggers wiki ingest for insurance pattern.
   */
  postEob(
    claimId: string,
    eob: EobPosting,
    phiContext: PhiAccessContext
  ): Promise<CanonicalClaim>;

  // ── Prior Authorization ───────────────────────────────────────────────────

  getPriorAuths(personUid: string, phiContext: PhiAccessContext): Promise<CanonicalPriorAuth[]>;

  createPriorAuth(
    data: Omit<CanonicalPriorAuth, "authId">,
    phiContext: PhiAccessContext
  ): Promise<CanonicalPriorAuth>;

  updatePriorAuth(authId: string, updates: Partial<CanonicalPriorAuth>): Promise<CanonicalPriorAuth>;

  // ── Financing ─────────────────────────────────────────────────────────────

  getFinancingPlans(personUid: string, phiContext: PhiAccessContext): Promise<CanonicalFinancingPlan[]>;

  createFinancingPlan(
    data: Omit<CanonicalFinancingPlan, "planId">,
    phiContext: PhiAccessContext
  ): Promise<CanonicalFinancingPlan>;

  // ── Intelligence (cross-clinic wiki feed) ────────────────────────────────

  /**
   * Push an anonymized pattern to the backend for cross-clinic learning.
   * Called by WikiService after ingest.
   * Backend stores this in their intelligence layer (fusion_crm's /api/v1/intelligence).
   */
  pushIntelligence(pattern: AnonymizedIntelligencePattern): Promise<void>;

  /**
   * Pull intelligence patterns from the network.
   * Called by agents before making insurance / clinical decisions.
   */
  queryIntelligence(
    patternType: string,
    query: Record<string, unknown>
  ): Promise<AnonymizedIntelligencePattern[]>;

  // ── HIPAA Audit ───────────────────────────────────────────────────────────

  /**
   * Write a PHI access entry to the audit log.
   * Must complete before the PHI data is returned to the caller.
   */
  logPhiAccess(entry: Omit<PhiAuditEntry, "id" | "timestamp">): Promise<void>;

  /**
   * Retrieve audit log for compliance review.
   * Requires purpose === "audit".
   */
  getAuditLog(
    options: { tenantId: string; from: Date; to: Date; patientId?: string },
    phiContext: PhiAccessContext
  ): Promise<PhiAuditEntry[]>;
}

// ─── Supplementary types ─────────────────────────────────────────────────────

export interface CdtCodeResult {
  code: string;          // e.g. "D6010"
  description: string;   // e.g. "Surgical placement of implant body: endosteal implant"
  category: string;      // e.g. "Implant Services"
  subcategory?: string;
  nomenclature?: string;
}

export interface EobPosting {
  payerClaimNumber: string;
  serviceDate: Date;
  processedDate: Date;
  allowedAmount: number;
  paidAmount: number;
  patientPortion: number;
  adjustmentAmount?: number;
  adjustmentReason?: string;
  denialCode?: string;
  denialDescription?: string;
  remarksCode?: string;
}
