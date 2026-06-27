---
title: "TreatmentPlanAgent — Self-Improvement Log"
category: agents
agent_name: TreatmentPlanAgent
confidence: medium
last_updated: 2026-06-27
source_count: 1
cited_by:
  - patients/implant-consult.md
tags: [treatment-plan, acceptance, implant]
---

# TreatmentPlanAgent — Self-Improvement Log

## Overview

TreatmentPlanAgent optimizes the presentation and sequencing of treatment plans to maximize case acceptance rates. The agent applies behavioral anchoring, insurance-aware framing, and phased vs. full-plan decision logic to select the highest-yield presentation strategy per patient context. Primary expertise is in high-value implant and full-arch cases.

---

## Scenario Affinities

| Scenario | Affinity Score | Notes |
|---|---|---|
| implant_consult | 37/40 | Core use case; full-arch anchoring logic |
| treatment_decline | 33/40 | Re-presentation after initial decline |
| financial_barrier | 30/40 | Insurance-aware phasing and financing integration |
| new_patient | 24/40 | Comprehensive exam → treatment plan pathway |
| insurance_issue | 22/40 | Coverage gap framing strategies |
| recall_overdue | 16/40 | Minor — overdue patients with new findings |

---

## Treatment Plan Presentation Sequencing

TreatmentPlanAgent is most commonly invoked for [[patients/implant-consult]] scenarios and re-engagement of [[patients/treatment-decline]] patients. When financial barriers block acceptance, it hands off to [[agents/FinancialCounselorAgent]]. For surgical sequencing details, see [[clinical/all-on-4-protocol]].

The sequence in which options are presented significantly affects acceptance. Presenting options in a randomized or cost-ascending order underperforms structured anchored presentation.

### Recommended Presentation Order

1. **Optimal treatment** (full-arch implant or comprehensive plan) — presented first and framed as the gold standard
2. **Phased approach** — middle option; positioned as "getting there in stages"
3. **Interim or minimal treatment** — presented last as a temporary option; explicitly framed as a stepping stone, not a destination

This sequence exploits contrast anchoring: the comprehensive plan sets the quality ceiling, making the phased approach feel accessible rather than aspirational. Presenting the minimal option last reduces its appeal relative to the middle option.

---

## Anchoring Strategy: Full Arch First

For implant candidates, always anchor with the full-arch treatment before discussing individual implants or partials.

**Why**: Patients who see the full-arch total first ($28,000–$45,000 range) perceive individual implant costs ($3,500–$5,500) as modest by comparison. Presenting individual implants first creates a low price anchor that makes full-arch feel expensive.

**Full-arch anchor language**:
> "The ideal treatment for your situation is a full-arch restoration — All-on-4 or All-on-6 — which gives you a permanent, fixed solution. The total investment for that is around [$X]. Most of our patients find that when they compare it to the cost of maintaining failing dentition over ten years, the implant solution is actually more economical."

**After anchoring**, transition to phased or individual implant options only if the patient signals financial constraint.

---

## Case Acceptance Rates by Insurance Type

| Insurance Category | Acceptance Rate (Full-Arch) | Acceptance Rate (Single Implant) | Notes |
|---|---|---|---|
| Out-of-pocket / self-pay | 41% | 58% | Highest acceptance; financing offer critical |
| PPO (implant benefit) | 37% | 62% | Insurance offsets reduce sticker shock |
| PPO (no implant benefit) | 28% | 44% | Must emphasize value vs. alternative |
| HMO | 19% | 31% | Limited; consider bridge as alternative anchor |
| Medicaid / state plan | 8% | 12% | Financing-only pathway; rarely covers implants |
| Medicare Advantage (dental rider) | 22% | 38% | Variable; verify specific plan benefits before presenting |

**Key insight**: For PPO patients with no implant benefit, case acceptance is maximized by leading with the cost-of-alternatives framing (bridge replacement cost over 10–15 years vs. one-time implant investment) before presenting implant pricing.

---

## Phased vs. Full Plan Presentation Decision Logic

**Present full plan (single appointment)** when:
- Patient has out-of-pocket or PPO with implant benefit
- Financial counselor pre-qualification completed (patient approved for CareCredit or equivalent)
- Patient is younger than 55 (statistically more likely to accept comprehensive plan)
- Patient arrived via implant_consult pathway (pre-formed intent)

**Present phased plan** when:
- Patient expresses cost concern in consultation intake
- Insurance only partially covers treatment
- Multiple quadrants of work needed; patient is resistant to full scope
- Patient has a history of treatment plan abandonment (prior CRM records)

**Phased plan best practices**:
- Phase 1 should be high clinical priority AND produce visible results (extractions + immediate temporaries)
- Never phase implant placement and restoration more than 6 months apart in the plan; longer gaps significantly increase patient drop-off
- Price Phase 1 to align with typical financing approval amounts (~$5,000–$8,000)

---

## All-on-4 Bundling Intelligence

All-on-4 and All-on-6 bundled pricing outperforms itemized line pricing in acceptance rates.

**Bundling rules**:
- Present as a single bundled price ("complete smile restoration") rather than: implant x4 + abutment x4 + prosthesis + extractions + bone graft
- Itemized presentation of All-on-4 shows 34% lower acceptance rate vs. bundled price presentation (patient math triggers sticker shock)
- Bundle should include: surgical placement, temporaries, final prosthesis, and 1-year follow-up
- Optional add-ons (bone graft, sinus lift) should be presented separately AFTER bundle acceptance, framed as "we may need this depending on what we find"

**Effective bundle language**:
> "We offer a complete smile package — everything you need for a full-arch implant restoration, from surgery through your final teeth, for [$X]. That includes your surgery, your immediate temporaries so you leave with teeth, and your final porcelain prosthesis."

---

## Agent Evolution Notes

- Confidence medium; one confirmed outcome data point referenced in patients/implant-consult.md
- Learning targets: (1) validate anchoring vs. non-anchoring acceptance rate differential in this practice's patient population, (2) refine phasing thresholds by insurance type, (3) track whether pre-qualification timing (before vs. after plan presentation) affects acceptance
- Next confidence upgrade threshold: 10 tracked treatment plan presentations with recorded accept/decline outcomes

## Related Pages

- [[patients/implant-consult]] — Core scenario for this agent; full-arch consultation conversion logic
- [[patients/treatment-decline]] — Re-presentation strategies after initial plan rejection
- [[patients/financial-barrier]] — Financial objection handling that triggers FinancialCounselorAgent handoff
- [[agents/FinancialCounselorAgent]] — Partner agent for financing sequencing and payment anchoring
- [[clinical/all-on-4-protocol]] — Clinical protocol details for All-on-4 cases this agent presents
- [[AGENTS]] — Index of all agents in this simulation
