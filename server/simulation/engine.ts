// SimulationEngine: orchestrates patient generation, agent runs, learning, and
// self-improvement. State is persisted as JSON to server/simulation/state.json
// (no database, no migrations). A module-level singleton is exported for use by
// the route handlers.

import fs from "fs";
import path from "path";
import { generatePatients } from "./patients";
import { ALL_AGENTS } from "./agents";
import {
  applyEvolution,
  extractPatterns,
  generateHypotheses,
  scoreRun,
} from "./learning";
import type { SimEpisode, SimState } from "./types";
import { wikiService } from "./wiki/wiki-service";

const STATE_PATH = path.join(import.meta.dirname, "state.json");

function freshState(): SimState {
  return {
    runCount: 0,
    totalEpisodes: 0,
    avgScore: 0,
    totalRevenueSim: 0,
    patients: [],
    episodes: [],
    patterns: [],
    hypotheses: [],
    evolutions: [],
    lastRunAt: null,
    isRunning: false,
  };
}

export class SimulationEngine {
  private state: SimState;

  constructor() {
    this.state = this.loadState();
  }

  async runBatch(patientCount: number = 20): Promise<SimState> {
    this.state.isRunning = true;
    this.saveState();

    try {
      const patients = generatePatients(patientCount);
      const episodes: SimEpisode[] = [];

      for (const patient of patients) {
        for (const agent of ALL_AGENTS) {
          episodes.push(await agent.process(patient));
        }
      }

      const patterns = extractPatterns(episodes, patients);
      const hypotheses = generateHypotheses(patterns, this.state.evolutions);
      const runScore = scoreRun(episodes);
      const runRevenue = episodes.reduce(
        (acc, ep) => acc + ep.revenueImpact,
        0,
      );

      this.state.runCount += 1;
      this.state.patients = patients;
      this.state.episodes = episodes;
      this.state.patterns = patterns;
      // Keep still-pending hypotheses from prior runs alongside the new ones.
      const pendingPrior = this.state.hypotheses.filter(
        (h) => h.status === "pending" || h.status === "testing",
      );
      this.state.hypotheses = [...pendingPrior, ...hypotheses];
      this.state.totalEpisodes += episodes.length;
      this.state.totalRevenueSim += runRevenue;
      this.state.avgScore = runScore;
      this.state.lastRunAt = new Date().toISOString();

      // Karpathy wiki: ingest simulation batch results (fire-and-forget, non-blocking)
      const runState = this.state;
      void wikiService.ingest({
        type: 'simulation_batch',
        sourceId: `sim-batch-${runState.runCount}`,
        score: runState.avgScore,
        agentName: 'SimulationEngine',
        episodeIds: episodes.slice(0, 20).map((_, i) => `ep-${runState.runCount}-${i}`),
      }).catch((err: Error) => console.warn('[WikiService] ingest error (non-fatal):', err.message));

      return this.state;
    } finally {
      this.state.isRunning = false;
      this.saveState();
    }
  }

  async runContinuous(
    iterations: number = 5,
    delayMs: number = 1000,
  ): Promise<void> {
    for (let i = 0; i < iterations; i++) {
      await this.runBatch();
      if (i < iterations - 1 && delayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
    }
  }

  getState(): SimState {
    return this.state;
  }

  approveHypothesis(hypothesisId: string): SimState {
    const hypothesis = this.state.hypotheses.find(
      (h) => h.id === hypothesisId,
    );
    if (!hypothesis) return this.state;

    hypothesis.status = "approved";
    // Model the improvement: an approved change nudges the run score upward.
    const baselineScore = this.state.avgScore;
    const newScore = Math.min(100, Math.round((baselineScore + 5) * 100) / 100);
    const evolution = applyEvolution(hypothesis, baselineScore, newScore);
    this.state.evolutions.push(evolution);
    this.state.avgScore = newScore;

    this.saveState();
    return this.state;
  }

  rejectHypothesis(hypothesisId: string): SimState {
    const hypothesis = this.state.hypotheses.find(
      (h) => h.id === hypothesisId,
    );
    if (hypothesis) {
      hypothesis.status = "rejected";
      this.saveState();
    }
    return this.state;
  }

  resetState(): SimState {
    const runCount = this.state.runCount;
    this.state = freshState();
    this.state.runCount = runCount;
    this.saveState();
    return this.state;
  }

  private saveState(): void {
    try {
      fs.writeFileSync(
        STATE_PATH,
        JSON.stringify(this.state, null, 2),
        "utf-8",
      );
    } catch {
      // Persistence is best-effort; a write failure must not crash a run.
    }
  }

  private loadState(): SimState {
    try {
      if (fs.existsSync(STATE_PATH)) {
        const raw = fs.readFileSync(STATE_PATH, "utf-8");
        const parsed = JSON.parse(raw) as Partial<SimState>;
        return { ...freshState(), ...parsed, isRunning: false };
      }
    } catch {
      // Fall through to a fresh state on any read/parse error.
    }
    return freshState();
  }
}

export const simulationEngine = new SimulationEngine();
