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
import { getKBScoreBonus } from "./knowledge-base";

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

    // Learned rules from approved hypotheses feed back into scoring so the
    // knowledge base measurably improves outcomes for affected scenarios.
    score += getKBScoreBonus(patient.scenario);

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
