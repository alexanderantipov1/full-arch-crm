# PM/Analyst Dashboard V1 Goal

## Mission

Build the first useful read-only PM/Analyst dashboard for human project
operations and manual analysis.

The dashboard should provide filtered pipeline visibility, consult funnel
health, treatment/payment visibility, risk lists, sync health, drilldowns, and
fast person lookup across Salesforce and CareStack evidence.

## Source Handoff

- Strategy handoff: `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md` →
  `PM/Analyst Dashboard V1`
- Candidate mission: `.agents/strategy/CANDIDATE_MISSIONS.md` →
  `PM/Analyst Dashboard V1`
- External requirements source:
  `/Users/eduardkarionov/Downloads/unified-patient-profile-spec.docx`

## Product Intent

This is a human operations dashboard first. It supports project managers,
analysts, and manual work. It is intentionally separate from the deeper agent
context/workflow architecture that will be built later.

## Non-Goals

- Do not implement the uploaded document's old `patients` / `patient_*` schema
  literally.
- Do not add provider write-back in this mission.
- Do not expose raw provider payloads through dashboard responses.
- Do not turn the first treatment/payment slice into a full billing platform.

## Current State

Linear is linked:

- Parent: ENG-250.
- Children: ENG-251 through ENG-259.
- Integration gate: ENG-265.

All mission-board child tasks are merged on `main` and synced to Done in
Linear. The parent issue is ready for closeout after push/CI confirmation.
