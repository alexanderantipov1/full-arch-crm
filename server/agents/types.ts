/**
 * full-arch-crm — AI Agent Shared Types
 * ──────────────────────────────────────
 * Canonical types for all AI agents in the full-arch-crm agent suite.
 * Agents NEVER import from adapter implementations directly — they use
 * these shared types alongside the canonical adapter types.
 *
 * Current agents:
 *   - TreatmentCoordinator — case acceptance scoring + follow-up drafting
 *   - CollectionsAgent     — risk scoring + payment plan automation
 */

// ─── Treatment Coordinator ────────────────────────────────────────────────────

/**
 * Scored snapshot of a single patient's treatment plan acceptance likelihood.
 * Calculated nightly by the TreatmentCoordinator agent.
 * Contains no PHI — only derived aggregate signals.
 */
export interface PatientScore {
  /** Canonical patient identifier */
  personUid: string;

  /** Internal treatment plan identifier */
  planId: string;

  /**
   * Composite acceptance likelihood score, 0–100.
   * Higher = more likely to accept treatment.
   * < 50 → high priority outreach
   * 50–69 → medium priority follow-up
   * 70+ → on track, low priority
   */
  score: number;

  /** Human-readable score breakdown for coordinator review */
  scoreBreakdown: ScoreBreakdown;

  /** ISO date string of the treatment plan creation */
  planCreatedAt: string;

  /**
   * Personalized follow-up message template.
   * Only generated when score < 70.
   * undefined for patients already on track.
   */
  followUp?: FollowUpDraft;
}

/**
 * Detailed breakdown of each factor contributing to the acceptance score.
 * Enables coordinators to understand WHY a patient scored low.
 */
export interface ScoreBreakdown {
  /** Base score from days since plan was created (0–30). Longer = lower. */
  recencyPoints: number;

  /** Score from insurance coverage percentage (0–25). Higher coverage = higher. */
  insurancePoints: number;

  /** Flat bonus for having a financing plan approved (+20 or 0). */
  financingPoints: number;

  /** Score from appointment attendance history (0–15). More kept = higher. */
  engagementPoints: number;

  /** Penalty for outstanding balance (0 to -20). High balance = lower score. */
  balancePenalty: number;

  /** Sum of all factors = final score, clamped to [0, 100]. */
  total: number;
}

/**
 * Personalized follow-up message template for patients scoring < 70.
 * Template variables use [PLACEHOLDER] format — fill before sending.
 */
export interface FollowUpDraft {
  subject: string;
  body: string;

  /** Recommended send timing — days from now */
  sendInDays: number;

  /** Which personalization variables were injected into the template */
  variablesUsed: string[];
}

/**
 * Summary report produced by a single nightly TreatmentCoordinator run.
 * Returned by runTreatmentCoordinator() and suitable for dashboard display,
 * Slack alerts, or scheduled job logging.
 */
export interface CoordinatorReport {
  /** Patients scoring < 50 — need immediate outreach today */
  highPriority: PatientScore[];

  /** Patients scoring 50–69 — need a follow-up this week */
  mediumPriority: PatientScore[];

  /** Patients scoring 70+ — on track, minimal intervention needed */
  lowPriority: PatientScore[];

  /** Total patients with pending treatment plans evaluated this run */
  totalPatients: number;

  /**
   * Mean acceptance likelihood score across all evaluated patients.
   * Rounded to one decimal place.
   */
  avgScore: number;

  /** ISO 8601 timestamp of when this report was generated */
  generatedAt: string;

  /** Tenant this report covers */
  tenantId: string;
}

// ─── Collections Agent ────────────────────────────────────────────────────────

/**
 * A single patient's collections risk snapshot, produced by the CollectionsAgent
 * nightly run. Contains no PHI — only derived aggregate signals.
 */
export interface CollectionsCase {
  /** Canonical patient identifier */
  patientId: string;

  /** Display name (first name + last initial) */
  patientName: string;

  /** Total outstanding patient balance in dollars */
  outstandingBalance: number;

  /** Number of calendar days the balance has been past due */
  daysPastDue: number;

  /** ISO date string of the most recent payment, if any */
  lastPaymentDate?: string;

  /** Dollar amount still pending from insurance (reduces net patient liability) */
  insurancePending: number;

  /** Net patient balance: outstandingBalance − insurancePending */
  netPatientBalance: number;

  /**
   * Collections risk score, 0–100. Higher = more at risk of non-payment.
   *
   * Scoring factors:
   *   - Days past due: 0d=0, 30d=20, 60d=40, 90d+=60 pts
   *   - Balance tier: <$1k=0, $1k-$5k=10, $5k-$15k=20, $15k+=30 pts
   *   - No insurance pending: +10 pts
   *   - No prior payment plan: +10 pts
   * Clamped to [0, 100].
   */
  riskScore: number;

  /**
   * Recommended next action based on riskScore and daysPastDue.
   *   - statement           riskScore < 30
   *   - call                riskScore 30–49
   *   - payment_plan        riskScore 50–69 AND balance > $500
   *   - collections_referral riskScore 70–89
   *   - write_off           riskScore >= 90 OR balance < $50
   */
  recommendedAction:
    | 'payment_plan'
    | 'statement'
    | 'call'
    | 'collections_referral'
    | 'write_off';
}

/**
 * A structured payment plan for a patient, generated by the CollectionsAgent
 * when recommendedAction === 'payment_plan'.
 */
export interface PaymentPlan {
  /** Canonical patient identifier */
  patientId: string;

  /** Total plan amount in dollars */
  totalAmount: number;

  /** Monthly installment, always a whole dollar (Math.ceil) */
  monthlyPayment: number;

  /** Plan length in months (12 for balances < $5k, 24 for $5k+) */
  termMonths: number;

  /** Interest rate — always 0 for in-house plans */
  interestRate: number;

  /** ISO date string of the first scheduled payment */
  firstPaymentDate: string;

  /** Financing source: in-house installment, CareCredit, or Lending Club */
  planType: 'in_house' | 'carecredit' | 'lending_club';
}

/**
 * Summary report produced by a single CollectionsAgent run.
 * Returned by runCollectionsAgent() and suitable for dashboard display,
 * Slack alerts, or scheduled job logging.
 */
export interface CollectionsReport {
  /** ISO date string of when this report was generated */
  runDate: string;

  /** Sum of all outstanding balances across all cases */
  totalOutstanding: number;

  /** Total number of past-due cases evaluated */
  totalCases: number;

  /** Count of cases per recommended action */
  byAction: Record<CollectionsCase['recommendedAction'], number>;

  /** Number of payment plans auto-generated this run */
  paymentPlansCreated: number;

  /**
   * Estimated total dollar recovery if all payment-plan cases proceed.
   * Equal to the sum of netPatientBalance for all payment_plan cases.
   */
  estimatedRecovery: number;

  /** Cases with riskScore >= 70 — require immediate attention */
  highRisk: CollectionsCase[];

  /** All evaluated cases, sorted by riskScore descending */
  cases: CollectionsCase[];
}
