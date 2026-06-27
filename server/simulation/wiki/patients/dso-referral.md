---
title: "DSO Referral — Patient Profile"
category: patients
confidence: low
last_updated: 2026-06-27
source_count: 1
cited_by:
  - agents/PatientAcquisition.md
  - dso/network-overview.md
tags: [dso, referral, multi-location]
---

# DSO Referral

## Profile Summary
Patient referred from another location within the DSO network, or from an affiliated referring practice. High trust level (warm referral). Often already has records, X-rays, and partial treatment plan from prior location.

## Conversion Intelligence
- Convert at 71% vs 38% for cold leads — highest conversion scenario
- Managed by [[agents/PatientAcquisition]] with warm handoff script acknowledging the referring provider by name
- Transfer records request before first appointment — patients who arrive "prepared" convert at 84%
- If referral note includes surgical consultation, route to [[patients/implant-consult]] workflow immediately
- Treatment plan at first visit presented by [[agents/TreatmentPlanAgent]]

## Related Pages

- [[agents/PatientAcquisition]] — Manages warm handoff, records transfer, and booking for DSO referrals
- [[agents/TreatmentPlanAgent]] — Presents treatment plan at first visit; leverages records transferred from referring provider
- [[patients/implant-consult]] — Escalation pathway when DSO referral includes surgical or implant consultation
