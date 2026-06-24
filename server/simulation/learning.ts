// Pattern extraction, hypothesis generation, and evolution tracking for the
// self-improvement loop. All pure functions over episode/patient data.

import type {
  SimConfidence,
  SimEpisode,
  SimEvolution,
  SimHypothesis,
  SimOutcome,
  SimPattern,
  SimPatient,
} from "./types";

const SUCCESS_OUTCOMES: SimOutcome[] = ["converted", "scheduled", "referred"];

function isSuccess(outcome: SimOutcome): boolean {
  return SUCCESS_OUTCOMES.includes(outcome);
}

function confidenceFor(sampleSize: number): SimConfidence {
  if (sampleSize >= 8) return "high";
  if (sampleSize >= 4) return "medium";
  return "low";
}

let patternCounter = 0;
let hypothesisCounter = 0;
let evolutionCounter = 0;

// Group episodes by agentName + patient scenario, then compute success rate
// and average revenue per group. Produces one pattern per active group.
export function extractPatterns(
  episodes: SimEpisode[],
  patients: SimPatient[],
): SimPattern[] {
  const scenarioById = new Map(patients.map((p) => [p.id, p.scenario]));

  interface Bucket {
    agentName: string;
    scenario: string;
    successes: number;
    total: number;
    revenueSum: number;
  }

  const buckets = new Map<string, Bucket>();

  for (const ep of episodes) {
    const scenario = scenarioById.get(ep.patientId) ?? "unknown";
    const key = `${ep.agentName}::${scenario}`;
    let bucket = buckets.get(key);
    if (!bucket) {
      bucket = {
        agentName: ep.agentName,
        scenario,
        successes: 0,
        total: 0,
        revenueSum: 0,
      };
      buckets.set(key, bucket);
    }
    bucket.total += 1;
    bucket.revenueSum += ep.revenueImpact;
    if (isSuccess(ep.outcome)) bucket.successes += 1;
  }

  const patterns: SimPattern[] = [];
  // Most-sampled, then highest-converting groups first.
  const ranked = [...buckets.values()].sort(
    (a, b) =>
      b.total - a.total ||
      b.successes / b.total - a.successes / a.total,
  );

  for (const bucket of ranked.slice(0, 10)) {
    const successRate = bucket.total ? bucket.successes / bucket.total : 0;
    const avgRevenueImpact = bucket.total
      ? Math.round(bucket.revenueSum / bucket.total)
      : 0;
    const scenarioLabel = bucket.scenario.replace(/_/g, " ");
    patternCounter += 1;

    patterns.push({
      id: `pat-${Date.now()}-${patternCounter}`,
      name: `${bucket.agentName} × ${scenarioLabel}`,
      description: `${bucket.agentName} on ${scenarioLabel} cases converts ${Math.round(
        successRate * 100,
      )}% of the time across ${bucket.total} episodes.`,
      triggerConditions: [
        `scenario = ${bucket.scenario}`,
        `agent = ${bucket.agentName}`,
      ],
      successRate: Math.round(successRate * 100) / 100,
      avgRevenueImpact,
      sampleSize: bucket.total,
      confidence: confidenceFor(bucket.total),
    });
  }

  return patterns;
}

// Inspect underperforming patterns (successRate < 0.5) and propose changes.
// Skips proposals already represented by an existing evolution so the loop
// keeps advancing instead of re-suggesting implemented changes.
export function generateHypotheses(
  patterns: SimPattern[],
  evolutions: SimEvolution[],
): SimHypothesis[] {
  const implemented = new Set(evolutions.map((e) => e.change));
  const weak = patterns
    .filter((p) => p.successRate < 0.5)
    .sort((a, b) => a.successRate - b.successRate);

  const hypotheses: SimHypothesis[] = [];

  for (const pattern of weak) {
    if (hypotheses.length >= 5) break;
    const change = `Reassign or augment "${pattern.name}" handling`;
    if (implemented.has(change)) continue;
    hypothesisCounter += 1;

    hypotheses.push({
      id: `hyp-${Date.now()}-${hypothesisCounter}`,
      title: `Improve ${pattern.name} (${Math.round(
        pattern.successRate * 100,
      )}% success)`,
      rationale: `Pattern "${pattern.name}" underperforms at ${Math.round(
        pattern.successRate * 100,
      )}% success over ${pattern.sampleSize} episodes (${pattern.confidence} confidence), dragging revenue (avg $${pattern.avgRevenueImpact}).`,
      proposedChange: change,
      expectedImpact: `Target +${Math.max(
        10,
        Math.round((0.6 - pattern.successRate) * 100),
      )}pp success rate, lifting avg revenue impact above $${
        pattern.avgRevenueImpact + 250
      }.`,
      status: "pending",
      createdAt: new Date().toISOString(),
    });
  }

  // Guarantee at least 3 hypotheses per run when weak patterns are scarce by
  // proposing reinforcement of the strongest patterns.
  if (hypotheses.length < 3) {
    const strong = patterns
      .filter((p) => p.successRate >= 0.5)
      .sort((a, b) => b.successRate - a.successRate);
    for (const pattern of strong) {
      if (hypotheses.length >= 3) break;
      const change = `Scale up "${pattern.name}" as a playbook`;
      if (implemented.has(change)) continue;
      hypothesisCounter += 1;
      hypotheses.push({
        id: `hyp-${Date.now()}-${hypothesisCounter}`,
        title: `Scale ${pattern.name} (${Math.round(
          pattern.successRate * 100,
        )}% success)`,
        rationale: `"${pattern.name}" is a top performer at ${Math.round(
          pattern.successRate * 100,
        )}% success. Codifying it as a default playbook should raise overall run score.`,
        proposedChange: change,
        expectedImpact: `Broaden a proven pattern to adjacent scenarios; expect modest run-score lift with low risk.`,
        status: "pending",
        createdAt: new Date().toISOString(),
      });
    }
  }

  return hypotheses;
}

// Overall run score: mean episode score, 0 when there are no episodes.
export function scoreRun(episodes: SimEpisode[]): number {
  if (episodes.length === 0) return 0;
  const sum = episodes.reduce((acc, ep) => acc + ep.score, 0);
  return Math.round((sum / episodes.length) * 100) / 100;
}

// Record an evolution when a hypothesis is approved and implemented.
export function applyEvolution(
  hypothesis: SimHypothesis,
  baselineScore: number,
  newScore: number,
): SimEvolution {
  evolutionCounter += 1;
  return {
    id: `evo-${Date.now()}-${evolutionCounter}`,
    hypothesisId: hypothesis.id,
    change: hypothesis.proposedChange,
    baselineScore,
    newScore,
    implementedAt: new Date().toISOString(),
  };
}
