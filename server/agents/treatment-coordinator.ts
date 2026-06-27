/**
 * full-arch-crm — AI Treatment Coordinator Agent
 * ────────────────────────────────────────────────
 * Nightly agent that scores case acceptance likelihood for every patient
 * with a pending treatment plan, then drafts personalized follow-up messages
 * for patients unlikely to proceed without intervention.
 *
 * Responsibilities:
 *   1. Fetch all patients with pending treatment plans from the adapter
 *   2. Score each patient (0–100) using five weighted signals
 *   3. Draft follow-up messages for patients scoring < 70
 *   4. Return a CoordinatorReport bucketing patients into priority tiers
 *   5. Ingest a learning event into the Karpathy wiki
 *   6. Append one line to the HIPAA-adjacent audit log
 *
 * Usage:
 *   import { runTreatmentCoordinator } from "./treatment-coordinator";
 *   const report = await runTreatmentCoordinator("tenant-uuid-here");
 *
 * HIPAA note: All data flowing through this agent is handled under
 * purpose "treatment". No PHI is written to the wiki or audit log —
 * only aggregate, anonymized signals.
 */

import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";
import { adapterRegistry } from "../adapters/registry";
import { wikiService } from "../simulation/wiki/wiki-service";
import type { PhiAccessContext } from "../adapters/types";
import type {
  CoordinatorReport,
  PatientScore,
  ScoreBreakdown,
  FollowUpDraft,
} from "./types";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUDIT_LOG_PATH = path.join(__dirname, "../audit/treatment-coordinator.log");

// ─── Scoring constants ────────────────────────────────────────────────────────

/** Maximum points available from each scoring factor */
const SCORING_WEIGHTS = {
  /** Recency: 0–30 points. Score decays linearly over 90 days. */
  RECENCY_MAX: 30,
  /** Insurance: 0–25 points. Scales with coverage percentage. */
  INSURANCE_MAX: 25,
  /** Financing: flat +20 if an approved plan exists, else 0. */
  FINANCING_BONUS: 20,
  /** Engagement: 0–15 points. 3 pts per kept appointment, capped at 5 appts. */
  ENGAGEMENT_PER_APPT: 3,
  ENGAGEMENT_MAX_APPTS: 5,
  /** Balance penalty: 0 to –20. Scales linearly up to $5 000 outstanding. */
  BALANCE_MAX_PENALTY: 20,
  BALANCE_PENALTY_THRESHOLD: 5000,
} as const;

// ─── PHI Access Context ───────────────────────────────────────────────────────

function buildPhiContext(tenantId: string): PhiAccessContext {
  return {
    purpose: "treatment",
    requestedBy: "TreatmentCoordinatorAgent",
    tenantId,
    reason: "Nightly case acceptance scoring for treatment coordinator outreach",
    traceId: `tc-nightly-${Date.now()}`,
  };
}

// ─── Scoring logic ────────────────────────────────────────────────────────────

/**
 * Calculate how many days have elapsed since a Date or ISO string.
 */
function daysSince(date: Date | string): number {
  const then = typeof date === "string" ? new Date(date) : date;
  const diffMs = Date.now() - then.getTime();
  return Math.max(0, Math.floor(diffMs / (1000 * 60 * 60 * 24)));
}

/**
 * Recency score: full 30 points on day 0, decays linearly to 0 at day 90+.
 */
function recencyScore(planCreatedAt: Date): number {
  const days = daysSince(planCreatedAt);
  const fraction = Math.max(0, 1 - days / 90);
  return Math.round(SCORING_WEIGHTS.RECENCY_MAX * fraction);
}

/**
 * Insurance score: scales linearly with coverage percentage.
 * 0% coverage → 0 pts; 100% coverage → 25 pts.
 */
function insuranceScore(coveragePct: number): number {
  const clamped = Math.max(0, Math.min(100, coveragePct));
  return Math.round(SCORING_WEIGHTS.INSURANCE_MAX * (clamped / 100));
}

/**
 * Financing bonus: +20 if the patient has an approved financing plan.
 */
function financingScore(hasApprovedPlan: boolean): number {
  return hasApprovedPlan ? SCORING_WEIGHTS.FINANCING_BONUS : 0;
}

/**
 * Engagement score: 3 points per kept appointment, capped at 5 appointments.
 * "Kept" = status is "completed" or "checked_in".
 */
function engagementScore(keptAppointments: number): number {
  const capped = Math.min(keptAppointments, SCORING_WEIGHTS.ENGAGEMENT_MAX_APPTS);
  return capped * SCORING_WEIGHTS.ENGAGEMENT_PER_APPT;
}

/**
 * Balance penalty: 0 at $0 outstanding, –20 at $5 000+.
 * Scales linearly between those bounds.
 */
function balancePenalty(outstandingBalance: number): number {
  const clamped = Math.max(0, Math.min(outstandingBalance, SCORING_WEIGHTS.BALANCE_PENALTY_THRESHOLD));
  const fraction = clamped / SCORING_WEIGHTS.BALANCE_PENALTY_THRESHOLD;
  return -Math.round(SCORING_WEIGHTS.BALANCE_MAX_PENALTY * fraction);
}

/**
 * Compose all signals into a final ScoreBreakdown.
 * Final score is clamped to [0, 100].
 */
function buildScoreBreakdown(params: {
  planCreatedAt: Date;
  coveragePct: number;
  hasApprovedFinancing: boolean;
  keptAppointments: number;
  outstandingBalance: number;
}): ScoreBreakdown {
  const recencyPoints = recencyScore(params.planCreatedAt);
  const insurancePoints = insuranceScore(params.coveragePct);
  const financingPoints = financingScore(params.hasApprovedFinancing);
  const engagementPoints = engagementScore(params.keptAppointments);
  const bp = balancePenalty(params.outstandingBalance);

  const raw = recencyPoints + insurancePoints + financingPoints + engagementPoints + bp;
  const total = Math.max(0, Math.min(100, raw));

  return {
    recencyPoints,
    insurancePoints,
    financingPoints,
    engagementPoints,
    balancePenalty: bp,
    total,
  };
}

// ─── Follow-up drafting ───────────────────────────────────────────────────────

/**
 * Clinic configuration injected from environment variables.
 * Falls back to placeholder values when env vars are not set.
 */
interface ClinicConfig {
  name: string;
  phone: string;
  coordinatorName: string;
}

function getClinicConfig(): ClinicConfig {
  return {
    name: process.env.CLINIC_NAME ?? "[CLINIC_NAME]",
    phone: process.env.CLINIC_PHONE ?? "[CLINIC_PHONE]",
    coordinatorName: process.env.COORDINATOR_NAME ?? "[COORDINATOR_NAME]",
  };
}

/**
 * Build a personalized follow-up message for a patient whose score < 70.
 *
 * Template variables are filled from what is known at scoring time.
 * PHI-derived variables (first name, plan date) are included because this
 * template is rendered inside the clinic's own system — it never leaves
 * the tenant context.
 */
function draftFollowUp(params: {
  firstName: string;
  planCreatedAt: Date;
  coveragePct: number;
  hasApprovedFinancing: boolean;
  monthlyPayment: number | undefined;
  score: number;
}): FollowUpDraft {
  const clinic = getClinicConfig();
  const planDate = params.planCreatedAt.toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  const variablesUsed: string[] = ["PATIENT_FIRST_NAME", "PLAN_DATE", "CLINIC_NAME", "CLINIC_PHONE", "COORDINATOR_NAME"];

  // Build conditional paragraphs
  let financingLine = "";
  if (params.hasApprovedFinancing) {
    const monthlyStr =
      params.monthlyPayment !== undefined
        ? `$${params.monthlyPayment.toFixed(0)}/month`
        : "affordable monthly payments";
    financingLine = `We have flexible payment options starting at ${monthlyStr} to help make your treatment more accessible.`;
    variablesUsed.push("MONTHLY_PAYMENT");
  }

  let insuranceLine = "";
  if (params.coveragePct > 0) {
    insuranceLine = `Your insurance covers ${params.coveragePct}% of your treatment, which significantly reduces your out-of-pocket cost.`;
    variablesUsed.push("COVERAGE_PCT");
  }

  const middleBlock = [financingLine, insuranceLine].filter(Boolean).join("\n\n");

  const body = `Hi ${params.firstName},

We wanted to follow up on your treatment plan from ${planDate}. Your care team has reserved time for you and we want to make sure you have everything you need to move forward.
${middleBlock ? "\n" + middleBlock + "\n" : ""}
Ready to take the next step? Call us at ${clinic.phone} or simply reply to this message to schedule your next appointment.

Warm regards,
${clinic.coordinatorName}
${clinic.name}`;

  // Send sooner for the lowest-scoring patients
  const sendInDays = params.score < 30 ? 1 : params.score < 50 ? 3 : 7;

  return {
    subject: `Your All-on-4 Treatment Plan — ${clinic.name}`,
    body,
    sendInDays,
    variablesUsed,
  };
}

// ─── Main nightly runner ──────────────────────────────────────────────────────

/**
 * Primary entry point for the Treatment Coordinator nightly job.
 *
 * Fetches all patients with pending treatment plans for the given tenant,
 * scores each one, generates follow-up drafts for those unlikely to proceed,
 * and returns a fully populated CoordinatorReport.
 *
 * Side effects:
 *   - Calls wikiService.ingest() with AGENT_LEARNING data (fire-and-forget)
 *   - Appends one line to server/audit/treatment-coordinator.log
 *
 * @param tenantId  The canonical tenant UUID. Must be registered in adapterRegistry.
 * @returns         A CoordinatorReport with all priority buckets populated.
 */
export async function runTreatmentCoordinator(
  tenantId: string,
): Promise<CoordinatorReport> {
  const adapter = adapterRegistry.getAdapter(tenantId);
  const phiCtx = buildPhiContext(tenantId);

  // ── 1. Fetch all patients ─────────────────────────────────────────────────
  //
  // We page through all patients and then filter to those with pending plans.
  // A production implementation could push this filter down to the adapter,
  // but the canonical listPatients API doesn't support plan-status filtering,
  // so we do a two-step fetch: list non-PHI summaries, then hydrate plans.

  const pageSize = 200;
  let cursor: string | undefined;
  const allPersonUids: string[] = [];

  do {
    const page = await adapter.listPatients({ limit: pageSize, cursor });
    allPersonUids.push(...page.items.map((p) => p.personUid));
    cursor = page.nextCursor;
  } while (cursor);

  // ── 2. Score each patient with a pending treatment plan ───────────────────

  const patientScores: PatientScore[] = [];

  await Promise.all(
    allPersonUids.map(async (personUid) => {
      try {
        // Fetch treatment plans — filter to pending statuses in-memory
        const plans = await adapter.getTreatmentPlans(personUid, phiCtx);
        const pendingPlans = plans.filter(
          (p) => p.status === "presented" || p.status === "draft",
        );
        if (pendingPlans.length === 0) return;

        // Use the most recently created pending plan for scoring
        const plan = pendingPlans.sort(
          (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
        )[0];

        // Fetch supporting data in parallel (insurance, financing, appointments)
        const [insuranceRecords, financingPlans, appointments, patient] =
          await Promise.all([
            adapter.getInsurance(personUid, phiCtx).catch(() => []),
            adapter.getFinancingPlans(personUid, phiCtx).catch(() => []),
            adapter.listAppointments({ personUid }).catch(() => []),
            adapter.getPatient(personUid, phiCtx).catch(() => null),
          ]);

        // Derive scoring inputs ──────────────────────────────────────────────

        // Coverage: use primary insurance coverage percentage, or 0 if none
        const primaryInsurance = insuranceRecords.find(
          (i) => i.insuranceType === "primary",
        );
        const coveragePct = primaryInsurance?.coveragePercentage ?? 0;

        // Financing: does an approved plan exist?
        const approvedFinancing = financingPlans.find(
          (f) => f.applicationStatus === "approved",
        );
        const hasApprovedFinancing = Boolean(approvedFinancing);

        // Engagement: count kept appointments (completed or checked_in)
        const keptAppointments = appointments.filter(
          (a) => a.status === "completed" || a.status === "checked_in",
        ).length;

        // Outstanding balance: patient responsibility on the active plan
        const outstandingBalance = plan.patientResponsibility;

        // Build score ──────────────────────────────────────────────────────
        const breakdown = buildScoreBreakdown({
          planCreatedAt: plan.createdAt,
          coveragePct,
          hasApprovedFinancing,
          keptAppointments,
          outstandingBalance,
        });

        // Draft follow-up for patients unlikely to proceed ─────────────────
        let followUp: FollowUpDraft | undefined;
        if (breakdown.total < 70) {
          followUp = draftFollowUp({
            firstName: patient?.firstName ?? "there",
            planCreatedAt: plan.createdAt,
            coveragePct,
            hasApprovedFinancing,
            monthlyPayment: approvedFinancing?.monthlyPayment ?? undefined,
            score: breakdown.total,
          });
        }

        patientScores.push({
          personUid,
          planId: plan.planId,
          score: breakdown.total,
          scoreBreakdown: breakdown,
          planCreatedAt: plan.createdAt.toISOString(),
          followUp,
        });
      } catch (err) {
        // Log and continue — one bad patient record should not halt the run
        console.warn(
          `[TreatmentCoordinator] Skipping patient ${personUid}: ${String(err)}`,
        );
      }
    }),
  );

  // ── 3. Bucket patients by priority ───────────────────────────────────────

  const highPriority = patientScores.filter((p) => p.score < 50);
  const mediumPriority = patientScores.filter(
    (p) => p.score >= 50 && p.score < 70,
  );
  const lowPriority = patientScores.filter((p) => p.score >= 70);

  const totalPatients = patientScores.length;
  const avgScore =
    totalPatients > 0
      ? Math.round(
          (patientScores.reduce((sum, p) => sum + p.score, 0) / totalPatients) * 10,
        ) / 10
      : 0;

  const generatedAt = new Date().toISOString();

  const report: CoordinatorReport = {
    highPriority,
    mediumPriority,
    lowPriority,
    totalPatients,
    avgScore,
    generatedAt,
    tenantId,
  };

  // ── 4. Wiki ingest (fire-and-forget) ─────────────────────────────────────
  //
  // We use orchestration_cycle type because it maps to the agents/ wiki
  // category, which is exactly where TreatmentCoordinator learnings belong.
  // The agentName field determines the target wiki page.

  void wikiService
    .ingest({
      type: "orchestration_cycle",
      sourceId: `tc-nightly-${tenantId}-${generatedAt}`,
      agentName: "TreatmentCoordinator",
      score: avgScore,
    })
    .catch((err: Error) =>
      console.warn(
        "[TreatmentCoordinator] Wiki ingest error:",
        err.message,
      ),
    );

  // ── 5. Audit log ─────────────────────────────────────────────────────────

  const auditLine =
    `[${generatedAt}] [${tenantId}] TreatmentCoordinator: ` +
    `${totalPatients} patients scored, ${highPriority.length} high-priority\n`;

  try {
    const auditDir = path.dirname(AUDIT_LOG_PATH);
    if (!fs.existsSync(auditDir)) {
      fs.mkdirSync(auditDir, { recursive: true });
    }
    fs.appendFileSync(AUDIT_LOG_PATH, auditLine, "utf-8");
  } catch (err) {
    console.error("[TreatmentCoordinator] Audit log write failed:", String(err));
  }

  return report;
}
