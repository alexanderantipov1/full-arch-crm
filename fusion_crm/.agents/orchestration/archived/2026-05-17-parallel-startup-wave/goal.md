# Mission Goal

## Desired Outcome

Stabilize the current Salesforce/CareStack data-foundation path and start
the next additive implementation wave while keeping Codex as orchestrator,
reviewer, and verifier and Claude Code as scoped implementation worker.

## Done State

This mission segment is complete when:

- `ENG-188` Alembic drift is resolved and Linear reflects the result.
- `ENG-182` has a reviewed `identity.match_candidate` foundation patch or a
  documented blocker report.
- Worker changes stay inside assigned ownership.
- No shipped Alembic revision is edited.
- No `.env*`, secrets, deploy scripts, GitHub Actions deploy workflow, Cloud
  Run services/jobs, commits, pushes, merges, or deployments are performed
  without explicit user approval.
- Codex records verification evidence and updates Linear/mission handoff.

## Evidence Required

- `reports/Q0-eng188-alembic-drift.md` exists and documents the Alembic drift
  fix.
- `reports/Q1.md` exists for the `ENG-182` worker result, or the worker
  blocker is recorded.
- `cd packages/db && ../../.venv/bin/alembic check` exits 0 after integration.
- Focused tests for changed domains pass.
- `git diff --check` exits 0.
- Linear comments/statuses are synced for `ENG-188`, `ENG-181`, and `ENG-182`.

## Constraints

- Conversation with the user is in Russian.
- Repository artifacts are written in English.
- Follow root and local `CLAUDE.md` files.
- PHI stays out of `ops` and identity matching evidence.
- `identity.person.id` remains the canonical `person_uid`.
- Additive migrations only; existing migrations are immutable.

## Evaluator

Codex orchestrator evaluates the mission goal after every worker report and
returns only:

- `complete`
- `not complete`

If `not complete`, Codex lists the smallest missing evidence or blocker.

## Continuation Budget

Maximum next actions before asking the user again:

1. Review Q1 report and diff.
2. Run focused verification.
3. Apply only minor integration fixes inside Q1 ownership if needed.
4. Update Linear and handoff.

Escalate if Q1 requires broader architecture changes, production/deploy
actions, edits outside ownership, or a second failed worker launch.

## Latest Evaluation

Date: 2026-05-19
Result: complete

Evidence:

- `reports/Q0-eng188-alembic-drift.md` documents the ENG-188 Alembic drift
  fix.
- `reports/Q1.md` documents the ENG-182 implementation, Codex review fix, and
  post-review verification.
- `cd packages/db && ../../.venv/bin/alembic check` exits 0.
- `.venv/bin/python -m pytest tests/identity -q` exits 0 with 45 passed.
- `make verify` exits 0.
- `git diff --check` exits 0.
- Linear sync for ENG-182 is updated to In Review with evidence comments;
  ENG-181 receives a parent progress comment. ENG-188 was already synced Done
  after Q0.

## Next Segment: Wave R

Date: 2026-05-19

### Desired Outcome

Start the next additive data-foundation wave with more parallelism while
keeping only one active migration writer.

### Done State

Wave R is complete when:

- `ENG-185` has either a reviewed `ingest.normalized_person_hint` foundation
  patch or a documented blocker report.
- `ENG-185` has a read-only implementation plan that accounts for Q1/R1 and
  the existing Salesforce ingest path.
- The verification scout report identifies the post-R1 review checklist and
  any migration-chain risk.
- Worker changes stay inside assigned ownership.
- No shipped Alembic revision is edited.
- No `.env*`, secrets, deploy scripts, GitHub Actions deploy workflow, Cloud
  Run services/jobs, commits, pushes, merges, or deployments are performed
  without explicit user approval.

### Evidence Required

- `reports/R1.md` exists for the `ENG-185` worker result, or the worker
  blocker is recorded.
- `reports/R2.md` exists for the `ENG-185` read-only plan.
- `reports/R3.md` exists for verification scouting.
- Focused ingest tests pass after R1, unless a blocker is documented.
- `cd packages/db && ../../.venv/bin/alembic check` exits 0 after R1 review,
  unless a blocker is documented.
- `git diff --check` exits 0.
- Linear comments/statuses are synced for `ENG-185`; `ENG-183` remains
  untouched because it is the later `ops.inquiry` slice.

### Continuation Budget

Maximum next actions before asking the user again:

1. Launch R1/R2/R3.
2. Review R1/R2/R3 reports.
3. Run focused verification.
4. Apply only minor integration fixes inside R1 ownership if needed.
5. Update Linear and handoff.

Escalate if R1 requires broader architecture changes, a second migration
writer, production/deploy actions, edits outside ownership, or a second failed
worker launch.

### Latest Wave R Evaluation

Date: 2026-05-19
Result: complete

Evidence:

- `reports/R1.md` documents the ENG-185 normalized-hint implementation,
  Codex review correction, and post-review verification.
- `reports/R2.md` documents the follow-up ENG-185 pipeline integration plan.
- `reports/R3.md` documents the verification scout checklist.
- `.venv/bin/python -m pytest tests/ingest -q` exits 0 with 31 passed.
- `.venv/bin/python -m pytest tests/ingest tests/identity tests/ops -q` exits
  0 with 95 passed.
- `make verify` exits 0.
- `cd packages/db && ../../.venv/bin/alembic check` exits 0 after local
  `upgrade head`.
- `cd packages/db && ../../.venv/bin/alembic downgrade -1 && ../../.venv/bin/alembic upgrade head && ../../.venv/bin/alembic check`
  exits 0.
- `git diff --check` exits 0.
- Linear sync: `ENG-185` is ready for In Review with evidence; `ENG-183` was
  corrected back to Backlog.

## Next Segment: Wave S

Date: 2026-05-19

### Desired Outcome

Implement the identity-only ENG-185 follow-up that introduces
`IdentityService.resolve_or_create_from_hint(...)` and its match policy result
contract, while keeping Salesforce/CareStack cutover and `ops.inquiry` out of
scope.

### Done State

Wave S is complete when:

- `ENG-185` has either a reviewed identity match policy entry-point patch or a
  documented blocker report.
- A read-only Salesforce cutover plan identifies the next safe wave after the
  identity service is reviewed.
- A read-only verification scout report identifies import-boundary,
  idempotency, PHI/raw-payload, tenant isolation, and migration-free review
  risks.
- Worker changes stay inside assigned ownership.
- No Alembic revision is added or edited.
- No Salesforce/CareStack behavior, `ops.inquiry`, `.env*`, secrets, deploy
  scripts, GitHub Actions deploy workflow, Cloud Run services/jobs, commits,
  pushes, merges, or deployments are performed without explicit user approval.

### Evidence Required

- `reports/S1.md` exists for the identity match policy worker result, or the
  worker blocker is recorded.
- `reports/S2.md` exists for the Salesforce cutover plan.
- `reports/S3.md` exists for verification scouting.
- Focused identity tests pass after S1, unless a blocker is documented.
- `cd packages/db && ../../.venv/bin/alembic check` exits 0 after S1 review,
  unless a blocker is documented.
- `git diff --check` exits 0.
- Linear comments/statuses are synced for `ENG-185`; `ENG-183` remains
  untouched because it is the later `ops.inquiry` slice.

### Continuation Budget

Maximum next actions before asking the user again:

1. Launch S1/S2/S3.
2. Review S1/S2/S3 reports.
3. Run focused verification.
4. Apply only minor integration fixes inside S1 ownership if needed.
5. Update Linear and handoff.

Escalate if S1 requires broader architecture changes, any migration writer,
production/deploy actions, edits outside ownership, PHI-sensitive decisions, or
a second failed worker launch.

### Latest Wave S Evaluation

Date: 2026-05-19
Result: complete

Evidence:

- `reports/S1.md` documents the ENG-185 identity match policy entry point,
  Codex review, and post-review verification.
- `reports/S2.md` documents the future Salesforce cutover plan.
- `reports/S3.md` documents the Wave S verification scout checklist.
- `.venv/bin/python -m pytest tests/identity -q` exits 0 with 66 passed.
- `.venv/bin/python -m pytest tests/identity tests/ingest tests/ops -q` exits
  0 with 116 passed.
- `cd packages/db && ../../.venv/bin/alembic check` exits 0 with no new upgrade
  operations detected.
- `git diff --check` exits 0.
- `make verify` exits 0 after a small orchestrator-tooling lint fix outside
  product scope.
- Linear sync: `ENG-185` is ready to return to In Review with evidence;
  `ENG-183` remains Backlog.

## Next Segment: Wave T

Date: 2026-05-19

### Desired Outcome

Cut Salesforce Lead pull over to the reviewed ENG-185 hint + identity match
policy path while preserving the current API/UI contract and
`is_reactivation` semantics.

### Done State

Wave T is complete when:

- Salesforce `SfLeadIngestService.pull_recent(...)` captures a raw event,
  captures one normalized person hint from that raw event, calls
  `IdentityService.resolve_or_create_from_hint(...)`, and upserts the lead.
- Hidden SF-specific identity matching is removed from the ingest service.
- The manual pull API shape and frontend contract remain unchanged.
- Worker changes stay inside assigned ownership.
- No Alembic revision is added or edited.
- No `ops.inquiry`, `.env*`, secrets, deploy scripts, GitHub Actions deploy
  workflow, Cloud Run services/jobs, commits, pushes, merges, or deployments
  are performed without explicit user approval.

### Evidence Required

- `reports/T1.md` exists for the Salesforce cutover worker result, or the
  worker blocker is recorded.
- `reports/T2.md` exists for verification scouting.
- Focused ingest/API/identity tests pass after T1, unless a blocker is
  documented.
- `cd packages/db && ../../.venv/bin/alembic check` exits 0 after T1 review,
  unless a blocker is documented.
- `git diff --check` exits 0.
- Linear comments/statuses are synced for `ENG-185`; `ENG-183` remains
  untouched because it is the later `ops.inquiry` slice.

### Continuation Budget

Maximum next actions before asking the user again:

1. Launch T1/T2.
2. Review T1/T2 reports.
3. Run focused verification.
4. Apply only minor integration fixes inside T1 ownership if needed.
5. Update Linear and handoff.

Escalate if T1 requires identity edits, schema/migration work, API/UI changes,
production/deploy actions, edits outside ownership, PHI-sensitive decisions, or
a failed worker launch.

### Latest Wave T Evaluation

Date: 2026-05-19
Result: complete

Evidence:

- `reports/T1.md` documents the Salesforce cutover recovery result.
- `reports/T2.md` documents the verification scout recovery result.
- `SfLeadIngestService.pull_recent(...)` now captures raw event, captures a
  normalized person hint using the returned `raw_event.id`, builds `MatchHintIn`,
  calls `IdentityService.resolve_or_create_from_hint(...)`, fetches the person,
  and upserts the lead.
- Old hidden identity matching calls are removed from Salesforce ingest.
- `.venv/bin/python -m pytest tests/ingest/test_sf_lead_service.py -q` exits 0
  with 10 passed.
- `.venv/bin/python -m pytest tests/ingest tests/identity tests/api/test_integrations_salesforce.py -q`
  exits 0 with 111 passed.
- `cd packages/db && ../../.venv/bin/alembic check` exits 0 with no new upgrade
  operations detected.
- `git diff --check` exits 0.
- Focused ruff and mypy on T1 files exit 0.
- `make verify` exits 0.
- Process incidents `INC-20260519-004` and `INC-20260519-005` document the
  failed worker report-writing path; no code blocker remains.
- Linear sync: `ENG-185` is ready to return to In Review with evidence;
  `ENG-183` remains Backlog.
