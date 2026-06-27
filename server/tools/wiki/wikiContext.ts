/**
 * wiki_context — The "Second Brain" session loader.
 *
 * This is the tool Claude Code calls FIRST at every session start.
 * It loads the full context of full-arch-crm — architecture, agents,
 * active work, known issues, decision principles — from the wiki vault.
 *
 * After calling this, Claude Code knows the entire system without
 * being given any session summary. This is the Karpathy Second Brain
 * pattern applied: the wiki IS the persistent session context.
 *
 * Usage in .mcp.json:
 *   "on_session_start": [{ "tool": "wiki_context", "args": {} }]
 */

import { z } from "zod";
import * as fs from "fs";
import * as path from "path";
import { defineTool, ToolErrorCode } from "../types";
import { wikiService } from "../../simulation/wiki/wiki-service";
import { rawSourceWriter } from "../../simulation/wiki/raw-source-writer";

const inputSchema = z.object({
  focus: z
    .enum(["full", "clinical", "agents", "insurance", "architecture", "active_work"])
    .optional()
    .default("full")
    .describe(
      "Which slice of context to load. " +
      "'full' = everything (recommended for session start). " +
      "'clinical' = patient scenarios + clinical protocols. " +
      "'agents' = agent playbooks + orchestration. " +
      "'insurance' = PPO rules + denial patterns. " +
      "'architecture' = AGENTS.md + adapter layer. " +
      "'active_work' = log.md + recent changes only."
    ),
  includeLog: z
    .boolean()
    .optional()
    .default(true)
    .describe("Include recent wiki log entries (last 20). Gives current operational pulse."),
});

export type WikiContextInput  = z.infer<typeof inputSchema>;
export interface WikiContextOutput {
  /** High-level system summary synthesized from wiki */
  systemContext:   string;
  /** Pages loaded, as { slug, wordCount } */
  pagesLoaded:     Array<{ slug: string; wordCount: number }>;
  /** Recent log entries (last 20) */
  recentLog:       string[];
  /** Key metrics extracted from wiki */
  keyMetrics:      Record<string, string>;
  /** Active work items the AI should know about */
  activeWork:      string[];
  totalWords:      number;
  dataClass:       "ops_safe";
  /** Karpathy compliance health (Rule I + VI) */
  karpathyHealth: {
    rawSourceCounts: Record<string, number>;
    orphanWarnings:  string[];
    wikilinkHealth:  "good" | "needs_links" | "unknown";
  };
}

// Wiki base directory
const WIKI_BASE = path.resolve(
  process.cwd(),
  "server/simulation/wiki"
);

// Pages to load per focus area
const FOCUS_PAGES: Record<string, string[]> = {
  full: [
    "AGENTS.md",
    "index.md",
    "patients/implant-consult.md",
    "patients/new-patient.md",
    "patients/financial-barrier.md",
    "patients/insurance-issue.md",
    "agents/InsuranceAgent.md",
    "agents/TreatmentPlanAgent.md",
    "agents/SchedulingAgent.md",
    "agents/FinancialCounselorAgent.md",
    "insurance/ppo-general.md",
    "insurance/delta-dental.md",
    "insurance/appeals/ppo-d6010.md",
    "clinical/all-on-4-protocol.md",
  ],
  clinical: [
    "patients/implant-consult.md",
    "patients/treatment-decline.md",
    "patients/financial-barrier.md",
    "patients/emergency.md",
    "clinical/all-on-4-protocol.md",
  ],
  agents: [
    "AGENTS.md",
    "agents/InsuranceAgent.md",
    "agents/TreatmentPlanAgent.md",
    "agents/SchedulingAgent.md",
    "agents/FinancialCounselorAgent.md",
    "agents/RecallAgent.md",
    "agents/PatientAcquisition.md",
  ],
  insurance: [
    "insurance/ppo-general.md",
    "insurance/delta-dental.md",
    "insurance/appeals/ppo-d6010.md",
    "patients/insurance-issue.md",
  ],
  architecture: [
    "AGENTS.md",
    "index.md",
  ],
  active_work: [
    "log.md",
    "index.md",
  ],
};

function readWikiPage(slug: string): string | null {
  const filePath = path.join(WIKI_BASE, slug);
  try {
    return fs.readFileSync(filePath, "utf-8");
  } catch {
    return null;
  }
}

function extractKeyMetrics(content: string): Record<string, string> {
  const metrics: Record<string, string> = {};
  // Extract percentage patterns
  const pctMatches = content.matchAll(/(\d+(?:\.\d+)?%)\s+(?:of|for|in|approval|acceptance|no.show|denial)/gi);
  for (const m of pctMatches) {
    const context = m.input?.slice(Math.max(0, m.index! - 30), m.index! + 60) ?? "";
    const key = context.replace(/\s+/g, "_").slice(0, 40);
    metrics[key] = m[1];
    if (Object.keys(metrics).length >= 8) break;
  }
  // Extract CDT code patterns
  const cdtMatches = content.matchAll(/D\d{4}\s*[:-]\s*(.{0,40})/g);
  for (const m of cdtMatches) {
    metrics[`CDT_${m[0].split(" ")[0]}`] = m[1].trim().slice(0, 40);
    if (Object.keys(metrics).length >= 12) break;
  }
  return metrics;
}

function extractActiveWork(agentsContent: string): string[] {
  const items: string[] = [];
  const lines = agentsContent.split("\n");
  let inActiveSection = false;
  for (const line of lines) {
    if (/active work|in progress|todo|current task/i.test(line)) {
      inActiveSection = true;
    }
    if (inActiveSection && line.startsWith("- ") || line.startsWith("* ")) {
      items.push(line.slice(2).trim());
      if (items.length >= 10) break;
    }
  }
  return items;
}

export const wikiContextTool = defineTool<WikiContextInput, WikiContextOutput>({
  name: "wiki_context",
  description:
    "CALL THIS FIRST AT EVERY SESSION START. " +
    "Loads the full-arch-crm Second Brain context from the Karpathy wiki vault. " +
    "Returns a synthesized system context, active work items, key metrics, and " +
    "recent operational log — everything needed to understand the current state " +
    "of the system without any manual session summary. " +
    "After calling this, you know: the architecture, all agent playbooks, " +
    "current insurance rules, active development work, and recent changes. " +
    "Focus='full' for session start. Focus='active_work' for quick pulse check. " +
    "Data class is always ops_safe — no PHI is in the wiki.",

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  inputSchema: inputSchema as any,

  async handler(_ctx, input) {
    try {
      const pageSlugs = FOCUS_PAGES[input.focus] ?? FOCUS_PAGES.full;
      const pagesLoaded: WikiContextOutput["pagesLoaded"] = [];
      const allContent: string[] = [];
      let keyMetrics: Record<string, string> = {};
      let activeWork: string[] = [];

      // Load each wiki page
      for (const slug of pageSlugs) {
        const content = readWikiPage(slug);
        if (content) {
          const wordCount = content.split(/\s+/).length;
          pagesLoaded.push({ slug, wordCount });
          allContent.push(`\n\n## Wiki: ${slug}\n${content}`);

          // Extract metrics from insurance pages
          if (slug.includes("ppo") || slug.includes("insurance")) {
            Object.assign(keyMetrics, extractKeyMetrics(content));
          }
          // Extract active work from AGENTS.md
          if (slug === "AGENTS.md") {
            activeWork = extractActiveWork(content);
          }
        }
      }

      // Load recent log entries
      const recentLog: string[] = [];
      if (input.includeLog) {
        const logContent = readWikiPage("log.md");
        if (logContent) {
          const logLines = logContent.split("\n").filter(l => l.trim().startsWith("- ") || l.trim().startsWith("*"));
          recentLog.push(...logLines.slice(-20).map(l => l.trim()));
        }
      }

      // Synthesize context via wiki query
      const contextQuestion =
        input.focus === "full"
          ? "Give me a concise executive summary of full-arch-crm: architecture, active development work, agent capabilities, and current system state."
          : `Give me a focused summary of the ${input.focus} aspects of full-arch-crm based on the current wiki.`;

      let systemContext: string;
      try {
        const queryResult = await wikiService.query({ category: "agents", question: contextQuestion });
        systemContext = queryResult?.answer ?? JSON.stringify(queryResult);
      } catch {
        // Fallback: concatenate page summaries
        systemContext = allContent
          .map(c => c.slice(0, 500))
          .join("\n---\n")
          .slice(0, 3000);
      }

      const totalWords = pagesLoaded.reduce((sum, p) => sum + p.wordCount, 0);

      // ── Karpathy compliance health check ────────────────────────────────
      const rawLint = rawSourceWriter.lint(180);
      // Check wikilink density across loaded pages
      const pagesWithSparseLinks = pagesLoaded.filter(p => {
        const filePath = path.join(WIKI_BASE, p.slug);
        const fullPath = filePath.endsWith('.md') ? filePath : filePath + '.md';
        try {
          const content = fs.readFileSync(fullPath, 'utf-8');
          const links = [...content.matchAll(/\[\[([^\]]+)\]\]/g)];
          return links.length < 3;
        } catch { return false; }
      });
      const wikilinkHealth = pagesWithSparseLinks.length === 0
        ? "good"
        : pagesWithSparseLinks.length < 5 ? "needs_links" : "needs_links";

      return {
        ok: true,
        data: {
          systemContext,
          pagesLoaded,
          recentLog,
          keyMetrics,
          activeWork: activeWork.length > 0 ? activeWork : [
            "DatabaseAdapter platform — PR #11 open",
            "Wiki seeding — 18 pages complete",
            "Karpathy compliance: raw/ layer + wikilinks — in progress",
            "MCP Second Brain — PR #13 open",
          ],
          totalWords,
          dataClass: "ops_safe" as const,
          karpathyHealth: {
            rawSourceCounts:  rawLint.categoryCounts,
            orphanWarnings:   rawLint.warnings,
            wikilinkHealth,
          },
        },
      };
    } catch (err: unknown) {
      return {
        ok: false,
        error: {
          code:    ToolErrorCode.Internal,
          message: err instanceof Error ? err.message : "Wiki context load failed",
        },
      };
    }
  },
});
