# Acceptance — ENG-309

## Code fix

- [ ] Identity-resolution service (path confirmed by pre-flight) gains a
      hard-block: if both candidate records expose a DOB AND the values
      differ → refuse merge BEFORE any soft-signal scoring runs.
- [ ] Same rule for SSN: if both expose an SSN AND the values differ →
      refuse merge.
- [ ] Both fields read from the latest `carestack.patient.upsert`
      payload (or whatever resolved DTO the resolver already operates on).
- [ ] Soft signals (phone, email, address, accountId, lastName) keep
      contributing to merge scoring ONLY when the DOB/SSN checks pass
      (i.e. equal, OR at least one side missing the field).

## Unit tests for the merge matrix

- [ ] DOB equal + SSN equal + phone match → merge.
- [ ] DOB equal + SSN equal + no other signal → merge (exact identity).
- [ ] DOB equal + one side missing SSN + phone+address match → merge.
- [ ] DOB mismatch + every soft signal matches → **NO merge** (Torosyan
      Eduard vs Gaiane reproducer).
- [ ] SSN mismatch + every soft signal matches → **NO merge**.
- [ ] Both sides missing DOB + phone+address+accountId+lastName match →
      may merge (document this as soft path).
- [ ] Same person multi-registration (same DOB + same SSN, different
      pid, different location) → merge (legitimate Gaiane case:
      pids 1461274 + 2171827).

## Audit script

- [ ] New `infra/scripts/audit_identity_merges.py` (or sibling) that
      enumerates `person.id` rows where any pair of linked CareStack
      patient_ids has DOB or SSN mismatch in their latest
      `carestack.patient.upsert` payload.
- [ ] Output: count + sample (first 20 person_uid + the conflicting
      payload subset). NO PHI in log values — sample is on stdout
      for operator review, log lines carry only counts.
- [ ] `--dry-run` flag (default) prints the report; `--apply` would
      execute un-merge (if Part D is in this ticket) — never auto-run.

## Un-merge script (Part D — conditional on audit count)

- [ ] If audit reports ≤ 50 wrong persons: include
      `infra/scripts/split_wrong_merged_persons.py` in this ticket,
      idempotent + dry-run + cap-safe. Each split creates new
      `person.id` rows; existing source_links + accounting/payment
      history is partitioned by DOB+SSN bucket; an
      `audit.access_log` row is written per split for the audit trail.
- [ ] If audit reports > 50 wrong persons: file a follow-up ticket
      (ENG-311) and ship only Parts A-C in this commit; document the
      decision in the worker report.

## Verify

- [ ] `make lint && mypy . && make test` green.
- [ ] `cd packages/db && alembic check` clean (no migration expected
      unless un-merge needs an audit-table column — unlikely).
- [ ] All new tests in the merge matrix pass.
- [ ] Worker report at
      `.agents/orchestration/current/reports/ENG-309-worker-report.md`.

## Out of scope

- Multi-link expander UI showing per-pid names — that's ENG-310.
- Surfacing patient details PHI panel — also ENG-310.
- SF-lead-to-patient identity matching (different code path, not
  covered here).
