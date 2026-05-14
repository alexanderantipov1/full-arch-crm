import { z } from "zod";
import { askClaude } from "../../services/ai";
import { defineTool, ToolErrorCode } from "../types";

const probingToothSchema = z.object({
  missing: z.boolean().optional(),
  facialProbing: z.array(z.number()).optional(),
  lingualProbing: z.array(z.number()).optional(),
  facialBop: z.array(z.boolean()).optional(),
  lingualBop: z.array(z.boolean()).optional(),
});

const inputSchema = z.object({
  // Map of toothNumber → probing data. We accept unknown keys so the UI can
  // pass whatever tooth identifiers it's using.
  probingData: z.record(z.string(), probingToothSchema),
  patientName: z.string().optional(),
});

export type PerioAssessmentInput = z.infer<typeof inputSchema>;
export interface PerioAssessmentStats {
  avgDepth: string;
  bopPct: number;
  sitesGt4: number;
  sitesGt6: number;
  totalSites: number;
}
export interface PerioAssessmentOutput {
  assessment: string;
  stats: PerioAssessmentStats;
}

function calculateStats(probingData: PerioAssessmentInput["probingData"]): PerioAssessmentStats {
  const allDepths: number[] = [];
  let bopCount = 0;
  let totalSites = 0;
  let sitesGt4 = 0;
  let sitesGt6 = 0;
  for (const tooth of Object.values(probingData)) {
    if (tooth.missing) continue;
    const depths = [...(tooth.facialProbing ?? []), ...(tooth.lingualProbing ?? [])];
    const bops = [...(tooth.facialBop ?? []), ...(tooth.lingualBop ?? [])];
    for (const d of depths) {
      allDepths.push(d);
      totalSites++;
      if (d >= 4) sitesGt4++;
      if (d >= 6) sitesGt6++;
    }
    for (const b of bops) {
      if (b) bopCount++;
    }
  }
  const avgDepth = allDepths.length
    ? (allDepths.reduce((a, b) => a + b, 0) / allDepths.length).toFixed(1)
    : "0";
  const bopPct = totalSites ? Math.round((bopCount / totalSites) * 100) : 0;
  return { avgDepth, bopPct, sitesGt4, sitesGt6, totalSites };
}

export const perioAssessmentTool = defineTool<PerioAssessmentInput, PerioAssessmentOutput>({
  name: "perio.aiAssessment",
  description: "Generate a clinical periodontal assessment + CDT recommendations from a probing chart.",
  inputSchema,
  async handler(_ctx, input) {
    const stats = calculateStats(input.probingData);
    try {
      const assessment = await askClaude(
        "You are a periodontist generating a clinical AI assessment for a perio chart. Be concise, clinical, and specific. Include diagnosis, treatment recommendations (CDT codes D4341/D4342/D4910), and prognosis. Keep under 120 words.",
        `Patient: ${input.patientName ?? "(unnamed)"}. Avg probing: ${stats.avgDepth}mm. Sites ≥4mm: ${stats.sitesGt4}. Sites ≥6mm: ${stats.sitesGt6}. BOP: ${stats.bopPct}%. Generate a periodontal assessment and treatment plan.`,
        400,
      );
      return { ok: true, data: { assessment, stats } };
    } catch {
      return {
        ok: false,
        error: { code: ToolErrorCode.AiCallFailed, message: "Failed to generate AI assessment" },
      };
    }
  },
});
