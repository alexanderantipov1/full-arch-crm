/**
 * full-arch-crm — AI Scheduling Agent
 * ─────────────────────────────────────
 * AI-optimized appointment booking agent that maximizes chair utilization
 * and matches case complexity to the right slot type and time of day.
 *
 * Responsibilities:
 *   1. Build an availability grid for the current week (or location)
 *   2. Score every unscheduled patient by urgency (0–100)
 *   3. Rank open slots by fit for each patient's appointment type
 *   4. Return a SchedulingReport with top recommendations and bottleneck warnings
 *   5. Ingest a learning event into the wiki
 *   6. Append one line to the audit log
 *
 * Usage:
 *   import { runSchedulingAgent } from "./scheduling-agent";
 *   const report = await runSchedulingAgent("tenant-uuid", "loc-001");
 *
 * HIPAA note: No PHI is written to the wiki or audit log — only aggregate,
 * anonymized signals (utilization rates, recommendation counts).
 */

import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";
import { adapterRegistry } from "../adapters/registry";
import { wikiService } from "../simulation/wiki/wiki-service";
import type { PhiAccessContext } from "../adapters/types";
import type {
  TimeSlot,
  BookingRecommendation,
  SchedulingReport,
} from "./types";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUDIT_LOG_PATH = path.join(__dirname, "../audit/scheduling-agent.log");

// ─── Constants ────────────────────────────────────────────────────────────────

/** Number of days ahead to build the scheduling window */
const SCHEDULE_WINDOW_DAYS = 7;

/** Utilization threshold (%) above which a day/period is flagged as a bottleneck */
const BOTTLENECK_UTILIZATION_THRESHOLD = 90;

/** Urgency scoring increments (spec-defined) */
const URGENCY = {
  OLD_PLAN_NO_SURGERY: 40,    // Treatment plan > 14 days old, no surgery scheduled
  HIGH_CASE_ACCEPTANCE: 20,   // Case acceptance score > 70 from TreatmentCoordinator
  PREAUTH_APPROVED: 20,       // Insurance pre-authorization approved
  MISSED_APPOINTMENT: -20,    // Patient missed 1+ appointments
  FINANCING_IN_PLACE: 10,     // Financing plan approved
  OUTSTANDING_BALANCE: -10,   // Balance > $1,000 outstanding
} as const;

/** Appointment type → slot preference rules */
const SLOT_RULES = {
  surgery: {
    preferredStartHour: 8,
    preferredEndHour: 12,
    minDurationMinutes: 180,
    slotType: "surgery" as const,
  },
  consult: {
    preferredStartHour: 13,
    preferredEndHour: 17,
    minDurationMinutes: 45,
    maxDurationMinutes: 60,
    slotType: "consult" as const,
  },
  followup: {
    preferredStartHour: 0,
    preferredEndHour: 24,
    minDurationMinutes: 30,
    maxDurationMinutes: 30,
    slotType: "followup" as const,
  },
  restoration: {
    preferredStartHour: 8,
    preferredEndHour: 17,
    minDurationMinutes: 60,
    slotType: "restoration" as const,
  },
} as const;

// ─── PHI Access Context ───────────────────────────────────────────────────────

function buildPhiContext(tenantId: string): PhiAccessContext {
  return {
    purpose: "treatment",
    requestedBy: "SchedulingAgent",
    tenantId,
    reason: "AI scheduling optimization — urgency scoring and slot recommendation",
    traceId: `sched-${Date.now()}`,
  };
}

// ─── Date / Time Helpers ──────────────────────────────────────────────────────

/** Parse "HH:MM" → hour as a number (e.g. "08:30" → 8.5) */
function timeToHour(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h + m / 60;
}

/** Format a Date to "HH:MM" */
function formatTime(date: Date): string {
  const h = String(date.getHours()).padStart(2, "0");
  const m = String(date.getMinutes()).padStart(2, "0");
  return `${h}:${m}`;
}

/** Format a Date to ISO date "YYYY-MM-DD" */
function formatDate(date: Date): string {
  return date.toISOString().split("T")[0];
}

/** How many calendar days since a Date or ISO string */
function daysSince(date: Date | string): number {
  const then = typeof date === "string" ? new Date(date) : date;
  const diffMs = Date.now() - then.getTime();
  return Math.max(0, Math.floor(diffMs / (1000 * 60 * 60 * 24)));
}

/** Day-of-week name (Mon–Sun) for a given Date */
function dayName(date: Date): string {
  return date.toLocaleDateString("en-US", { weekday: "short" });
}

// ─── Availability Grid ────────────────────────────────────────────────────────

/**
 * A simple in-memory grid keyed by "YYYY-MM-DD|chairId" → booked minutes.
 * Used for double-booking detection and utilization calculation.
 */
type AvailabilityGrid = Map<string, number>;

function gridKey(date: string, chairId: string): string {
  return `${date}|${chairId}`;
}

/**
 * Build a blank grid for the scheduling window.
 * For simulation purposes we treat each chair as having 8 available hours/day.
 */
function buildAvailabilityGrid(
  dates: string[],
  chairIds: string[],
): AvailabilityGrid {
  const grid = new Map<string, number>();
  for (const date of dates) {
    for (const chairId of chairIds) {
      grid.set(gridKey(date, chairId), 0); // 0 minutes booked
    }
  }
  return grid;
}

/** Total available chair-minutes per day (8 working hours = 480 min) */
const DAILY_CHAIR_MINUTES = 480;

// ─── Slot Generation ──────────────────────────────────────────────────────────

/**
 * Generate candidate TimeSlots for the scheduling window.
 *
 * For each date × chair × provider combination, we produce one slot per
 * appointment type per day-period so the ranker has candidates to work with.
 * In production these would come from the practice management system's
 * availability API — here we generate them synthetically based on rules.
 */
function generateCandidateSlots(
  dates: string[],
  chairIds: string[],
  providerIds: string[],
  bookedSlots: TimeSlot[],
): TimeSlot[] {
  const slots: TimeSlot[] = [];

  // Build a set of already-booked windows for double-booking detection
  const bookedWindows = new Set<string>();
  for (const s of bookedSlots) {
    const startH = timeToHour(s.startTime);
    const endH = timeToHour(s.endTime);
    // Mark every 30-min block within this slot as occupied
    for (let h = startH; h < endH; h += 0.5) {
      bookedWindows.add(`${s.date}|${s.chairId}|${h}`);
    }
  }

  // For each date, generate slots per slot type
  const slotTemplates: Array<{
    slotType: TimeSlot["slotType"];
    startTime: string;
    endTime: string;
    durationMinutes: number;
  }> = [
    { slotType: "surgery", startTime: "08:00", endTime: "11:00", durationMinutes: 180 },
    { slotType: "surgery", startTime: "09:00", endTime: "12:00", durationMinutes: 180 },
    { slotType: "consult", startTime: "13:00", endTime: "13:45", durationMinutes: 45 },
    { slotType: "consult", startTime: "14:00", endTime: "15:00", durationMinutes: 60 },
    { slotType: "consult", startTime: "15:00", endTime: "16:00", durationMinutes: 60 },
    { slotType: "followup", startTime: "09:00", endTime: "09:30", durationMinutes: 30 },
    { slotType: "followup", startTime: "11:00", endTime: "11:30", durationMinutes: 30 },
    { slotType: "followup", startTime: "16:00", endTime: "16:30", durationMinutes: 30 },
    { slotType: "restoration", startTime: "08:00", endTime: "09:00", durationMinutes: 60 },
    { slotType: "restoration", startTime: "10:00", endTime: "11:30", durationMinutes: 90 },
    { slotType: "restoration", startTime: "14:00", endTime: "15:30", durationMinutes: 90 },
  ];

  for (const date of dates) {
    for (const chairId of chairIds) {
      for (const providerId of providerIds) {
        for (const tmpl of slotTemplates) {
          // Check for double-booking
          const startH = timeToHour(tmpl.startTime);
          const endH = timeToHour(tmpl.endTime);
          let blocked = false;
          for (let h = startH; h < endH; h += 0.5) {
            if (bookedWindows.has(`${date}|${chairId}|${h}`)) {
              blocked = true;
              break;
            }
          }

          slots.push({
            date,
            startTime: tmpl.startTime,
            endTime: tmpl.endTime,
            chairId,
            providerId,
            durationMinutes: tmpl.durationMinutes,
            slotType: tmpl.slotType,
            available: !blocked,
          });
        }
      }
    }
  }

  return slots;
}

// ─── Slot Ranking ─────────────────────────────────────────────────────────────

/**
 * Score a slot's fit for a given appointment type.
 * Higher = better fit.
 *
 * Factors:
 *   - Time-of-day match to the appointment type's preference: +50
 *   - Slot type matches appointment type: +30
 *   - Earlier in the week (prefer sooner): +0–20 (linear, earlier = more)
 *   - Adequate duration: must pass minimum (already filtered before ranking)
 */
function scoreSlotFit(
  slot: TimeSlot,
  appointmentType: string,
  dateIndex: number,
  totalDates: number,
): number {
  let score = 0;

  const rules =
    SLOT_RULES[appointmentType as keyof typeof SLOT_RULES] ??
    SLOT_RULES.restoration;

  const startHour = timeToHour(slot.startTime);

  // Time-of-day preference match
  if (
    startHour >= rules.preferredStartHour &&
    startHour < rules.preferredEndHour
  ) {
    score += 50;
  }

  // Slot type match
  if (slot.slotType === rules.slotType) {
    score += 30;
  }

  // Earlier in the window = slightly preferred (urgency-driven)
  const recencyBonus = Math.round(
    20 * (1 - dateIndex / Math.max(1, totalDates - 1)),
  );
  score += recencyBonus;

  return score;
}

/**
 * Map a canonical appointment type to the scheduling slot type.
 */
function appointmentTypeToSlotType(
  apptType: string,
): "surgery" | "consult" | "followup" | "restoration" {
  switch (apptType) {
    case "surgery":
    case "pre_op":
      return "surgery";
    case "consultation":
    case "new_patient":
      return "consult";
    case "post_op":
    case "maintenance":
    case "recall":
      return "followup";
    default:
      return "restoration";
  }
}

// ─── Urgency Scoring ──────────────────────────────────────────────────────────

interface UrgencyInputs {
  /** Days since treatment plan was created */
  planAgeDays: number;
  /** Case acceptance score from TreatmentCoordinator (0–100); undefined if not scored */
  caseAcceptanceScore: number | undefined;
  /** Whether insurance pre-authorization is approved */
  preAuthApproved: boolean;
  /** Number of missed (no-show) appointments */
  missedAppointments: number;
  /** Whether the patient has approved financing */
  financingInPlace: boolean;
  /** Outstanding balance in USD */
  outstandingBalance: number;
}

/**
 * Compute urgency score for an unscheduled patient.
 * Score is clamped to [0, 100].
 */
export function computeUrgencyScore(inputs: UrgencyInputs): number {
  let score = 0;

  // Treatment plan created > 14 days ago with no surgery scheduled
  if (inputs.planAgeDays > 14) {
    score += URGENCY.OLD_PLAN_NO_SURGERY;
  }

  // Case acceptance score > 70 (patient likely to proceed)
  if (inputs.caseAcceptanceScore !== undefined && inputs.caseAcceptanceScore > 70) {
    score += URGENCY.HIGH_CASE_ACCEPTANCE;
  }

  // Insurance pre-auth approved
  if (inputs.preAuthApproved) {
    score += URGENCY.PREAUTH_APPROVED;
  }

  // Patient missed 1+ appointments
  if (inputs.missedAppointments >= 1) {
    score += URGENCY.MISSED_APPOINTMENT; // negative
  }

  // Financing in place
  if (inputs.financingInPlace) {
    score += URGENCY.FINANCING_IN_PLACE;
  }

  // Outstanding balance > $1,000
  if (inputs.outstandingBalance > 1000) {
    score += URGENCY.OUTSTANDING_BALANCE; // negative
  }

  return Math.max(0, Math.min(100, score));
}

// ─── Bottleneck Detection ─────────────────────────────────────────────────────

/**
 * Inspect the availability grid and return human-readable bottleneck warnings
 * for any chair+day where booked minutes > 90% of daily capacity.
 */
function detectBottlenecks(
  grid: AvailabilityGrid,
  allDates: string[],
  chairIds: string[],
): string[] {
  const bottlenecks: string[] = [];

  for (const date of allDates) {
    let dayTotalBooked = 0;
    let dayTotalCapacity = 0;

    for (const chairId of chairIds) {
      const booked = grid.get(gridKey(date, chairId)) ?? 0;
      dayTotalBooked += booked;
      dayTotalCapacity += DAILY_CHAIR_MINUTES;
    }

    const utilizationPct =
      dayTotalCapacity > 0
        ? Math.round((dayTotalBooked / dayTotalCapacity) * 100)
        : 0;

    if (utilizationPct > BOTTLENECK_UTILIZATION_THRESHOLD) {
      const dateObj = new Date(date + "T12:00:00Z");
      bottlenecks.push(
        `${dayName(dateObj)} ${date}: utilization at ${utilizationPct}% (>${BOTTLENECK_UTILIZATION_THRESHOLD}% threshold — over-booked)`,
      );
    }

    // Also detect surgery-specific over-booking in morning block
    for (const chairId of chairIds) {
      const booked = grid.get(gridKey(date, chairId)) ?? 0;
      if (booked > DAILY_CHAIR_MINUTES) {
        const dateObj = new Date(date + "T12:00:00Z");
        bottlenecks.push(
          `Surgery chair ${chairId} over-booked on ${dayName(dateObj)} — ${booked}min scheduled vs ${DAILY_CHAIR_MINUTES}min capacity`,
        );
      }
    }
  }

  return [...new Set(bottlenecks)]; // deduplicate
}

// ─── Main agent runner ────────────────────────────────────────────────────────

/**
 * Primary entry point for the Scheduling Agent.
 *
 * Fetches existing appointments for the given tenant and location, builds
 * an availability grid, scores unscheduled patients by urgency, and returns
 * a SchedulingReport with top recommendations.
 *
 * Side effects:
 *   - Calls wikiService.ingest() with AGENT_LEARNING data (fire-and-forget)
 *   - Appends one line to server/audit/scheduling-agent.log
 *
 * @param tenantId    The canonical tenant UUID registered in adapterRegistry.
 * @param locationId  Optional location filter. Defaults to first location.
 * @returns           A fully populated SchedulingReport.
 */
export async function runSchedulingAgent(
  tenantId: string,
  locationId?: string,
): Promise<SchedulingReport> {
  const adapter = adapterRegistry.getAdapter(tenantId);
  const phiCtx = buildPhiContext(tenantId);
  const runDate = new Date().toISOString();

  // ── 1. Build date window ──────────────────────────────────────────────────

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const schedulingDates: string[] = [];
  for (let i = 0; i < SCHEDULE_WINDOW_DAYS; i++) {
    const d = new Date(today);
    d.setDate(d.getDate() + i);
    schedulingDates.push(formatDate(d));
  }

  // ── 2. Fetch existing appointments in the window ──────────────────────────

  const existingAppointments = await adapter
    .listAppointments({
      ...(locationId ? { locationId } : {}),
      dateFrom: new Date(schedulingDates[0]),
      dateTo: new Date(schedulingDates[schedulingDates.length - 1] + "T23:59:59"),
    })
    .catch(() => []);

  // Derive chair and provider IDs from existing appointments
  const chairIds: string[] = [];
  const providerIds: string[] = [];

  for (const appt of existingAppointments) {
    if (appt.chair != null) {
      const chairId = String(appt.chair);
      if (!chairIds.includes(chairId)) chairIds.push(chairId);
    }
    if (appt.providerId) {
      if (!providerIds.includes(appt.providerId)) providerIds.push(appt.providerId);
    }
  }

  // Ensure at least one chair and one provider for slot generation
  if (chairIds.length === 0) chairIds.push("chair-1", "chair-2");
  if (providerIds.length === 0) providerIds.push("provider-1");

  // ── 3. Build availability grid from existing bookings ─────────────────────

  const grid = buildAvailabilityGrid(schedulingDates, chairIds);

  // Convert existing appointments to TimeSlots and mark grid
  const bookedSlots: TimeSlot[] = existingAppointments
    .filter((a) => a.status !== "cancelled" && a.status !== "no_show")
    .map((a) => {
      const date = formatDate(a.startTime);
      const chairId = a.chair != null ? String(a.chair) : "chair-1";
      const slot: TimeSlot = {
        date,
        startTime: formatTime(a.startTime),
        endTime: formatTime(a.endTime),
        chairId,
        providerId: a.providerId ?? "provider-1",
        durationMinutes: a.durationMinutes,
        slotType: appointmentTypeToSlotType(a.appointmentType),
        available: false,
      };

      // Update grid — add booked minutes
      const key = gridKey(date, chairId);
      grid.set(key, (grid.get(key) ?? 0) + a.durationMinutes);

      return slot;
    });

  // ── 4. Generate candidate open slots ─────────────────────────────────────

  const allCandidateSlots = generateCandidateSlots(
    schedulingDates,
    chairIds,
    providerIds,
    bookedSlots,
  );
  const openSlots = allCandidateSlots.filter((s) => s.available);

  // ── 5. Calculate overall utilization rate ────────────────────────────────

  const totalCapacityMinutes =
    schedulingDates.length * chairIds.length * DAILY_CHAIR_MINUTES;
  const totalBookedMinutes = bookedSlots.reduce(
    (sum, s) => sum + s.durationMinutes,
    0,
  );
  const utilizationRate =
    totalCapacityMinutes > 0
      ? Math.round((totalBookedMinutes / totalCapacityMinutes) * 100)
      : 0;

  // ── 6. Fetch and score unscheduled patients ───────────────────────────────

  const pageSize = 200;
  let cursor: string | undefined;
  const allPersonUids: string[] = [];

  do {
    const page = await adapter.listPatients({ limit: pageSize, cursor });
    allPersonUids.push(...page.items.map((p) => p.personUid));
    cursor = page.nextCursor;
  } while (cursor);

  interface ScoredPatient {
    personUid: string;
    urgencyScore: number;
    appointmentType: string;
    notes: string;
  }

  const scoredPatients: ScoredPatient[] = [];

  await Promise.all(
    allPersonUids.map(async (personUid) => {
      try {
        // Only consider patients with pending treatment plans and no scheduled surgery
        const [plans, appointments, financingPlans, insuranceRecords] =
          await Promise.all([
            adapter.getTreatmentPlans(personUid, phiCtx).catch(() => []),
            adapter.listAppointments({ personUid }).catch(() => []),
            adapter.getFinancingPlans(personUid, phiCtx).catch(() => []),
            adapter.getInsurance(personUid, phiCtx).catch(() => []),
          ]);

        const pendingPlans = plans.filter(
          (p) => p.status === "presented" || p.status === "draft",
        );
        if (pendingPlans.length === 0) return;

        // Check if any surgery is already scheduled
        const hasSurgeryScheduled = appointments.some(
          (a) =>
            a.appointmentType === "surgery" &&
            (a.status === "scheduled" || a.status === "confirmed"),
        );

        const plan = pendingPlans.sort(
          (a, b) =>
            new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
        )[0];

        const planAgeDays = daysSince(plan.createdAt);

        // Determine if pre-auth is approved (check insurance records)
        const primaryInsurance = insuranceRecords.find(
          (i) => i.insuranceType === "primary",
        );
        const preAuthApproved =
          primaryInsurance?.authorizationStatus === "approved" ||
          primaryInsurance?.verificationStatus === "verified";

        // Count missed appointments
        const missedAppointments = appointments.filter(
          (a) => a.status === "no_show",
        ).length;

        // Check financing
        const hasApprovedFinancing = financingPlans.some(
          (f) => f.applicationStatus === "approved",
        );

        // Outstanding balance
        const outstandingBalance = plan.patientResponsibility ?? 0;

        // Determine case acceptance score from plan metadata if available
        // (In production this would come from TreatmentCoordinator output)
        const caseAcceptanceScore: number | undefined = undefined;

        const urgencyScore = computeUrgencyScore({
          planAgeDays: hasSurgeryScheduled ? 0 : planAgeDays,
          caseAcceptanceScore,
          preAuthApproved,
          missedAppointments,
          financingInPlace: hasApprovedFinancing,
          outstandingBalance,
        });

        if (urgencyScore <= 0) return; // not a scheduling candidate right now

        // Determine appointment type based on plan and history
        const appointmentType = hasSurgeryScheduled
          ? "post_op"
          : planAgeDays > 0
          ? "surgery"
          : "consultation";

        const notesParts: string[] = [];
        if (planAgeDays > 14 && !hasSurgeryScheduled) {
          notesParts.push(`Treatment plan ${planAgeDays}d old, no surgery booked`);
        }
        if (preAuthApproved) notesParts.push("Pre-auth approved");
        if (hasApprovedFinancing) notesParts.push("Financing in place");
        if (missedAppointments > 0) {
          notesParts.push(`${missedAppointments} missed appt(s)`);
        }
        if (outstandingBalance > 1000) {
          notesParts.push(`$${outstandingBalance.toFixed(0)} balance outstanding`);
        }

        scoredPatients.push({
          personUid,
          urgencyScore,
          appointmentType,
          notes: notesParts.join("; ") || "Standard scheduling candidate",
        });
      } catch (err) {
        console.warn(
          `[SchedulingAgent] Skipping patient ${personUid}: ${String(err)}`,
        );
      }
    }),
  );

  // ── 7. Build recommendations — top 3 patients by urgency ─────────────────

  const topPatients = scoredPatients
    .sort((a, b) => b.urgencyScore - a.urgencyScore)
    .slice(0, 3);

  const recommendedBookings: BookingRecommendation[] = topPatients.map(
    (patient) => {
      const rules =
        SLOT_RULES[
          appointmentTypeToSlotType(patient.appointmentType) as keyof typeof SLOT_RULES
        ] ?? SLOT_RULES.restoration;

      // Filter open slots that meet minimum duration for this appointment type
      const eligibleSlots = openSlots.filter(
        (s) =>
          s.durationMinutes >= rules.minDurationMinutes &&
          s.slotType === rules.slotType,
      );

      // Rank eligible slots by fit
      const rankedSlots = eligibleSlots
        .map((slot) => ({
          slot,
          fitScore: scoreSlotFit(
            slot,
            appointmentTypeToSlotType(patient.appointmentType),
            schedulingDates.indexOf(slot.date),
            schedulingDates.length,
          ),
        }))
        .sort((a, b) => b.fitScore - a.fitScore)
        .slice(0, 3)
        .map((r) => r.slot);

      return {
        patientId: patient.personUid,
        appointmentType: patient.appointmentType,
        recommendedSlots: rankedSlots,
        urgencyScore: patient.urgencyScore,
        notes: patient.notes,
      };
    },
  );

  // ── 8. Bottleneck detection ───────────────────────────────────────────────

  const bottlenecks = detectBottlenecks(grid, schedulingDates, chairIds);

  // Additional utilization-based warning
  if (utilizationRate > BOTTLENECK_UTILIZATION_THRESHOLD) {
    bottlenecks.unshift(
      `Overall utilization at ${utilizationRate}% this week — approaching capacity`,
    );
  }

  // ── 9. Build final report ─────────────────────────────────────────────────

  const report: SchedulingReport = {
    runDate,
    locationId: locationId ?? "all",
    utilizationRate,
    recommendedBookings,
    openSlots,
    bottlenecks: [...new Set(bottlenecks)],
  };

  // ── 10. Wiki ingest (fire-and-forget) ─────────────────────────────────────

  void wikiService
    .ingest({
      type: "orchestration_cycle",
      sourceId: `sched-${tenantId}-${runDate}`,
      agentName: "SchedulingAgent",
      score: utilizationRate,
    })
    .catch((err: Error) =>
      console.warn("[SchedulingAgent] Wiki ingest error:", err.message),
    );

  // ── 11. Audit log ─────────────────────────────────────────────────────────

  const auditLine =
    `[${runDate}] [${tenantId}] SchedulingAgent: utilization ${utilizationRate}%, ` +
    `${recommendedBookings.length} recommendations\n`;

  try {
    const auditDir = path.dirname(AUDIT_LOG_PATH);
    if (!fs.existsSync(auditDir)) {
      fs.mkdirSync(auditDir, { recursive: true });
    }
    fs.appendFileSync(AUDIT_LOG_PATH, auditLine, "utf-8");
  } catch (err) {
    console.error("[SchedulingAgent] Audit log write failed:", String(err));
  }

  return report;
}
