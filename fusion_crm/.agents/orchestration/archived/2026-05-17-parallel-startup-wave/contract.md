# Shared Contract

## Purpose

- Coordinate independent workstreams without allowing them to mutate shared state unexpectedly.

## API Contract

- No API contract changes are assigned in Wave 1.
- B1 may recommend API changes but must not implement them.

## Data / Schema Contract

- No schema or migration changes are assigned in Wave 1.
- No shipped Alembic revisions may be edited.

## UI / UX Contract

- No UI changes are assigned in Wave 1.

## Acceptance Criteria

- A2-live report identifies the latest deploy-prod failure evidence or explains the exact access blocker.
- B1 report identifies correctness risks in the current tenant credential diff and whether it can proceed as ENG-177/ENG-165 work.
- C1 report decomposes ENG-166/ENG-167/ENG-168 into safe next tasks with file ownership and sequencing.

## Non-Negotiable Constraints

- Do not change this contract inside a worker task.
- If the contract is incomplete or wrong, stop and report to the orchestrator.
- Do not commit, push, merge, deploy, rerun workflows, change Cloud Run traffic/config, edit env/secrets, or mutate Linear statuses from worker tasks.

## Wave R Contract

### Purpose

Advance the data-foundation sequence after Q1 with one migration writer and
parallel read-only planning/review work.

### Data / Schema Contract

- R1 is the only Wave R writer allowed to add a migration.
- R1 may add `ingest.normalized_person_hint` only.
- R1 must not edit shipped Alembic revisions.
- R1 must not change Salesforce/CareStack ingest behavior.
- `person_uid` and `source_link_id` in `ingest.normalized_person_hint` are
  plain UUID pointers; no identity model/repository imports.
- Normalized hints must not contain raw provider payloads or clinical text in
  `meta` or `quality_flags`.

### API / Worker Contract

- No API routes or worker jobs are assigned in Wave R.
- R2 may propose future ENG-185 route/job/service changes in its report only.

### Acceptance Criteria

- R1 report documents files changed, migration revision/down_revision,
  verification, and deviations from P2.
- R2 report documents the future ENG-185 implementation sequence and
  ownership.
- R3 report documents migration-chain and verification risks.
- Codex reviews reports before any Linear status is moved beyond In Progress.

## Wave S Contract

### Purpose

Advance ENG-185 with one identity-service writer and parallel read-only
planning/review work, without opening a new migration writer wave.

### Data / Schema Contract

- S1 must not add or edit Alembic revisions.
- S1 may update identity models only for Python constants / service validation,
  not schema shape.
- `identity.match_candidate.hint_id` remains a plain UUID pointer in this wave.
- `identity` must not import `ingest`; use an identity-owned `MatchHintIn` DTO
  or equivalent adapter contract.
- Match policy evidence and conflicts must not contain raw provider payloads or
  clinical text.

### API / Worker Contract

- No API routes, worker jobs, Salesforce/CareStack ingest behavior, or
  `ops.inquiry` work is assigned in Wave S.
- S2 may propose the future Salesforce cutover in its report only.

### Acceptance Criteria

- S1 report documents files changed, DTO/result contract, match policy tier
  behavior, verification, and deviations from R2/P2.
- S2 report documents the future Salesforce cutover sequence and ownership.
- S3 report documents import-boundary, migration-free, PHI, idempotency, and
  verification risks.
- Codex reviews reports before any Linear status is moved beyond In Progress.

## Wave T Contract

### Purpose

Complete the ENG-185 Salesforce cutover after S1 by wiring the existing manual
Lead pull to normalized hints and the identity match policy entry point.

### Data / Schema Contract

- T1 must not add or edit Alembic revisions.
- T1 must not edit identity schemas/models/services/repositories.
- T1 must not edit `ops` schema/service/model files.
- Raw Salesforce records remain captured verbatim before any normalization.
- The normalized hint and identity match DTO carry normalized fields only; raw
  SOQL records must not be passed into identity.

### API / Worker Contract

- No API routes, frontend files, or worker jobs are assigned in Wave T.
- The existing manual pull API and `SfLeadOut` DTO contract must remain stable.
- `ops.lead.extra.is_reactivation` remains a boolean. Map it from
  `ResolveFromHintResult.was_existing_person_match`.

### Acceptance Criteria

- T1 report documents files changed, cutover behavior, verification, and
  deviations from S2.
- T2 report documents cutover risks and post-T1 verification checklist.
- Codex reviews reports before any Linear status is moved beyond In Progress.
