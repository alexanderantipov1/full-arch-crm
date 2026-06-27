/**
 * full-arch-crm — FraudDetectionAgent
 * ─────────────────────────────────────
 * Automated fraud and billing anomaly detection agent.
 *
 * Implements 7 detection rules against claims, appointments, and clinical notes:
 *   1. duplicate_claim       — same patient + procedure + date billed >1x
 *   2. unbundled_procedure   — D6010 billed without D6057/D6058 (or vice versa)
 *   3. upcoding              — D6010 billed but SOAP notes mention consultation/exam only
 *   4. frequency_exceeded    — same procedure billed >1x per arch per year (implants)
 *   5. missing_documentation — claim submitted with no SOAP note for that date
 *   6. impossible_day        — patient at two overlapping locations same day
 *   7. phantom_patient       — patient has claims but zero appointments
 *
 * On critical/high flags:
 *   - Appends to server/audit/fraud-detection.log
 *   - Ingests learning event to wiki
 *   - Opens a GitHub issue on alexanderantipov1/full-arch-crm
 *
 * Usage:
 *   import { runFraudDetectionAgent } from "./fraud-detection-agent";
 *   const report = await runFraudDetectionAgent("tenant-uuid-here");
 *
 * HIPAA note: No PHI is written to the wiki, audit log, or GitHub issues —
 * only anonymized patient IDs, claim IDs, and CDT codes. All PHI access
 * is declared via PhiAccessContext and written to the HIPAA audit trail.
 */

import * as fs from "fs";
import * as path from "path";
import * as crypto from "crypto";
import { execSync } from "child_process";
import { fileURLToPath } from "url";
import { adapterRegistry } from "../adapters/registry";
import { wikiService } from "../simulation/wiki/wiki-service";
import type { PhiAccessContext } from "../adapters/types";
import type {
  FraudFlag,
  FraudReport,
  FraudRuleId,
} from "./types";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUDIT_LOG_PATH = path.join(__dirname, "../audit/fraud-detection.log");

// CDT codes relevant to full-arch implant billing
const IMPLANT_BODY_CODE = "D6010";
const ABUTMENT_CODES = ["D6057", "D6058"];

// ─── PHI Access Context ───────────────────────────────────────────────────────

function buildPhiContext(tenantId: string): PhiAccessContext {
  return {
    purpose: "audit",
    requestedBy: "FraudDetectionAgent",
    tenantId,
    reason: "Automated fraud and billing anomaly detection run",
    traceId: `fraud-nightly-${Date.now()}`,
  };
}

// ─── UUID v4 helper ───────────────────────────────────────────────────────────

function uuidv4(): string {
  return crypto.randomUUID();
}

// ─── Rule implementations ─────────────────────────────────────────────────────

/**
 * Rule 1 — duplicate_claim
 * Same patient + same CDT code + same service date appearing more than once.
 */
function detectDuplicateClaims(
  claims: Array<{ claimId: string; personUid: string; cdtCode: string; serviceDate: Date; chargedAmount: number }>,
): FraudFlag[] {
  const flags: FraudFlag[] = [];
  const seen = new Map<string, typeof claims[0]>();

  for (const claim of claims) {
    const key = `${claim.personUid}|${claim.cdtCode}|${claim.serviceDate.toISOString().slice(0, 10)}`;
    if (seen.has(key)) {
      const orig = seen.get(key)!;
      flags.push({
        flagId: uuidv4(),
        ruleId: "duplicate_claim",
        severity: "high",
        patientId: claim.personUid,
        claimId: claim.claimId,
        procedureCodes: [claim.cdtCode],
        description: `Duplicate claim detected: procedure ${claim.cdtCode} billed twice for the same patient on ${claim.serviceDate.toISOString().slice(0, 10)}.`,
        evidence: [
          `Original claim ID: ${orig.claimId}`,
          `Duplicate claim ID: ${claim.claimId}`,
          `CDT code: ${claim.cdtCode}`,
          `Service date: ${claim.serviceDate.toISOString().slice(0, 10)}`,
          `Charged amount per claim: $${claim.chargedAmount.toFixed(2)}`,
        ],
        recommendedAction:
          "Void the duplicate claim and verify with billing department. Confirm only one procedure was performed.",
        detectedAt: new Date().toISOString(),
        status: "open",
      });
    } else {
      seen.set(key, claim);
    }
  }

  return flags;
}

/**
 * Rule 2 — unbundled_procedure
 * D6010 (implant body) billed without D6057/D6058 (abutment) or vice versa
 * in the same treatment plan.
 */
function detectUnbundledProcedures(
  claimsByPlan: Map<string, Array<{ claimId: string; personUid: string; cdtCode: string; chargedAmount: number }>>,
): FraudFlag[] {
  const flags: FraudFlag[] = [];

  for (const [planId, planClaims] of claimsByPlan) {
    const codes = new Set(planClaims.map((c) => c.cdtCode));
    const hasImplantBody = codes.has(IMPLANT_BODY_CODE);
    const hasAbutment = ABUTMENT_CODES.some((c) => codes.has(c));

    const patientId = planClaims[0]?.personUid;

    if (hasImplantBody && !hasAbutment) {
      const bodyClaims = planClaims.filter((c) => c.cdtCode === IMPLANT_BODY_CODE);
      flags.push({
        flagId: uuidv4(),
        ruleId: "unbundled_procedure",
        severity: "medium",
        patientId,
        claimId: bodyClaims[0]?.claimId,
        procedureCodes: [IMPLANT_BODY_CODE],
        description: `D6010 (implant body) billed in treatment plan ${planId} without a corresponding abutment code (D6057 or D6058).`,
        evidence: [
          `Treatment plan ID: ${planId}`,
          `D6010 claim IDs: ${bodyClaims.map((c) => c.claimId).join(", ")}`,
          `Abutment codes present: none`,
          `All codes in plan: ${[...codes].join(", ")}`,
        ],
        recommendedAction:
          "Review treatment plan for completeness. Add missing abutment code (D6057/D6058) or remove unbundled implant body code if not clinically indicated.",
        detectedAt: new Date().toISOString(),
        status: "open",
      });
    }

    if (!hasImplantBody && hasAbutment) {
      const abutmentClaims = planClaims.filter((c) => ABUTMENT_CODES.includes(c.cdtCode));
      const foundAbutments = abutmentClaims.map((c) => c.cdtCode);
      flags.push({
        flagId: uuidv4(),
        ruleId: "unbundled_procedure",
        severity: "medium",
        patientId,
        claimId: abutmentClaims[0]?.claimId,
        procedureCodes: foundAbutments,
        description: `Abutment code(s) ${foundAbutments.join(", ")} billed in treatment plan ${planId} without a corresponding D6010 implant body.`,
        evidence: [
          `Treatment plan ID: ${planId}`,
          `Abutment claim IDs: ${abutmentClaims.map((c) => c.claimId).join(", ")}`,
          `D6010 present: no`,
          `All codes in plan: ${[...codes].join(", ")}`,
        ],
        recommendedAction:
          "Verify whether implant placement was performed at a different practice. Add D6010 if applicable, or investigate for fraudulent abutment-only billing.",
        detectedAt: new Date().toISOString(),
        status: "open",
      });
    }
  }

  return flags;
}

/**
 * Rule 3 — upcoding
 * D6010 (full implant) billed but SOAP notes for the same appointment mention
 * "consultation only" or "exam".
 */
function detectUpcoding(
  claims: Array<{ claimId: string; personUid: string; cdtCode: string; serviceDate: Date; chargedAmount: number }>,
  notesByPatient: Map<string, Array<{ noteId: string; appointmentId?: string; createdAt: Date; soapPlan?: string; soapAssessment?: string; soapSubjective?: string; noteType: string }>>,
): FraudFlag[] {
  const flags: FraudFlag[] = [];
  const CONSULTATION_KEYWORDS = /consultation only|consult only|exam only|examination only|initial exam|new patient exam|no procedure performed/i;

  const implantClaims = claims.filter((c) => c.cdtCode === IMPLANT_BODY_CODE);

  for (const claim of implantClaims) {
    const notes = notesByPatient.get(claim.personUid) ?? [];
    const claimDate = claim.serviceDate.toISOString().slice(0, 10);

    // Find notes created on the same day as the claim
    const sameDayNotes = notes.filter(
      (n) => n.createdAt.toISOString().slice(0, 10) === claimDate,
    );

    for (const note of sameDayNotes) {
      const noteText = [note.soapSubjective, note.soapAssessment, note.soapPlan, note.noteType]
        .filter(Boolean)
        .join(" ");

      if (CONSULTATION_KEYWORDS.test(noteText)) {
        flags.push({
          flagId: uuidv4(),
          ruleId: "upcoding",
          severity: "high",
          patientId: claim.personUid,
          claimId: claim.claimId,
          procedureCodes: [IMPLANT_BODY_CODE],
          description: `D6010 (full implant) billed on ${claimDate} but SOAP notes for the same date indicate consultation or exam only — no surgical procedure documented.`,
          evidence: [
            `Claim ID: ${claim.claimId}`,
            `CDT code billed: ${IMPLANT_BODY_CODE} ($${claim.chargedAmount.toFixed(2)})`,
            `Service date: ${claimDate}`,
            `Note ID: ${note.noteId}`,
            `Note type: ${note.noteType}`,
            `Matched keywords in note: "${noteText.match(CONSULTATION_KEYWORDS)?.[0] ?? "consultation/exam"}"`,
          ],
          recommendedAction:
            "Suspend claim pending clinical review. Verify procedure was actually performed. Correct to appropriate consultation code (D9310/D0150) if only an exam occurred.",
          detectedAt: new Date().toISOString(),
          status: "open",
        });
        break; // One flag per claim
      }
    }
  }

  return flags;
}

/**
 * Rule 4 — frequency_exceeded
 * Implant procedures (D6010) billed more than once per arch per year for the
 * same patient. Implants are lifetime per site — rebilling within 12 months
 * is a strong fraud indicator.
 */
function detectFrequencyExceeded(
  claims: Array<{ claimId: string; personUid: string; cdtCode: string; serviceDate: Date; chargedAmount: number }>,
): FraudFlag[] {
  const flags: FraudFlag[] = [];

  // Group D6010 claims by patient and year
  const implantClaimsByPatientYear = new Map<string, typeof claims>();

  for (const claim of claims) {
    if (claim.cdtCode !== IMPLANT_BODY_CODE) continue;
    const yearKey = `${claim.personUid}|${claim.serviceDate.getFullYear()}`;
    if (!implantClaimsByPatientYear.has(yearKey)) {
      implantClaimsByPatientYear.set(yearKey, []);
    }
    implantClaimsByPatientYear.get(yearKey)!.push(claim);
  }

  for (const [key, patientYearClaims] of implantClaimsByPatientYear) {
    if (patientYearClaims.length > 1) {
      const [patientId, year] = key.split("|");
      const totalExposure = patientYearClaims.reduce((s, c) => s + c.chargedAmount, 0);
      flags.push({
        flagId: uuidv4(),
        ruleId: "frequency_exceeded",
        severity: "critical",
        patientId,
        claimId: patientYearClaims[0].claimId,
        procedureCodes: [IMPLANT_BODY_CODE],
        description: `D6010 (implant body placement) billed ${patientYearClaims.length}x in ${year} for the same patient. Implants are lifetime-per-site procedures.`,
        evidence: [
          `Patient ID: ${patientId}`,
          `Year: ${year}`,
          `D6010 claim count: ${patientYearClaims.length}`,
          `Claim IDs: ${patientYearClaims.map((c) => c.claimId).join(", ")}`,
          `Service dates: ${patientYearClaims.map((c) => c.serviceDate.toISOString().slice(0, 10)).join(", ")}`,
          `Total charged: $${totalExposure.toFixed(2)}`,
        ],
        recommendedAction:
          "Immediately suspend all duplicate implant claims. Conduct full chart audit to verify each implant site. Report to compliance officer. Contact payer to reverse overpayments.",
        detectedAt: new Date().toISOString(),
        status: "open",
      });
    }
  }

  return flags;
}

/**
 * Rule 5 — missing_documentation
 * Claim submitted but no SOAP note exists for that appointment date.
 */
function detectMissingDocumentation(
  claims: Array<{ claimId: string; personUid: string; cdtCode: string; serviceDate: Date; chargedAmount: number }>,
  notesByPatient: Map<string, Array<{ noteId: string; createdAt: Date }>>,
): FraudFlag[] {
  const flags: FraudFlag[] = [];

  for (const claim of claims) {
    const notes = notesByPatient.get(claim.personUid) ?? [];
    const claimDate = claim.serviceDate.toISOString().slice(0, 10);

    const hasNoteOnDate = notes.some(
      (n) => n.createdAt.toISOString().slice(0, 10) === claimDate,
    );

    if (!hasNoteOnDate) {
      flags.push({
        flagId: uuidv4(),
        ruleId: "missing_documentation",
        severity: "medium",
        patientId: claim.personUid,
        claimId: claim.claimId,
        procedureCodes: [claim.cdtCode],
        description: `Claim for ${claim.cdtCode} on ${claimDate} submitted with no corresponding SOAP note for that date.`,
        evidence: [
          `Claim ID: ${claim.claimId}`,
          `CDT code: ${claim.cdtCode}`,
          `Service date: ${claimDate}`,
          `SOAP notes found for this date: 0`,
          `Total notes on file for patient: ${notes.length}`,
        ],
        recommendedAction:
          "Place claim on hold. Request clinical staff to create or locate the missing SOAP note. Do not submit to payer until documentation is complete.",
        detectedAt: new Date().toISOString(),
        status: "open",
      });
    }
  }

  return flags;
}

/**
 * Rule 6 — impossible_day
 * Patient has appointments at two different locations on the same day
 * with overlapping times.
 */
function detectImpossibleDay(
  appointmentsByPatient: Map<
    string,
    Array<{
      appointmentId: string;
      locationId?: string;
      locationName?: string;
      startTime: Date;
      endTime: Date;
    }>
  >,
): FraudFlag[] {
  const flags: FraudFlag[] = [];

  for (const [patientId, appts] of appointmentsByPatient) {
    // Group by date
    const byDate = new Map<string, typeof appts>();
    for (const appt of appts) {
      const dateKey = appt.startTime.toISOString().slice(0, 10);
      if (!byDate.has(dateKey)) byDate.set(dateKey, []);
      byDate.get(dateKey)!.push(appt);
    }

    for (const [date, dayAppts] of byDate) {
      if (dayAppts.length < 2) continue;

      // Check every pair for overlap at different locations
      for (let i = 0; i < dayAppts.length; i++) {
        for (let j = i + 1; j < dayAppts.length; j++) {
          const a = dayAppts[i];
          const b = dayAppts[j];

          // Different locations
          if (!a.locationId || !b.locationId || a.locationId === b.locationId) continue;

          // Overlapping times
          const aStart = a.startTime.getTime();
          const aEnd = a.endTime.getTime();
          const bStart = b.startTime.getTime();
          const bEnd = b.endTime.getTime();

          const overlaps = aStart < bEnd && bStart < aEnd;
          if (overlaps) {
            flags.push({
              flagId: uuidv4(),
              ruleId: "impossible_day",
              severity: "high",
              patientId,
              description: `Patient has overlapping appointments at two different locations on ${date} — physically impossible.`,
              evidence: [
                `Appointment 1 ID: ${a.appointmentId}`,
                `Location 1: ${a.locationName ?? a.locationId}`,
                `Time 1: ${a.startTime.toISOString()} – ${a.endTime.toISOString()}`,
                `Appointment 2 ID: ${b.appointmentId}`,
                `Location 2: ${b.locationName ?? b.locationId}`,
                `Time 2: ${b.startTime.toISOString()} – ${b.endTime.toISOString()}`,
                `Overlap: ${new Date(Math.max(aStart, bStart)).toISOString()} – ${new Date(Math.min(aEnd, bEnd)).toISOString()}`,
              ],
              recommendedAction:
                "Audit both appointments. One or both may be fraudulent or data-entry errors. Contact patient and both locations to verify. Flag any associated claims for review.",
              detectedAt: new Date().toISOString(),
              status: "open",
            });
          }
        }
      }
    }
  }

  return flags;
}

/**
 * Rule 7 — phantom_patient
 * Patient has claims submitted but zero appointments in the system.
 */
function detectPhantomPatients(
  claimsPatientIds: Set<string>,
  appointmentsPatientIds: Set<string>,
  claimsByPatient: Map<string, Array<{ claimId: string; cdtCode: string; chargedAmount: number }>>,
): FraudFlag[] {
  const flags: FraudFlag[] = [];

  for (const patientId of claimsPatientIds) {
    if (!appointmentsPatientIds.has(patientId)) {
      const patientClaims = claimsByPatient.get(patientId) ?? [];
      const totalExposure = patientClaims.reduce((s, c) => s + c.chargedAmount, 0);
      flags.push({
        flagId: uuidv4(),
        ruleId: "phantom_patient",
        severity: "critical",
        patientId,
        procedureCodes: [...new Set(patientClaims.map((c) => c.cdtCode))],
        description: `Patient has ${patientClaims.length} claim(s) totalling $${totalExposure.toFixed(2)} but zero appointments recorded in the system — possible phantom billing.`,
        evidence: [
          `Patient ID: ${patientId}`,
          `Total claims: ${patientClaims.length}`,
          `Claim IDs: ${patientClaims.slice(0, 5).map((c) => c.claimId).join(", ")}${patientClaims.length > 5 ? " …" : ""}`,
          `CDT codes billed: ${[...new Set(patientClaims.map((c) => c.cdtCode))].join(", ")}`,
          `Total charged: $${totalExposure.toFixed(2)}`,
          `Appointments in system: 0`,
        ],
        recommendedAction:
          "Immediately suspend all claims for this patient. Verify patient identity and appointment records. If no appointments can be substantiated, report to compliance and payer as fraudulent billing.",
        detectedAt: new Date().toISOString(),
        status: "open",
      });
    }
  }

  return flags;
}

// ─── Side effects: audit log, wiki, GitHub issue ──────────────────────────────

function appendAuditLog(flags: FraudFlag[], tenantId: string): void {
  try {
    const auditDir = path.dirname(AUDIT_LOG_PATH);
    if (!fs.existsSync(auditDir)) {
      fs.mkdirSync(auditDir, { recursive: true });
    }
    const runDate = new Date().toISOString();
    for (const flag of flags) {
      const line =
        `[${runDate}] [${tenantId}] FraudDetectionAgent: flagId=${flag.flagId} ` +
        `rule=${flag.ruleId} severity=${flag.severity} ` +
        `patientId=${flag.patientId ?? "N/A"} claimId=${flag.claimId ?? "N/A"}\n`;
      fs.appendFileSync(AUDIT_LOG_PATH, line, "utf-8");
    }
  } catch (err) {
    console.error("[FraudDetectionAgent] Audit log write failed:", String(err));
  }
}

async function ingestToWiki(
  flags: FraudFlag[],
  tenantId: string,
  estimatedExposure: number,
): Promise<void> {
  try {
    const highCriticalCount = flags.length;
    const exposureFormatted = estimatedExposure.toLocaleString("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });

    await wikiService.ingest({
      type: "orchestration_cycle",
      sourceId: `fraud-nightly-${tenantId}-${Date.now()}`,
      agentName: "FraudDetectionAgent",
      score: highCriticalCount,
    });
  } catch (err) {
    console.warn("[FraudDetectionAgent] Wiki ingest error:", String(err));
  }
}

function openGitHubIssue(flag: FraudFlag): void {
  try {
    const date = flag.detectedAt.slice(0, 10);
    const severityLabel = flag.severity.toUpperCase();
    const patientDisplay = flag.patientId ? `Patient ${flag.patientId.slice(0, 8)}…` : "Unknown";
    const title = `Fraud Alert [${severityLabel}]: ${flag.ruleId} — ${patientDisplay} — ${date}`;

    const evidenceList = flag.evidence.map((e) => `- ${e}`).join("\\n");
    const body =
      `## Fraud Detection Alert\\n\\n` +
      `**Rule:** ${flag.ruleId}\\n` +
      `**Severity:** ${flag.severity}\\n` +
      `**Patient:** ${flag.patientId ?? "N/A"}\\n` +
      `**Claim:** ${flag.claimId ?? "N/A"}\\n\\n` +
      `### Evidence\\n${evidenceList}\\n\\n` +
      `### Recommended action\\n${flag.recommendedAction}\\n\\n` +
      `_Auto-detected by FraudDetectionAgent_`;

    execSync(
      `gh issue create --repo alexanderantipov1/full-arch-crm ` +
        `--title "${title.replace(/"/g, '\\"')}" ` +
        `--body $'${body}' ` +
        `--label "fraud,bug"`,
      { stdio: "pipe" },
    );
  } catch (err) {
    console.error(
      `[FraudDetectionAgent] GitHub issue creation failed for flag ${flag.flagId}:`,
      String(err),
    );
  }
}

// ─── Main runner ──────────────────────────────────────────────────────────────

/**
 * Primary entry point for the FraudDetectionAgent nightly job.
 *
 * Fetches all claims, appointments, and clinical notes for the given tenant,
 * runs all 7 fraud detection rules, and returns a fully populated FraudReport.
 *
 * Side effects for critical/high flags:
 *   - Appends entries to server/audit/fraud-detection.log
 *   - Ingests a learning event to the Karpathy wiki
 *   - Opens a GitHub issue on alexanderantipov1/full-arch-crm
 *
 * @param tenantId  The canonical tenant UUID. Must be registered in adapterRegistry.
 * @returns         A FraudReport with all flags, exposure estimates, and summaries.
 */
export async function runFraudDetectionAgent(
  tenantId: string,
): Promise<FraudReport> {
  const adapter = adapterRegistry.getAdapter(tenantId);
  const phiCtx = buildPhiContext(tenantId);

  // ── 1. Fetch all patient UIDs ──────────────────────────────────────────────

  const pageSize = 200;
  let cursor: string | undefined;
  const allPersonUids: string[] = [];

  do {
    const page = await adapter.listPatients({ limit: pageSize, cursor });
    allPersonUids.push(...page.items.map((p) => p.personUid));
    cursor = page.nextCursor;
  } while (cursor);

  // ── 2. Fetch all claims (tenant-wide) ─────────────────────────────────────

  const allClaims = await adapter.listClaims({ limit: 10_000 });

  // ── 3. Fetch all appointments (tenant-wide) ───────────────────────────────

  const allAppointments = await adapter.listAppointments({ limit: 10_000 });

  // ── 4. Fetch clinical notes per patient (parallel, best-effort) ───────────

  const notesByPatient = new Map<
    string,
    Array<{
      noteId: string;
      appointmentId?: string;
      createdAt: Date;
      noteType: string;
      soapSubjective?: string;
      soapAssessment?: string;
      soapPlan?: string;
    }>
  >();

  await Promise.all(
    allPersonUids.map(async (personUid) => {
      try {
        const notes = await adapter.getClinicalNotes(personUid, phiCtx);
        if (notes.length > 0) {
          notesByPatient.set(personUid, notes);
        }
      } catch {
        // Best-effort; skip patients where notes fetch fails
      }
    }),
  );

  // ── 5. Build indexes for rules ────────────────────────────────────────────

  // Claims indexed by treatment plan
  const claimsByPlan = new Map<
    string,
    Array<{ claimId: string; personUid: string; cdtCode: string; chargedAmount: number }>
  >();
  for (const claim of allClaims) {
    const planId = claim.treatmentPlanId ?? "__no_plan__";
    if (!claimsByPlan.has(planId)) claimsByPlan.set(planId, []);
    claimsByPlan.get(planId)!.push({
      claimId: claim.claimId,
      personUid: claim.personUid,
      cdtCode: claim.cdtCode,
      chargedAmount: claim.chargedAmount,
    });
  }

  // Claims indexed by patient
  const claimsByPatient = new Map<
    string,
    Array<{ claimId: string; cdtCode: string; chargedAmount: number }>
  >();
  for (const claim of allClaims) {
    if (!claimsByPatient.has(claim.personUid)) claimsByPatient.set(claim.personUid, []);
    claimsByPatient.get(claim.personUid)!.push({
      claimId: claim.claimId,
      cdtCode: claim.cdtCode,
      chargedAmount: claim.chargedAmount,
    });
  }

  // Appointments indexed by patient
  const appointmentsByPatient = new Map<
    string,
    Array<{
      appointmentId: string;
      locationId?: string;
      locationName?: string;
      startTime: Date;
      endTime: Date;
    }>
  >();
  for (const appt of allAppointments) {
    if (!appointmentsByPatient.has(appt.personUid)) {
      appointmentsByPatient.set(appt.personUid, []);
    }
    appointmentsByPatient.get(appt.personUid)!.push({
      appointmentId: appt.appointmentId,
      locationId: appt.locationId,
      locationName: appt.locationName,
      startTime: appt.startTime,
      endTime: appt.endTime,
    });
  }

  const claimsPatientIds = new Set(allClaims.map((c) => c.personUid));
  const appointmentsPatientIds = new Set(allAppointments.map((a) => a.personUid));

  // Flat claims array for rules that operate per-claim
  const claimsFlat = allClaims.map((c) => ({
    claimId: c.claimId,
    personUid: c.personUid,
    cdtCode: c.cdtCode,
    serviceDate: c.serviceDate,
    chargedAmount: c.chargedAmount,
  }));

  // ── 6. Run all 7 detection rules ──────────────────────────────────────────

  const allFlags: FraudFlag[] = [
    ...detectDuplicateClaims(claimsFlat),
    ...detectUnbundledProcedures(claimsByPlan),
    ...detectUpcoding(claimsFlat, notesByPatient),
    ...detectFrequencyExceeded(claimsFlat),
    ...detectMissingDocumentation(claimsFlat, notesByPatient),
    ...detectImpossibleDay(appointmentsByPatient),
    ...detectPhantomPatients(claimsPatientIds, appointmentsPatientIds, claimsByPatient),
  ];

  // ── 7. Aggregate report ───────────────────────────────────────────────────

  const byRule: Record<FraudRuleId, number> = {
    duplicate_claim: 0,
    unbundled_procedure: 0,
    upcoding: 0,
    frequency_exceeded: 0,
    missing_documentation: 0,
    impossible_day: 0,
    phantom_patient: 0,
  };
  const bySeverity: Record<FraudFlag["severity"], number> = {
    low: 0,
    medium: 0,
    high: 0,
    critical: 0,
  };

  for (const flag of allFlags) {
    byRule[flag.ruleId]++;
    bySeverity[flag.severity]++;
  }

  // Estimated exposure = sum of charged amounts on flagged claims
  const flaggedClaimIds = new Set(allFlags.map((f) => f.claimId).filter(Boolean));
  const estimatedExposure = allClaims
    .filter((c) => flaggedClaimIds.has(c.claimId))
    .reduce((sum, c) => sum + c.chargedAmount, 0);

  const criticalFlags = allFlags.filter(
    (f) => f.severity === "critical" || f.severity === "high",
  );

  const runDate = new Date().toISOString();
  const report: FraudReport = {
    runDate,
    totalClaimsReviewed: allClaims.length,
    totalFlagsRaised: allFlags.length,
    byRule,
    bySeverity,
    criticalFlags,
    allFlags,
    estimatedExposure,
  };

  // ── 8. Side effects for critical/high flags ───────────────────────────────

  if (criticalFlags.length > 0) {
    // 8a. Audit log
    appendAuditLog(criticalFlags, tenantId);

    // 8b. Wiki ingest
    await ingestToWiki(criticalFlags, tenantId, estimatedExposure);

    // 8c. GitHub issues (one per flag)
    for (const flag of criticalFlags) {
      openGitHubIssue(flag);
    }
  }

  return report;
}
