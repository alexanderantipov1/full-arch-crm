// SelfCheckAgent: a watchdog that produces a health report for the simulation.
// It derives per-agent performance, score trajectory, and pattern quality from
// state + episodes, recommends interventions, and asks Claude for a short
// diagnosis. Consumed by GET /api/simulation/self-check and the dashboard.

import { askClaude } from "../services/ai";
import type { SimState } from "./types";

export type HealthLevel = "excellent" | "good" | "degraded" | "critical";
export type Trajectory = "improving" | "stable" | "declining";

export interface AgentHealthMetric {
  agentName: string;
  avgScore: number;
  successRate: number;
  health: "strong" | "average" | "weak";
}

export interface HealthReport {
  timestamp: Date;
  overallHealth: HealthLevel;
  scoreTrajectory: Trajectory;
  agentPerformance: AgentHealthMetric[];
  patternQuality: "rich" | "sparse" | "stale";
  recommendedInterventions: string[];
  aiAnalysis: string;
}

export class SelfCheckAgent {
  async analyze(state: SimState, allEpisodes: any[]): Promise<HealthReport> {
    // Per-agent metrics
    const agentMap = new Map<
      string,
      { scores: number[]; outcomes: string[] }
    >();
    for (const ep of allEpisodes) {
      if (!agentMap.has(ep.agentName)) {
        agentMap.set(ep.agentName, { scores: [], outcomes: [] });
      }
      const m = agentMap.get(ep.agentName)!;
      m.scores.push(ep.score);
      m.outcomes.push(ep.outcome);
    }

    const agentPerformance: AgentHealthMetric[] = Array.from(
      agentMap.entries(),
    ).map(([name, d]) => {
      const avg = d.scores.reduce((a, b) => a + b, 0) / (d.scores.length || 1);
      const successRate =
        d.outcomes.filter((o) =>
          ["converted", "scheduled", "recalled", "recovered"].includes(o),
        ).length / (d.outcomes.length || 1);
      return {
        agentName: name,
        avgScore: avg,
        successRate,
        health: avg >= 70 ? "strong" : avg >= 50 ? "average" : "weak",
      };
    });

    const evols = state.evolutions;
    const scoreTrajectory: Trajectory =
      evols.length < 2
        ? "stable"
        : evols[evols.length - 1].newScore > evols[0].baselineScore
          ? "improving"
          : "declining";

    const patternQuality =
      state.patterns.length >= 8
        ? "rich"
        : state.patterns.length >= 3
          ? "sparse"
          : "stale";

    const overallHealth: HealthLevel =
      state.avgScore >= 80 && scoreTrajectory === "improving"
        ? "excellent"
        : state.avgScore >= 65
          ? "good"
          : state.avgScore >= 45
            ? "degraded"
            : "critical";

    const interventions: string[] = [];
    if (overallHealth === "critical")
      interventions.push(
        "Inject high-value full-arch implant scenarios to reset baseline",
      );
    if (patternQuality === "stale")
      interventions.push(
        "Run 50-episode batch to generate sufficient pattern data",
      );
    if (scoreTrajectory === "declining")
      interventions.push(
        "Approve top-confidence hypothesis to reverse score decline",
      );
    agentPerformance
      .filter((a) => a.health === "weak")
      .forEach((a) =>
        interventions.push(
          `${a.agentName} underperforming (${a.avgScore.toFixed(0)}/100) — review agent prompts`,
        ),
      );
    if (interventions.length === 0)
      interventions.push("System healthy — maintain current loop cadence");

    const weakest = [...agentPerformance].sort(
      (a, b) => a.avgScore - b.avgScore,
    )[0];
    const prompt = `Dental CRM AI watchdog. score=${state.avgScore.toFixed(
      1,
    )}/100, trajectory=${scoreTrajectory}, weakest_agent=${
      weakest?.agentName ?? "none"
    }(${weakest?.avgScore.toFixed(0) ?? "n/a"}), patterns=${
      state.patterns.length
    }, evolutions=${evols.length}. In 2 sentences: diagnose and suggest the single most impactful fix.`;

    let aiAnalysis = "";
    try {
      aiAnalysis = await askClaude(
        "You are a watchdog for a dental AI CRM simulation. All data is synthetic. Be concise.",
        prompt,
        300,
        { dataClass: "ops_safe", purpose: "simulation_health_report" },
      );
    } catch {
      aiAnalysis = "AI analysis unavailable — metric-based assessment active.";
    }

    return {
      timestamp: new Date(),
      overallHealth,
      scoreTrajectory,
      agentPerformance,
      patternQuality,
      recommendedInterventions: interventions,
      aiAnalysis,
    };
  }
}

export const selfCheckAgent = new SelfCheckAgent();
