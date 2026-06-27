// Deterministic synthetic patient generation for the simulation engine.
//
// IMPORTANT: every value here is fabricated. There is no real PHI in this
// module — names, ages, and scenarios are drawn from hardcoded arrays and
// seeded by index so runs are reproducible without an external faker package.

import type {
  SimInsuranceType,
  SimPatient,
  SimScenario,
} from "./types";

const FIRST_NAMES = [
  "Ava", "Liam", "Noah", "Mia", "Ethan", "Sophia", "Mason", "Isabella",
  "Lucas", "Amelia", "Logan", "Harper", "Jackson", "Evelyn", "Aiden",
  "Abigail", "Carter", "Emily", "Grayson", "Ella", "Wyatt", "Scarlett",
  "Owen", "Grace", "Caleb", "Chloe", "Nathan", "Lily", "Ryan", "Zoe",
];

const LAST_NAMES = [
  "Carter", "Reyes", "Brooks", "Nguyen", "Patel", "Foster", "Hughes",
  "Bennett", "Coleman", "Russell", "Griffin", "Hayes", "Sanders", "Powell",
  "Long", "Flores", "Washington", "Butler", "Simmons", "Barnes", "Ross",
  "Henderson", "Jenkins", "Perry", "Powers", "Hart", "Lane", "Mills",
  "Curtis", "Day",
];

const SCENARIOS: SimScenario[] = [
  "implant_consult",
  "recall_overdue",
  "treatment_decline",
  "new_patient",
  "emergency",
  "financial_barrier",
  "dso_referral",
  "insurance_issue",
];

interface ScenarioProfile {
  valueMin: number;
  valueMax: number;
  insurances: SimInsuranceType[];
  likelihoodMin: number;
  likelihoodMax: number;
  lastVisitMin: number;
  lastVisitMax: number;
  contactMin: number;
  contactMax: number;
  ageMin: number;
  ageMax: number;
}

const PROFILES: Record<SimScenario, ScenarioProfile> = {
  implant_consult: {
    valueMin: 3500, valueMax: 6000,
    insurances: ["ppo", "none"],
    likelihoodMin: 0.4, likelihoodMax: 0.75,
    lastVisitMin: 30, lastVisitMax: 200,
    contactMin: 0, contactMax: 3,
    ageMin: 45, ageMax: 78,
  },
  recall_overdue: {
    valueMin: 200, valueMax: 800,
    insurances: ["ppo", "hmo", "medicaid", "medicare", "none"],
    likelihoodMin: 0.3, likelihoodMax: 0.7,
    lastVisitMin: 200, lastVisitMax: 540,
    contactMin: 1, contactMax: 5,
    ageMin: 18, ageMax: 80,
  },
  treatment_decline: {
    valueMin: 1000, valueMax: 4000,
    insurances: ["ppo", "hmo", "none"],
    likelihoodMin: 0.15, likelihoodMax: 0.45,
    lastVisitMin: 60, lastVisitMax: 300,
    contactMin: 2, contactMax: 6,
    ageMin: 30, ageMax: 70,
  },
  new_patient: {
    valueMin: 500, valueMax: 2000,
    insurances: ["ppo", "hmo", "medicaid", "none"],
    likelihoodMin: 0.5, likelihoodMax: 0.9,
    lastVisitMin: 0, lastVisitMax: 14,
    contactMin: 0, contactMax: 2,
    ageMin: 18, ageMax: 65,
  },
  emergency: {
    valueMin: 300, valueMax: 1500,
    insurances: ["ppo", "hmo", "medicaid", "medicare", "none"],
    likelihoodMin: 0.6, likelihoodMax: 0.95,
    lastVisitMin: 0, lastVisitMax: 7,
    contactMin: 0, contactMax: 1,
    ageMin: 20, ageMax: 75,
  },
  financial_barrier: {
    valueMin: 2000, valueMax: 5000,
    insurances: ["none"],
    likelihoodMin: 0.1, likelihoodMax: 0.4,
    lastVisitMin: 30, lastVisitMax: 240,
    contactMin: 1, contactMax: 5,
    ageMin: 25, ageMax: 68,
  },
  dso_referral: {
    valueMin: 1500, valueMax: 4000,
    insurances: ["ppo", "hmo", "medicare"],
    likelihoodMin: 0.45, likelihoodMax: 0.8,
    lastVisitMin: 0, lastVisitMax: 30,
    contactMin: 0, contactMax: 2,
    ageMin: 22, ageMax: 72,
  },
  insurance_issue: {
    valueMin: 1000, valueMax: 3000,
    insurances: ["ppo", "hmo", "medicaid", "medicare"],
    likelihoodMin: 0.25, likelihoodMax: 0.6,
    lastVisitMin: 14, lastVisitMax: 120,
    contactMin: 1, contactMax: 4,
    ageMin: 19, ageMax: 80,
  },
};

// Deterministic pseudo-random in [0, 1) seeded by an integer. Keeps batch
// generation reproducible so pattern extraction is stable across runs.
function seeded(n: number): number {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
}

function pick<T>(arr: T[], n: number): T {
  return arr[Math.floor(seeded(n) * arr.length) % arr.length];
}

function rangeInt(min: number, max: number, n: number): number {
  return Math.round(min + seeded(n) * (max - min));
}

function rangeFloat(min: number, max: number, n: number): number {
  return Math.round((min + seeded(n) * (max - min)) * 100) / 100;
}

export function generatePatients(count: number = 20): SimPatient[] {
  const batchSeed = Math.floor(Date.now() / 1000);
  const patients: SimPatient[] = [];

  for (let i = 0; i < count; i++) {
    const s = batchSeed + i * 17;
    const scenario = SCENARIOS[i % SCENARIOS.length];
    const profile = PROFILES[scenario];
    const first = pick(FIRST_NAMES, s + 1);
    const last = pick(LAST_NAMES, s + 2);

    patients.push({
      id: `sim-patient-${batchSeed}-${i}`,
      name: `${first} ${last}`,
      age: rangeInt(profile.ageMin, profile.ageMax, s + 3),
      scenario,
      treatmentValue: rangeInt(profile.valueMin, profile.valueMax, s + 4),
      insuranceType: pick(profile.insurances, s + 5),
      lastVisitDaysAgo: rangeInt(
        profile.lastVisitMin,
        profile.lastVisitMax,
        s + 6,
      ),
      contactAttempts: rangeInt(profile.contactMin, profile.contactMax, s + 7),
      likelihood: rangeFloat(
        profile.likelihoodMin,
        profile.likelihoodMax,
        s + 8,
      ),
    });
  }

  return patients;
}
