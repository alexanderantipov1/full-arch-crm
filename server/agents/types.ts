/**
 * full-arch-crm — AI Agent Shared Types
 * ──────────────────────────────────────
 * Canonical types for all AI agents in the full-arch-crm agent suite.
 *
 * Current agents:
 *   - TreatmentCoordinator — case acceptance scoring + follow-up drafting
 *   - CollectionsAgent     — risk scoring + payment plan automation
 *   - SchedulingAgent      — AI-optimized appointment booking + utilization
 */

// ─── Treatment Coordinator ────────────────────────────────────────────────────

export interface PatientScore {
  personUid: string;
  planId: string;
  score: number;
  scoreBreakdown: ScoreBreakdown;
  planCreatedAt: string;
  followUp?: FollowUpDraft;
}

export interface ScoreBreakdown {
  recencyPoints: number;
  insurancePoints: number;
  financingPoints: number;
  engagementPoints: number;
  balancePenalty: number;
  total: number;
}

export interface FollowUpDraft {
  subject: string;
  body: string;
  sendInDays: number;
  variablesUsed: string[];
}

export interface CoordinatorReport {
  highPriority: PatientScore[];
  mediumPriority: PatientScore[];
  lowPriority: PatientScore[];
  totalPatients: number;
  avgScore: number;
  generatedAt: string;
  tenantId: string;
}

// ─── Collections Agent ────────────────────────────────────────────────────────

export interface CollectionsCase {
  patientId: string;
  patientName: string;
  outstandingBalance: number;
  daysPastDue: number;
  lastPaymentDate?: string;
  insurancePending: number;
  netPatientBalance: number;
  riskScore: number;
  recommendedAction:
    | 'payment_plan'
    | 'statement'
    | 'call'
    | 'collections_referral'
    | 'write_off';
}

export interface PaymentPlan {
  patientId: string;
  totalAmount: number;
  monthlyPayment: number;
  termMonths: number;
  interestRate: number;
  firstPaymentDate: string;
  planType: 'in_house' | 'carecredit' | 'lending_club';
}

export interface CollectionsReport {
  runDate: string;
  totalOutstanding: number;
  totalCases: number;
  byAction: Record<CollectionsCase['recommendedAction'], number>;
  paymentPlansCreated: number;
  estimatedRecovery: number;
  highRisk: CollectionsCase[];
  cases: CollectionsCase[];
}

// ─── Scheduling Agent ─────────────────────────────────────────────────────────

export interface TimeSlot {
  date: string;
  startTime: string;
  endTime: string;
  chairId: string;
  providerId: string;
  durationMinutes: number;
  slotType: 'consult' | 'surgery' | 'followup' | 'restoration';
  available: boolean;
}

export interface BookingRecommendation {
  patientId: string;
  appointmentType: string;
  recommendedSlots: TimeSlot[];
  urgencyScore: number;
  notes: string;
}

export interface SchedulingReport {
  runDate: string;
  locationId: string;
  utilizationRate: number;
  recommendedBookings: BookingRecommendation[];
  openSlots: TimeSlot[];
  bottlenecks: string[];
}

// ─── Fraud Detection Agent ────────────────────────────────────────────────────

export type FraudRuleId =
  | 'duplicate_claim'
  | 'unbundled_procedure'
  | 'upcoding'
  | 'frequency_exceeded'
  | 'missing_documentation'
  | 'impossible_day'
  | 'phantom_patient';

export interface FraudFlag {
  flagId: string;              // UUID v4
  ruleId: FraudRuleId;
  severity: 'low' | 'medium' | 'high' | 'critical';
  patientId?: string;
  claimId?: string;
  procedureCodes?: string[];
  description: string;         // human-readable explanation
  evidence: string[];          // list of specific data points that triggered the flag
  recommendedAction: string;
  detectedAt: string;          // ISO timestamp
  status: 'open' | 'reviewed' | 'dismissed' | 'escalated';
}

export interface FraudReport {
  runDate: string;
  totalClaimsReviewed: number;
  totalFlagsRaised: number;
  byRule: Record<FraudRuleId, number>;
  bySeverity: Record<FraudFlag['severity'], number>;
  criticalFlags: FraudFlag[];
  allFlags: FraudFlag[];
  estimatedExposure: number;   // dollar amount at risk
}
