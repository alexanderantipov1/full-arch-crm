# Workflow Ready Ingest Foundation

## Goal

Convert the Salesforce and CareStack data Fusion already pulls into
workflow-ready person-linked events and reviewable context inputs.

Future workflow runners and agents should consume normalized facts from
services and tool contracts instead of reverse-engineering raw provider
payloads.

## Source Handoff

- Strategy handoff: `.agents/strategy/HANDOFF_TO_ORCHESTRATOR.md` →
  `Workflow Ready Ingest Foundation`
- Source candidate: `.agents/strategy/CANDIDATE_MISSIONS.md` →
  `Person Data And Event Provenance Foundation`
- Source doctrine:
  `.agents/strategy/PERSON_DATA_EVENT_PROVENANCE_DOCTRINE.md`
- Source technical spec:
  `.agents/strategy/RAW_TO_CONTEXT_NORMALIZATION_SPEC.md`

## Linear

- Parent issue: ENG-235
- Child issues: ENG-236 through ENG-244

