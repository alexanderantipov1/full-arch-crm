/**
 * wiki_query — MCP tool that lets Claude Code (or any agent) query the
 * Karpathy wiki with a natural-language question.
 *
 * Called by Claude Code at session start via:
 *   tools/call  { name: "wiki_query", arguments: { question: "What is the current state of full-arch-crm?" } }
 *
 * No PHI ever passes through — wiki is ops_safe data class only.
 */

import { z } from "zod";
import type { ZodType } from "zod";
import { defineTool, ToolErrorCode } from "../types";
import { wikiService } from "../../simulation/wiki/wiki-service";

const inputSchema = z.object({
  question: z
    .string()
    .trim()
    .min(3, "Question must be at least 3 characters")
    .describe(
      "Natural-language question to ask the wiki. Examples: " +
      '"What causes D6010 denials at Delta Dental?", ' +
      '"What is the current state of the simulation engine?", ' +
      '"What agent playbooks exist for patient recall?"'
    ),
  maxPages: z
    .number()
    .int()
    .min(1)
    .max(10)
    .optional()
    .default(3)
    .describe("Max wiki pages to search before synthesizing answer (default 3)"),
});

export type WikiQueryInput  = z.infer<typeof inputSchema>;
export interface WikiQueryOutput {
  answer:    string;
  sources:   string[];   // wiki page slugs that contributed
  confidence: "high" | "medium" | "low";
  dataClass: "ops_safe"; // always — never phi
}

export const wikiQueryTool = defineTool<WikiQueryInput, WikiQueryOutput>({
  name: "wiki_query",
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  inputSchema: inputSchema as any,
  description:
    "Query the full-arch-crm Karpathy wiki with a natural-language question. " +
    "Returns a synthesized answer grounded in the persistent wiki knowledge base " +
    "(patient scenario patterns, agent playbooks, insurance rules, clinical protocols). " +
    "Use this at session start to load system context, before clinical decisions, " +
    "and whenever you need to recall established patterns without re-reading raw files. " +
    "Data class is always ops_safe — no PHI is ever stored in the wiki.",

  async handler(_ctx, input) {
    try {
      const result = await wikiService.query({
        category: "agents",
        question: input.question,
        topK: input.maxPages,
      });

      // result has .answer from WikiQueryResult
      const answer = result?.answer ?? JSON.stringify(result);

      // Extract page slugs mentioned in the answer (heuristic: wiki page names)
      const wikiPageSlugs = [
        "implant-consult", "recall-overdue", "treatment-decline", "new-patient",
        "financial-barrier", "insurance-issue", "dso-referral", "emergency",
        "PatientAcquisition", "RecallAgent", "TreatmentPlanAgent", "InsuranceAgent",
        "SchedulingAgent", "FinancialCounselorAgent",
        "ppo-general", "delta-dental", "ppo-d6010", "all-on-4-protocol",
        "AGENTS", "index", "log",
      ];
      const sources = wikiPageSlugs.filter(slug =>
        answer.toLowerCase().includes(slug.toLowerCase())
      );

      const confidence: WikiQueryOutput["confidence"] =
        result.confidence === "high" ? "high" :
        result.confidence === "medium" ? "medium" : "low";

      return {
        ok: true,
        data: { answer, sources, confidence, dataClass: "ops_safe" as const },
      };
    } catch (err: unknown) {
      return {
        ok: false,
        error: {
          code:    ToolErrorCode.AiCallFailed,
          message: err instanceof Error ? err.message : "Wiki query failed",
        },
      };
    }
  },
});
