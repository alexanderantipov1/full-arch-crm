/**
 * full-arch-crm — AI Agent Shared Types
 * ──────────────────────────────────────
 * Canonical types for all AI agents in the full-arch-crm agent suite.
 * Agents NEVER import from adapter implementations directly — they use
 * these shared types alongside the canonical adapter types.
 *
 * Current agents:
 *   - TreatmentCoordinator — case acceptance scoring + follow-up drafting
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
