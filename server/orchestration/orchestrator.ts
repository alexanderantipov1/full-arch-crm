/**
 * full-arch-crm — Master Agent Orchestration Loop
 * ─────────────────────────────────────────────────
 * Runs all AI agents sequentially every night and produces a unified
 * morning briefing formatted for Slack.
 *
 * Agent execution order:
 *   1. TreatmentCoordinator  — score patients + draft follow-ups
 *   2. CollectionsAgent      — flag past-due + auto-create payment plans
 *   3. SchedulingAgent       — optimize bookings + surface utilization
 *   4. FraudDetectionAgent   — detect anomalies (graceful skip if unavailable)
 *   5. CommunicationHub      — schedule patient messages (graceful skip if unavailable)
 *
 * Each agent is wrapped in try/catch so a single failure never blocks others.
 * After all agents run the orchestrator:
 *   - Assembles highlights (top findings) + actionRequired (items needing human review)
 *   - Ingests a learning event into the Karpathy wiki
 *   - Appends a one-line summary to the orchestrator audit log
 *
 * Usage:
 *   import { runOrchestrator, buildSlackBriefing } from "./orchestrator";
 *   const report = await runOrchestrator("tenant-uuid");
 *   const slackMsg = buildSlackBriefing(report);
 *
 * HIPAA note: No PHI is written to logs or wiki — only anonymised aggregate signals.
 */

import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";
import { runTreatmentCoordinator } from "../agents/treatment-coordinator";
import { runCollectionsAgent } from "../agents/collections-agent";
import { runSchedulingAgent } from "../agents/scheduling-agent";
import { wikiService } from "../simulation/wiki/wiki-service";
import type { CoordinatorReport } from "../agents/types";
import type { CollectionsReport } from "../agents/types";
import type { SchedulingReport } from "../agents/types";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUDIT_LOG_PATH = path.join(__dirname, "../audit/orchestrator.log");

// ─── Public interfaces ────────────────────────────────────────────────────────

export interface AgentRunResult {
  agentName: string;
  status: "success" | "failed" | "skipped";
  durationMs: number;
  /** One-line human-readable result */
  summary: string;
  error?: string;
}

export interface OrchestratorReport {
  runDate: string;
  tenantId: string;
  totalDurationMs: number;
  agents: AgentRunResult[];
  /** Top 3–5 most important findings across all agents */
  highlights: string[];
  /** Items needing human review today */
  actionRequired: string[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function appendAuditLog(line: string): void {
  try {
    const dir = path.dirname(AUDIT_LOG_PATH);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.appendFileSync(AUDIT_LOG_PATH, line + "\n", "utf8");
  } catch {
    // Never let an audit-log write crash the orchestrator
  }
}

/** Run an async agent function and return a typed AgentRunResult. */
async function runAgent<T>(
  agentName: string,
  fn: () => Promise<T>,
): Promise<{ result: AgentRunResult; data?: T }> {
  const start = Date.now();
  try {
    const data = await fn();
    const durationMs = Date.now() - start;
    return {
      result: { agentName, status: "success", durationMs, summary: "" },
      data,
    };
  } catch (err: unknown) {
    const durationMs = Date.now() - start;
    const error = err instanceof Error ? err.message : String(err);
    return {
      result: {
        agentName,
        status: "failed",
        durationMs,
        summary: "Agent failed — see error field",
        error,
      },
    };
  }
}

// ─── Optional agent dynamic imports ──────────────────────────────────────────
// FraudDetectionAgent and CommunicationHub live on separate feature branches.
// We attempt a dynamic import and gracefully skip if the module is absent.

interface FraudReport {
  fraudFlags: Array<{ patientId: string; reason: string; estimatedExposure: number }>;
  totalExposure: number;
}

interface CommsReport {
  scheduledMessages: number;
}

async function tryRunFraudAgent(
  tenantId: string,
): Promise<{ result: AgentRunResult; data?: FraudReport }> {
  const start = Date.now();
  try {
    // Dynamic import — succeeds only if branch is merged
    const mod = await import("../agents/fraud-detection-agent" as string);
    if (typeof mod.runFraudDetectionAgent !== "function") throw new Error("runFraudDetectionAgent not exported");
    const data: FraudReport = await mod.runFraudDetectionAgent(tenantId);
    const durationMs = Date.now() - start;
    const flagCount = data.fraudFlags?.length ?? 0;
    const exposure = data.totalExposure ?? 0;
    const summary = `${flagCount} fraud flag${flagCount !== 1 ? "s" : ""} raised, $${exposure.toLocaleString()} exposure`;
    return { result: { agentName: "FraudDetectionAgent", status: "success", durationMs, summary }, data };
  } catch {
    const durationMs = Date.now() - start;
    return {
      result: {
        agentName: "FraudDetectionAgent",
        status: "skipped",
        durationMs,
        summary: "Module not available — feature branch not merged",
      },
    };
  }
}

async function tryRunCommunicationHub(
  tenantId: string,
): Promise<{ result: AgentRunResult; data?: CommsReport }> {
  const start = Date.now();
  try {
    const mod = await import("../agents/communication-hub" as string);
    if (typeof mod.runCommunicationHub !== "function") throw new Error("runCommunicationHub not exported");
    const data: CommsReport = await mod.runCommunicationHub(tenantId);
    const durationMs = Date.now() - start;
    const msgCount = data.scheduledMessages ?? 0;
    const summary = `${msgCount} message${msgCount !== 1 ? "s" : ""} scheduled`;
    return { result: { agentName: "CommunicationHub", status: "success", durationMs, summary }, data };
  } catch {
    const durationMs = Date.now() - start;
    return {
      result: {
        agentName: "CommunicationHub",
        status: "skipped",
        durationMs,
        summary: "Module not available — feature branch not merged",
      },
    };
  }
}

// ─── Highlights & actionRequired builders ────────────────────────────────────

function buildHighlights(
  coordinator?: CoordinatorReport,
  collections?: CollectionsReport,
  scheduling?: SchedulingReport,
  fraud?: FraudReport,
  comms?: CommsReport,
): string[] {
  const highlights: string[] = [];

  if (coordinator) {
    const highCount = coordinator.highPriority?.length ?? 0;
    highlights.push(
      `${highCount} high-priority patient${highCount !== 1 ? "s" : ""} need outreach (TreatmentCoordinator)`,
    );
  }

  if (collections) {
    const atRisk = collections.totalOutstanding ?? 0;
    const plansCreated = (collections.cases ?? []).filter(
      (c: any) => c.recommendedAction === "payment_plan",
    ).length;
    highlights.push(
      `$${atRisk.toLocaleString()} at risk; ${plansCreated} payment plan${plansCreated !== 1 ? "s" : ""} auto-created (CollectionsAgent)`,
    );
  }

  if (scheduling) {
    const util = Math.round((scheduling.utilizationRate ?? 0) * 100);
    const bookings = scheduling.recommendedBookings?.length ?? 0;
    highlights.push(
      `Chair utilization at ${util}%; ${bookings} booking${bookings !== 1 ? "s" : ""} recommended (SchedulingAgent)`,
    );
  }

  if (fraud) {
    const flagCount = fraud.fraudFlags?.length ?? 0;
    const exposure = fraud.totalExposure ?? 0;
    highlights.push(
      `${flagCount} fraud flag${flagCount !== 1 ? "s" : ""} raised, $${exposure.toLocaleString()} exposure (FraudDetectionAgent)`,
    );
  }

  if (comms) {
    const msgCount = comms.scheduledMessages ?? 0;
    highlights.push(
      `${msgCount} patient message${msgCount !== 1 ? "s" : ""} scheduled (CommunicationHub)`,
    );
  }

  return highlights;
}

function buildActionRequired(
  coordinator?: CoordinatorReport,
  collections?: CollectionsReport,
  scheduling?: SchedulingReport,
  fraud?: FraudReport,
): string[] {
  const actions: string[] = [];

  // High-priority treatment patients
  if (coordinator) {
    const highCount = coordinator.highPriority?.length ?? 0;
    if (highCount > 0) {
      actions.push(
        `Review ${highCount} high-priority patient${highCount !== 1 ? "s" : ""} flagged by TreatmentCoordinator`,
      );
    }
  }

  // Past-due > 90 days
  if (collections) {
    const severe = (collections.cases ?? []).filter(
      (c: any) => (c.daysPastDue ?? 0) > 90,
    );
    if (severe.length > 0) {
      actions.push(
        `${severe.length} patient${severe.length !== 1 ? "s" : ""} with balance >90 days past due — review for collections referral`,
      );
    }
    const referrals = (collections.cases ?? []).filter(
      (c: any) => c.recommendedAction === "collections_referral",
    );
    if (referrals.length > 0) {
      actions.push(
        `${referrals.length} case${referrals.length !== 1 ? "s" : ""} ready for external collections referral`,
      );
    }
  }

  // Scheduling bottlenecks / broken appointments
  if (scheduling) {
    const bottlenecks = scheduling.bottlenecks ?? [];
    if (bottlenecks.length > 0) {
      actions.push(`Scheduling bottlenecks detected: ${bottlenecks.slice(0, 3).join("; ")}`);
    }
  }

  // Fraud flags always require human review
  if (fraud) {
    const flagCount = fraud.fraudFlags?.length ?? 0;
    if (flagCount > 0) {
      actions.push(
        `URGENT: ${flagCount} fraud flag${flagCount !== 1 ? "s" : ""} require immediate human review`,
      );
    }
  }

  return actions;
}

// ─── Main orchestrator ────────────────────────────────────────────────────────

/**
 * Run all agents in sequence and return a unified OrchestratorReport.
 * One failed agent never blocks the rest.
 */
export async function runOrchestrator(tenantId: string): Promise<OrchestratorReport> {
  const orchestratorStart = Date.now();
  const runDate = new Date().toISOString();

  const agentResults: AgentRunResult[] = [];

  // 1. TreatmentCoordinator
  let coordinatorData: CoordinatorReport | undefined;
  {
    const { result, data } = await runAgent("TreatmentCoordinator", () =>
      runTreatmentCoordinator(tenantId),
    );
    if (data) {
      coordinatorData = data;
      const highCount = data.highPriority?.length ?? 0;
      const total = data.totalPatients ?? 0;
      result.summary = `${total} patients scored; ${highCount} high-priority`;
    }
    agentResults.push(result);
  }

  // 2. CollectionsAgent
  let collectionsData: CollectionsReport | undefined;
  {
    const { result, data } = await runAgent("CollectionsAgent", () =>
      runCollectionsAgent(tenantId),
    );
    if (data) {
      collectionsData = data;
      const outstanding = data.totalOutstanding ?? 0;
      const plans = (data.cases ?? []).filter(
        (c: any) => c.recommendedAction === "payment_plan",
      ).length;
      result.summary = `$${outstanding.toLocaleString()} outstanding; ${plans} payment plans auto-created`;
    }
    agentResults.push(result);
  }

  // 3. SchedulingAgent
  let schedulingData: SchedulingReport | undefined;
  {
    const { result, data } = await runAgent("SchedulingAgent", () =>
      runSchedulingAgent(tenantId),
    );
    if (data) {
      schedulingData = data;
      const util = Math.round((data.utilizationRate ?? 0) * 100);
      const bookings = data.recommendedBookings?.length ?? 0;
      result.summary = `${util}% chair utilization; ${bookings} bookings recommended`;
    }
    agentResults.push(result);
  }

  // 4. FraudDetectionAgent (graceful skip)
  let fraudData: FraudReport | undefined;
  {
    const { result, data } = await tryRunFraudAgent(tenantId);
    fraudData = data;
    agentResults.push(result);
  }

  // 5. CommunicationHub (graceful skip)
  let commsData: CommsReport | undefined;
  {
    const { result, data } = await tryRunCommunicationHub(tenantId);
    commsData = data;
    agentResults.push(result);
  }

  // ── Assemble report ──────────────────────────────────────────────────────
  const totalDurationMs = Date.now() - orchestratorStart;

  const highlights = buildHighlights(
    coordinatorData,
    collectionsData,
    schedulingData,
    fraudData,
    commsData,
  );

  const actionRequired = buildActionRequired(
    coordinatorData,
    collectionsData,
    schedulingData,
    fraudData,
  );

  const report: OrchestratorReport = {
    runDate,
    tenantId,
    totalDurationMs,
    agents: agentResults,
    highlights,
    actionRequired,
  };

  // ── Wiki ingest ──────────────────────────────────────────────────────────
  try {
    const agentStatuses = agentResults
      .map((a) => `${a.agentName}=${a.status}`)
      .join(", ");
    await wikiService.ingest({
      eventType: "AGENT_LEARNING",
      summary: `Nightly orchestration completed for tenant ${tenantId}. ` +
        `Agents: ${agentStatuses}. ` +
        `Highlights: ${highlights.join(" | ")}`,
      targetPage: "AGENTS",
    });
  } catch {
    // Wiki ingest failure must not abort the report
  }

  // ── Audit log ────────────────────────────────────────────────────────────
  const succeeded = agentResults.filter((a) => a.status === "success").length;
  const failed = agentResults.filter((a) => a.status === "failed").length;
  const skipped = agentResults.filter((a) => a.status === "skipped").length;
  appendAuditLog(
    `${runDate} [ORCHESTRATOR] tenant=${tenantId} ` +
    `durationMs=${totalDurationMs} ` +
    `agents_ok=${succeeded} agents_failed=${failed} agents_skipped=${skipped} ` +
    `highlights=${highlights.length} actionRequired=${actionRequired.length}`,
  );

  return report;
}

// ─── Slack briefing formatter ─────────────────────────────────────────────────

const STATUS_ICON: Record<AgentRunResult["status"], string> = {
  success: "✅",
  failed: "❌",
  skipped: "⚠️",
};

/**
 * Format an OrchestratorReport as a rich Slack block-kit-compatible message string.
 */
export function buildSlackBriefing(report: OrchestratorReport): string {
  const date = new Date(report.runDate).toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const runTimeSec = (report.totalDurationMs / 1000).toFixed(1);

  // Header
  const lines: string[] = [
    `:sunrise: *FullArch CRM — Morning Briefing [${date}]*`,
    `*Tenant:* ${report.tenantId} | *Run time:* ${runTimeSec}s`,
    "",
  ];

  // Highlights
  lines.push("*Highlights*");
  if (report.highlights.length > 0) {
    for (const h of report.highlights) {
      lines.push(`• ${h}`);
    }
  } else {
    lines.push("• No highlights — all agents returned empty data");
  }
  lines.push("");

  // Action Required
  lines.push("*Action Required*");
  if (report.actionRequired.length > 0) {
    for (const a of report.actionRequired) {
      lines.push(`• ${a}`);
    }
  } else {
    lines.push("✅ Nothing urgent today");
  }
  lines.push("");

  // Agent Results
  lines.push("*Agent Results*");
  for (const agent of report.agents) {
    const icon = STATUS_ICON[agent.status];
    const durationStr = agent.durationMs < 1000
      ? `${agent.durationMs}ms`
      : `${(agent.durationMs / 1000).toFixed(1)}s`;
    const summaryText = agent.summary || agent.status;
    lines.push(`${icon} ${agent.agentName} — ${summaryText} (${durationStr})`);
    if (agent.status === "failed" && agent.error) {
      lines.push(`   _Error: ${agent.error.slice(0, 120)}_`);
    }
  }
  lines.push("");

  lines.push("_Next run: tomorrow at 11pm PDT_");

  return lines.join("\n");
}
