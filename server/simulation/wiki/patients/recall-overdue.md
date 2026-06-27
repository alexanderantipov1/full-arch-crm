---
title: "Recall Overdue — Patient Profile"
category: patients
confidence: medium
last_updated: 2026-06-27
source_count: 2
cited_by:
  - agents/RecallAgent.md
tags: [recall, reactivation, hygiene]
---

# Recall Overdue

## Profile Summary
Existing patient, 12–36+ months since last visit. Often lapsed due to cost, life changes, or dissatisfaction. High risk of having untreated decay or periodontal progression. Typically responds well to personal outreach vs. generic reminders.

## Treatment Patterns

| Procedure | CDT | Avg Value | Conversion Rate |
|-----------|-----|-----------|-----------------|
| Prophy + exam | D1110+D0120 | $280–$420 | 81% once in chair |
| Periodontal scaling | D4341 | $220–$380/quad | 44% |
| Restorative follow-up | D2140–D2750 | $380–$2,100 | 37% |

## Conversion Intelligence
- **Converts when:** Personal phone call (not SMS), specific reminder of last visit, 10% loyalty discount offered, morning appointment
- **Declines when:** Generic automated text only, balance due on account, appointment >3 weeks out

## Communication Intelligence
- Segment by time-since-visit: 12–18 mo (warm), 19–36 mo (warm-cold), 36+ mo (re-acquisition)
- 36+ month: treat as [[patients/new-patient]] acquisition, not recall; hand off to [[agents/PatientAcquisition]] pipeline
- Best channel: phone call → voicemail → text → email (in that order)
- Booking is coordinated through [[agents/SchedulingAgent]] after initial outreach converts

## Related Pages

- [[agents/RecallAgent]] — Primary agent for recall outreach, segmentation, and re-engagement campaigns
- [[agents/SchedulingAgent]] — Downstream agent that books appointments after recall outreach converts
- [[patients/new-patient]] — Treatment path for 36+ month lapsed patients who re-enter as new patients
