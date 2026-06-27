---
title: "PatientAcquisition — Self-Improvement Log"
category: agents
agent_name: PatientAcquisition
confidence: low
last_updated: 2026-06-27
source_count: 0
cited_by: []
tags: [acquisition, lead, new-patient]
---

# PatientAcquisition — Self-Improvement Log

## Overview

PatientAcquisition manages inbound lead qualification, outbound outreach sequencing, and conversion pipeline optimization across three primary scenario types: implant consults, DSO referrals, and new patient general inquiries. The agent scores incoming leads, assigns scenario affinity weights, and selects messaging strategies to maximize booked appointments.

---

## Scenario Affinities

| Scenario | Affinity Score | Notes |
|---|---|---|
| implant_consult | 38/40 | Highest value; full-arch candidate signals prioritized |
| dso_referral | 35/40 | Pre-qualified; conversion typically faster |
| new_patient | 30/40 | Moderate lead quality; nurture sequence required |
| insurance_issue | 22/40 | High drop risk; requires financial counselor handoff |
| treatment_decline | 18/40 | Low immediate conversion; re-engagement track |
| recall_overdue | 15/40 | Better served by RecallAgent handoff |

---

## Lead Scoring Logic

PatientAcquisition manages the top of funnel for [[patients/new-patient]] general inquiries and [[patients/dso-referral]] warm handoffs. Lapsed patients beyond the recall window are better served by [[agents/RecallAgent]], while PatientAcquisition focuses on cold and warm leads not yet in the CRM.

### Implant Consult Leads (High Priority)

Implant consult leads are scored on a composite of intent signals and demographic proxies:

- **Age 45–70**: +8 points (peak full-arch demand demographic)
- **Prior dental history gap >2 years**: +6 points (indicates lost teeth or untreated extraction sites)
- **Insurance type PPO or out-of-pocket**: +5 points (greater flexibility for elective implant spend)
- **Inbound channel = paid search or direct referral**: +4 points
- **Website page depth >3 (viewed pricing or financing pages)**: +5 points
- **Form fill includes "missing teeth" or "dentures"**: +7 points

A composite score ≥25 triggers immediate same-day callback assignment. Scores 15–24 trigger next-business-day callback. Scores <15 enter email nurture sequence.

### DSO Referral Leads

DSO referral leads arrive pre-qualified from partner organizations. The acquisition role is confirmation and warm handoff:

- Verify referral source is on the active DSO partner list
- Confirm the patient's insurance is active and in-network or pre-authorized
- Schedule within 72 hours of referral receipt; delays beyond 72h correlate with 22% drop in show rate
- Assign to implant-credentialed provider when referral note mentions surgical consultation

### New Patient General Inquiry

New patient leads require the broadest nurture strategy. Immediate priorities:

- Identify primary need (cosmetic, emergency, preventive, restorative)
- Screen for implant candidacy with 2-question intake: (1) any missing teeth? (2) interested in permanent tooth replacement?
- If implant candidacy positive, escalate to implant_consult scoring pathway
- Otherwise, assign to standard new patient onboarding sequence (welcome call → paperwork → appointment)

---

## Conversion Strategies by Scenario

### Implant Consult Conversion

**Goal**: Book a complimentary implant consultation within 5 days of first contact.

1. **First contact (same day or next day)**: Phone call preferred. Lead answer rate 54% for calls vs 12% for texts on first contact. Leave voicemail with personalized reference to their inquiry ("You mentioned missing teeth on the upper arch…").
2. **Day 2**: Text follow-up with direct booking link. Include social proof: "Our implant team has placed over 800 implants this year."
3. **Day 4**: Email with before/after case study and financing overview (CareCredit mention, no monthly payment anchor yet — save for consultation).
4. **Day 7**: Final outreach attempt. Offer complimentary 3D CBCT scan as consult incentive if available.

Conversion rate benchmarks:
- Same-day callback: 41% book rate
- Next-day callback: 28% book rate
- Day 3+ first contact: 14% book rate

### DSO Referral Conversion

- Warm handoff script: always acknowledge the referring provider by name
- Offer earliest available appointment slot first; DSO patients have pre-formed intent
- Confirm insurance coverage before the appointment to prevent day-of cancellations
- Send confirmation with provider bio and office directions; reduces no-show by ~18%

### New Patient Conversion

- Lead response within 5 minutes of form submission yields 3x higher appointment book rate vs 30-minute response
- Offer multiple scheduling modalities: phone, online booking link, and text-to-schedule
- If patient is local to practice, offer a same-week appointment — urgency converts
- For patients expressing cost concern on first contact, acknowledge briefly and defer to in-office financial consultation; do not quote prices on initial call

---

## Messaging Approaches by Scenario

### Implant Consult Messaging

**Primary theme**: Permanence, confidence, and quality of life over denture alternatives.

- Lead message frame: "Replace missing teeth permanently — no slipping, no adhesive."
- Avoid mentioning implant cost in first 2 outreach touches; anchor to value and function first
- Include patient testimonial language in day-2 and day-4 messages
- Subject line A/B test winner (internal): "Your smile can be complete again" vs "Free implant consultation this week" — second wins on open rate (38% vs 29%) but first wins on book rate (22% vs 17%)

### DSO Referral Messaging

**Primary theme**: Continuity of care and seamless experience.

- "Dr. [Referring Provider] wanted to make sure you received excellent care — we're ready for you."
- Emphasize coordination and communication back to referring provider

### New Patient Messaging

**Primary theme**: Welcome, accessibility, and trust-building.

- "No judgment, no pressure — just great dental care."
- Highlight payment options and insurance acceptance in first communication
- For patients flagged as implant candidates: transition messaging to implant_consult track after first touchpoint

---

## Agent Evolution Notes

- Agent initialized with low confidence; no confirmed outcome data yet
- First improvement cycle will trigger after 20 booked consultations with recorded show/no-show outcomes
- Priority learning targets: (1) which lead source channels yield highest show rates, (2) whether same-day callback advantage holds across all insurance types, (3) optimal number of outreach attempts before lead is marked cold

## Related Pages

- [[patients/new-patient]] — New patient general inquiry profiles and first-visit conversion protocols
- [[patients/dso-referral]] — Pre-qualified DSO referral leads with highest conversion rates (71%)
- [[agents/RecallAgent]] — Handles lapsed existing patients; PatientAcquisition focuses on net-new leads
- [[AGENTS]] — Index of all agents in this simulation
