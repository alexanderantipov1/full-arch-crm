# Acceptance

## Parent Mission Acceptance

1. Existing Salesforce Lead/Event and CareStack Patient/Appointment pullers
   remain idempotent and continue writing raw evidence first.
2. Existing pullers emit normalized `interaction.event` rows for
   workflow-relevant changes.
3. The event taxonomy covers lead, consultation, task, and call-reference
   milestones needed by the first operational timeline.
4. Scheduled and manual provider pulls write real `integrations.sync_run`
   rows with counts, status, object scope, and errors.
5. Salesforce Task pull exists and classifies each task as action-oriented,
   historical activity, or call-related.
6. Call references from Salesforce Tasks/Events are captured as person-linked
   evidence with source references, without downloading or transcribing audio.
7. A person operational timeline read surface exists for UI/tools to fetch
   normalized events and safe summaries by `person_uid`.
8. Tests prove no raw provider payload or clinical/free-text field leaks into
   ordinary timeline/context outputs.

## Linear Acceptance Mapping

- ENG-236: interaction event schema contract.
- ENG-237: Salesforce Lead timeline events.
- ENG-238: Salesforce Event and CareStack Appointment consultation events.
- ENG-239: provider sync-run journaling.
- ENG-240: Salesforce Task ingest and classification.
- ENG-241: call reference extraction without transcription.
- ENG-242: person operational timeline read surface.
- ENG-243: fixtures and verification coverage.
- ENG-244: docs and data catalog sync.

