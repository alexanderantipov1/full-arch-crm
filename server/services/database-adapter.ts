/**
 * full-arch-crm — DatabaseAdapter Interface
 *
 * This is the universal contract that any dental practice backend must implement
 * to connect to full-arch-crm. Think of full-arch-crm as the SaaS AI layer
 * (like Dentrix/Eaglesoft but AI-native) and each clinic's database as a plugin.
 *
 * Architecture:
 *   full-arch-crm  =  universal SaaS (owns AI Scribe, insurance calling, wiki, simulation)
 *   fusion_crm     =  Fusion Dental's implementation of this interface
 *   clinic-b-db    =  Another clinic's implementation (they build their own)
 *   clinic-c-db    =  Any clinic can plug in by implementing this interface
 *
 * The Karpathy wiki (WikiService) lives in full-arch-crm. It learns from ALL
 * connected clinics and feeds intelligence back to each via the adapter.
 *
 * Connection:
 *   const adapter = new FusionCrmAdapter(config);      // Fusion Dental
 *   const adapter = new SomethingElseAdapter(config);  // any other clinic
 *   // full-arch-crm doesn't care which — it only talks through this interface
 */

// ── Shared Types ───────────────────────────────────────────────────────────────

export interface PagedResult<T> {
  items: T[];
  total: number;
  cursor?: string | null;
}

export interface PatientListItem {
  personUid: string;
  displayName: string;       // "First L." — non-PHI
  ageBand: string;           // "35-44" — never exact DOB in list views
  insuranceType?: string;    // ppo | hmo | medicaid | medicare | self_pay
  lastVisitDate?: string;
  activeTreatmentPlan: boolean;
  scenarioTag?: string;
}

export interface PatientSnapshot {
  personUid: string;
  fullName: string;
  dob?: string;
  phone?: string;
  email?: string;
  address?: {
    line1?: string;
    city?: string;
    state?: string;
    zip?: string;
  };
  insurance?: InsuranceCoverage;
  emergencyContact?: { name?: string; phone?: string };
  phiAccessLogged: true;
  reason: string;
}

export interface TreatmentHistory {
  personUid: string;
  visits: Array<{
    visitDate: string;
    providerId?: string;
    procedures: Array<{
      cdtCode: string;
      description: string;
      fee?: number;
      status?: string;
    }>;
    clinicalNotesAvailable: boolean;
    noteId?: string;
  }>;
}

export interface AppointmentSlot {
  appointmentId: string;
  startTime: string;
  endTime: string;
  status: 'confirmed' | 'pending' | 'cancelled' | 'completed';
  personUid?: string;
  patientDisplay?: string;   // "First L." — non-PHI
  providerId?: string;
  providerName?: string;
  procedureCodes: string[];
  chair?: number;
  notes?: string;
  insuranceVerified: boolean;
}

export interface BookAppointmentInput {
  personUid: string;
  providerId: string;
  locationId: string;
  date: string;
  startTime: string;
  procedureCodes?: string[];
  notes?: string;
  insuranceVerified?: boolean;
}

export interface ClinicalNote {
  noteId: string;
  personUid: string;
  appointmentId?: string;
  providerId?: string;
  visitDate: string;
  noteType: string;
  subjective?: string;
  objective?: string;
  assessment?: string;
  plan?: string;
  aiGenerated: boolean;
  aiModel?: string;
  providerApproved: boolean;
  source?: string;
}

export interface SoapNote {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
}

export interface InsuranceCoverage {
  personUid: string;
  primaryPayer?: string;
  payerId?: string;
  memberId?: string;
  groupId?: string;
  planType?: string;
  copay?: number;
  deductibleAnnual?: number;
  deductibleRemaining?: number;
  maxAnnualBenefit?: number;
  benefitUsed?: number;
  inNetwork?: boolean;
  verifiedDate?: string;
}

export interface EligibilityResult {
  personUid: string;
  eligible: boolean;
  payerName?: string;
  planType?: string;
  copay?: number;
  deductibleRemaining?: number;
  benefitRemaining?: number;
  procedureCoverage: Record<string, { covered: boolean; estimatedBenefitPct: number }>;
  verificationId?: string;
  verifiedAt?: string;
  notes?: string;
}

export interface ClaimProcedure {
  cdtCode: string;
  description?: string;
  billedAmount: number;
  allowedAmount?: number;
  paidAmount?: number;
  status?: string;
  denialReason?: string;
}

export interface Claim {
  claimId: string;
  personUid: string;
  payerId?: string;
  payerName?: string;
  submissionDate?: string;
  procedures: ClaimProcedure[];
  totalBilled: number;
  totalPaid?: number;
  status: 'pending' | 'submitted' | 'paid' | 'denied' | 'appealed';
  eobDocumentUrl?: string;
  notes?: string;
}

export interface CreateClaimInput {
  personUid: string;
  payerId: string;
  appointmentId?: string;
  procedures: ClaimProcedure[];
  notes?: string;
}

export interface ClaimStatusUpdate {
  status: string;
  denialReason?: string;
  denialDate?: string;
  paidAmount?: number;
  eobNotes?: string;
  source?: string;
}

export interface AppealInput {
  appealDate: string;
  appealReason: string;
  letterText: string;
  supportingDocs?: string[];
  source?: string;
}

export interface AnonymizedPattern {
  source: string;
  patternType: string;
  payerType?: string;
  cdtCode?: string;
  approvalRate?: number;
  topApprovalDriver?: string;
  topDenialReason?: string;
  appealSuccessRate?: number;
  sampleCount: number;   // minimum 10 (k-anonymity)
  confidence: 'medium' | 'high';
  metadata?: Record<string, unknown>;
}

export interface IntelligenceQueryResult {
  category: string;
  patterns: Array<Record<string, unknown>>;
  confidence: 'low' | 'medium' | 'high';
  sourceCount: number;
}

export interface CDTCode {
  code: string;
  description: string;
  category?: string;
  requiresPreauth: boolean;
  avgFee?: number;
}

export interface AvailabilitySlot {
  date: string;
  providerId: string;
  startTime: string;
  endTime: string;
  chair?: number;
}

// ── DatabaseAdapter Interface ─────────────────────────────────────────────────

/**
 * The contract any dental clinic backend must implement to connect to full-arch-crm.
 *
 * Implementations:
 *   - FusionCrmAdapter  (Fusion Dental — uses fusion_crm REST API)
 *   - MockAdapter       (dev/test — uses local in-memory data)
 *   - [YourClinic]Adapter — any clinic can build their own
 *
 * All PHI-returning methods require a `reason` string for HIPAA audit logging.
 */
export interface DatabaseAdapter {
  /** Adapter identifier — used in logs and UI */
  readonly adapterId: string;

  /** True when running in mock mode (no real backend connected) */
  isMockMode(): boolean;

  // ── Patients ───────────────────────────────────────────────────────────────

  /** Paginated patient list — non-PHI fields only (display name + age band) */
  getPatients(cursor?: string, limit?: number): Promise<PagedResult<PatientListItem>>;

  /** Full PHI record — audit logged with reason */
  getPatient(personUid: string, reason: string): Promise<PatientSnapshot>;

  /** All visits, procedures, and CDT codes for a patient */
  getPatientTreatmentHistory(personUid: string): Promise<TreatmentHistory>;

  /** Search patients by name, phone, or email — returns non-PHI list items */
  searchPatients(query: string, limit?: number): Promise<PagedResult<PatientListItem>>;

  /** Create a new patient record */
  createPatient(data: Omit<PatientSnapshot, 'personUid' | 'phiAccessLogged' | 'reason'>): Promise<{ personUid: string }>;

  /** Update patient demographics */
  updatePatient(personUid: string, data: Partial<PatientSnapshot>): Promise<void>;

  // ── Appointments ───────────────────────────────────────────────────────────

  /** Day's schedule for a location */
  getAppointments(date: string, locationId?: string): Promise<AppointmentSlot[]>;

  /** Upcoming appointments for a patient */
  getUpcomingAppointments(personUid: string, limit?: number): Promise<AppointmentSlot[]>;

  /** Provider availability within a date range */
  getAvailability(providerId: string, dateFrom: string, dateTo: string): Promise<AvailabilitySlot[]>;

  /** Get single appointment by ID */
  getAppointment(appointmentId: string): Promise<AppointmentSlot | null>;

  /** Book a new appointment */
  bookAppointment(data: BookAppointmentInput): Promise<{ appointmentId: string }>;

  /** Update or reschedule an appointment */
  updateAppointment(appointmentId: string, data: Partial<BookAppointmentInput & { status: string }>): Promise<void>;

  /** Cancel an appointment */
  cancelAppointment(appointmentId: string): Promise<void>;

  // ── Clinical Notes ─────────────────────────────────────────────────────────

  /** List clinical notes for a patient — PHI, audit logged */
  getClinicalNotes(personUid: string, limit?: number): Promise<ClinicalNote[]>;

  /** Get a single clinical note — PHI, audit logged */
  getClinicalNote(noteId: string): Promise<ClinicalNote | null>;

  /**
   * AI Scribe saves a SOAP note here after transcription.
   * source should be 'full_arch_crm.ai_scribe'
   */
  saveScribeOutput(
    personUid: string,
    appointmentId: string,
    soap: SoapNote,
    cdtCodes: string[],
    options?: { aiModel?: string; providerId?: string }
  ): Promise<{ noteId: string }>;

  /** CDT code search — used by treatment plan builders */
  searchCdtCodes(query: string, limit?: number): Promise<CDTCode[]>;

  /** Get a single CDT code */
  getCdtCode(code: string): Promise<CDTCode | null>;

  // ── Insurance & Claims ─────────────────────────────────────────────────────

  /** Patient insurance coverage details — PHI, audit logged */
  getInsurance(personUid: string): Promise<InsuranceCoverage | null>;

  /** Trigger live real-time eligibility verification */
  checkEligibility(personUid: string, procedureCodes: string[], appointmentDate?: string): Promise<EligibilityResult>;

  /** List claims for a patient, optionally filtered by status */
  getClaims(personUid: string, status?: string): Promise<Claim[]>;

  /** Get a single claim by ID */
  getClaim(claimId: string): Promise<Claim | null>;

  /** EOB batch for RCM — called daily by eob-service.ts */
  getEobs(dateFrom: string, dateTo: string): Promise<Claim[]>;

  /** Submit a new insurance claim */
  createClaim(data: CreateClaimInput): Promise<{ claimId: string }>;

  /**
   * Update claim status — EOB posting.
   * Called by server/rcm/eob-service.ts after processing remittance.
   */
  updateClaimStatus(claimId: string, update: ClaimStatusUpdate): Promise<void>;

  /** File an insurance appeal with a generated letter */
  fileAppeal(claimId: string, data: AppealInput): Promise<{ appealId: string }>;

  // ── Intelligence (Wiki Feedback Loop) ──────────────────────────────────────

  /**
   * Push anonymized intelligence patterns from the wiki back to the clinic's DB.
   * The clinic's local agents (InsuranceCallAgent etc.) use these patterns
   * without needing to call back to full-arch-crm on every decision.
   * All patterns must meet k-anonymity threshold (sampleCount >= 10).
   */
  pushIntelligence(patterns: AnonymizedPattern[]): Promise<{ accepted: number; rejected: number }>;

  /**
   * Pull raw intelligence patterns from this clinic's DB.
   * Used by WikiService to bootstrap or fill gaps in network intelligence.
   */
  queryIntelligence(category: string, cdtCode?: string, payerType?: string): Promise<IntelligenceQueryResult>;
}

// ── Error types ────────────────────────────────────────────────────────────────

export class DatabaseAdapterError extends Error {
  constructor(
    public readonly adapterId: string,
    public readonly statusCode: number,
    message: string,
    public readonly detail?: unknown,
  ) {
    super(`[${adapterId}] ${message}`);
    this.name = 'DatabaseAdapterError';
  }
}

export class AdapterAuthError extends DatabaseAdapterError {
  constructor(adapterId: string, detail?: unknown) {
    super(adapterId, 401, 'Authentication failed — check API key and tenant ID', detail);
    this.name = 'AdapterAuthError';
  }
}

export class AdapterNotFoundError extends DatabaseAdapterError {
  constructor(adapterId: string, resource: string, id: string) {
    super(adapterId, 404, `${resource} not found: ${id}`);
    this.name = 'AdapterNotFoundError';
  }
}

export class AdapterUnavailableError extends DatabaseAdapterError {
  constructor(adapterId: string, detail?: unknown) {
    super(adapterId, 503, 'Backend unavailable', detail);
    this.name = 'AdapterUnavailableError';
  }
}
