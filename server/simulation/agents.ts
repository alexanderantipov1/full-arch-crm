// Six deterministic simulation agents. Each agent inspects a synthetic patient
// and produces a SimEpisode. No real Claude API calls are made during a
// simulation run — scoring is a pure function of patient attributes and the
// agent's scenario affinities, which keeps batches reproducible and free.
//
// askClaude is intentionally NOT invoked here. If a future variant wants
// natural-language rationale it must use dataClass: "ops_safe" (never "phi"),
// since all simulation data is synthetic ops data.

import type {
  SimEpisode,
  SimOutcome,
  SimPatient,
  SimScenario,
} from "./types";

interface OutcomeBand {
  min: number; // inclusive lower score bound
  outcome: SimOutcome;
}

// Higher scores map to better outcomes. Bands are evaluated high-to-low.
const OUTCOME_BANDS: OutcomeBand[] = [
  { min: 85, outcome: "converted" },
  { min: 70, outcome: "scheduled" },
  { min: 55, outcome: "referred" },
  { min: 40, outcome: "no_response" },
  { min: 25, outcome: "declined" },
  { min: 0, outcome: "lost" },
];

function outcomeForScore(score: number): SimOutcome {
  for (const band of OUTCOME_BANDS) {
    if (score >= band.min) return band.outcome;
  }
  return "lost";
}

// Revenue is realized only on outcomes that capture the case. Partial credit
// for referrals (they leave the practice but generate downstream value).
function revenueForOutcome(outcome: SimOutcome, value: number): number {
  switch (outcome) {
    case "converted":
      return value;
    case "scheduled":
      return Math.round(value * 0.6);
    case "referred":
      return Math.round(value * 0.2);
    default:
      return 0;
  }
}

let episodeCounter = 0;
function nextEpisodeId(agent: string): string {
  episodeCounter += 1;
  return `ep-${Date.now()}-${agent}-${episodeCounter}`;
}

abstract class BaseAgent {
  abstract readonly agentName: string;

  // Per-scenario affinity bonus (0-40 points). Strong fit scenarios score high.
  protected abstract affinity(scenario: SimScenario): number;

  // The concrete action this agent takes for a patient.
  protected abstract actionFor(patient: SimPatient): string;

  async process(patient: SimPatient): Promise<SimEpisode> {
    const score = this.scorePatient(patient);
    const outcome = outcomeForScore(score);
    const revenueImpact = revenueForOutcome(outcome, patient.treatmentValue);

    return {
      id: nextEpisodeId(this.agentName),
      patientId: patient.id,
      agentName: this.agentName,
      action: this.actionFor(patient),
      outcome,
      revenueImpact,
      timestamp: new Date().toISOString(),
      score,
      notes: this.noteFor(patient, outcome, score),
    };
  }

  protected scorePatient(patient: SimPatient): number {
    // Base signal: the patient's intrinsic likelihood to convert.
    let score = patient.likelihood * 45;

    // Scenario fit is the dominant differentiator between agents.
    score += this.affinity(patient.scenario);

    // Engagement decays with repeated unanswered contact attempts.
    score -= Math.min(patient.contactAttempts * 3, 15);

    // Recency: long gaps since last visit reduce reachability.
    if (patient.lastVisitDaysAgo > 365) score -= 10;
    else if (patient.lastVisitDaysAgo > 180) score -= 5;

    // Insurance friction lowers the odds of a clean conversion.
    if (patient.insuranceType === "none") score -= 6;
    else if (patient.insuranceType === "medicaid") score -= 3;

    return Math.max(0, Math.min(100, Math.round(score)));
  }

  protected noteFor(
    patient: SimPatient,
    outcome: SimOutcome,
    score: number,
  ): string {
    return `${this.agentName} handled ${patient.scenario} (value $${patient.treatmentValue}) → ${outcome} @ score ${score}`;
  }
}

export class PatientAcquisitionAgent extends BaseAgent {
  readonly agentName = "PatientAcquisition";

  protected affinity(scenario: SimScenario): number {
    switch (scenario) {
      case "new_patient":
        return 38;
      case "dso_referral":
        return 28;
      case "implant_consult":
        return 18;
      case "emergency":
        return 14;
      default:
        return 6;
    }
  }

  protected actionFor(patient: SimPatient): string {
    return `Nurture intake & book consult for ${patient.scenario.replace(/_/g, " ")}`;
  }
}

export class ClinicalDecisionAgent extends BaseAgent {
  readonly agentName = "ClinicalDecision";

  protected affinity(scenario: SimScenario): number {
    switch (scenario) {
      case "emergency":
        return 36;
      case "implant_consult":
        return 30;
      case "treatment_decline":
        return 20;
      case "new_patient":
        return 12;
      default:
        return 8;
    }
  }

  protected actionFor(patient: SimPatient): string {
    return `Present treatment options & clinical rationale (age ${patient.age})`;
  }
}

export class RevenueOptimizationAgent extends BaseAgent {
  readonly agentName = "RevenueOptimization";

  protected affinity(scenario: SimScenario): number {
    switch (scenario) {
      case "financial_barrier":
        return 34;
      case "treatment_decline":
        return 30;
      case "implant_consult":
        return 22;
      case "insurance_issue":
        return 16;
      default:
        return 7;
    }
  }

  protected actionFor(patient: SimPatient): string {
    const lever =
      patient.insuranceType === "none"
        ? "financing + membership plan"
        : "maximize benefits + financing";
    return `Offer ${lever} on $${patient.treatmentValue} case`;
  }
}

export class RecallRecoveryAgent extends BaseAgent {
  readonly agentName = "RecallRecovery";

  protected affinity(scenario: SimScenario): number {
    switch (scenario) {
      case "recall_overdue":
        return 40;
      case "treatment_decline":
        return 18;
      case "insurance_issue":
        return 10;
      default:
        return 6;
    }
  }

  protected actionFor(patient: SimPatient): string {
    return `Re-engage recall (last visit ${patient.lastVisitDaysAgo}d ago)`;
  }
}

export class DSOScalingAgent extends BaseAgent {
  readonly agentName = "DSOScaling";

  protected affinity(scenario: SimScenario): number {
    switch (scenario) {
      case "dso_referral":
        return 40;
      case "new_patient":
        return 20;
      case "implant_consult":
        return 14;
      default:
        return 6;
    }
  }

  protected actionFor(patient: SimPatient): string {
    return `Route referral across network & balance provider load`;
  }
}

export class ComplianceAgent extends BaseAgent {
  readonly agentName = "Compliance";

  protected affinity(scenario: SimScenario): number {
    switch (scenario) {
      case "insurance_issue":
        return 38;
      case "financial_barrier":
        return 18;
      case "treatment_decline":
        return 12;
      default:
        return 8;
    }
  }

  protected actionFor(patient: SimPatient): string {
    return `Resolve auth/coverage & document compliance (${patient.insuranceType})`;
  }
}

export const ALL_AGENTS: BaseAgent[] = [
  new PatientAcquisitionAgent(),
  new ClinicalDecisionAgent(),
  new RevenueOptimizationAgent(),
  new RecallRecoveryAgent(),
  new DSOScalingAgent(),
  new ComplianceAgent(),
];

// Resolve an agent by name. Accepts both the bare name ("PatientAcquisition")
// and the "<Name>Agent" form ("PatientAcquisitionAgent") used by callers.
function resolveAgent(agentName: string): BaseAgent | undefined {
  const wanted = agentName.replace(/Agent$/, "");
  return ALL_AGENTS.find((a) => a.agentName === wanted);
}

// Deterministic, reproducible effect of a prompt addition on an episode.
// The simulation never calls a real model, so an A/B "prompt suffix" is scored
// by a pure heuristic instead: instruction keywords that reflect known levers
// add points, plus a small stable jitter seeded by the prompt + patient so the
// same (prompt, patient) pair always yields the same delta. An empty addition
// (the control variant) yields zero delta, leaving the base episode untouched.
const PROMPT_LEVER_KEYWORDS = [
  "empathy",
  "urgency",
  "financing",
  "follow up",
  "follow-up",
  "value",
  "benefit",
  "reassure",
  "clarity",
  "personalize",
  "personalized",
  "concise",
];

function promptAdditionDelta(promptAddition: string, patient: SimPatient): number {
  const text = promptAddition.trim().toLowerCase();
  if (!text) return 0;

  let delta = 0;
  for (const kw of PROMPT_LEVER_KEYWORDS) {
    if (text.includes(kw)) delta += 3;
  }

  let hash = 0;
  const seed = `${promptAddition}|${patient.id}`;
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  }
  delta += (hash % 9) - 3; // stable jitter in [-3, +5]

  return delta;
}

// Run a named agent against a patient with an extra instruction appended to its
// effective prompt. This is the core primitive for A/B testing: variant A
// passes an empty promptAddition (control) and variant B passes a challenger
// suffix. Returns a SimEpisode with the same shape as a normal agent run.
export async function runAgentWithPromptAddition(
  agentName: string,
  patient: SimPatient,
  promptAddition: string,
): Promise<SimEpisode> {
  const agent = resolveAgent(agentName);
  if (!agent) throw new Error(`Unknown agent: ${agentName}`);

  const base = await agent.process(patient);

  const delta = promptAdditionDelta(promptAddition, patient);
  if (delta === 0) return base;

  const score = Math.max(0, Math.min(100, base.score + delta));
  const outcome = outcomeForScore(score);
  const revenueImpact = revenueForOutcome(outcome, patient.treatmentValue);
  const suffix = promptAddition.trim()
    ? ` [+prompt: ${promptAddition.trim().slice(0, 60)}]`
    : "";

  return {
    ...base,
    score,
    outcome,
    revenueImpact,
    notes: `${base.notes}${suffix}`,
  };
}
