// Persistent knowledge base for the self-improvement loop.
//
// Approved hypotheses are distilled into durable KBRules that survive server
// restarts (stored as JSON next to state.json) and are fed back into the
// agents so learned best practices keep influencing future runs.
//
// NOTE: SimHypothesis does not carry an explicit scenario list or numeric
// confidence, so both are derived here from the hypothesis text/rationale
// (see scenariosFromHypothesis / confidenceFromHypothesis).

import { readFileSync, writeFileSync, existsSync } from "fs";
import { join } from "path";
import type { SimHypothesis, SimScenario } from "./types";

export interface KBRule {
  id: string;
  title: string;
  rule: string;
  affectedScenarios: SimScenario[];
  confidence: number; // 0-1
  appliedAt: string;
  sourceHypothesisId: string;
  scoreImpact: number;
}

export interface KnowledgeBase {
  version: number;
  rules: KBRule[];
  lastUpdatedAt: string | null;
}

const KB_PATH = join(import.meta.dirname, "knowledge-base.json");

const ALL_SCENARIOS: SimScenario[] = [
  "implant_consult",
  "recall_overdue",
  "treatment_decline",
  "new_patient",
  "emergency",
  "financial_barrier",
  "dso_referral",
  "insurance_issue",
];

// Hypotheses reference patterns by their label (e.g. "PatientAcquisition ×
// new patient"), so scan the hypothesis text for any scenario token in either
// snake_case or the space-separated label form used in pattern names.
function scenariosFromHypothesis(h: SimHypothesis): SimScenario[] {
  const haystack =
    `${h.title} ${h.proposedChange} ${h.rationale}`.toLowerCase();
  return ALL_SCENARIOS.filter(
    (s) => haystack.includes(s) || haystack.includes(s.replace(/_/g, " ")),
  );
}

// Pattern confidence ("low"/"medium"/"high") is embedded in the rationale for
// weak-pattern hypotheses; map it to a numeric score, defaulting to 0.5.
function confidenceFromHypothesis(h: SimHypothesis): number {
  const text = h.rationale.toLowerCase();
  if (text.includes("high confidence")) return 0.9;
  if (text.includes("medium confidence")) return 0.6;
  if (text.includes("low confidence")) return 0.3;
  return 0.5;
}

function loadKB(): KnowledgeBase {
  try {
    if (existsSync(KB_PATH)) {
      return JSON.parse(readFileSync(KB_PATH, "utf-8")) as KnowledgeBase;
    }
  } catch {
    // Fall through to an empty knowledge base on any read/parse error.
  }
  return { version: 1, rules: [], lastUpdatedAt: null };
}

function saveKB(kb: KnowledgeBase): void {
  try {
    writeFileSync(KB_PATH, JSON.stringify(kb, null, 2), "utf-8");
  } catch {
    // Persistence is best-effort; a write failure must not crash a run.
  }
}

export function addRule(
  hypothesis: SimHypothesis,
  scoreImpact: number,
): KBRule {
  const kb = loadKB();
  const rule: KBRule = {
    id: `kb-${Date.now()}`,
    title: hypothesis.title,
    rule: hypothesis.proposedChange,
    affectedScenarios: scenariosFromHypothesis(hypothesis),
    confidence: confidenceFromHypothesis(hypothesis),
    appliedAt: new Date().toISOString(),
    sourceHypothesisId: hypothesis.id,
    scoreImpact,
  };
  kb.rules.push(rule);
  kb.version += 1;
  kb.lastUpdatedAt = new Date().toISOString();
  saveKB(kb);
  return rule;
}

export function getRules(scenario?: SimScenario): KBRule[] {
  const kb = loadKB();
  if (!scenario) return kb.rules;
  return kb.rules.filter((r) => r.affectedScenarios.includes(scenario));
}

// Bounded score nudge applied by agents for scenarios with learned rules.
// Each matching rule contributes up to 3 points (weighted by confidence),
// capped at 12 so the knowledge base biases — but never dominates — scoring.
export function getKBScoreBonus(scenario: SimScenario): number {
  const rules = getRules(scenario);
  const bonus = rules.reduce((acc, r) => acc + Math.min(r.confidence * 3, 3), 0);
  return Math.min(bonus, 12);
}

// Human-readable summary of the top learned rules for a scenario, formatted
// for injection into an agent prompt (used by LLM-backed agent variants).
export function getKBContext(scenario?: SimScenario): string {
  const rules = getRules(scenario);
  if (rules.length === 0) return "";
  const sorted = [...rules]
    .sort((a, b) => b.scoreImpact - a.scoreImpact)
    .slice(0, 5);
  return (
    `\n\nLEARNED BEST PRACTICES (from ${rules.length} improvement cycles):\n` +
    sorted
      .map(
        (r, i) =>
          `${i + 1}. ${r.rule} [confidence: ${(r.confidence * 100).toFixed(0)}%]`,
      )
      .join("\n")
  );
}

export function deleteRule(id: string): boolean {
  const kb = loadKB();
  const before = kb.rules.length;
  kb.rules = kb.rules.filter((r) => r.id !== id);
  if (kb.rules.length < before) {
    kb.lastUpdatedAt = new Date().toISOString();
    saveKB(kb);
    return true;
  }
  return false;
}

export function getKB(): KnowledgeBase {
  return loadKB();
}
