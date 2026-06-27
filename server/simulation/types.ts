// Simulation + Self-Improvement domain types.
//
// All data described by these types is synthetic. No real patient PHI ever
// flows through the simulation module — generated patients use fabricated
// names and scenarios only.

export type SimScenario =
  | "implant_consult"
  | "recall_overdue"
  | "treatment_decline"
  | "new_patient"
  | "emergency"
  | "financial_barrier"
  | "dso_referral"
  | "insurance_issue";

export type SimInsuranceType =
  | "none"
  | "ppo"
  | "hmo"
  | "medicaid"
  | "medicare";

export type SimOutcome =
  | "scheduled"
  | "declined"
  | "no_response"
  | "converted"
  | "referred"
  | "lost";

export type SimConfidence = "low" | "medium" | "high";

export type SimHypothesisStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "testing";

// Simulation patient with dental scenario.
export interface SimPatient {
  id: string;
  name: string;
  age: number;
  scenario: SimScenario;
  treatmentValue: number; // USD
  insuranceType: SimInsuranceType;
  lastVisitDaysAgo: number;
  contactAttempts: number;
  likelihood: number; // 0-1
}

// A single simulated interaction episode.
export interface SimEpisode {
  id: string;
  patientId: string;
  agentName: string;
  action: string;
  outcome: SimOutcome;
  revenueImpact: number;
  timestamp: string;
  score: number; // 0-100
  notes: string;
}

// Learned pattern from episodes.
export interface SimPattern {
  id: string;
  name: string;
  description: string;
  triggerConditions: string[];
  successRate: number;
  avgRevenueImpact: number;
  sampleSize: number;
  confidence: SimConfidence;
}

// Hypothesis for improvement.
export interface SimHypothesis {
  id: string;
  title: string;
  rationale: string;
  proposedChange: string;
  expectedImpact: string;
  status: SimHypothesisStatus;
  createdAt: string;
}

// Evolution record — an approved hypothesis that was implemented.
export interface SimEvolution {
  id: string;
  hypothesisId: string;
  change: string;
  baselineScore: number;
  newScore: number;
  implementedAt: string;
}

// Full simulation state, persisted to server/simulation/state.json.
export interface SimState {
  runCount: number;
  totalEpisodes: number;
  avgScore: number;
  totalRevenueSim: number;
  patients: SimPatient[];
  episodes: SimEpisode[];
  patterns: SimPattern[];
  hypotheses: SimHypothesis[];
  evolutions: SimEvolution[];
  lastRunAt: string | null;
  isRunning: boolean;
}
