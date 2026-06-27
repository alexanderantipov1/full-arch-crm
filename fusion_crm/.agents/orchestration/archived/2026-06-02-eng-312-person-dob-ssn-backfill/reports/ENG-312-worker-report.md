# Worker Report — ENG-312

- Task id: ENG-312
- Linear issue: ENG-312 — Backfill identity.person.dob/ssn from latest CareStack payload
- Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-312/backfill-identitypersondobssn-from-latest-carestack-payload-activate
- Role / agent: worker / claude-code (session d621c06a6df2)
- Branch: `eng-312-eng-312`
- Worktree: `/Users/eduardkarionov/.fusion-agent-orchestrator/c2db50910d08/current/worktrees/ENG-312`
- Allowed scope: background-only infra script + tests. No product
  routes, no migrations, no schema/model changes, no service edits,
  no MSW handlers.

## Touched files

| File | Status | Purpose |
| --- | --- | --- |
| `infra/scripts/backfill_person_dob_ssn.py` | NEW | Backfill script |
| `tests/infra/test_backfill_person_dob_ssn.py` | NEW | Unit tests (28) |

No edits to: `packages/identity/service.py`, any migration, any
schema/model, any HTTP route, `apps/web/lib/msw/handlers.ts`, any
`.env*`, any shipped Alembic revision.

## What changed

`infra/scripts/backfill_person_dob_ssn.py` mirrors the shape of
`backfill_payment_summary.py` (parse_args, `_default_session_factory`,
async `main(args, *, session_factory=None)`, `run(argv=None)`,
`asyncio.run`, lazy `async_session` import). The selection SQL copies
the working DISTINCT-ON join from
`infra/scripts/audit_identity_merges.py` /
`split_wrong_merged_persons.py` (`re.external_id = sl.source_id`,
`event_type='carestack.patient.upsert'`, `source_system='carestack'`,
`source_kind='patient'`) and adds a `JOIN identity.person` with
`p.dob IS NULL OR p.ssn IS NULL` so SF-only persons (no CareStack
source_link) are never selected.

Per candidate:

1. Pull the latest payload per linked patient_id; extract raw
   `dob`/`ssn` strings.
2. Parse via the existing
   `packages.ingest.carestack_patient_service._parse_carestack_dob`
   and `._normalize_ssn` (reused, not re-implemented; the CLAUDE.md
   crossing matrix permits infra/ scripts to import from `ingest`).
3. Build distinct sets across the person's pids excluding `None` and
   the placeholder `date(1900, 1, 1)` (CareStack's "unknown DOB"
   sentinel).
4. If non-null parsed dobs disagree (>1 distinct) OR ssns disagree →
   SKIP person, `needs_manual_review++`.
5. Else pick the single agreed `dob` / `ssn`. If the only dob signal
   was the placeholder, count `skipped_placeholder_dob` and leave
   `person.dob` NULL but still write ssn if available.
6. Apply via `UPDATE identity.person SET dob = COALESCE(dob, :dob),
   ssn = COALESCE(ssn, :ssn) WHERE id = :uid AND tenant_id = :tid` —
   `COALESCE` enforces write-once at the DB layer (mirrors
   `IdentityService._maybe_backfill_demographic`).
7. Insert one `AccessLog` per updated person:
   - `action='identity.person.demographic_backfill'`
   - `extra = {set_dob: bool, set_ssn: bool, source_pid_count: int}`
     — counts/booleans only; no dob/ssn/name VALUES.

CLI flags: `--tenant-id` (required), `--dry-run` (default), `--apply`
(opt-in), `--max-persons 200`, `--commit-every 50`, `--person-uid`.
Exit codes: 0 success, 2 invalid tenant / invalid `--person-uid`,
1 uncaught.

Transaction model: per-person `async with session.begin_nested():`
SAVEPOINT under `--apply`; one failing person rolls back ONLY that
person, batch keeps prior successes. Outer `await session.commit()`
fires every `--commit-every` persons plus once at the end. Dry-run
never enters the SAVEPOINT/commit path. Services/repos do not commit
— consistent with the layering rules in `packages/CLAUDE.md`.

PHI hygiene: structured logs carry counts + uuids ONLY. Dry-run
stdout prints `person_uid`, `source_pid_count`, `would_set_dob`,
`would_set_ssn`, optional `skip_reason` / `placeholder_dob=true` —
never the parsed dob / ssn VALUES. `_format_dry_run_line` is unit-
tested to confirm no PHI leaks. AccessLog `extra` is asserted to
contain only `set_dob` / `set_ssn` / `source_pid_count` keys.

Tests (28) mirror `tests/infra/test_split_wrong_merged_persons.py`
fixture style (asyncmock session, recorder of `add()` / `execute()`
calls, SAVEPOINT lifecycle recorder). Coverage:

- argparse defaults + apply opt-in + `--person-uid` / `--max-persons`
- `--tenant-id` / `--person-uid` validation (exit code 2 path)
- single-pid set dob+ssn
- multi-pid AGREE → set once
- multi-pid DISAGREE on dob → skip + manual-review path
- multi-pid DISAGREE on ssn → skip + manual-review path
- write-once: existing non-null dob preserved
- write-once: existing non-null ssn preserved
- fully-populated person → strict no-op (no UPDATE, no AccessLog)
- placeholder `1900-01-01` only → dob stays NULL, ssn still written
- placeholder + no ssn → full no-op
- SF-only person (no CS source_link → empty SELECT) → untouched
- AccessLog `extra` contains booleans/counts only, no PHI
- dry-run writes nothing (only one SELECT execute; no commit)
- dry-run plan line carries no dob/ssn values
- ISO-timestamp dob parses
- `--max-persons` caps audit row count to the cap
- `--person-uid` filter restricts processing to the single target
- idempotent re-run on empty result set
- per-person SAVEPOINT isolates a failing UPDATE; batch survives;
  rolled_back/released lifecycle states verified

## Tests run + results

```
pytest tests/infra/test_backfill_person_dob_ssn.py -o pythonpath=. -v
→ 28 passed in 0.28s
```

## Verification status

| Check | Result |
| --- | --- |
| `pytest tests/infra/test_backfill_person_dob_ssn.py -o pythonpath=. -v` | 28 / 28 passed |
| `ruff check infra/scripts/backfill_person_dob_ssn.py tests/infra/test_backfill_person_dob_ssn.py` | clean |
| `mypy infra/scripts/backfill_person_dob_ssn.py tests/infra/test_backfill_person_dob_ssn.py` | Success: no issues found |
| `mypy .` (full tree) | Success: no issues found in 308 source files |
| `make lint` (full repo) | 4 pre-existing baseline UP037/I001 in `packages/ingest/repository.py:477`, `packages/interaction/repository.py:131/140`, `tests/ingest/test_carestack_patients_with_payments_sql.py:14` — NONE from this branch (verified by inspecting `git status`: only my 2 untracked files are present) |
| `make test` (full repo) | Pre-existing collection errors in `tests/api/*` + 2 in `tests/integration/*` due to missing env in this worktree — same baseline noise on `main`; my test file collects + runs clean in isolation |
| `cd packages/db && alembic check` | NOT runnable in this worktree session — `packages.core.config.Settings` requires `SECRET_KEY` / `DATABASE_URL` / `REDIS_URL` env vars + a reachable Postgres for the metadata-vs-DB compare. The shared `.venv` is editable-installed against the source repo, but its `.env` lives in the source-repo working directory; the worktree does not inherit it. **My changes touch no models and add no migration**, so the ORM↔DB drift status is unchanged by this branch. The operator can re-run `alembic check` from the source repo at merge time. |

## Risks

- **No real DB exercise.** The script and tests are fully unit-tested
  with a mocked session. The first `--apply` against a live tenant
  is therefore the first end-to-end exercise of the
  `_SELECT_CANDIDATES_SQL` / `_UPDATE_PERSON_SQL` round-trip on real
  data. Mitigated by:
  * `--dry-run` default + `--person-uid` single-target rehearsal step
    on a known canary (`1e80cb31` per the mission verification block);
  * per-person SAVEPOINT so one bad row cannot poison the batch;
  * `--commit-every 50` so a botched run can be killed mid-stream
    and only the last partial batch rolls back.
- **CareStack payload coverage.** The SQL only sees patient_ids that
  have at least one `carestack.patient.upsert` raw_event AND a
  `source_link` row. If a CareStack patient_id is linked via
  `source_link` but its raw_event was never ingested (or was purged),
  the JOIN drops that pid silently — the person may still have other
  pids whose payloads provide a usable signal; if not, the person
  becomes a "no usable signal" no-op and is counted under
  `nothing_to_do`. Surfacing via the run summary is the only
  mitigation; this is the same behavior as
  `audit_identity_merges.py`.
- **Placeholder-DOB edge case.** A person whose only CareStack
  pid carries the placeholder `1900-01-01` and no SSN remains a
  no-op. The `skipped_placeholder_dob` counter surfaces this so
  the operator can re-pull a real DOB on those patients.
- **Disagreement classification is strict.** A person with one pid
  carrying a real DOB and a second pid carrying the placeholder is
  counted as agreed (placeholder is filtered out) and the real DOB
  is written. This is intentional per spec but worth flagging — it
  is the inverse of the ENG-311 split behavior which treats the
  placeholder as a distinct DOB bucket. The veto on subsequent
  re-pulls behaves the same regardless (placeholder is not a real
  DOB anywhere in the resolver).

## Blockers / questions

- None outstanding. The `--apply` go is operator-gated and explicitly
  out of this mission's scope per `verification.md` ("Real `--apply`
  = SEPARATE operator go (not part of this mission's merge)").

## Suggested next task

After merge: operator-led `--dry-run` against the local `:5434`
stack with `--person-uid 1e80cb31...` (the canary used in the
ENG-311 verification block) → confirm the plan line shows
`would_set_dob=True` / `would_set_ssn=True` and `source_pid_count` is
sane. Then a `--max-persons 20 --dry-run` smoke pass over the broader
tenant. Then an operator decision on `--apply` cadence (one batch
at a time with `--max-persons` + `--commit-every` 50).

## Do-not-merge conditions

- Any `--apply` invocation against any database (this branch is for
  the script + tests only; the production run is a separately gated
  operator step).
- Any addition of an Alembic revision (none is required and none is
  shipped here).
- Any edit to `packages/identity/service.py`, the identity models,
  or `apps/web/lib/msw/handlers.ts`.
- Any check-in of `.env*` (the verification step uses worktree-local
  stubs only; none are committed; `git status` shows only the two
  new files above).
- Failure of `pytest tests/infra/test_backfill_person_dob_ssn.py` in
  CI (the suite is fully self-contained and database-free, so a CI
  red would indicate a real regression).

## Round 2 (test hardening)

Scope: tests only. No changes to
`infra/scripts/backfill_person_dob_ssn.py`. No test revealed a script
bug — the original Round 1 logic stood up to every new assertion, so
no minimal fix was required.

### New tests added (7 in total)

| # | Test | What it pins |
| --- | --- | --- |
| 1 | `test_commit_every_boundary_arithmetic_is_off_by_one_safe` | 6 updatable persons with `commit_every=2` → exactly 4 commits (3 intermediate flushes at updated=2/4/6 + 1 final). Catches off-by-one in `updated % commit_every == 0`. |
| 2 | `test_commit_every_zero_only_commits_at_end` | `commit_every=0` disables intermediate flushes; only the post-loop commit fires. Pins the `args.commit_every > 0` guard. |
| 3 | `test_disagree_dob_apply_increments_needs_manual_review_counter` | Multi-pid DISAGREE on dob in apply path → no UPDATE, no AccessLog, and the structlog summary call carries `needs_manual_review=1` / `updated=0` / `scanned=1`. Captured via `patch.object(backfill, "log")` (the project's existing log-capture pattern, mirroring `test_backfill_payment_summary.py`'s approach since structlog's `cache_logger_on_first_use=True` makes `capture_logs()` brittle across the session). |
| 4 | `test_disagree_ssn_only_apply_path_skips_and_counts` | Pids AGREE on dob but DISAGREE on ssn → skip fires on `mismatch_ssn` (the existing multi-pid-disagree test trips on dob first); end-to-end through `main`. No UPDATE, no AccessLog, summary shows `needs_manual_review=1`. |
| 5 | `test_dry_run_line_placeholder_dob_carries_marker_no_phi` | Dry-run on a `1900-01-01` row prints `placeholder_dob=true` + `would_set_dob=False` + `would_set_ssn=True`; literal `1900-01-01` and any ssn digits are absent from stdout (PHI gate on the dry-run formatter). |
| 6 | `test_dry_run_line_mismatch_row_renders_skip_reason_no_phi` | Dry-run on a disagree row renders `skip_reason=mismatch_dob` + `source_pid_count=2`; no dob/ssn values in stdout. |
| 7 | `test_person_uid_filter_is_python_side_not_in_select_params` | The SELECT param dict contains only `tenant_id` — `--person-uid` filtering stays in Python (post-fetch). A future bad refactor that pushes the filter into the SQL is caught. |

### Final pytest count

```
pytest tests/infra/test_backfill_person_dob_ssn.py -o pythonpath=. -v
→ 35 passed in 0.32s
```

(28 Round-1 tests + 7 new tests; all green.)

### Verification this round

| Check | Result |
| --- | --- |
| `pytest tests/infra/test_backfill_person_dob_ssn.py -o pythonpath=. -v` | 35 / 35 passed |
| `ruff check infra/scripts/backfill_person_dob_ssn.py tests/infra/test_backfill_person_dob_ssn.py` | clean |
| `mypy infra/scripts/backfill_person_dob_ssn.py tests/infra/test_backfill_person_dob_ssn.py` | Success: no issues found in 2 source files |
| `mypy .` (full tree) | Success: no issues found in 308 source files |
| `make lint` (full repo) | 4 baseline UP037 / I001 in `packages/ingest/repository.py:477`, `packages/interaction/repository.py:131/140`, `tests/ingest/test_carestack_patients_with_payments_sql.py:14` — same 4 as Round 1, NONE from this branch (touched files are clean per `ruff check` above). |

### Real-script-bug findings

None. Every new test passed on the unmodified Round 1 script:

- The `commit_every` arithmetic was correct on the boundary cases
  (test 1 + 2).
- The `needs_manual_review` counter increments for both `mismatch_dob`
  AND `mismatch_ssn` skip paths (tests 3 + 4) and is surfaced in the
  summary log call as advertised.
- `_format_dry_run_line` is PHI-clean on the placeholder and mismatch
  shapes (tests 5 + 6).
- `_select_candidates` keeps `--person-uid` filtering Python-side
  (test 7).

No edits to `infra/scripts/backfill_person_dob_ssn.py` this round.
`git status` shows only the modified test file + the two original
untracked files; nothing committed.

### Branch state

Branch `eng-312-eng-312` is uncommitted and ready for orchestrator
review + merge. Two untracked files (the script + tests) plus the
in-place edit to the same test file are the entire delta.
