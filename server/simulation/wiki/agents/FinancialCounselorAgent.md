---
title: "FinancialCounselorAgent — Self-Improvement Log"
category: agents
agent_name: FinancialCounselorAgent
confidence: medium
last_updated: 2026-06-27
source_count: 1
cited_by:
  - patients/financial-barrier.md
  - patients/treatment-decline.md
tags: [financing, carecredit, case-acceptance]
---

# FinancialCounselorAgent — Self-Improvement Log

## Overview

FinancialCounselorAgent manages the financial consultation layer of case acceptance: financing option sequencing, payment anchoring, pre-qualification timing, and re-engagement for patients who declined treatment due to cost. The agent's primary goal is to eliminate financial barriers to treatment acceptance by matching patients to the right financing product and framing, in the right order, at the right moment in the patient journey.

---

## Scenario Affinities

| Scenario | Affinity Score | Notes |
|---|---|---|
| financial_barrier | 38/40 | Core use case; direct financial objection handling |
| treatment_decline | 35/40 | Post-decline re-engagement with financing |
| implant_consult | 32/40 | High-value case; financing critical to acceptance |
| insurance_issue | 30/40 | Insurance gap filled by financing pathway |
| new_patient | 22/40 | Upfront financing intro at comprehensive exam |
| recall_overdue | 14/40 | Low relevance; occasional benefit expiry framing |

---

## Financing Option Sequencing

The order in which financing products are offered materially affects approval rates and case acceptance. Lead with the highest-approval, lowest-friction product and work down.

### Recommended Sequence

**1. CareCredit (First)**
- Highest brand recognition among dental patients
- Approval rate: ~68% for standard plans; ~52% for extended plans
- Promotional periods: 6-, 12-, 18-, 24-month no-interest if paid in full
- Best for: cases $1,000–$8,000; patients with fair to good credit
- Application: in-office or patient self-apply via QR code/link
- Key benefit: instant decision; can be applied at consultation

**2. Lending Club Patient Solutions (Second)**
- Longer-term installment loan structure; better for high-dollar cases
- Approval rate: ~61% for applicants with good credit
- Loan amounts: up to $65,000; terms 24–84 months
- Best for: full-arch implant cases ($15,000–$45,000); patients who need low monthly payments
- Application: online; decision typically within minutes
- Key benefit: fixed rate; predictable payment; high dollar limit

**3. Denefits (Third)**
- In-house financing facilitation; does not require credit check
- Approval rate: ~89% (near-universal; Denefits takes on collection risk)
- Payment structure: practice sets terms; Denefits manages collection
- Best for: patients who declined CareCredit and Lending Club; patients with poor credit
- Typical terms: 20% down, balance over 12–24 months
- Key benefit: credit agnostic; high approval for patients otherwise unfinanceable

**4. In-House Payment Plan (Fourth / Last Resort)**
- Practice carries the receivable directly; no third-party
- Approval rate: 100% (practice decides internally)
- Best for: established patients with strong payment history; small balance situations (<$2,000)
- Require signed payment agreement; minimum 25% down recommended
- Risk: collection exposure is practice's; use selectively

---

## Pre-Qualification Timing

**Pre-qualification before treatment plan presentation = 2.3x better acceptance rate** than presenting the plan first and discussing financing after the patient has already reacted to the total price.

### Why Timing Matters

When a patient sees a $28,000 treatment plan without knowing they can afford it, the number anchors as "impossible." When they arrive at the plan presentation already knowing their monthly payment options, the same number anchors as "$285/month."

### Pre-Qualification Protocol

**Trigger**: Patient has been scheduled for a treatment consultation (implant consult, comprehensive exam with expected restorative findings, or any case expected to exceed $3,000).

**Timing**: 24–48 hours before the consultation appointment.

**Method**:
1. Send pre-qualification link via text + email: "Before your appointment tomorrow, you can preview your financing options — it only takes 2 minutes and won't affect your credit score."
2. Patient completes soft-pull pre-qualification through CareCredit or Lending Club
3. Results available at time of consultation — financial counselor reviews with patient during or immediately after treatment plan presentation
4. If patient did not pre-qualify: have in-office Denefits application ready as fallback

**Pre-qualification timing impact data**:
- Pre-qual before plan presentation: 41% case acceptance rate
- Post-plan financing discussion (no pre-qual): 18% case acceptance rate
- No financing discussion: 11% case acceptance rate

---

## Monthly Payment Anchoring

Monthly payment anchoring reframes a large treatment cost into a manageable recurring number.

### Anchoring Formula

Calculate and lead with the monthly payment equivalent of the treatment plan:
- Full-arch implant ($28,000) at 84 months / 6.99% APR = approximately $430/month
- Full-arch implant ($28,000) at 24 months / 0% promotional = approximately $1,167/month
- Single implant ($4,500) at 18 months / 0% promotional = approximately $250/month

**Anchor language**:
> "For most patients, a complete smile restoration like yours works out to around $430 a month — less than a car payment. And this is a permanent investment in your health, not something you're replacing every few years."

**Rules for monthly payment anchoring**:
- Lead with the lowest monthly option (longest term) to set the most attractive anchor
- Then present the shorter-term option as a way to pay less total interest
- Never present total interest paid unless patient specifically asks — it undermines the anchoring effect
- Always qualify: "These are estimates — your exact rate depends on your credit profile"

---

## Re-Engagement for Declined Patients

Patients who declined treatment due to cost are among the highest-value re-engagement targets. They have already accepted the clinical need — only the financial pathway is missing.

### Re-Engagement Trigger Conditions

- Patient declined a treatment plan citing cost within the last 6 months
- Patient was previously denied financing (Denefits not yet offered)
- Patient's insurance has renewed (new benefit year)
- Patient inquiry resumed (website visit, call, or text after silence)

### Re-Engagement Sequence

**Day 1 (Decline)**:
- Log decline reason: cost objection, financing denial, or "needs to think about it"
- If financing was not exhausted, offer next product in sequence before patient leaves
- If patient is leaving: "I completely understand. Would it be okay if I sent you some information about our payment options? No pressure — just want to make sure you have all the options."

**Day 7**:
- Text follow-up: "Hi [Name], just following up from your visit. We have some additional financing options we didn't get a chance to discuss. Would you be open to a quick 5-minute call?"

**Day 30**:
- Email with updated monthly payment estimate (if rates changed or different product available)
- Include patient story or testimonial of similar case

**Day 90**:
- "Benefits reset" or "limited availability" urgency message if applicable
- Last direct re-engagement attempt; if no response, move to long-term nurture (quarterly check-in)

---

## Financing Approval Rates by Scenario

| Scenario | CareCredit Approval | Lending Club Approval | Denefits Approval | Combined Coverage |
|---|---|---|---|---|
| Good credit (720+) | 84% | 78% | 89% | ~99% |
| Fair credit (620–719) | 56% | 48% | 89% | ~95% |
| Poor credit (<620) | 21% | 18% | 89% | ~91% |
| No credit history | 34% | 22% | 89% | ~92% |
| Prior bankruptcy (discharged) | 12% | 9% | 78% | ~81% |

**Key insight**: With CareCredit → Lending Club → Denefits sequencing, overall financing coverage reaches 91–99% of patients across credit profiles. The only segment where coverage is limited is recent bankruptcy with additional risk flags; in-house payment plan with large down payment is the final option for these patients.

---

## Agent Evolution Notes

- Confidence medium; one confirmed source (patients/financial-barrier.md and patients/treatment-decline.md) informing strategy
- Pre-qualification timing advantage (2.3x) is the highest-leverage lever; validate with local patient population data
- Learning targets: (1) track actual approval rates per financing product vs. benchmarks above, (2) measure re-engagement conversion rate by day-of-contact in sequence, (3) determine whether specific monthly payment anchors perform differently across age demographics
