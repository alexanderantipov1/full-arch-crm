You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: **ENG-311**
(https://linear.app/fusion-dental-implants/issue/ENG-311/un-merge-backfill-split-3416-wrong-merged-carestack-persons-post-eng).
Isolated git worktree. Implement → verify → write a report. Do NOT touch `main`,
do NOT push, do NOT open a PR. Commit to YOUR worktree branch only once green;
the Orchestrator integrates.

## Mission (background un-merge script)

ENG-309 (merged) stopped NEW household-merges via a DOB/SSN hard-block.
This ticket cleans the **3,416 EXISTING wrong-merged persons** (audit
confirmed: whole households collapsed into one person.id). Ship
`infra/scripts/split_wrong_merged_persons.py` that splits each
wrong-merged person into N persons — one per `(dob, ssn)` bucket.

## Pre-flight facts (AUDITED — do NOT re-investigate)

### Models (packages/identity/models.py)

- `Person` (lines 115-150): `id` UUID PK (= person_uid), `dob` (Date,
  nullable), `ssn` (String(32), normalized, nullable), name fields,
  `TenantScopedMixin`.
- `PersonIdentifier` (152-177): links to Person via `person_id` FK;
  `kind` (email/phone), `value` (normalized).
- `SourceLink` (180-245): links via **`person_uid` FK** (plain UUID,
  MUTABLE, `ondelete=CASCADE`). Unique on
  `(tenant, source_system, source_instance, source_kind, source_id)`.

### Create-person + repoint mechanics

- `IdentityService.create_person(tenant_id, payload: PersonIn) -> Person`
  (service.py:610-640) — creates Person with dob/ssn + identifier rows.
  Use it (or a thinner repo-level `add_person`) to clone a Person for
  each non-surviving bucket.
- **Repoint a source_link:** `person_uid` is a plain mutable column.
  `UPDATE identity.source_link SET person_uid = :new WHERE id = :sl_id`.
  No service wrapper exists; a direct repo-layer UPDATE in the
  transaction is the established path.

### Downstream attribution (CRITICAL — read carefully)

- **Financials need ZERO rewrites:** payment_summary snapshots,
  accounting transactions, appointments, invoices all key on the
  CareStack `external_id` (patient_id), NOT person_uid. Moving a
  source_link to a new person auto-reattributes all financials.
- **BUT these tables denormalize `person_uid` and DO need repointing
  when their owning patient_id moves to a new person:**
  - `ops.lead` (person_uid plain FK)
  - `ops.consultation`
  - `ops.followup_task`
  - `ops.person_location_profile`
  - `interaction.event` (person_uid plain column)
- **Repointing policy (document in report):** each downstream row that
  is traceable to a specific CareStack patient_id should follow that
  patient_id's bucket. A downstream row with NO patient_id linkage
  (pure person-level, e.g. a lead that came from Salesforce not
  CareStack) STAYS on the surviving (largest) bucket — we never had
  CareStack identity for it, so it keeps the original person.
  - For rows traceable via a source link / external ref: repoint to the
    new person_uid of the bucket that owns that patient_id.
  - For rows with only person_uid and no provider trace: leave on the
    surviving person.
  - **If you cannot reliably determine which bucket a downstream row
    belongs to, leave it on the surviving person and LOG a
    `needs_manual_review` count** (not the row contents) — do NOT guess.
    Document this in the report as a known limitation.

### audit.access_log write (append-only)

- `AuditService.record(*, principal, action, resource=None,
  person_uid=None, reason=None, extra=None) -> AccessLog`
  (packages/audit/service.py:79-99).
- For each split write ONE row:
  `action="identity.person.split"`, `principal` = a SYSTEM principal,
  `person_uid` = the surviving person, `extra = {"surviving_person_uid":
  ..., "new_person_uids": [...], "bucket_count": N,
  "source_links_moved": M}`. **NO PHI in extra** (no dob/ssn/name
  values — only uuids + counts).

### Wrong-merged-person selection (reuse ENG-309 query)

`infra/scripts/audit_identity_merges.py` already has `_AUDIT_SQL`
(lines 105-134): the `WITH latest_payload` CTE joining
`identity.source_link` → `ingest.raw_event` on `external_id`,
`GROUP BY person_uid HAVING COUNT(*) > 1`, aggregating
`patient_ids / dobs / ssns`. **Import / copy that exact query** so the
split script selects the same population. Add the DOB/SSN-mismatch
filter (the audit script reports all multi-link; the split only acts on
the ones with a real DOB or SSN mismatch — mirror the
`distinct_dob > 1 OR distinct_ssn > 1` predicate the orchestrator's
audit used).

### Backfill script + test scaffolds

- Mirror `infra/scripts/backfill_payment_summary.py` +
  `infra/scripts/audit_identity_merges.py`: `async def main(args, *,
  session_factory=None) -> int`, `_default_session_factory()` deferred
  import, `configure_logging` at `run()`, `asyncio.run(main(args))`,
  exit codes 0/1/2.
- Tests: `tests/infra/test_audit_identity_merges.py:42-95` pattern —
  `importlib.util.spec_from_file_location` to load the script,
  `_fake_session_cm(rows)` mocking `session.execute().all()`,
  `_args(Namespace)` builder. No real DB / network.

## Tasks (TDD)

### 1. The split script

`infra/scripts/split_wrong_merged_persons.py` (NEW):

- CLI: `--tenant-id` (required), `--dry-run` (default True),
  `--apply` (explicit; mutually-clears dry-run), `--max-splits N`
  (default 100), `--person-uid <uuid>` (optional single target).
- `async def main(args, *, session_factory=None) -> int`.
- Select wrong-merged persons (reuse `_AUDIT_SQL` + DOB/SSN-mismatch
  filter). When `--person-uid` set, filter to that one.
- For each person (up to `--max-splits`):
  1. Resolve per-pid `(dob, ssn)` from the latest patient payload.
  2. Group pids into buckets keyed by `(dob_normalized, ssn_normalized)`.
     Document the partial-null precedence: a pid with a dob but null
     ssn joins a bucket sharing that dob if exactly one such bucket
     exists; otherwise it forms its own bucket. NEVER merge two
     different non-null dobs.
  3. If only 1 bucket → not actually wrong (skip; log skipped count).
  4. Largest bucket stays on the original person.id. Tie-break:
     the bucket containing the lexicographically smallest patient_id
     stays (deterministic).
  5. For each non-surviving bucket: create a new Person (clone name
     fields; set dob+ssn from the bucket); repoint that bucket's
     source_links (`UPDATE ... SET person_uid = new`); repoint the
     downstream `ops.*` + `interaction.event` rows traceable to that
     bucket's patient_ids per the policy above; copy relevant
     PersonIdentifier rows (the phone/email that belong to that human —
     if ambiguous, copy shared identifiers to BOTH and log; document).
  6. Write one `audit.access_log` row per split person.
- `--dry-run`: compute + print the full plan (person_uid → bucket
  breakdown → planned new person count) on stdout; do NO writes, open
  NO transaction that commits.
- `--apply`: execute within a per-person transaction; batch commit
  every 50 persons.
- Structured logs: counts only (`scanned`, `split`, `new_persons`,
  `skipped`, `needs_manual_review`) + `selector` field. NO PHI values.
- Exit codes: 0 success, 2 missing credential / no tenant, 1 uncaught.

### 2. Tests

`tests/infra/test_split_wrong_merged_persons.py` (NEW), mirror the
audit test scaffold:

- **Torosyan-shape**: 3 pids — Eduard (dob 1968, ssn A) + Gaiane
  (dob 1972, ssn B) ×2 registrations. → 2 buckets. Gaiane bucket
  (2 pids) stays on original; Eduard bucket (1 pid) → 1 new person.
  Assert: 1 new Person created, Eduard's source_link repointed,
  1 audit row.
- **Perevertov-shape**: 5 pids, 5 distinct (dob, ssn) → 5 buckets →
  4 new persons (largest=1 each, tie-break by smallest patient_id;
  here all buckets size 1 so the smallest-patient_id bucket survives).
  Assert 4 new persons + 4 audit rows.
- **Legitimate same-person**: 2 pids, SAME dob + SAME ssn → 1 bucket →
  skip (0 splits). Assert no Person created, no audit row.
- `--dry-run` no-op: assert zero `add_person` / zero UPDATE / zero
  audit writes; plan printed to stdout.
- `--max-splits` cap: 10 wrong persons, `--max-splits 3` → only 3
  processed.
- `--person-uid` single-target: only the named person processed.
- Idempotent: a person that's already clean (1 bucket) → 0 splits.
- Downstream repoint: a fixture with an `ops.consultation` /
  `interaction.event` row tied to Eduard's patient_id → asserts that
  row's person_uid updated to Eduard's new person; a person-level row
  with no patient trace → stays on surviving.
- Audit-row shape: assert `action="identity.person.split"`, extra has
  uuids + counts, NO dob/ssn/name values.

All mocked — `_fake_session_cm` style, AsyncMock, no real DB / network.

## Hard constraints

- **Background-only.** NOT wired to HTTP.
- **`--apply` is OPT-IN.** Default `--dry-run`. Real fleet split is a
  SEPARATE operator go AFTER merge.
- **Append-only audit:** one `audit.access_log` row per split. NO PHI
  values in `extra` (uuids + counts only).
- **No PHI in structured log values.**
- **Tenant-scoped:** every query + write filtered by tenant_id.
- **Idempotent:** re-run on clean persons → no-op.
- **No new migration** — uses existing tables.
- **`except Exception`, never `except BaseException`.**
- **English in repo files. Strict mypy.**
- **Do NOT touch `apps/web/lib/msw/handlers.ts`.**
- **Legitimate same-person multi-registration (same DOB+SSN) is NEVER
  split** — those pids share a bucket.
- **When uncertain which bucket a downstream row belongs to, leave it
  on the surviving person + increment `needs_manual_review` — never
  guess.**

## Verify (sandbox-aware)

```bash
ruff check infra/scripts/split_wrong_merged_persons.py tests/infra/
mypy infra/scripts/split_wrong_merged_persons.py
pytest tests/infra/test_split_wrong_merged_persons.py -v -o pythonpath=.
```

Document what ran vs deferred.

## Definition of done

1. Sandbox-allowed verify commands green.
2. ONE commit on worktree branch:
   `ENG-311: un-merge split script for wrong-merged CareStack persons`.
3. Worker report at
   `.agents/orchestration/current/reports/ENG-311-worker-report.md`
   covering: touched files, the bucketing + downstream-repoint policy
   you implemented, the `needs_manual_review` fallback, tests + results,
   verify outcomes, risks, DO-NOT-MERGE conditions.
4. Do NOT run the real `--apply` against prod — SEPARATE operator go.

If the split mechanics conflict with reality, STOP and write `Blocked:`
rather than guess — this script mutates identity, correctness > speed.
