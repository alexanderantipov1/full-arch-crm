# ENG-311 — Worker report

- **Task:** ENG-311 — Un-merge backfill: split 3,416 wrong-merged
  CareStack persons
- **Linear:** ENG-311 —
  https://linear.app/fusion-dental-implants/issue/ENG-311/un-merge-backfill-split-3416-wrong-merged-carestack-persons-post-eng
- **Role / agent:** worker / claude-code (sid `3b994984d512`)
- **Branch:** `eng-311-eng-311`
- **Worktree:**
  `~/.fusion-agent-orchestrator/c2db50910d08/current/worktrees/ENG-311/`
- **Scope:** background un-merge script + tests. NO migration. NO HTTP.
  `--apply` is opt-in.

## Touched files

| Path | Kind |
|---|---|
| `infra/scripts/split_wrong_merged_persons.py` | NEW — background un-merge script |
| `tests/infra/test_split_wrong_merged_persons.py` | NEW — 21 unit tests, fully mocked session |

No Alembic migration. No HTTP route. No edits to `apps/web/lib/msw/handlers.ts`.

## What changed

### `infra/scripts/split_wrong_merged_persons.py`

Background-only operator script that splits an `identity.person` row
that was wrong-merged across multiple CareStack patient_ids into N
persons -- one per `(dob, ssn)` bucket.

- **CLI:** `--tenant-id` (required), `--dry-run` (default True),
  `--apply` (explicit opt-in), `--max-splits` (default 100),
  `--person-uid <uuid>` (single-target), `--commit-every` (default 50).
- **Selection:** reuses the same SQL shape as
  `infra/scripts/audit_identity_merges.py::_AUDIT_SQL` (the
  `WITH latest_payload` CTE joining `identity.source_link` →
  `ingest.raw_event` on `external_id` for
  `event_type = 'carestack.patient.upsert'`), aggregating
  `payload->>'firstName'` + `payload->>'lastName'` in addition to
  `dobs` / `ssns` so the new Person rows can clone demographic
  identity. The mismatch filter mirrors the audit predicate:
  `distinct_dob > 1 OR distinct_ssn > 1`.
- **Bucketing (`_bucket_pids`):** groups pids by `(dob, ssn)` per the
  partial-null precedence rule documented in the spec:
  - Pids with identical `(dob, ssn)` share a bucket.
  - A pid with `(dob, None)` merges into the unique `(dob, X)` bucket
    iff exactly one non-null `X` exists for that dob; otherwise it
    forms its own bucket. Symmetric for `(None, ssn)`.
  - NEVER merge two different non-null dobs — that would re-violate
    the ENG-309 veto.
  - `(None, None)` pids stay on their own bucket (no evidence to
    attach them to a specific human).
- **Surviving bucket:** largest pid count wins. Tie-break: bucket
  containing the lexicographically smallest patient_id stays
  (deterministic across re-runs and operator-friendly when the
  Torosyan-shape spans all size-1 buckets).
- **Per-split mechanics in `--apply` mode:**
  1. For each non-surviving bucket: insert a new `Person` row
     (dob/ssn from the bucket; first/last/display name cloned from
     the bucket's first pid).
  2. `UPDATE identity.source_link SET person_uid = :new` where
     `source_id ∈ bucket_pids`. Mutable plain-UUID column —
     established path.
  3. `UPDATE interaction.event SET person_uid = :new` where
     `source_provider = 'carestack' AND source_kind = 'patient' AND
     source_external_id ∈ bucket_pids`. (Conservative trace: only
     patient-keyed events.)
  4. After all non-surviving buckets done, count downstream rows
     still on the surviving person that have a CareStack provider
     stamp but no clean patient_id trace
     (`ops.consultation`, non-`patient` `interaction.event`,
     `ops.person_location_profile`, `ops.followup_task`); bump the
     run-level `needs_manual_review` counter.
  5. Append one `audit.access_log` row,
     `action = "identity.person.split"`,
     `extra = { surviving_person_uid, new_person_uids, bucket_count,
     source_links_moved }` — uuids + counts only.
- **Dry-run:** prints the per-person plan to stdout
  (`person_uid=… buckets=N surviving_pids=[…] new_persons=K
  new[0]_pids=[…] …`). Zero `add()`, zero `UPDATE`, zero audit
  write. Stdout carries patient_ids (operator non-PII references)
  but NEVER dob/ssn/name.
- **Idempotency:** a clean person (1 bucket after grouping) is
  skipped; the script never touches it. Re-running on the same fleet
  after a successful pass is a no-op.
- **Tenant scoping:** every read + write filters by `tenant_id`.
- **Exit codes:** 0 success, 2 invalid tenant / person_uid, 1
  uncaught exception (logged before propagation by `run`).

### `tests/infra/test_split_wrong_merged_persons.py`

21 unit tests, all mocked — zero DB / network. Pattern mirrors
`tests/infra/test_audit_identity_merges.py` (`importlib.util` loader +
`_fake_session_cm`). The session mock records `add()`,
`execute()` (with SQL + params), `flush()`, and `commit()` calls so
tests can assert exactly what the script wrote.

Test coverage (all PASS):

| # | Test | What it pins |
|---|---|---|
| 1 | `test_parse_args_defaults_match_spec` | default flags |
| 2 | `test_parse_args_apply_flag_opts_in` | `--apply` flips writes ON |
| 3 | `test_parse_args_person_uid_filter` | single-target flag |
| 4 | `test_parse_args_max_splits_override` | cap override |
| 5 | `test_bucket_pids_groups_same_dob_ssn_together` | legitimate multi-registration → 1 bucket |
| 6 | `test_bucket_pids_torosyan_shape_two_buckets` | 2 distinct dobs → 2 buckets |
| 7 | `test_bucket_pids_perevertov_shape_five_buckets` | 5 distinct (dob, ssn) → 5 buckets |
| 8 | `test_pick_surviving_prefers_largest_bucket` | largest wins |
| 9 | `test_pick_surviving_tie_break_smallest_patient_id` | deterministic tie-break |
| 10 | `test_bucket_pids_partial_null_ssn_joins_unique_matching_dob` | partial-null precedence |
| 11 | `test_bucket_pids_never_merges_two_different_non_null_dobs` | ENG-309 veto invariant in bucketer |
| 12 | `test_dry_run_writes_nothing` | default mode → 0 add/UPDATE, plan printed |
| 13 | `test_apply_torosyan_shape_creates_one_new_person_and_audit_row` | 1 new Person + 1 AccessLog |
| 14 | `test_apply_perevertov_shape_creates_four_new_persons` | 5 buckets → 4 new persons + 1 audit |
| 15 | `test_legitimate_same_person_is_skipped` | mismatch filter blocks 1-bucket persons |
| 16 | `test_idempotent_on_clean_persons` | empty selection → 0 writes |
| 17 | `test_max_splits_caps_processing` | cap honored |
| 18 | `test_person_uid_filter_processes_only_target` | single-target filter honored |
| 19 | `test_audit_row_contains_only_uuids_and_counts_no_phi` | NO dob / ssn / name / patient_id in `extra` |
| 20 | `test_interaction_event_repoint_issued_per_bucket` | downstream repoint emitted |
| 21 | `test_needs_manual_review_counted_per_split` | manual-review SELECT issued |

## Policy decisions (documented for the report)

1. **PersonIdentifier rows stay on the surviving person.** The
   global `UniqueConstraint("kind", "value")` on
   `identity.person_identifier` prevents copying the same phone /
   email to two Person rows. The next CareStack re-pull of a
   non-surviving patient_id resolves through
   `IdentityService.resolve_or_create_from_hint`; ENG-309's DOB/SSN
   veto blocks the re-merge to the OLD person and either creates a
   fresh Person or routes to the existing split person (depending on
   match strength). Documented limitation: identity rebuild for the
   new persons is lazy and happens on the next CS pull, not at
   split-time.
2. **Downstream repoint scope is conservative.** Only
   `interaction.event` rows with `source_kind = 'patient'` and
   `source_external_id ∈ bucket_pids` are repointed — those have a
   direct, unambiguous CareStack patient_id trace.
   `ops.consultation`, non-`patient` `interaction.event` rows,
   `ops.person_location_profile`, and `ops.followup_task` rows STAY
   on the surviving person and bump `needs_manual_review`. The
   alternative (joining through `raw_event.payload->>'patientId'`)
   adds payload-shape assumptions that are brittle and could
   re-merge financials across humans if the payload schema drifts.
   Better to under-attribute and let the operator triage than to
   guess.
3. **`needs_manual_review` is a count, not a list.** Per-row
   identification would surface PHI-adjacent context in the run log
   (consultation external_id, location_id, etc.); the count is
   sufficient for batch-level operator triage.
4. **Audit row carries uuids + counts only.** No dob, no ssn, no
   name, no patient_id values in `extra`. Test #19 asserts the
   serialised dict has none of the Torosyan fixture's PHI/PII
   strings.
5. **Financials require ZERO rewrites.** Confirmed by reading the
   spec: `payment_summary` snapshots, accounting transactions,
   appointments, and invoices all key on the CareStack `external_id`
   (patient_id). When `source_link.person_uid` moves to the new
   person, those projections auto-reattribute on next pull.

## Tests run

| Command | Outcome |
|---|---|
| `ruff check infra/scripts/split_wrong_merged_persons.py tests/infra/test_split_wrong_merged_persons.py` | ✅ All checks passed |
| `mypy infra/scripts/split_wrong_merged_persons.py tests/infra/test_split_wrong_merged_persons.py` | ✅ Success: no issues found in 2 source files |
| `pytest tests/infra/test_split_wrong_merged_persons.py -v -o pythonpath=.` | ✅ 21 passed in 0.23 s |

Deferred (sandbox-blocked / integrator scope):

- `make lint` — passes for my files; pre-existing lint debt in
  unrelated files (`packages/ingest/repository.py`,
  `packages/interaction/repository.py`,
  `tests/ingest/test_carestack_patients_with_payments_sql.py`) was
  NOT touched. Re-run on integrator's branch.
- `make test` — collection of unrelated `tests/api/*` and
  `tests/integration/*` aborts on missing `SECRET_KEY` /
  `DATABASE_URL` / `REDIS_URL` env (sandbox does not load `.env`).
  My file collects + passes in isolation. Re-run on integrator's
  canonical `.env`-loaded shell.
- `cd packages/db && alembic check` — sandbox-blocked for the same
  Settings reason. No migration was added in this ticket, so the
  drift check should remain clean. Integrator should re-run.

## Verification status

✅ **Worker-side green.** The split mechanics (bucketing,
tie-break, partial-null precedence, no-merge-across-non-null-dobs,
dry-run no-op, audit row shape, downstream repoint emission,
needs-manual-review counter) are unit-tested with full mocks.

⚠ Integrator MUST re-run `make lint && mypy . && pytest tests
--ignore=tests/integration -q && cd packages/db && alembic check`
on a canonical-`.env` shell before merge.

## Risks

1. **No real-DB integration test in this ticket.** The mocked-session
   suite verifies WHAT the script writes (Person + AccessLog rows;
   UPDATE source_link / UPDATE interaction.event SQL; manual-review
   SELECT issued), not THAT the writes land correctly under a real
   Postgres concurrency profile. The mitigation is the
   acceptance-defined operator smoke test in
   `.agents/orchestration/current/verification.md` § "Smoke
   (post-merge)": dry-run single-target Torosyan → operator inspects
   the plan → dry-run fleet (5000 cap) → operator approves → real
   `--apply` in batches of 500 → re-run audit between batches.
2. **PersonIdentifier rows stay on the surviving person**
   (documented above). A non-surviving patient_id whose next CS pull
   hits an existing identifier (phone / email already on the OLD
   person) relies on the ENG-309 DOB/SSN veto to refuse the re-link.
   If the CS payload's dob/ssn for that pid is missing on a future
   pull, the veto cannot fire and the resolver may auto-link back to
   the surviving person. Operator action: monitor
   `interaction.event` for `kind = 'person_created'` rate after the
   batches; an unexpected spike means the veto is silently failing.
3. **`needs_manual_review` is a count, not a triage list.** An
   operator who sees `needs_manual_review = 47` for a batch has to
   query the four denormalised tables manually to surface the rows.
   Acceptable for the 3,416-person backfill (operator can run one
   read-only query per batch); could be productised into a follow-up
   ticket if the operator burden is high.
4. **Race against in-flight CareStack ingest.** The script holds a
   per-person transaction but does NOT lock the
   `identity.source_link` row. A concurrent CS pull that touches the
   same patient_id could see the link mid-move. Mitigation: the
   spec calls for batched apply WITH the operator pausing the CS
   cron job before each batch; this matches the
   `--commit-every 50` cadence.
5. **The DB-level FK `identity.source_link.person_uid →
   identity.person.id` is `ondelete=CASCADE`.** Moving the
   `person_uid` to a new Person via plain UPDATE is the established
   path (the column is mutable and the FK is referential, not
   exclusive). No cascade fires because we're updating, not
   deleting. Confirmed by reading the model annotations.

## Blockers / questions

None. Implementation is complete; verification passed within the
sandbox-allowed envelope.

## Suggested next task

- ENG-311-followup: Productise the `needs_manual_review` triage
  output (per-bucket downstream row breakdown) if the operator
  burden during the fleet apply is non-trivial. Out of scope for
  this ticket.
- After ENG-311 merges + operator runs the real fleet split:
  re-run `infra/scripts/audit_identity_merges.py` and confirm the
  wrong-merged count drops from 3,416 to ~0 (some same-DOB +
  missing-SSN edge cases may remain — those are NOT split because
  the bucketing rules treat them as legitimate same-human
  multi-registration).

## DO-NOT-MERGE conditions

- ❌ Do NOT merge if the integrator's `make lint && mypy . &&
  pytest tests --ignore=tests/integration -q && cd packages/db &&
  alembic check` is anything but green.
- ❌ Do NOT run the real `--apply` against prod from this branch —
  per the spec, fleet split is a SEPARATE operator go AFTER merge.
- ❌ Do NOT skip the post-merge smoke sequence in
  `verification.md` § "Smoke (post-merge)". The Torosyan
  single-target dry-run is the canonical safety check before any
  fleet-scale apply.
- ❌ Do NOT change the bucketing rules or the partial-null
  precedence without re-validating against the ENG-309 veto
  invariant (tests #5–#11 in
  `tests/infra/test_split_wrong_merged_persons.py`).
- ❌ Do NOT loosen the audit row's `extra` shape to include
  patient_id / dob / ssn / name — test #19 is the PHI guard and
  must stay green.

---

## Round 2 — adversarial-review fixes

Round 1's commit `44e4833` passed the worker's own 21 tests but failed
adversarial review with 3 blockers. This section documents the
follow-up fix on the same worktree branch
(`ENG-311: repoint ops.consultation + per-person savepoint + stronger
repoint tests`).

### Blocker 1 — `ops.consultation` repoint + docstring honesty (CRITICAL)

**Root cause.** Round 1 lumped `ops.consultation` into
`needs_manual_review` on the grounds that it had no clean patient_id
trace. That was wrong: every consultation captured by
`packages/ingest/carestack_appointment_service.py` stores
`raw_event_id` pointing at the `carestack.appointment.upsert` raw event
whose payload carries `patientId` (camelCase per CareStack sync feed;
PascalCase `PatientId` is also tolerated). This is the same kind of
trace as `interaction.event`'s `source_external_id`. The module
docstring also lied — it claimed `ops.lead` was traceable + repointed
when the code never touched it.

**Fix.** New `_REPOINT_OPS_CONSULTATION_SQL` issues an UPDATE through an
EXISTS join on `ingest.raw_event` for each non-surviving bucket, with
the bucket's pids in `:patient_ids`. The `_count_needs_manual_review`
SELECT no longer counts `ops.consultation` rows with a `raw_event_id`
(those are now repointed); it does still count consultations with
`raw_event_id IS NULL` (defensive — should not happen in practice but
covers any future ingest path that bypasses the appointment service).

**Per-table decision table** (also lives at the top of the module
docstring, abbreviated here):

| Table | Repointed? | Why |
|---|---|---|
| `identity.source_link` | YES | `source_id` IS the patient_id. Direct trace. |
| `interaction.event` (kind=patient) | YES | `source_external_id` IS the patient_id. Direct trace. |
| `ops.consultation` (raw_event_id NOT NULL) | YES (NEW Round 2) | `raw_event.payload->>'patientId'` join. Clean trace. |
| `ops.lead` | NO | Salesforce-origin; predates the CareStack patient. No patient_id column, no provider-traceable join. Stays + manual-review. |
| `ops.followup_task` | NO | No `source_provider` / `external_id` / `raw_event_id` columns. No trace exists. Stays + manual-review. |
| `ops.person_location_profile` | NO | Aggregate row (UNIQUE per `(tenant, person, location)`). The latest-evidence raw_event trace is clean for the row, but moving the row would orphan the surviving person's profile at that location; operator must regenerate from CareStack after the split. Stays + manual-review. |
| `interaction.event` (kind != 'patient') | NO | Tasks / non-patient events have no patient_id trace. Stays + manual-review. |
| `ops.consultation` (raw_event_id IS NULL) | NO | Defensive: rows without a raw_event trace cannot be attributed. Stays + manual-review. |

The module docstring at the top of `split_wrong_merged_persons.py` was
rewritten to reflect exactly this table — no claim of behavior the code
does not implement.

**Audit row.** `extra` now carries `interaction_events_moved` and
`consultations_moved` alongside the existing `source_links_moved` count
(all uuids + counts only — no PHI). Test #22
(`test_ops_consultation_repoint_counts_into_audit_row`) pins this.

### Blocker 2 — per-person SAVEPOINT (MAJOR)

**Root cause.** Round 1 wrapped one transaction around the entire
`commit_every=50` batch. One bad person would re-raise and roll back up
to 49 correct splits already done in the same batch — operator pain.

**Fix.** Each candidate's split now runs inside
`async with session.begin_nested():` (SAVEPOINT). On a per-person
exception:

1. The SAVEPOINT auto-rolls back (only that person's writes).
2. `error_count` increments.
3. A count-only warning is logged with `tenant_id` + `person_uid` +
   `error_count` (no PHI; person_uid is non-PII).
4. The loop `continue`s; previously-completed splits in the same batch
   remain pending in the outer transaction and commit at the next
   `commit_every` boundary.

`error_count` is surfaced in the final `split.wrong_merged.summary` log
line so the operator knows to triage.

New test #25 (`test_per_person_savepoint_isolates_failure`):

- 3 candidates; middle one's `_create_new_person` flush raises
  `RuntimeError`.
- Asserts `main` returns exit_code 0 (batch survived).
- Asserts exactly 2 audit rows exist (A + C); none for B
  (`_write_audit_row` is the last call in `_apply_split`; B never
  reached it because flush raised earlier).
- Asserts `session.savepoints` lifecycle: 3 entered; index 1 status =
  `rolled_back`; indices 0 and 2 status = `released`.

The mock recorder was extended to expose `begin_nested()` as an async
context manager that records `enter` → status (`open` →
`rolled_back`/`released`) so future tests can assert SAVEPOINT scoping
directly.

### Blocker 3 — strengthened repoint tests (MAJOR)

**Root cause.** Round 1's `test_interaction_event_repoint_issued_per_bucket`
only asserted that an `UPDATE interaction.event` SQL string was issued.
A bug that swapped `:new_person_uid` for the surviving uid would still
have passed.

**Fix.** Tests now inspect the executed statement's bound parameters
via the existing `session.executed_params` capture:

- Test #20
  (`test_interaction_event_repoint_issued_per_bucket`, strengthened):
  asserts `params["new_person_uid"]` equals the new person's `.id`, and
  that the bucket's non-surviving patient_id ("1461274" — wins over
  "1460847" via lexicographic tie-break) is in `params["patient_ids"]`.
- Test #21
  (`test_ops_consultation_repoint_issued_per_bucket`, NEW): mirror for
  `ops.consultation` — params bound correctly, plus SQL text checks
  for `payload->>'patientId'`, the `PatientId` PascalCase fallback,
  and the `carestack.appointment.upsert` event-type filter (so future
  refactors cannot silently drop the join through raw_event).
- Test #22
  (`test_ops_consultation_repoint_counts_into_audit_row`, NEW): the
  `consultations_moved` count from the UPDATE's `rowcount` lands in the
  audit row's `extra`.
- Test #23
  (`test_followup_task_and_location_profile_kept_in_manual_review`,
  NEW): no `UPDATE ops.followup_task` or
  `UPDATE ops.person_location_profile` is ever issued; both tables ARE
  referenced from the manual-review COUNT SELECT.
- Test #24
  (`test_ops_lead_not_repointed_kept_in_manual_review`, NEW): no
  `UPDATE ops.lead` is ever issued; the manual-review SELECT references
  `ops.lead`.

### Verify (all green, sandbox-isolated)

| Command | Outcome |
|---|---|
| `ruff check infra/scripts/split_wrong_merged_persons.py tests/infra/` | ✅ All checks passed |
| `mypy infra/scripts/split_wrong_merged_persons.py` | ✅ Success: no issues found in 1 source file |
| `mypy infra/scripts/split_wrong_merged_persons.py tests/infra/test_split_wrong_merged_persons.py` | ✅ Success: no issues found in 2 source files |
| `pytest tests/infra/test_split_wrong_merged_persons.py -v -o pythonpath=.` | ✅ 26 passed (21 from Round 1 + 5 new/strengthened in Round 2) |

### Blocker closure

- **Blocker 1 (CRITICAL):** ✅ Closed. `ops.consultation` is now
  repointed via the `raw_event.payload->>'patientId'` trace. `ops.lead`,
  `ops.followup_task`, and `ops.person_location_profile` stay on the
  surviving person and are counted in `needs_manual_review`. The module
  docstring and the report's decision table say exactly what the code
  does.
- **Blocker 2 (MAJOR):** ✅ Closed. Per-person SAVEPOINT scoping is
  active; one failing person no longer aborts the batch. Test #25 pins
  the lifecycle with savepoint status assertions.
- **Blocker 3 (MAJOR):** ✅ Closed. Repoint tests now inspect bound
  params (not just SQL text). New tests pin `ops.consultation` repoint
  and the no-touch + counted behavior for `ops.lead`,
  `ops.followup_task`, and `ops.person_location_profile`.

### Touched files (Round 2)

| Path | Kind |
|---|---|
| `infra/scripts/split_wrong_merged_persons.py` | UPDATED — module docstring rewrite, new `_REPOINT_OPS_CONSULTATION_SQL` + `_repoint_ops_consultations`, updated `_COUNT_NEEDS_MANUAL_REVIEW_SQL`, `_write_audit_row` carries 2 new count fields, `_apply_split` calls the new repoint and tracks the 2 new counts, `main()` per-person `session.begin_nested()` + `error_count` + summary log update |
| `tests/infra/test_split_wrong_merged_persons.py` | UPDATED — mock session exposes `begin_nested` lifecycle; existing repoint test strengthened to assert bound params; 5 new tests (consultation repoint + counts; followup_task / location_profile / lead no-touch; per-person savepoint isolation) |
| `.agents/orchestration/current/reports/ENG-311-worker-report.md` | UPDATED — this section appended |

No Alembic migration. No HTTP route. No edits to
`apps/web/lib/msw/handlers.ts`. Same constraints as Round 1.
