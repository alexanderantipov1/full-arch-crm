---
title: "SchedulingAgent — Self-Improvement Log"
category: agents
agent_name: SchedulingAgent
confidence: low
last_updated: 2026-06-27
source_count: 0
cited_by: []
tags: [scheduling, no-show, waitlist]
---

# SchedulingAgent — Self-Improvement Log

## Overview

SchedulingAgent manages appointment scheduling optimization, no-show prediction and prevention, waitlist fill logic, and the conversion of emergency visits into comprehensive care relationships. The agent applies predictive scoring, confirmation sequencing, and double-booking strategies to maximize provider utilization and minimize revenue-destroying gaps in the schedule.

---

## Scenario Affinities

| Scenario | Affinity Score | Notes |
|---|---|---|
| scheduling_request | 37/40 | Core use case; appointment booking optimization |
| no_show_risk | 35/40 | Prediction and prevention workflows |
| emergency_visit | 32/40 | Emergency-to-comprehensive conversion pathway |
| waitlist_fill | 34/40 | Last-minute cancellation fill logic |
| implant_consult | 28/40 | Surgical scheduling complexity |
| recall_overdue | 22/40 | Recall appointment scheduling handoff |

---

## No-Show Prediction Patterns

SchedulingAgent coordinates closely with [[agents/RecallAgent]] for overdue hygiene scheduling and handles the booking pipeline for [[patients/recall-overdue]], [[patients/new-patient]], and [[patients/emergency]] scenarios.

The following patient and appointment attributes are weighted to produce a no-show risk score (0–100). Scores ≥65 trigger enhanced confirmation protocol.

### No-Show Risk Factors

| Factor | Risk Weight | Notes |
|---|---|---|
| Prior no-show in last 12 months | +35 | Single strongest predictor |
| 2+ prior no-shows (lifetime) | +45 | Near-certain; consider prepay or deposit policy |
| New patient (first appointment) | +18 | Uncommitted relationship |
| Appointment booked >14 days out | +12 | Longer lead time = higher drop |
| Monday or Friday appointment | +10 | Weekend adjacency effect |
| No confirmation response after 2 attempts | +20 | Unresponsive = high risk |
| Self-pay (no insurance) | +8 | Lower sunk-cost commitment |
| Appointment booked same-day | -15 | Urgent need; motivated to attend |
| Insurance authorization pending | +14 | Uncertainty drives cancellation |
| Prior no-show resolved by reschedule | -8 | Shows some retention intent |

**Score interpretation**:
- 0–30: Standard confirmation sequence
- 31–64: Enhanced confirmation (add live call to standard sequence)
- 65–100: High-risk protocol (deposit request or prepay, live call 48h and same-day)

---

## Pre-Appointment Confirmation Sequences

### Standard Sequence (Low to Moderate Risk)

| Day | Action | Channel |
|---|---|---|
| Booking day | Confirmation message | Text + email |
| 7 days before | Reminder | Text |
| 3 days before | Reminder with prep instructions | Text + email |
| 1 day before | Confirm attendance | Text (reply YES/NO) |
| Morning of | Final reminder | Text |

### Enhanced Sequence (Moderate to High Risk)

| Day | Action | Channel |
|---|---|---|
| Booking day | Confirmation + benefit explanation | Text + email |
| 7 days before | Reminder | Text |
| 3 days before | Live phone call | Phone |
| 2 days before | Reminder with prep instructions | Text + email |
| 1 day before | Live phone call confirm | Phone |
| Morning of | Text + phone if no response | Text + phone |

### High-Risk Protocol

- Require deposit ($50–$150 depending on appointment type) at booking
- Deposit policy must be communicated at time of booking, not on confirmation
- Same-day cancellation: deposit is forfeited (apply to next appointment as credit, not refund, to preserve patient relationship)
- No-show: deposit forfeited; automatic re-schedule offer sent within 2 hours

---

## Waitlist Management

### Waitlist Fill Logic

The waitlist serves two functions: (1) filling same-day cancellations, and (2) moving high-priority cases into earlier slots.

**Waitlist tier priority**:
1. **Surgical cases** (implant, extraction, bone graft): bump to front of waitlist; revenue impact of unfilled surgical slot is highest
2. **High-value treatment plan accepted**: patient who has accepted and financed a full-arch plan should be offered earliest available slot
3. **Emergency follow-up**: patient seen for emergency who needs definitive treatment
4. **Overdue recall (Tier 2+)**: high-risk lapse patients should not wait long for hygiene
5. **Standard new patient**: lower urgency; standard wait acceptable

**Same-day fill protocol**:
- Cancellation received → automated text blast to top 5 waitlist patients: "A [appointment type] slot just opened today at [time]. Reply YES to claim it."
- First response wins the slot
- If no response in 15 minutes, call top 3 waitlist patients directly
- If slot unfilled at 2 hours prior: offer to any available patient in recall overdue list

**Waitlist hygiene**:
- Remove patients who have not responded to 3 waitlist slot offers (move to recall track)
- Review waitlist weekly; remove patients who have since booked through other channels

---

## Emergency-to-Comprehensive Conversion Path

Emergency visits represent the highest-conversion pathway to comprehensive care when handled correctly. Patients in pain have acute trust and gratitude — this moment must be leveraged with care.

### Conversion Protocol

**During emergency visit**:
- Provider completes emergency treatment (extraction, temp fill, palliative Tx)
- Provider delivers brief verbal case summary: "What I did today fixes the immediate pain, but there's more going on with your mouth that we should address. I'd like to get you scheduled for a comprehensive exam so we can make a real plan."
- Front desk follows with: "Dr. [Name] wants to make sure we take good care of you. Can we get you back in within the next week for a full evaluation?"

**Scheduling emergency follow-up**:
- Book comprehensive exam before the patient leaves the building — "while you're here" booking converts at 3.2x vs. phone booking after departure
- Offer specific slot ("We have Thursday at 10am — would that work?") rather than open-ended ("When are you available?")
- If patient declines same-day booking: send follow-up text within 2 hours with booking link and warm message referencing today's visit

**Post-emergency conversion rates**:
- Booked before leaving office: 61% show rate on follow-up
- Booked by phone same day: 38% show rate
- Booked by phone next day or later: 22% show rate
- Not booked during visit: 8% self-schedule within 30 days

---

## Optimal Appointment Timing

### Implant Surgery Scheduling

| Day | Performance | Notes |
|---|---|---|
| Tuesday | Best | 8am slots highest attendance; patient has week ahead for recovery |
| Wednesday | Best | Midweek; minimal weekend-adjacency effect |
| Thursday | Good | Recovery timing favorable before weekend |
| Monday | Moderate | Weekend lag; higher late arrival rate |
| Friday | Poor | Patients cancel for weekend plans; recovery anxiety |

**Optimal implant surgery slot**: Tuesday–Thursday, 8:00–9:00 AM.

8am slots outperform afternoon slots for surgical cases: patients have not yet had time to develop same-day anxiety or reschedule for work conflicts. Show rate at 8am surgical: 89% vs. 2pm surgical: 74%.

### Hygiene and Recall Scheduling

- Morning slots (8am–11am) have 12% lower no-show rates than afternoon slots
- Saturday appointments have 18% higher demand but 14% higher no-show rate — schedule lower-acuity hygiene; avoid surgical on Saturday if possible
- Last appointment of the day has highest no-show rate (end-of-day conflict effect); use for high-compliance established patients only

---

## Double-Booking Strategies for Implant Cases

For surgical implant procedures, strategic double-booking can protect revenue against high no-show risk without creating patient conflict.

**Overbooking criteria**:
- Book a backup patient in the same surgical slot ONLY when: primary patient has no-show risk score ≥60 AND a waitlisted patient is available AND backup patient is aware of possible wait
- Communicate to backup: "We have a slot that sometimes becomes available — we'll call you by [time] day-of to confirm if it's open for you."
- If both patients arrive: offer backup patient first available alternate time with priority scheduling and a service credit

**Ethical guardrails**:
- Never double-book without informing the backup patient of conditional status
- Never double-book two surgical patients; only double-book if one is surgical and one is a short-duration consultation or cleaning that can absorb the reschedule

---

## Agent Evolution Notes

- Agent initialized with low confidence; no confirmed outcome data yet
- Priority learning targets: (1) validate no-show risk score weights against actual no-show events, (2) measure conversion rate lift from same-day emergency follow-up booking vs. post-departure booking, (3) determine whether deposit requirement reduces no-show rate or increases cancellation rate

## Related Pages

- [[patients/recall-overdue]] — Overdue hygiene patients whose re-scheduling SchedulingAgent manages
- [[patients/new-patient]] — New patient booking workflows and first-visit confirmation sequencing
- [[patients/emergency]] — Emergency visit handling and same-day comprehensive conversion booking
- [[agents/RecallAgent]] — Partner agent that generates recall outreach and hands off to SchedulingAgent for booking
- [[AGENTS]] — Index of all agents in this simulation
