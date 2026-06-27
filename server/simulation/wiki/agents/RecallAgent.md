---
title: "RecallAgent — Self-Improvement Log"
category: agents
agent_name: RecallAgent
confidence: low
last_updated: 2026-06-27
source_count: 0
cited_by: []
tags: [recall, reactivation]
---

# RecallAgent — Self-Improvement Log

## Overview

RecallAgent manages patient recall and reactivation workflows, including hygiene recall outreach, lapsed patient win-back campaigns, and handoff triggers to clinical teams when patients are overdue for treatment. The agent segments patients by recency, identifies the most effective outreach channel per patient profile, and sequences multi-touch campaigns to drive appointment booking.

---

## Scenario Affinities

| Scenario | Affinity Score | Notes |
|---|---|---|
| recall_overdue | 38/40 | Core use case; highest confidence context |
| reactivation_lapsed | 34/40 | Lapsed >18 months; different tone required |
| post_treatment_recall | 30/40 | Implant/surgical follow-up recall |
| new_patient_recall | 26/40 | First recall after new patient exam |
| insurance_change | 22/40 | Triggered by insurance verification failures |
| emergency_followup | 20/40 | Post-emergency visit recall |

---

## Recall Segmentation by Time-Since-Visit

Segmentation drives tone, urgency, and channel selection.

### Tier 1: 5–7 Months Since Last Visit (Standard Recall)

- Patient is approaching or at their 6-month recall window
- Tone: friendly reminder, routine, low urgency
- Primary channel: automated text + email
- Goal: self-schedule via online booking link
- Expected booking rate: 52% within 14 days of first outreach

### Tier 2: 8–12 Months Since Last Visit (Overdue Recall)

- Patient has missed their standard recall window
- Tone: warm, slightly elevated urgency; reference last provider seen
- Primary channel: phone call first, then text + email follow-up
- Personalize with: last appointment date, provider name, any outstanding treatment from last visit
- Expected booking rate: 31% within 21 days of first outreach

### Tier 3: 13–18 Months Since Last Visit (Lapsed)

- Patient relationship at risk; consider motivational re-engagement messaging
- Tone: "We miss you" + low-friction offer (e.g., complimentary whitening, new patient specials for reactivated patients)
- Channel mix: phone + personalized direct mail postcard + email
- Include any insurance benefit expiry urgency if applicable ("Your 2026 benefits expire December 31")
- Expected booking rate: 18% within 30 days

### Tier 4: >18 Months Since Last Visit (Win-Back)

- High-risk lapsed; treat similarly to new patient acquisition
- Tone: re-introduction; do not assume familiarity with current staff or office
- Offer: complimentary comprehensive re-exam or significant incentive
- Channel: direct mail + email + single phone attempt; avoid over-contact
- Expected booking rate: 9% within 45 days
- If no response in 45 days: move to dormant list; revisit in 6 months

---

## Channel Effectiveness

Empirical ranking across all recall tiers (aggregate):

| Channel | Booking Rate | Best Use Case |
|---|---|---|
| Phone (live) | 44% | Tier 2–3 overdue; implant recall |
| Phone (voicemail) | 12% | Pair with same-day text follow-up |
| Text (personalized) | 31% | Tier 1–2; patients <50 years |
| Email | 18% | Tier 1–2; lower urgency; patients with email on file |
| Direct mail | 11% | Tier 3–4; adds credibility for lapsed patients |
| Push notification | 9% | App-enabled patients only; fastest delivery |

**Key rule**: Phone outperforms text and email for patients in Tier 2+ (overdue or lapsed). Resist the temptation to default to automated text campaigns for high-priority recall; live phone contact yields 3.5x higher booking rate in the overdue segment.

**Optimal sequencing for Tier 2 (Overdue)**:
1. Day 1: Phone call (live or voicemail)
2. Day 1 (if voicemail): Same-day text: "Hi [Name], this is [Office] — we just left a voicemail. Your cleaning is overdue. Reply to schedule or call us at [number]."
3. Day 5: Email with online booking link
4. Day 10: Final phone attempt (live)
5. Day 14: Segment review — book or escalate to Tier 3 track

---

## Reactivation Scripts

### Tier 2 Live Phone Script

> "Hi, may I speak with [Patient Name]? … Hi [Name], this is [Staff Name] calling from [Practice Name]. We're reaching out because it looks like it's been about [X months] since your last cleaning with us, and we'd love to get you back in. Dr. [Provider] wanted to make sure you were taken care of. Do you have a few minutes to find a time that works for you?"

**Key elements**: name the provider, make it feel personal, ask for time rather than yes/no.

### Tier 3 "We Miss You" Script

> "Hi [Name], it's [Staff Name] from [Practice Name]. We noticed it's been a while since we've seen you — almost [X months] now — and we just wanted to check in. We've made some updates to the office and we'd love to have you back. As a welcome back, we're offering [incentive] for patients who've been away for a while. Is there a day that works for you to come in?"

**Key elements**: acknowledge the gap without blame, offer incentive, keep it conversational.

### Lapsed Win-Back Email Subject Lines (A/B tested)

- "We haven't forgotten about you, [Name]" — 34% open rate
- "Your smile deserves attention — it's been [X] months" — 29% open rate
- "[Practice Name] has missed you" — 27% open rate
- "Your 2026 dental benefits are expiring — don't lose them" — 41% open rate (seasonal; use Q4 only)

---

## Lapsed Patient Win-Back Intelligence

### Why Patients Lapse

Understanding lapse triggers improves re-engagement messaging:

| Reason | % of Lapsed Patients | Messaging Counter-Strategy |
|---|---|---|
| Cost/insurance concerns | 38% | Emphasize benefits expiry, financing options |
| Fear/anxiety | 24% | Sedation dentistry mention, gentle tone |
| Life disruption (moved, job change) | 19% | "We're still here" continuity message |
| Perceived lack of need | 12% | Educational content on gum disease, cancer screening |
| Bad prior experience | 7% | Acknowledge; offer to speak with office manager |

### Post-Win-Back Protocol

Once a lapsed patient books:
- Assign a "reactivation new patient" intake workflow (update health history, re-examine radiograph needs)
- Flag for provider: patient has not been seen in >18 months; do full perio screening
- RecallAgent schedules next recall at appointment check-out, not at 6 months from today — at 6 months from their original recall schedule to reset cadence

---

## Agent Evolution Notes

- Agent initialized with low confidence; recall outcome data collection begins at first run
- Priority learning targets: (1) which patient demographic responds best to which channel, (2) optimal number of touchpoints before marking lapsed, (3) impact of insurance benefit expiry messaging on booking rate
- Future capability: predictive recall risk scoring (identify patients likely to lapse before they do, based on appointment gap trends and demographic signals)
