/**
 * wiki_ingest — MCP tool that lets Claude Code (or any external agent)
 * push a new learning event into the Karpathy wiki.
 *
 * Use case: Claude Code notices something worth preserving (a new pattern,
 * a fix that worked, an agent decision outcome) and calls this tool to
 * write it into the wiki so it survives the session.
 *
 * All ingests are ops_safe — no PHI accepted.
 */

import { z } from "zod";
import { defineTool, ToolErrorCode } from "../types";
import { wikiService, type WikiIngestTrigger } from "../../simulation/wiki/wiki-service";

const EventTypeSchema = z.enum([
  // Clinical
  "EOB_APPROVED", "EOB_DENIED", "PRIOR_AUTH_APPROVED", "PRIOR_AUTH_DENIED",
  "TREATMENT_ACCEPTED", "TREATMENT_DECLINED", "APPOINTMENT_COMPLETED",
  "APPOINTMENT_NO_SHOW", "APPOINTMENT_CANCELLED",
  // System / AI
  "SIMULATION_BATCH_COMPLETE", "AGENT_DECISION", "ORCHESTRATION_CYCLE",
  "WIKI_LINT_COMPLETE", "ADAPTER_SYNC",
  // Dev / architectural (for Claude Code to document learnings)
  "CODE_FIX", "ARCHITECTURE_DECISION", "AGENT_LEARNING", "PATTERN_DISCOVERED",
]);

const inputSchema = z.object({
  eventType: EventTypeSchema.describe(
    "Category of the event being recorded. Use CODE_FIX / ARCHITECTURE_DECISION / " +
    "AGENT_LEARNING / PATTERN_DISCOVERED for development insights from Claude Code sessions."
  ),
  summary: z
    .string()
    .trim()
    .min(10)
    .describe(
      "Brief summary of what happened. This becomes the wiki entry headline. " +
      "Max 200 chars. Example: 'D6010 claim approved after adding prior auth documentation.'"
    )
    .max(500),
  details: z
    .string()
    .trim()
    .optional()
    .describe(
      "Extended details, pattern analysis, or code notes. Markdown supported. " +
      "No PHI — anonymized patterns and statistics only."
    ),
  targetPage: z
    .string()
    .optional()
    .describe(
      "Wiki page slug to target. If omitted, wikiService auto-routes based on eventType. " +
      "Examples: 'InsuranceAgent', 'ppo-d6010', 'all-on-4-protocol', 'AGENTS'"
    ),
  cdtCode: z.string().optional().describe("CDT code if applicable (e.g. D6010)"),
  payer:   z.string().optional().describe("Insurance payer if applicable (e.g. delta_dental)"),
  outcome: z.string().optional().describe("Outcome if applicable (e.g. approved, denied, converted)"),
});

export type WikiIngestInput  = z.infer<typeof inputSchema>;
export interface WikiIngestOutput {
  ingested: boolean;
  targetPage: string;
  entrySummary: string;
  timestamp: string;
}

// Map event types to target wiki pages when caller doesn't specify
const EVENT_PAGE_MAP: Partial<Record<z.infer<typeof EventTypeSchema>, string>> = {
  EOB_APPROVED:             "insurance/ppo-general",
  EOB_DENIED:               "insurance/appeals/ppo-d6010",
  PRIOR_AUTH_APPROVED:      "insurance/ppo-general",
  PRIOR_AUTH_DENIED:        "insurance/appeals/ppo-d6010",
  TREATMENT_ACCEPTED:       "patients/treatment-decline",
  TREATMENT_DECLINED:       "patients/treatment-decline",
  APPOINTMENT_COMPLETED:    "patients/implant-consult",
  APPOINTMENT_NO_SHOW:      "agents/SchedulingAgent",
  APPOINTMENT_CANCELLED:    "agents/SchedulingAgent",
  SIMULATION_BATCH_COMPLETE:"agents/PatientAcquisition",
  AGENT_DECISION:           "AGENTS",
  ORCHESTRATION_CYCLE:      "AGENTS",
  CODE_FIX:                 "AGENTS",
  ARCHITECTURE_DECISION:    "AGENTS",
  AGENT_LEARNING:           "AGENTS",
  PATTERN_DISCOVERED:       "AGENTS",
};

export const wikiIngestTool = defineTool<WikiIngestInput, WikiIngestOutput>({
  name: "wiki_ingest",
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  inputSchema: inputSchema as any,
  description:
    "Push a new event or learning into the full-arch-crm Karpathy wiki. " +
    "Use this after any significant clinical event, agent decision, simulation result, " +
    "or development discovery to preserve the pattern permanently in the wiki. " +
    "The wiki is the system's persistent memory — anything ingested here is available " +
    "to all agents in future sessions without re-explanation. " +
    "NEVER pass PHI (patient names, DOB, chart numbers). Anonymized patterns only.",

  async handler(_ctx, input) {
    try {
      const targetPage = input.targetPage ??
        EVENT_PAGE_MAP[input.eventType] ??
        "AGENTS";

      // Map MCP event type to WikiIngestTrigger type
      const triggerType: WikiIngestTrigger["type"] =
        input.eventType.startsWith("EOB_") || input.eventType.startsWith("PRIOR_AUTH_")
          ? "claim_resolved"
          : input.eventType.startsWith("APPOINTMENT_") || input.eventType.startsWith("TREATMENT_")
            ? "patient_visit"
            : input.eventType.startsWith("SIMULATION_")
              ? "simulation_batch"
              : "orchestration_cycle";

      const trigger: WikiIngestTrigger = {
        type:      triggerType,
        sourceId:  `mcp_${Date.now()}`,
        agentName: "MCP_Tool",
        ...(input.cdtCode && {
          claimData: {
            payerType: "ppo" as const,
            cdtCode:   input.cdtCode,
            outcome:   (input.outcome ?? "approved") as "approved" | "denied" | "appealed" | "paid",
          },
        }),
      };

      await wikiService.ingest(trigger);

      return {
        ok: true,
        data: {
          ingested:     true,
          targetPage,
          entrySummary: `[${input.eventType}] ${input.summary.slice(0, 120)}`,
          timestamp:    new Date().toISOString(),
        },
      };
    } catch (err: unknown) {
      return {
        ok: false,
        error: {
          code:    ToolErrorCode.Internal,
          message: err instanceof Error ? err.message : "Wiki ingest failed",
        },
      };
    }
  },
});
