---
title: "Implant Consult — Patient Profile"
category: patients
confidence: medium
last_updated: 2026-06-27
source_count: 3
cited_by:
  - insurance/ppo-general.md
  - clinical/all-on-4-protocol.md
  - agents/TreatmentPlanAgent.md
tags: [implant, high-value, consultation]
---

# Implant Consult

## Profile Summary
Patient presenting for initial consultation regarding dental implants, most commonly All-on-4 or single implant replacement. Age 45–65, often referred by existing patient or found via search. Moderate-to-high anxiety about cost and surgery. Has often delayed treatment for years due to fear or finances.

## Treatment Patterns

| Procedure | CDT | Avg Value | Acceptance Rate |
|-----------|-----|-----------|-----------------|
| All-on-4 arch | D6010×4+D6114×4 | $22,000–$28,000 | 38% |
| Single implant | D6010+D6065 | $4,200–$5,800 | 52% |
| Implant + crown | D6010+D6065+D2740 | $5,500–$7,200 | 47% |
| Pre-surgical CT | D0330 | $450–$650 | 89% |

## Conversion Intelligence
- **Converts when:** Financing (CareCredit/Lending Club) approved day-of-consult, provider spends >20 min educating, before/after photos shown, prior auth submitted same day
- **Declines when:** No financing option presented, insurance denied before consult ends, patient leaves without written treatment plan
- **Best agent:** TreatmentPlanAgent + FinancialCounselorAgent tandem
- **Best scenario fit score:** 78/100

## Insurance Patterns
PPO: 60% of implant consults. Approve D0330 readily. D6010 requires prior auth ~72% of time. See [[insurance/ppo-general]] for documentation requirements and [[insurance/delta-dental]] for Delta-specific approval patterns.
Self-pay: 28%. Financing penetration is key — CareCredit approval in office closes 68% of self-pay.
Medicaid: 6%. Implants virtually never covered. Focus on denture alternative conversation.

Prior auth denials should be escalated via [[insurance/appeals/ppo-d6010]]. Patients who cannot pay out-of-pocket are routed to the [[patients/financial-barrier]] workflow.

## Communication Intelligence
- Lead with quality-of-life outcomes, not procedure names
- Show chewing function recovery photos immediately after exam
- Anchor at full arch value ($28,000) then present phased or single arch option
- Always provide written estimate before patient leaves — oral-only quotes convert at 18% vs 51%

## Related Pages

- [[agents/TreatmentPlanAgent]] — Primary agent for structuring and presenting implant treatment plans
- [[agents/InsuranceAgent]] — Handles prior auth submission and denial management for D6010
- [[clinical/all-on-4-protocol]] — Full-arch surgical protocol details for All-on-4 candidates
- [[insurance/ppo-general]] — PPO documentation requirements and approval rates for implant cases
- [[patients/financial-barrier]] — Patients who cannot accept due to cost; financing pathway details
