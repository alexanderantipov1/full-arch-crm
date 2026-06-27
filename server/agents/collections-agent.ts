/**
 * full-arch-crm — CollectionsAgent
 * ──────────────────────────────────
 * Nightly agent that evaluates every patient with a past-due balance, assigns
 * a collections risk score, recommends the appropriate next action, and
 * auto-generates payment plans for qualifying cases.
 *
 * Responsibilities:
 *   1. Fetch all patients with active/completed treatment plans from the adapter
 *   2. Derive outstanding balance, days past due, and insurance pending from plan data
 *   3. Score each case (0–100) using four weighted signals
 *   4. Recommend an action (statement / call / payment_plan / collections_referral / write_off)
 *   5. Auto-create PaymentPlan objects for payment_plan cases and draft follow-up messages
 *   6. Return a CollectionsReport with all cases, action buckets, and high-risk list
 *   7. Ingest a learning event into the Karpathy wiki
 *   8. Append one line to the HIPAA-adjacent audit log
 *
 * Usage:
 *   import { runCollectionsAgent } from "./collections-agent";
 *   const report = await runCollectionsAgent("tenant-uuid-here");
 *
 * HIPAA note: No PHI is written to the wiki or audit log — only aggregate,
 * anonymized signals. Follow-up messages are rendered inside the tenant context
 * and never leave it.
 */

import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";
import { adapterRegistry } from "../adapters/registry";
import { wikiService } from "../simulation/wiki/wiki-service";
import type { PhiAccessContext } from "../adapters/types";
import type {
  CollectionsCase,
  CollectionsReport,
  PaymentPlan,
} from "./types";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUDIT_LOG_PATH = path.join(__dirname, "../audit/collections-agent.log");

// ─── PHI Access Context ───────────────────────────────────────────────────────

function buildPhiContext(tenantId: string): PhiAccessContext {
  return {
    purpose: "payment",
    requestedBy: "CollectionsAgent",
    tenantId,
    reason: "Nightly collections risk scoring and payment plan generation",
    traceId: `col-nightly-${Date.now()}`,
  };
}

// ─── Clinic config ────────────────────────────────────────────────────────────

interface ClinicConfig {
  name: string;
  phone: string;
}

function getClinicConfig(): ClinicConfig {
  return {
    name: process.env.CLINIC_NAME ?? "[CLINIC_NAME]",
    phone: process.env.CLINIC_PHONE ?? "[CLINIC_PHONE]",
  };
}

// ─── Risk scoring ─────────────────────────────────────────────────────────────

/**
 * Score contribution from days past due.
 *   0 days  →  0 pts
 *  30 days  → 20 pts
 *  60 days  → 40 pts
 *  90+ days → 60 pts (capped)
 */
function daysPastDuePoints(days: number): number {
  if (days <= 0) return 0;
  if (days < 30) return Math.round((days / 30) * 20);
  if (days < 60) return 20 + Math.round(((days - 30) / 30) * 20);
  if (days < 90) return 40 + Math.round(((days - 60) / 30) * 20);
  return 60;
}

/**
 * Score contribution from outstanding balance tier.
 *   < $1 000  →  0 pts
 *   $1k–$5k   → 10 pts
 *   $5k–$15k  → 20 pts
 *   $15k+     → 30 pts
 */
function balanceTierPoints(balance: number): number {
  if (balance < 1_000) return 0;
  if (balance < 5_000) return 10;
  if (balance < 15_000) return 20;
  return 30;
}

/**
 * Compute the composite risk score for a single collections case.
 * Clamped to [0, 100].
 */
function computeRiskScore(params: {
  daysPastDue: number;
  outstandingBalance: number;
  hasInsurancePending: boolean;
  hasPriorPaymentPlan: boolean;
}): number {
  let score = 0;
  score += daysPastDuePoints(params.daysPastDue);
  score += balanceTierPoints(params.outstandingBalance);
  if (!params.hasInsurancePending) score += 10;
  if (!params.hasPriorPaymentPlan) score += 10;
  return Math.max(0, Math.min(100, score));
}

// ─── Recommended action ───────────────────────────────────────────────────────

/**
 * Derive the recommended collections action from risk score and balance.
 * Returns null when daysPastDue === 0 (skip the case entirely).
 */
function recommendAction(params: {
  riskScore: number;
  daysPastDue: number;
  netPatientBalance: number;
}): CollectionsCase["recommendedAction"] | null {
  const { riskScore, daysPastDue, netPatientBalance } = params;

  // Skip current balances entirely
  if (daysPastDue === 0) return null;

  if (riskScore >= 90 || netPatientBalance < 50) return "write_off";
  if (riskScore >= 70) return "collections_referral";
  if (riskScore >= 50 && netPatientBalance > 500) return "payment_plan";
  if (riskScore >= 30) return "call";
  return "statement";
}

// ─── Payment plan creation ────────────────────────────────────────────────────

/**
 * Auto-generate an in-house, 0%-interest payment plan for a qualifying case.
 *   - Balances < $5 000: 12-month term
 *   - Balances >= $5 000: 24-month term
 * Monthly payment is Math.ceil(balance / termMonths).
 */
function createPaymentPlan(patientId: string, balance: number): PaymentPlan {
  const termMonths = balance < 5_000 ? 12 : 24;
  const monthlyPayment = Math.ceil(balance / termMonths);

  // First payment is on the 1st of next month
  const now = new Date();
  const firstPayment = new Date(now.getFullYear(), now.getMonth() + 1, 1);

  return {
    patientId,
    totalAmount: balance,
    monthlyPayment,
    termMonths,
    interestRate: 0,
    firstPaymentDate: firstPayment.toISOString().split("T")[0],
    planType: "in_house",
  };
}

/**
 * Draft a personalised payment-plan follow-up message for the patient.
 */
function draftPaymentPlanMessage(params: {
  firstName: string;
  balance: number;
  plan: PaymentPlan;
}): string {
  const clinic = getClinicConfig();
  const { firstName, balance, plan } = params;
  const balanceFormatted = balance.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
  const monthlyFormatted = `$${plan.monthlyPayment}`;

  return (
    `Subject: Payment Plan Available — ${clinic.name}\n\n` +
    `Hi ${firstName}, we'd like to help you manage your balance of ${balanceFormatted}.\n` +
    `We can set up a payment plan of ${monthlyFormatted}/month for ${plan.termMonths} months at 0% interest.\n` +
    `Call us at ${clinic.phone} or reply to get started.`
  );
}

// ─── Main nightly runner ──────────────────────────────────────────────────────

/**
 * Primary entry point for the Collections nightly job.
 *
 * Fetches all patients with active or completed treatment plans for the given
 * tenant, evaluates each for past-due balances, scores the collections risk,
 * auto-creates payment plans for qualifying cases, and returns a fully
 * populated CollectionsReport.
 *
 * Side effects:
 *   - Calls wikiService.ingest() with orchestration_cycle data (fire-and-forget)
 *   - Appends one line to server/audit/collections-agent.log
 *
 * @param tenantId  The canonical tenant UUID. Must be registered in adapterRegistry.
 * @returns         A CollectionsReport with all cases and action buckets.
 */
export async function runCollectionsAgent(
  tenantId: string,
): Promise<CollectionsReport> {
  const adapter = adapterRegistry.getAdapter(tenantId);
  const phiCtx = buildPhiContext(tenantId);

  // ── 1. Fetch all patient UIDs ─────────────────────────────────────────────

  const pageSize = 200;
  let cursor: string | undefined;
  const allPersonUids: string[] = [];

  do {
    const page = await adapter.listPatients({ limit: pageSize, cursor });
    allPersonUids.push(...page.items.map((p) => p.personUid));
    cursor = page.nextCursor;
  } while (cursor);

  // ── 2. Evaluate each patient for past-due balances ────────────────────────

  const cases: CollectionsCase[] = [];
  const paymentPlans: PaymentPlan[] = [];
  const followUpMessages: Array<{ patientId: string; message: string }> = [];

  await Promise.all(
    allPersonUids.map(async (personUid) => {
      try {
        // Fetch treatment plans — only active/completed carry real balances
        const plans = await adapter.getTreatmentPlans(personUid, phiCtx);
        const billedPlans = plans.filter(
          (p) => p.status === "active" || p.status === "completed",
        );
        if (billedPlans.length === 0) return;

        // Fetch supporting data in parallel
        const [financingPlans, patient] = await Promise.all([
          adapter.getFinancingPlans(personUid, phiCtx).catch(() => []),
          adapter.getPatient(personUid, phiCtx).catch(() => null),
        ]);

        // Derive aggregate balances across all billed plans
        const outstandingBalance = billedPlans.reduce(
          (sum, p) => sum + p.patientResponsibility,
          0,
        );
        if (outstandingBalance <= 0) return;

        // Insurance pending: sum of insuranceCoverage on active plans
        // (portion not yet collected from insurer)
        const insurancePending = billedPlans
          .filter((p) => p.status === "active")
          .reduce((sum, p) => sum + (p.insuranceCoverage ?? 0), 0);

        const netPatientBalance = Math.max(
          0,
          outstandingBalance - insurancePending,
        );

        // Days past due: use most recent plan's updatedAt as the due-date proxy.
        // In a production system this would come from a dedicated A/R aging report.
        const mostRecentPlan = billedPlans.sort(
          (a, b) =>
            new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
        )[0];
        const planAgeMs =
          Date.now() - new Date(mostRecentPlan.updatedAt).getTime();
        const daysPastDue = Math.max(
          0,
          Math.floor(planAgeMs / (1000 * 60 * 60 * 24)),
        );

        // Prior payment plan: any approved in-house/external financing
        const hasPriorPaymentPlan = financingPlans.some(
          (f) => f.applicationStatus === "approved",
        );
        const lastPaymentDate = financingPlans
          .filter((f) => f.approvalDate)
          .sort(
            (a, b) =>
              new Date(b.approvalDate!).getTime() -
              new Date(a.approvalDate!).getTime(),
          )[0]
          ?.approvalDate?.toISOString()
          .split("T")[0];

        // ── Risk score ──────────────────────────────────────────────────────

        const riskScore = computeRiskScore({
          daysPastDue,
          outstandingBalance: netPatientBalance,
          hasInsurancePending: insurancePending > 0,
          hasPriorPaymentPlan,
        });

        // ── Recommended action ──────────────────────────────────────────────

        const action = recommendAction({
          riskScore,
          daysPastDue,
          netPatientBalance,
        });

        // Skip current-balance (0 days past due) patients
        if (action === null) return;

        const patientName = patient
          ? `${patient.firstName} ${patient.lastName.charAt(0)}.`
          : "Unknown Patient";

        const collectionsCase: CollectionsCase = {
          patientId: personUid,
          patientName,
          outstandingBalance,
          daysPastDue,
          lastPaymentDate,
          insurancePending,
          netPatientBalance,
          riskScore,
          recommendedAction: action,
        };

        cases.push(collectionsCase);

        // ── Payment plan auto-creation ──────────────────────────────────────

        if (action === "payment_plan") {
          const plan = createPaymentPlan(personUid, netPatientBalance);
          paymentPlans.push(plan);

          const firstName = patient?.firstName ?? "there";
          const message = draftPaymentPlanMessage({
            firstName,
            balance: netPatientBalance,
            plan,
          });
          followUpMessages.push({ patientId: personUid, message });
        }
      } catch (err) {
        console.warn(
          `[CollectionsAgent] Skipping patient ${personUid}: ${String(err)}`,
        );
      }
    }),
  );

  // ── 3. Aggregate report ───────────────────────────────────────────────────

  // Sort cases by risk score descending
  cases.sort((a, b) => b.riskScore - a.riskScore);

  const totalOutstanding = cases.reduce(
    (sum, c) => sum + c.netPatientBalance,
    0,
  );

  const byAction: CollectionsReport["byAction"] = {
    statement: 0,
    call: 0,
    payment_plan: 0,
    collections_referral: 0,
    write_off: 0,
  };
  for (const c of cases) {
    byAction[c.recommendedAction]++;
  }

  const estimatedRecovery = cases
    .filter((c) => c.recommendedAction === "payment_plan")
    .reduce((sum, c) => sum + c.netPatientBalance, 0);

  const highRisk = cases.filter((c) => c.riskScore >= 70);

  const runDate = new Date().toISOString();

  const report: CollectionsReport = {
    runDate,
    totalOutstanding,
    totalCases: cases.length,
    byAction,
    paymentPlansCreated: paymentPlans.length,
    estimatedRecovery,
    highRisk,
    cases,
  };

  // ── 4. Wiki ingest (fire-and-forget) ─────────────────────────────────────

  void wikiService
    .ingest({
      type: "orchestration_cycle",
      sourceId: `col-nightly-${tenantId}-${runDate}`,
      agentName: "CollectionsAgent",
      score: cases.length > 0 ? Math.round(totalOutstanding / cases.length) : 0,
    })
    .catch((err: Error) =>
      console.warn("[CollectionsAgent] Wiki ingest error:", err.message),
    );

  // ── 5. Audit log ─────────────────────────────────────────────────────────

  const totalStr = totalOutstanding.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
  const auditLine =
    `[${runDate}] [${tenantId}] CollectionsAgent: ` +
    `${cases.length} cases, ${totalStr} total outstanding\n`;

  try {
    const auditDir = path.dirname(AUDIT_LOG_PATH);
    if (!fs.existsSync(auditDir)) {
      fs.mkdirSync(auditDir, { recursive: true });
    }
    fs.appendFileSync(AUDIT_LOG_PATH, auditLine, "utf-8");
  } catch (err) {
    console.error("[CollectionsAgent] Audit log write failed:", String(err));
  }

  return report;
}
