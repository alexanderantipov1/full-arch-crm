---
title: "New Patient — Patient Profile"
category: patients
confidence: low
last_updated: 2026-06-27
source_count: 1
cited_by:
  - agents/PatientAcquisition.md
tags: [new-patient, acquisition, first-visit]
---

# New Patient

## Profile Summary
First-time patient. No prior relationship. Often comes via Google search, referral, or insurance directory. High anxiety about unknown practice. First 15 minutes determine lifetime value.

## Conversion Intelligence
- **Converts (becomes active patient) when:** Greeted by name before seated, provider addresses all stated concerns, treatment plan presented same day with clear next steps
- **Churns when:** Wait >15 min without acknowledgment, provider seems rushed, estimate not provided

## First Visit Protocol
1. Name recognition at front desk (pre-read chart before they arrive)
2. Comprehensive exam same day (D0150)
3. X-rays if not brought from prior dentist
4. Treatment plan printed and walked through before patient leaves — see [[agents/TreatmentPlanAgent]] for presentation sequencing
5. Next appointment booked before checkout via [[agents/SchedulingAgent]]
6. If implant candidacy identified at exam, transition to [[patients/implant-consult]] workflow

## Related Pages

- [[agents/PatientAcquisition]] — Agent responsible for lead scoring and first-contact conversion before the new patient visit
- [[agents/SchedulingAgent]] — Handles appointment booking and confirmation sequencing for new patient visits
- [[agents/TreatmentPlanAgent]] — Presents findings and treatment options at the first comprehensive exam
- [[patients/implant-consult]] — Escalation pathway when implant candidacy is identified at new patient exam
