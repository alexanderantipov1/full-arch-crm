---
title: "Emergency — Patient Profile"
category: patients
confidence: low
last_updated: 2026-06-27
source_count: 1
cited_by:
  - agents/SchedulingAgent.md
tags: [emergency, pain, same-day]
---

# Emergency

## Profile Summary
Patient in acute pain or dental emergency. Highest urgency, lowest tolerance for delays. Lifetime value depends entirely on how the emergency is handled — 68% of well-handled emergencies convert to active comprehensive care patients.

## Conversion Intelligence
- **Converts to long-term patient when:** Seen same day (within 4 hours), pain resolved, comprehensive exam offered at next visit with documented findings
- **Lost when:** Told "first available is in 3 weeks," referred elsewhere, or only immediate issue treated without pathway to comprehensive care

## Emergency-to-Comprehensive Conversion Path
1. Emergency visit → relieve pain → schedule follow-up within 5 days via [[agents/SchedulingAgent]]
2. Follow-up → comprehensive exam → treatment plan presented by [[agents/TreatmentPlanAgent]]
3. Treatment plan → financing offered day-of if large case
4. If exam reveals missing teeth, transition to [[patients/implant-consult]] workflow
5. Target: 68% of emergencies become comprehensive care patients within 90 days

## Related Pages

- [[agents/SchedulingAgent]] — Manages same-day booking and follow-up scheduling for emergency-to-comprehensive conversion
- [[agents/TreatmentPlanAgent]] — Presents comprehensive plan at follow-up exam after emergency pain resolution
- [[patients/implant-consult]] — Downstream scenario when emergency exam reveals implant candidacy
