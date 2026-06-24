// Multi-location DSO network simulator. Runs all six existing simulation
// agents against synthetic patient batches shaped per practice archetype, then
// rolls location-level KPIs up into a network expansion recommendation.
//
// All data is synthetic (see ./patients) — no real PHI flows through here. The
// existing agents in ./agents are reused as-is; scoring is never duplicated.

import { randomUUID } from "crypto";
import { generatePatients } from "./patients";
import { ALL_AGENTS } from "./agents";
import type {
  SimPatient,
  SimEpisode,
  SimScenario,
  SimInsuranceType,
} from "./types";

export type PracticeArchetype =
  | "solo_gp"
  | "implant_specialist"
  | "dso_satellite"
  | "multi_specialty"
  | "startup_location";

export interface PracticeProfile {
  archetype: PracticeArchetype;
  name: string;
  chairCount: number;
  annualProductionTarget: number;
  insuranceMix: Partial<Record<SimInsuranceType, number>>;
  scenarioBias: Partial<Record<SimScenario, number>>;
  staffing: { doctors: number; hygienists: number; frontDesk: number };
  dsoGroup: string | null;
}

export interface LocationKPIs {
  newPatientConversionRate: number;
  treatmentAcceptanceRate: number;
  recallComplianceRate: number;
  revenuePerChair: number;
  avgTreatmentValue: number;
  insuranceDenialRate: number;
  dsoReadinessScore: number;
}

export interface LocationSimResult {
  locationId: string;
  profile: PracticeProfile;
  episodeCount: number;
  avgScore: number;
  conversionRate: number;
  projectedAnnualRevenue: number;
  patientAcquisitionCost: number;
  topPerformingAgent: string;
  weakestAgent: string;
  kpis: LocationKPIs;
}

export interface DSONetworkResult {
  runId: string;
  runAt: string;
  locations: LocationSimResult[];
  networkSummary: {
    totalProjectedRevenue: number;
    bestPerformingArchetype: PracticeArchetype;
    worstPerformingArchetype: PracticeArchetype;
    avgNetworkScore: number;
    dsoExpansionRecommendation: string;
    optimalExpansionArchetype: PracticeArchetype;
  };
}

// Scenario keys map to the real SimScenario union from ./types.
const PRACTICE_PROFILES: Record<PracticeArchetype, PracticeProfile> = {
  solo_gp: {
    archetype: "solo_gp",
    name: "Solo GP Practice",
    chairCount: 1,
    annualProductionTarget: 150000,
    insuranceMix: { ppo: 0.7, hmo: 0.2, none: 0.1 },
    scenarioBias: { recall_overdue: 1.8, new_patient: 1.2, implant_consult: 0.4 },
    staffing: { doctors: 1, hygienists: 1, frontDesk: 1 },
    dsoGroup: null,
  },
  implant_specialist: {
    archetype: "implant_specialist",
    name: "Implant Specialist",
    chairCount: 2,
    annualProductionTarget: 1200000,
    insuranceMix: { none: 0.6, ppo: 0.3, medicaid: 0.1 },
    scenarioBias: { implant_consult: 2.5, treatment_decline: 1.4 },
    staffing: { doctors: 1, hygienists: 0, frontDesk: 2 },
    dsoGroup: null,
  },
  dso_satellite: {
    archetype: "dso_satellite",
    name: "DSO Satellite Location",
    chairCount: 4,
    annualProductionTarget: 800000,
    insuranceMix: { ppo: 0.5, hmo: 0.3, medicaid: 0.15, none: 0.05 },
    scenarioBias: { dso_referral: 2.0, insurance_issue: 1.5, new_patient: 1.3 },
    staffing: { doctors: 2, hygienists: 2, frontDesk: 3 },
    dsoGroup: "Fusion Dental DSO",
  },
  multi_specialty: {
    archetype: "multi_specialty",
    name: "Multi-Specialty Group",
    chairCount: 6,
    annualProductionTarget: 2500000,
    insuranceMix: { ppo: 0.55, none: 0.25, hmo: 0.15, medicaid: 0.05 },
    scenarioBias: { implant_consult: 1.5, treatment_decline: 1.5, financial_barrier: 1.3 },
    staffing: { doctors: 4, hygienists: 3, frontDesk: 4 },
    dsoGroup: null,
  },
  startup_location: {
    archetype: "startup_location",
    name: "New DSO Expansion Site",
    chairCount: 3,
    annualProductionTarget: 400000,
    insuranceMix: { ppo: 0.4, none: 0.4, hmo: 0.2 },
    scenarioBias: { new_patient: 3.0, emergency: 2.0 },
    staffing: { doctors: 1, hygienists: 1, frontDesk: 2 },
    dsoGroup: "Fusion Dental DSO",
  },
};

// Outcomes that count as a captured/retained patient for conversion KPIs.
const SUCCESS_OUTCOMES = new Set(["converted", "scheduled", "referred"]);

export class DSOSimulator {
  async runLocation(
    archetype: PracticeArchetype,
    patientCount = 15,
  ): Promise<LocationSimResult> {
    const profile = PRACTICE_PROFILES[archetype];
    const patients = generatePatients(patientCount);

    // Apply scenario bias by nudging the patient's intrinsic likelihood, which
    // is the dominant input to agent scoring (see BaseAgent.scorePatient).
    const biasedPatients: SimPatient[] = patients.map((p) => {
      const bias = profile.scenarioBias[p.scenario] ?? 1.0;
      return {
        ...p,
        likelihood: Math.max(0, Math.min(1, p.likelihood * bias)),
      };
    });

    // Episodes carry only patientId, so keep a lookup to recover the scenario.
    const scenarioByPatient = new Map<string, SimScenario>(
      biasedPatients.map((p) => [p.id, p.scenario]),
    );

    const episodes: SimEpisode[] = [];
    for (const patient of biasedPatients) {
      for (const agent of ALL_AGENTS) {
        try {
          episodes.push(await agent.process(patient));
        } catch {
          // Skip a failed agent rather than aborting the whole location.
        }
      }
    }

    const avgScore =
      episodes.length > 0
        ? episodes.reduce((s, e) => s + e.score, 0) / episodes.length
        : 50;
    const conversionRate =
      episodes.length > 0
        ? episodes.filter((e) => SUCCESS_OUTCOMES.has(e.outcome)).length /
          episodes.length
        : 0;
    const projectedAnnualRevenue = Math.min(
      profile.annualProductionTarget * (avgScore / 70),
      profile.annualProductionTarget * 1.3,
    );

    // Per-agent averages to identify the strongest/weakest performer.
    const agentScores = new Map<string, number[]>();
    for (const ep of episodes) {
      if (!agentScores.has(ep.agentName)) agentScores.set(ep.agentName, []);
      agentScores.get(ep.agentName)!.push(ep.score);
    }
    const agentAvgs = Array.from(agentScores.entries())
      .map(([name, scores]) => ({
        name,
        avg: scores.reduce((a, b) => a + b, 0) / scores.length,
      }))
      .sort((a, b) => b.avg - a.avg);

    const scenarioOf = (ep: SimEpisode) => scenarioByPatient.get(ep.patientId);
    const inScenario = (scenario: SimScenario) =>
      episodes.filter((e) => scenarioOf(e) === scenario);

    const newPatientEps = inScenario("new_patient");
    const treatmentEps = inScenario("treatment_decline");
    const recallEps = inScenario("recall_overdue");
    const insuranceEps = inScenario("insurance_issue");

    const kpis: LocationKPIs = {
      newPatientConversionRate:
        newPatientEps.filter((e) => SUCCESS_OUTCOMES.has(e.outcome)).length /
        Math.max(1, newPatientEps.length),
      treatmentAcceptanceRate:
        treatmentEps.filter((e) => e.outcome === "converted").length /
        Math.max(1, treatmentEps.length),
      recallComplianceRate:
        recallEps.filter((e) => SUCCESS_OUTCOMES.has(e.outcome)).length /
        Math.max(1, recallEps.length),
      revenuePerChair: projectedAnnualRevenue / profile.chairCount,
      avgTreatmentValue:
        biasedPatients.reduce((s, p) => s + p.treatmentValue, 0) /
        Math.max(1, biasedPatients.length),
      insuranceDenialRate:
        insuranceEps.filter((e) => e.outcome === "lost").length /
        Math.max(1, insuranceEps.length),
      dsoReadinessScore: Math.min(
        100,
        Math.round(avgScore * (profile.chairCount / 3) * conversionRate),
      ),
    };

    return {
      locationId: randomUUID(),
      profile,
      episodeCount: episodes.length,
      avgScore,
      conversionRate,
      projectedAnnualRevenue,
      patientAcquisitionCost: Math.round(
        (projectedAnnualRevenue * 0.08) / Math.max(1, biasedPatients.length),
      ),
      topPerformingAgent: agentAvgs[0]?.name ?? "N/A",
      weakestAgent: agentAvgs[agentAvgs.length - 1]?.name ?? "N/A",
      kpis,
    };
  }

  async runNetwork(
    archetypes: PracticeArchetype[] = [
      "solo_gp",
      "implant_specialist",
      "dso_satellite",
      "multi_specialty",
      "startup_location",
    ],
    patientCount = 15,
  ): Promise<DSONetworkResult> {
    const locations = await Promise.all(
      archetypes.map((a) => this.runLocation(a, patientCount)),
    );
    const sorted = [...locations].sort((a, b) => b.avgScore - a.avgScore);
    const avgNetworkScore =
      locations.reduce((s, l) => s + l.avgScore, 0) / locations.length;
    const totalRevenue = locations.reduce(
      (s, l) => s + l.projectedAnnualRevenue,
      0,
    );
    const best = sorted[0];
    const expansionRec = `Expand ${best.profile.name} archetype — DSO readiness: ${best.kpis.dsoReadinessScore}/100, revenue/chair: $${best.kpis.revenuePerChair.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

    return {
      runId: randomUUID(),
      runAt: new Date().toISOString(),
      locations,
      networkSummary: {
        totalProjectedRevenue: totalRevenue,
        bestPerformingArchetype: sorted[0].profile.archetype,
        worstPerformingArchetype: sorted[sorted.length - 1].profile.archetype,
        avgNetworkScore,
        dsoExpansionRecommendation: expansionRec,
        optimalExpansionArchetype: best.profile.archetype,
      },
    };
  }
}

export const dsoSimulator = new DSOSimulator();
