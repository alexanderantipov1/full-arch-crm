// A/B testing engine. Runs two variants of an agent (control vs. a challenger
// with an extra prompt instruction) against the same synthetic patient cohort
// and auto-selects a winner from average score and conversion rate. All data is
// synthetic — no real PHI flows through this module.

import { randomUUID } from "crypto";
import { generatePatients } from "./patients";
import { runAgentWithPromptAddition } from "./agents";
import type { SimPatient, SimEpisode, SimScenario } from "./types";

export interface AgentVariant {
  id: string;
  name: string;
  baseAgent: string;
  promptAddition: string;
  description: string;
}

export interface ABTestConfig {
  id: string;
  name: string;
  baseAgentName: string;
  variantA: AgentVariant; // control — empty promptAddition
  variantB: AgentVariant; // challenger — with promptAddition
  patientCount: number;
  scenarios: SimScenario[];
  status: "pending" | "running" | "complete" | "error";
  createdAt: string;
  error?: string;
}

export interface ABTestResult {
  testId: string;
  variantAAvgScore: number;
  variantBAvgScore: number;
  variantAConversionRate: number;
  variantBConversionRate: number;
  variantAEpisodeCount: number;
  variantBEpisodeCount: number;
  winner: "A" | "B" | "tie";
  improvement: number;
  confidence: "low" | "medium" | "high";
  recommendation: string;
  completedAt: string;
}

export interface ABSuite {
  tests: ABTestConfig[];
  results: Map<string, ABTestResult>;
  promotedVariants: AgentVariant[];
}

export class ABTestingEngine {
  private tests: ABTestConfig[] = [];
  private results = new Map<string, ABTestResult>();
  private promotedVariants: AgentVariant[] = [];

  createTest(input: {
    name: string;
    baseAgentName: string;
    variantBDescription: string;
    variantBPromptAddition: string;
    patientCount?: number;
    scenarios?: SimScenario[];
  }): ABTestConfig {
    const variantA: AgentVariant = {
      id: randomUUID(),
      name: `${input.baseAgentName}_control`,
      baseAgent: input.baseAgentName,
      promptAddition: "",
      description: "Original agent prompt (control)",
    };
    const variantB: AgentVariant = {
      id: randomUUID(),
      name: `${input.baseAgentName}_challenger`,
      baseAgent: input.baseAgentName,
      promptAddition: input.variantBPromptAddition,
      description: input.variantBDescription,
    };
    const test: ABTestConfig = {
      id: randomUUID(),
      name: input.name,
      baseAgentName: input.baseAgentName,
      variantA,
      variantB,
      patientCount: input.patientCount ?? 20,
      scenarios: input.scenarios ?? [],
      status: "pending",
      createdAt: new Date().toISOString(),
    };
    this.tests.push(test);
    return test;
  }

  async runTest(testId: string): Promise<ABTestResult> {
    const test = this.tests.find((t) => t.id === testId);
    if (!test) throw new Error(`Test ${testId} not found`);
    test.status = "running";

    try {
      const patients = generatePatients(test.patientCount);
      const cohort =
        test.scenarios.length > 0
          ? patients.filter((p) => test.scenarios.includes(p.scenario))
          : patients;
      const finalCohort = cohort.length > 0 ? cohort : patients;

      // Run both variants against the same cohort in parallel.
      const [variantAEps, variantBEps] = await Promise.all([
        this.runVariantEpisodes(test.variantA, finalCohort),
        this.runVariantEpisodes(test.variantB, finalCohort),
      ]);

      const successOutcomes = ["converted", "scheduled", "recalled", "recovered"];
      const avgA =
        variantAEps.reduce((s, e) => s + e.score, 0) /
        Math.max(1, variantAEps.length);
      const avgB =
        variantBEps.reduce((s, e) => s + e.score, 0) /
        Math.max(1, variantBEps.length);
      const convA =
        variantAEps.filter((e) => successOutcomes.includes(e.outcome)).length /
        Math.max(1, variantAEps.length);
      const convB =
        variantBEps.filter((e) => successOutcomes.includes(e.outcome)).length /
        Math.max(1, variantBEps.length);

      const scoreDiff = avgB - avgA;
      const improvement = avgA > 0 ? (Math.abs(scoreDiff) / avgA) * 100 : 0;
      const winner: "A" | "B" | "tie" =
        Math.abs(scoreDiff) < 2 ? "tie" : scoreDiff > 0 ? "B" : "A";
      const confidence: "low" | "medium" | "high" =
        finalCohort.length < 5 ? "low" : finalCohort.length < 15 ? "medium" : "high";

      const recommendation =
        winner === "tie"
          ? `No significant difference (Δ${scoreDiff.toFixed(1)} pts) — keep original prompt`
          : winner === "B"
            ? `Variant B wins by ${improvement.toFixed(1)}% — promote: "${test.variantB.description}"`
            : `Variant A wins — revert to original prompt for ${test.baseAgentName}`;

      const result: ABTestResult = {
        testId,
        variantAAvgScore: avgA,
        variantBAvgScore: avgB,
        variantAConversionRate: convA,
        variantBConversionRate: convB,
        variantAEpisodeCount: variantAEps.length,
        variantBEpisodeCount: variantBEps.length,
        winner,
        improvement,
        confidence,
        recommendation,
        completedAt: new Date().toISOString(),
      };

      test.status = "complete";
      this.results.set(testId, result);

      if (winner === "B" && confidence === "high") {
        this.promotedVariants.push(test.variantB);
      }

      return result;
    } catch (err: any) {
      test.status = "error";
      test.error = String(err?.message ?? err);
      throw err;
    }
  }

  private async runVariantEpisodes(
    variant: AgentVariant,
    patients: SimPatient[],
  ): Promise<SimEpisode[]> {
    const episodes: SimEpisode[] = [];
    for (const patient of patients) {
      try {
        const ep = await runAgentWithPromptAddition(
          variant.baseAgent,
          patient,
          variant.promptAddition,
        );
        episodes.push({ ...ep, agentName: variant.name });
      } catch {
        // Skip a patient if the variant run fails; the rest of the cohort
        // still produces a usable sample.
      }
    }
    return episodes;
  }

  getTests(): ABTestConfig[] {
    return this.tests;
  }

  getResult(testId: string): ABTestResult | undefined {
    return this.results.get(testId);
  }

  getPromotedVariants(): AgentVariant[] {
    return this.promotedVariants;
  }

  getSuite() {
    return {
      tests: this.tests,
      results: Object.fromEntries(this.results),
      promotedVariants: this.promotedVariants,
    };
  }
}

export const abTestingEngine = new ABTestingEngine();
