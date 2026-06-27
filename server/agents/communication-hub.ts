/**
 * full-arch-crm — Patient Communication Hub
 * ────────────────────────────────────────────
 * Automated patient communication sequencing agent.
 * Schedules and queues messages across 8 trigger types:
 *   appointment reminders (48h & 2h), post-op follow-ups (day 1 & 7),
 *   treatment plan nudges, payment plan reminders, 6-month recalls,
 *   and birthday greetings.
 *
 * Responsibilities:
 *   1. Fetch upcoming appointments → schedule appointment_reminder_48h / appointment_reminder_2h
 *   2. Fetch yesterday's surgery appointments → schedule post_op_day1
 *   3. Fetch surgery appointments from 7 days ago → schedule post_op_day7
 *   4. Fetch TreatmentCoordinator highPriority patients → schedule treatment_plan_nudge
 *   5. Fetch patients with payment due within 3 days → schedule payment_plan_reminder
 *   6. Fetch patients whose last visit was ~180 days ago → schedule recall_6month
 *   7. Fetch patients whose birthday is today → schedule birthday_greeting
 *   8. Append all messages to server/communication/queue.json (NDJSON, append-only)
 *   9. Wiki ingest after run
 *  10. Audit log entry
 *
 * Usage:
 *   import { runCommunicationHub } from "./communication-hub";
 *   const report = await runCommunicationHub("tenant-uuid-here");
 *
 * HIPAA note: Message bodies contain PHI (patient first name, appointment details).
 * They are written only to the tenant-local queue file and never leave the tenant
 * context. The wiki ingest and audit log contain only aggregate, anonymized signals.
 */

import * as fs from "fs";
import * as path from "path";
import * as crypto from "crypto";
import { fileURLToPath } from "url";
import { adapterRegistry } from "../adapters/registry";
import { wikiService } from "../simulation/wiki/wiki-service";
import { runTreatmentCoordinator } from "./treatment-coordinator";
import type { PhiAccessContext } from "../adapters/types";
import type {
  CommunicationChannel,
  CommunicationTrigger,
  PatientMessage,
  CommunicationReport,
} from "./types";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const QUEUE_PATH = path.join(__dirname, "../../server/communication/queue.json");
const AUDIT_LOG_PATH = path.join(__dirname, "../audit/communication-hub.log");

// ─── Clinic config ────────────────────────────────────────────────────────────

interface ClinicConfig {
  name: string;
  phone: string;
  portalUrl: string;
}

function getClinicConfig(): ClinicConfig {
  return {
    name: process.env.CLINIC_NAME ?? "[CLINIC_NAME]",
    phone: process.env.CLINIC_PHONE ?? "[CLINIC_PHONE]",
    portalUrl: process.env.PATIENT_PORTAL_URL ?? "[PORTAL_URL]",
  };
}

// ─── PHI Access Context ───────────────────────────────────────────────────────

function buildPhiContext(tenantId: string): PhiAccessContext {
  return {
    purpose: "treatment",
    requestedBy: "CommunicationHubAgent",
    tenantId,
    reason: "Patient communication sequencing for appointment and care reminders",
    traceId: `comms-hub-${Date.now()}`,
  };
}

// ─── UUID v4 helper ───────────────────────────────────────────────────────────

function uuidv4(): string {
  return crypto.randomUUID();
}

// ─── Date helpers ─────────────────────────────────────────────────────────────

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function addHours(date: Date, hours: number): Date {
  return new Date(date.getTime() + hours * 60 * 60 * 1000);
}

function addDays(date: Date, days: number): Date {
  return new Date(date.getTime() + days * 24 * 60 * 60 * 1000);
}

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0, 0);
}

function endOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999);
}

// ─── Message templates ────────────────────────────────────────────────────────

/**
 * appointment_reminder_48h — email + sms
 * Sent 48 hours before the appointment.
 */
function buildAppointmentReminder48h(params: {
  firstName: string;
  appointmentType: string;
  date: string;
  time: string;
  location: string;
}): { subject: string; body: string } {
  const clinic = getClinicConfig();
  const { firstName, appointmentType, date, time, location } = params;
  return {
    subject: `Your appointment is in 2 days — ${clinic.name}`,
    body:
      `Hi ${firstName}, just a reminder your ${appointmentType} appointment is scheduled for ` +
      `${date} at ${time} at ${location}. ` +
      `Reply CONFIRM to confirm or RESCHEDULE to change. See you soon!`,
  };
}

/**
 * appointment_reminder_2h — sms only
 * Sent 2 hours before the appointment.
 */
function buildAppointmentReminder2h(params: {
  firstName: string;
  appointmentType: string;
  location: string;
}): { body: string } {
  const { firstName, appointmentType, location } = params;
  return {
    body:
      `Hi ${firstName}! Your ${appointmentType} appointment is in 2 hours at ${location}. ` +
      `We look forward to seeing you. Reply HELP if you need assistance.`,
  };
}

/**
 * post_op_day1 — email + sms
 * Sent the day after a surgery.
 */
function buildPostOpDay1(params: { firstName: string }): { subject: string; body: string } {
  const clinic = getClinicConfig();
  const { firstName } = params;
  return {
    subject: `How are you feeling? — ${clinic.name}`,
    body:
      `Hi ${firstName}, we hope your recovery is going well after yesterday's procedure.\n` +
      `Some swelling and mild discomfort is normal. Take your prescribed medications as directed.\n` +
      `Call us at ${clinic.phone} if you have any concerns — we're here for you.`,
  };
}

/**
 * post_op_day7 — email + sms
 * Sent 7 days after a surgery.
 */
function buildPostOpDay7(params: {
  firstName: string;
  followUpDate: string;
}): { subject: string; body: string } {
  const clinic = getClinicConfig();
  const { firstName, followUpDate } = params;
  return {
    subject: `One-week check-in — ${clinic.name}`,
    body:
      `Hi ${firstName}, it's been one week since your procedure. ` +
      `Most patients feel significantly better by now. ` +
      `Your follow-up appointment is scheduled for ${followUpDate}. See you then!`,
  };
}

/**
 * treatment_plan_nudge — email + sms
 * Uses TreatmentCoordinator followUp draft when available, falls back to generic.
 */
function buildTreatmentPlanNudge(params: {
  firstName: string;
  coveragePct: number;
  hasFinancing: boolean;
  monthlyPayment?: number;
  followUpDraftBody?: string;
  followUpDraftSubject?: string;
}): { subject: string; body: string } {
  const clinic = getClinicConfig();
  const { firstName, coveragePct, hasFinancing, monthlyPayment, followUpDraftBody, followUpDraftSubject } = params;

  // Use TreatmentCoordinator follow-up draft if available
  if (followUpDraftBody && followUpDraftSubject) {
    return { subject: followUpDraftSubject, body: followUpDraftBody };
  }

  // Generic fallback template
  const insuranceLine =
    coveragePct > 0
      ? `Your insurance covers ${coveragePct}% of your treatment, significantly reducing your out-of-pocket cost.`
      : "";

  const financingLine = hasFinancing
    ? `Flexible payment options start at ${
        monthlyPayment !== undefined ? `$${monthlyPayment}/month` : "affordable monthly payments"
      } to help make your treatment accessible.`
    : "";

  const middleLines = [insuranceLine, financingLine].filter(Boolean).join("\n");

  return {
    subject: `Your treatment plan is waiting — ${clinic.name}`,
    body:
      `Hi ${firstName}, your personalized All-on-4 treatment plan is ready.\n` +
      (middleLines ? middleLines + "\n" : "") +
      `Ready to smile again? Call ${clinic.phone} or reply to schedule.`,
  };
}

/**
 * payment_plan_reminder — sms only
 * Sent when a payment is due within 3 days.
 */
function buildPaymentPlanReminder(params: {
  firstName: string;
  amount: number;
  dueDate: string;
}): { body: string } {
  const clinic = getClinicConfig();
  const { firstName, amount, dueDate } = params;
  return {
    body:
      `Hi ${firstName}, your payment of $${amount.toFixed(2)} is due on ${dueDate}. ` +
      `Pay online at ${clinic.portalUrl} or call ${clinic.phone}. Thank you!`,
  };
}

/**
 * recall_6month — email + sms
 * Sent when it has been approximately 6 months since the patient's last visit.
 */
function buildRecall6month(params: { firstName: string }): { subject: string; body: string } {
  const clinic = getClinicConfig();
  const { firstName } = params;
  return {
    subject: `Time for your 6-month check-up — ${clinic.name}`,
    body:
      `Hi ${firstName}, it's been 6 months since your last visit.\n` +
      `Regular check-ups keep your implants healthy for life.\n` +
      `Schedule online at ${clinic.portalUrl} or call ${clinic.phone}.`,
  };
}

/**
 * birthday_greeting — email + sms
 * Sent on the patient's birthday.
 */
function buildBirthdayGreeting(params: { firstName: string }): { subject: string; body: string } {
  const clinic = getClinicConfig();
  const { firstName } = params;
  return {
    subject: `Happy Birthday from ${clinic.name}!`,
    body:
      `Hi ${firstName}, wishing you a wonderful birthday!\n` +
      `As our gift to you, your next cleaning is complimentary. Call ${clinic.phone} to schedule.`,
  };
}

// ─── Message factory ──────────────────────────────────────────────────────────

/**
 * Create a PatientMessage with a new UUID, setting status to 'scheduled'.
 */
function createMessage(params: {
  patientId: string;
  trigger: CommunicationTrigger;
  channel: CommunicationChannel;
  subject?: string;
  body: string;
  scheduledAt: Date;
}): PatientMessage {
  return {
    messageId: uuidv4(),
    patientId: params.patientId,
    trigger: params.trigger,
    channel: params.channel,
    ...(params.subject !== undefined && { subject: params.subject }),
    body: params.body,
    scheduledAt: params.scheduledAt.toISOString(),
    status: "scheduled",
  };
}

// ─── Queue writer ─────────────────────────────────────────────────────────────

/**
 * Append messages to the NDJSON queue file (append-only).
 * Creates the file and parent directories if they do not exist.
 */
function appendToQueue(messages: PatientMessage[]): void {
  if (messages.length === 0) return;
  const dir = path.dirname(QUEUE_PATH);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  const lines = messages.map((m) => JSON.stringify(m)).join("\n") + "\n";
  fs.appendFileSync(QUEUE_PATH, lines, "utf-8");
}

// ─── Format helpers ───────────────────────────────────────────────────────────

function formatDate(d: Date): string {
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function formatTime(d: Date): string {
  return d.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

// ─── Main runner ──────────────────────────────────────────────────────────────

/**
 * Primary entry point for the Communication Hub nightly job.
 *
 * Fetches patient data from the tenant adapter, builds and schedules all
 * appropriate messages, writes them to the NDJSON queue, ingests to the wiki,
 * and appends an audit log line.
 *
 * @param tenantId  The canonical tenant UUID. Must be registered in adapterRegistry.
 * @returns         A CommunicationReport summarising every scheduled message.
 */
export async function runCommunicationHub(tenantId: string): Promise<CommunicationReport> {
  const adapter = adapterRegistry.getAdapter(tenantId);
  const phiCtx = buildPhiContext(tenantId);
  const now = new Date();

  const scheduledMessages: PatientMessage[] = [];

  // ── 1. Appointment reminders ───────────────────────────────────────────────
  //
  // Fetch all appointments in the next 48 hours. For each appointment:
  //   - Schedule appointment_reminder_48h if the appointment is 46–50 h away
  //     (i.e. this run is the closest nightly pass to "48 h before").
  //   - Schedule appointment_reminder_2h if the appointment is within the next 2–4 h.

  const apptWindowEnd = addHours(now, 50);
  const upcomingAppts = await adapter.listAppointments({
    dateFrom: now,
    dateTo: apptWindowEnd,
    status: "scheduled",
  }).catch(() => []);

  // Also include confirmed appointments in the window
  const upcomingConfirmed = await adapter.listAppointments({
    dateFrom: now,
    dateTo: apptWindowEnd,
    status: "confirmed",
  }).catch(() => []);

  const allUpcoming = [...upcomingAppts, ...upcomingConfirmed];

  for (const appt of allUpcoming) {
    const apptTime = new Date(appt.startTime);
    const hoursUntil = (apptTime.getTime() - now.getTime()) / (1000 * 60 * 60);
    const patient = await adapter.getPatient(appt.personUid, phiCtx).catch(() => null);
    const firstName = patient?.firstName ?? "there";
    const location = appt.locationName ?? "[LOCATION]";
    const appointmentType = appt.appointmentType.replace(/_/g, " ");

    if (hoursUntil >= 46 && hoursUntil <= 50) {
      // 48-hour reminder
      const tmpl = buildAppointmentReminder48h({
        firstName,
        appointmentType,
        date: formatDate(apptTime),
        time: formatTime(apptTime),
        location,
      });
      scheduledMessages.push(
        createMessage({
          patientId: appt.personUid,
          trigger: "appointment_reminder_48h",
          channel: "both",
          subject: tmpl.subject,
          body: tmpl.body,
          scheduledAt: now,
        }),
      );
    }

    if (hoursUntil >= 1.5 && hoursUntil <= 4) {
      // 2-hour reminder — SMS only
      const tmpl = buildAppointmentReminder2h({ firstName, appointmentType, location });
      scheduledMessages.push(
        createMessage({
          patientId: appt.personUid,
          trigger: "appointment_reminder_2h",
          channel: "sms",
          body: tmpl.body,
          scheduledAt: addHours(apptTime, -2),
        }),
      );
    }
  }

  // ── 2. Post-op day 1 ──────────────────────────────────────────────────────
  //
  // Fetch surgery/post_op appointments from yesterday that are completed.

  const yesterdayStart = startOfDay(addDays(now, -1));
  const yesterdayEnd = endOfDay(addDays(now, -1));

  const yesterdaySurgeries = await adapter.listAppointments({
    dateFrom: yesterdayStart,
    dateTo: yesterdayEnd,
    status: "completed",
  }).catch(() => []);

  for (const appt of yesterdaySurgeries) {
    if (appt.appointmentType !== "surgery" && appt.appointmentType !== "post_op") continue;

    const patient = await adapter.getPatient(appt.personUid, phiCtx).catch(() => null);
    const firstName = patient?.firstName ?? "there";
    const tmpl = buildPostOpDay1({ firstName });
    scheduledMessages.push(
      createMessage({
        patientId: appt.personUid,
        trigger: "post_op_day1",
        channel: "both",
        subject: tmpl.subject,
        body: tmpl.body,
        scheduledAt: now,
      }),
    );
  }

  // ── 3. Post-op day 7 ──────────────────────────────────────────────────────
  //
  // Fetch surgery appointments from 7 days ago that are completed.

  const sevenDaysAgoStart = startOfDay(addDays(now, -7));
  const sevenDaysAgoEnd = endOfDay(addDays(now, -7));

  const weekAgoSurgeries = await adapter.listAppointments({
    dateFrom: sevenDaysAgoStart,
    dateTo: sevenDaysAgoEnd,
    status: "completed",
  }).catch(() => []);

  for (const appt of weekAgoSurgeries) {
    if (appt.appointmentType !== "surgery") continue;

    const patient = await adapter.getPatient(appt.personUid, phiCtx).catch(() => null);
    const firstName = patient?.firstName ?? "there";

    // Look for a follow-up appointment to mention
    const followUps = await adapter.listAppointments({
      personUid: appt.personUid,
      dateFrom: now,
    }).catch(() => []);
    const followUpAppt = followUps.find(
      (a) => a.appointmentType === "post_op" || a.appointmentType === "maintenance",
    );
    const followUpDate = followUpAppt
      ? formatDate(new Date(followUpAppt.startTime))
      : "[FOLLOWUP_DATE]";

    const tmpl = buildPostOpDay7({ firstName, followUpDate });
    scheduledMessages.push(
      createMessage({
        patientId: appt.personUid,
        trigger: "post_op_day7",
        channel: "both",
        subject: tmpl.subject,
        body: tmpl.body,
        scheduledAt: now,
      }),
    );
  }

  // ── 4. Treatment plan nudges ──────────────────────────────────────────────
  //
  // Run TreatmentCoordinator and schedule nudges for high-priority patients.

  let coordinatorReport;
  try {
    coordinatorReport = await runTreatmentCoordinator(tenantId);
  } catch (err) {
    console.warn("[CommunicationHub] TreatmentCoordinator run failed:", String(err));
  }

  const highPriorityPatients = coordinatorReport?.highPriority ?? [];

  for (const scored of highPriorityPatients) {
    const patient = await adapter.getPatient(scored.personUid, phiCtx).catch(() => null);
    const firstName = patient?.firstName ?? "there";

    const insuranceRecords = await adapter.getInsurance(scored.personUid, phiCtx).catch(() => []);
    const primaryInsurance = insuranceRecords.find((i) => i.insuranceType === "primary");
    const coveragePct = primaryInsurance?.coveragePercentage ?? 0;

    const financingPlans = await adapter.getFinancingPlans(scored.personUid, phiCtx).catch(() => []);
    const approvedFinancing = financingPlans.find((f) => f.applicationStatus === "approved");
    const hasFinancing = Boolean(approvedFinancing);

    const tmpl = buildTreatmentPlanNudge({
      firstName,
      coveragePct,
      hasFinancing,
      monthlyPayment: approvedFinancing?.monthlyPayment ?? undefined,
      followUpDraftBody: scored.followUp?.body,
      followUpDraftSubject: scored.followUp?.subject,
    });

    const sendInDays = scored.followUp?.sendInDays ?? 1;
    scheduledMessages.push(
      createMessage({
        patientId: scored.personUid,
        trigger: "treatment_plan_nudge",
        channel: "both",
        subject: tmpl.subject,
        body: tmpl.body,
        scheduledAt: addDays(now, sendInDays),
      }),
    );
  }

  // ── 5. Payment plan reminders ─────────────────────────────────────────────
  //
  // Fetch all patients; find those with an upcoming payment within 3 days.
  //
  // Payment due date is approximated from the first payment date + elapsed
  // months on in-house plans. Production systems would expose a dedicated
  // next-payment endpoint.

  const pageSize = 200;
  let cursor: string | undefined;
  const allPersonUids: string[] = [];
  do {
    const page = await adapter.listPatients({ limit: pageSize, cursor });
    allPersonUids.push(...page.items.map((p) => p.personUid));
    cursor = page.nextCursor;
  } while (cursor);

  for (const personUid of allPersonUids) {
    try {
      const financingPlans = await adapter.getFinancingPlans(personUid, phiCtx).catch(() => []);
      for (const plan of financingPlans) {
        if (plan.applicationStatus !== "approved") continue;
        if (!plan.approvalDate || !plan.termMonths || !plan.monthlyPayment) continue;

        const approval = new Date(plan.approvalDate);
        const msPerMonth = 30.44 * 24 * 60 * 60 * 1000;
        const monthsElapsed = Math.floor((now.getTime() - approval.getTime()) / msPerMonth);

        if (monthsElapsed >= plan.termMonths) continue; // plan complete

        // Next payment date: first of the month following (monthsElapsed + 1) months
        const nextPayment = new Date(
          approval.getFullYear(),
          approval.getMonth() + monthsElapsed + 1,
          1,
        );

        const daysUntil = (nextPayment.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);
        if (daysUntil >= 0 && daysUntil <= 3) {
          const patient = await adapter.getPatient(personUid, phiCtx).catch(() => null);
          const firstName = patient?.firstName ?? "there";
          const dueDate = nextPayment.toLocaleDateString("en-US", {
            month: "long",
            day: "numeric",
            year: "numeric",
          });
          const tmpl = buildPaymentPlanReminder({
            firstName,
            amount: plan.monthlyPayment,
            dueDate,
          });
          scheduledMessages.push(
            createMessage({
              patientId: personUid,
              trigger: "payment_plan_reminder",
              channel: "sms",
              body: tmpl.body,
              scheduledAt: now,
            }),
          );
        }
      }
    } catch (err) {
      console.warn(`[CommunicationHub] Payment plan check failed for ${personUid}: ${String(err)}`);
    }
  }

  // ── 6. 6-month recall ─────────────────────────────────────────────────────
  //
  // Fetch patients whose last appointment was approximately 180 days ago
  // (170–190 day window to catch scheduling drift).

  const recall180Start = addDays(now, -190);
  const recall180End = addDays(now, -170);

  for (const personUid of allPersonUids) {
    try {
      const appts = await adapter.listAppointments({ personUid }).catch(() => []);
      const completedAppts = appts.filter((a) => a.status === "completed");
      if (completedAppts.length === 0) continue;

      const lastAppt = completedAppts.sort(
        (a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime(),
      )[0];

      const lastTime = new Date(lastAppt.startTime);
      if (lastTime >= recall180Start && lastTime <= recall180End) {
        // Check no upcoming appointment already booked
        const upcoming = await adapter.listAppointments({
          personUid,
          dateFrom: now,
        }).catch(() => []);

        if (upcoming.length > 0) continue; // already scheduled, skip recall

        const patient = await adapter.getPatient(personUid, phiCtx).catch(() => null);
        const firstName = patient?.firstName ?? "there";
        const tmpl = buildRecall6month({ firstName });
        scheduledMessages.push(
          createMessage({
            patientId: personUid,
            trigger: "recall_6month",
            channel: "both",
            subject: tmpl.subject,
            body: tmpl.body,
            scheduledAt: now,
          }),
        );
      }
    } catch (err) {
      console.warn(`[CommunicationHub] Recall check failed for ${personUid}: ${String(err)}`);
    }
  }

  // ── 7. Birthday greetings ─────────────────────────────────────────────────
  //
  // Fetch patients whose birthday matches today's month + day.

  for (const personUid of allPersonUids) {
    try {
      const patient = await adapter.getPatient(personUid, phiCtx).catch(() => null);
      if (!patient?.dateOfBirth) continue;

      const dob = new Date(patient.dateOfBirth);
      if (dob.getMonth() === now.getMonth() && dob.getDate() === now.getDate()) {
        const tmpl = buildBirthdayGreeting({ firstName: patient.firstName });
        scheduledMessages.push(
          createMessage({
            patientId: personUid,
            trigger: "birthday_greeting",
            channel: "both",
            subject: tmpl.subject,
            body: tmpl.body,
            scheduledAt: now,
          }),
        );
      }
    } catch (err) {
      console.warn(`[CommunicationHub] Birthday check failed for ${personUid}: ${String(err)}`);
    }
  }

  // ── 8. Build report ───────────────────────────────────────────────────────

  const runDate = now.toISOString();

  const messagesByTrigger: CommunicationReport["messagesByTrigger"] = {
    appointment_reminder_48h: 0,
    appointment_reminder_2h: 0,
    post_op_day1: 0,
    post_op_day7: 0,
    treatment_plan_nudge: 0,
    payment_plan_reminder: 0,
    recall_6month: 0,
    birthday_greeting: 0,
  };

  const byChannel: CommunicationReport["byChannel"] = {
    sms: 0,
    email: 0,
    both: 0,
  };

  for (const msg of scheduledMessages) {
    messagesByTrigger[msg.trigger]++;
    byChannel[msg.channel]++;
  }

  const report: CommunicationReport = {
    runDate,
    messagesScheduled: scheduledMessages.length,
    messagesByTrigger,
    byChannel,
    scheduledMessages,
  };

  // ── 9. Write to queue (NDJSON, append-only) ───────────────────────────────

  try {
    appendToQueue(scheduledMessages);
  } catch (err) {
    console.error("[CommunicationHub] Queue write failed:", String(err));
  }

  // ── 10. Wiki ingest (fire-and-forget) ─────────────────────────────────────

  void wikiService
    .ingest({
      type: "orchestration_cycle",
      sourceId: `comms-hub-${tenantId}-${runDate}`,
      agentName: "CommunicationHub",
      score: scheduledMessages.length,
    })
    .catch((err: Error) =>
      console.warn("[CommunicationHub] Wiki ingest error:", err.message),
    );

  // ── 11. Audit log ─────────────────────────────────────────────────────────

  const auditLine =
    `[${runDate}] [${tenantId}] CommunicationHub: ` +
    `${scheduledMessages.length} messages scheduled across ${Object.keys(messagesByTrigger).length} triggers\n`;

  try {
    const auditDir = path.dirname(AUDIT_LOG_PATH);
    if (!fs.existsSync(auditDir)) {
      fs.mkdirSync(auditDir, { recursive: true });
    }
    fs.appendFileSync(AUDIT_LOG_PATH, auditLine, "utf-8");
  } catch (err) {
    console.error("[CommunicationHub] Audit log write failed:", String(err));
  }

  return report;
}
