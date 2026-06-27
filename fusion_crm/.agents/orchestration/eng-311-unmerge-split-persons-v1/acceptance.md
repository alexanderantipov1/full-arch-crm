# Acceptance — ENG-311

## Script

- [ ] `infra/scripts/split_wrong_merged_persons.py` (NEW), mirrors the
      `backfill_payment_summary.py` / `audit_identity_merges.py` shape.
- [ ] CLI flags: `--tenant-id` (required), `--dry-run` (default True),
      `--apply` (explicit opt-in for writes), `--max-splits N`
      (default 100), `--person-uid <uuid>` (optional single-target).
- [ ] `async def main(args, *, session_factory=None) -> int` testable
      shape, exit codes 0/2/1.

## Split algorithm

- [ ] Select wrong-merged persons via the same logic as
      `audit_identity_merges.py` (reuse the SQL / a shared helper).
- [ ] For each person: pull linked CS source_links → latest
      `carestack.patient.upsert` payload per pid → extract `dob` (date)
      + `ssn` (normalized).
- [ ] Group pids by `(dob, ssn)` key. Document the partial-null
      precedence rule in the report (e.g. a pid with dob set + ssn null
      groups with the matching-dob bucket if unambiguous, else its own
      bucket).
- [ ] Largest bucket stays on the original `person.id`.
- [ ] Each other bucket → new `person.id` (clone Person row with fresh
      UUID + bucket's dob/ssn/name; copy relevant PersonIdentifier rows;
      repoint the bucket's SourceLink rows to the new person).
- [ ] Downstream attribution: confirm NO rewrites needed for
      payment_summary / accounting / appointments (they key on
      patient_id). For any table that DOES denormalize person_uid
      (interaction.event? ops.consultation? person_location_profile?
      — pre-flight identifies), repoint those rows too.
- [ ] One `audit.access_log` row per split (`action_code =
      "identity.person.split"`, principal=SYSTEM, before/after pid
      counts + bucket_count — NO PHI values).

## Idempotency + safety

- [ ] Re-run on already-split (clean) persons → 0 new splits.
- [ ] `--dry-run` is a true no-op (no Person inserts, no source_link
      repoint, no audit write) — prints the plan only.
- [ ] `--max-splits` cap honored.
- [ ] `--person-uid` filters to one target (for Torosyan single-case
      verification before fleet run).
- [ ] Batch commit (every 50 persons).

## Tests (CareStack not needed — DB-only; still no real DB in unit tests)

- [ ] Torosyan-shape fixture → split into 2 persons (1 Eduard pid +
      1 Gaiane with 2 pids preserved together).
- [ ] Perevertov-shape fixture (5 distinct (dob, ssn)) → 5 persons.
- [ ] Audit row written per split; shape verified; NO PHI in values.
- [ ] `--dry-run` no-op asserted.
- [ ] `--max-splits` cap asserted.
- [ ] `--person-uid` single-target asserted.
- [ ] Idempotent re-run → 0 splits asserted.
- [ ] Largest-bucket-stays rule asserted (original person keeps the
      biggest bucket).

## Verify

- [ ] `make lint && mypy . && make test && cd packages/db && alembic check`
      green (no migration expected — split uses existing tables).
- [ ] Worker report at
      `.agents/orchestration/current/reports/ENG-311-worker-report.md`.
- [ ] Commit to worker's worktree branch only; NO push; Orchestrator
      integrates.

## Out of scope

- The resolver fix going forward — that's ENG-309 (merged).
- UI per-pid names + PHI panel — ENG-310.
- SF lead → patient identity (different code path).
- Auto-running the split — `--apply` requires explicit operator go
  AFTER merge.
