// OrchestrationAgent: drives the simulation in autonomous cycles. Each cycle
// runs a batch, performs an AI-assisted self-check, decides the next action,
// and (when not stuck) auto-approves the strongest pending hypothesis. A loop
// keeps cycling until a target score is reached, a stop is requested, or a
// cycle cap is hit. Pairs with SelfCheckAgent (see ./self-check).

import { randomUUID } from "crypto";
import { askClaude } from "../services/ai";
import { simulationEngine } from "./engine";
import type { SimState } from "./types";

export interface OrchestrationCycle {
  id: string;
  cycleNumber: number;
  startedAt: Date;
  completedAt: Date | null;
  episodesThisCycle: number;
  avgScoreThisCycle: number;
  patternsExtracted: number;
  hypothesesGenerated: number;
  selfCheckPassed: boolean;
  nextAction: "continue" | "pause_for_review" | "apply_hypothesis" | "stop";
  reasoning: string;
}

export interface SelfCheckResult {
  passed: boolean;
  scoreImproving: boolean;
  stuckInLoop: boolean;
  hypothesesBacklogged: boolean;
  recommendedAction: string;
  issues: string[];
}

export class OrchestrationAgent {
  private cycleHistory: OrchestrationCycle[] = [];
  private isLooping = false;
  private targetScore = 85;

  async runCycle(patientCount = 20): Promise<OrchestrationCycle> {
    const startedAt = new Date();
    const state = await simulationEngine.runBatch(patientCount);
    const selfCheck = await this.selfCheck(state);
    const nextAction = this.decide(state, selfCheck);

    const cycle: OrchestrationCycle = {
      id: randomUUID(),
      cycleNumber: this.cycleHistory.length + 1,
      startedAt,
      completedAt: new Date(),
      episodesThisCycle: state.totalEpisodes,
      avgScoreThisCycle: state.avgScore,
      patternsExtracted: state.patterns.length,
      hypothesesGenerated: state.hypotheses.length,
      selfCheckPassed: selfCheck.passed,
      nextAction,
      reasoning: selfCheck.recommendedAction,
    };
    this.cycleHistory.push(cycle);

    // Auto-apply the next pending hypothesis each cycle (SimHypothesis has no
    // confidence field, so we take the most recently generated pending one).
    if (!selfCheck.stuckInLoop) {
      const top = state.hypotheses
        .filter((h) => h.status === "pending")
        .sort((a, b) => b.createdAt.localeCompare(a.createdAt))[0];
      if (top) simulationEngine.approveHypothesis(top.id);
    }

    return cycle;
  }

  async runLoop(options: {
    maxCycles?: number;
    targetScore?: number;
    patientCount?: number;
    onCycleComplete?: (cycle: OrchestrationCycle) => void;
  } = {}): Promise<{ cycles: OrchestrationCycle[]; stopReason: string }> {
    this.isLooping = true;
    const maxCycles = options.maxCycles ?? 30;
    this.targetScore = options.targetScore ?? 85;
    let stopReason = "max_cycles_reached";

    for (let i = 0; i < maxCycles && this.isLooping; i++) {
      const cycle = await this.runCycle(options.patientCount ?? 20);
      options.onCycleComplete?.(cycle);

      if (cycle.nextAction === "stop") {
        stopReason = "orchestrator_stop";
        break;
      }
      if (simulationEngine.getState().avgScore >= this.targetScore) {
        stopReason = `target_score_${this.targetScore}_reached`;
        break;
      }
      await new Promise((r) => setTimeout(r, 300));
    }

    this.isLooping = false;
    return { cycles: this.cycleHistory, stopReason };
  }

  stopLoop(): void {
    this.isLooping = false;
  }

  getCycleHistory(): OrchestrationCycle[] {
    return this.cycleHistory;
  }

  isCurrentlyLooping(): boolean {
    return this.isLooping;
  }

  private async selfCheck(state: SimState): Promise<SelfCheckResult> {
    const issues: string[] = [];

    const scoreImproving =
      state.evolutions.length > 1
        ? state.evolutions[state.evolutions.length - 1].newScore >
          state.evolutions[0].baselineScore
        : state.avgScore > 50;

    const recent = this.cycleHistory.slice(-3);
    const stuckInLoop =
      recent.length >= 3 &&
      recent.every(
        (c) =>
          Math.abs(
            c.avgScoreThisCycle -
              (this.cycleHistory[this.cycleHistory.length - 1]
                ?.avgScoreThisCycle ?? 0),
          ) < 1.5,
      );

    const hypothesesBacklogged =
      state.hypotheses.filter((h) => h.status === "pending").length > 8;

    if (!scoreImproving) issues.push("Score plateau — hypothesis injection needed");
    if (stuckInLoop) issues.push("Stuck in loop — diversify scenarios");
    if (hypothesesBacklogged) issues.push("Hypothesis backlog >8 — flush pending queue");

    const prompt = `Dental AI CRM simulation self-check. score=${state.avgScore.toFixed(1)}, runs=${state.runCount}, patterns=${state.patterns.length}, pending_hypotheses=${state.hypotheses.filter((h) => h.status === "pending").length}, evolutions=${state.evolutions.length}, issues="${issues.join("; ") || "none"}". Respond JSON only: {"passed": boolean, "recommendedAction": "one sentence"}`;

    let recommendedAction = "Continue simulation loop";
    try {
      const raw = await askClaude(
        "You are an orchestration self-check assistant for a dental AI CRM simulation. All data is synthetic. Respond with JSON only.",
        prompt,
        300,
        { dataClass: "ops_safe", purpose: "simulation_self_check" },
      );
      const parsed = JSON.parse(raw.replace(/```json\n?|\n?```/g, "").trim());
      recommendedAction = parsed.recommendedAction ?? recommendedAction;
      return {
        passed: parsed.passed ?? true,
        scoreImproving,
        stuckInLoop,
        hypothesesBacklogged,
        recommendedAction,
        issues,
      };
    } catch {
      return {
        passed: !stuckInLoop,
        scoreImproving,
        stuckInLoop,
        hypothesesBacklogged,
        recommendedAction,
        issues,
      };
    }
  }

  private decide(
    state: SimState,
    selfCheck: SelfCheckResult,
  ): OrchestrationCycle["nextAction"] {
    if (selfCheck.stuckInLoop) return "pause_for_review";
    if (state.avgScore >= this.targetScore) return "stop";
    if (this.cycleHistory.length % 3 === 0 || selfCheck.hypothesesBacklogged)
      return "apply_hypothesis";
    return "continue";
  }
}

export const orchestrationAgent = new OrchestrationAgent();
