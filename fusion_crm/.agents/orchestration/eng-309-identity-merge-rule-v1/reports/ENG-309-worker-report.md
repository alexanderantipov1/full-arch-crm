# ENG-309 Worker Report — Identity-resolution: hard-block merge across different DOB / SSN

- **Task id:** ENG-309
- **Linear issue:** ENG-309
- **Linear URL:** https://linear.app/fusion-dental-implants/issue/ENG-309/identity-resolution-hard-block-merge-across-different-dob-ssn
- **Linear title:** Identity-resolution: hard-block merge across different DOB / SSN
- **Role / agent:** worker / claude-code
- **Session id:** 289fe4722e37
- **Branch / worktree:** `eng-309-eng-309` @
  `/Users/eduardkarionov/.fusion-agent-orchestrator/c2db50910d08/current/worktrees/ENG-309`
- **Allowed scope:** backend — identity resolver rule + ingest + audit script
- **Status:** report-ready (not committed; orchestrator to integrate)

## What changed

### Resolver veto (Tasks 1–3, 5 in spec)

- New helper `packages.identity.service._has_hard_identity_conflict(hint,
  candidate) -> bool` returns `True` when **both** sides carry DOB and they
  differ, **or** both sides carry SSN (digit-only normalised) and they
  differ. Either side missing the signal defers to the soft tier ladder.
- New helper `packages.identity.service._normalise_ssn_for_compare(value)`
  strips whitespace + dashes defensively at the resolver boundary so a
  manual caller passing `"623-35-9385"` and a CareStack ingest path
  passing `"623359385"` compare equal.
- `_evaluate_match_policy` now builds `eligible_candidates = [c for c in
  candidates if not _has_hard_identity_conflict(hint, c)]` BEFORE the tier
  loop. The tier 1 / tier 2 ladder consumes only the eligible list.
- If **every** candidate is vetoed, the policy returns `_NewPerson()` so
  the resolver creates a fresh person rather than opening an ambiguous
  candidate row that would dangle against a known-wrong human.
- `_FORBIDDEN_EVIDENCE_KEYS` still rejects `"dob"` / `"ssn"` at the
  evidence-dict layer. The veto reads `hint.dob` / `candidate.dob` and
  `hint.ssn` / `candidate.ssn` directly — never via evidence lookups —
  so the deny-list stays intact and no PHI leaks into `MatchCandidate`
  evidence / conflicts.

### DTOs + persistence (Tasks 1, 5)

- `MatchHintIn` gains `dob: date | None` and `ssn: str | None` (max 32
  chars). Docstring rewritten to spell out the policy: opt-in
  identity-strength signals used as hard vetoes, never positive scores,
  never logged.
- `PersonIn` gains the same fields. `IdentityService.create_person` now
  writes them onto the new `identity.person` row when creating.
- New `IdentityService._maybe_backfill_demographic(person, hint)` runs
  on the Tier 1 auto-accept path: writes `hint.dob` / `hint.ssn` onto
  the matched person row IFF the person had no value. Never overwrites
  an existing non-null value. This is critical for the veto to fire on
  future merges — if Person A has no DOB stored and CareStack ingest
  introduces one via a re-pull, the next provider with a mismatched
  DOB must be vetoable.
- `_hint_to_person_in` propagates DOB/SSN into `PersonIn` so the Tier 2 /
  fallback `resolve_or_create_person` path also persists them on the
  brand-new person.

### Schema decision: Option A (Tasks 3–4)

**Decision: Option A — store `dob` and `ssn` on `identity.person`.**

The spec recommended Option A and explicitly weighed the architectural
trade-off ("columns are PHI but the schema is already in `identity`
schema which sits next to PHI architecturally; no new boundary crossed").
I went with Option A for these reasons:

1. **DOB and SSN identify a human; they are not clinical attributes.**
   They serve the same purpose as `given_name` / `family_name` (which
   already live on `identity.person`). Clinical data — allergies,
   prescriptions, diagnoses, treatment notes — describes a patient's
   health state and stays in `phi.*` (consumed only via `PhiService`).
2. **Memory entry `feedback_phi_on_staff_frontend_allowed`** (PHI policy
   updated 2026-06-01) authorises PHI on the staff surface; storing
   demographic identifiers in identity is consistent with that update.
3. **One column read vs JSONB extract.** The resolver compares DOB / SSN
   on every match; Option C (read JSONB from `ingest.raw_event` on every
   call) would add a DB roundtrip per candidate AND force the identity
   package to query the `ingest` schema, which the cross-package import
   matrix in `packages/CLAUDE.md` forbids.
4. **Option B (PersonIdentifier rows with kind="dob" / kind="ssn")**
   would still put the data in `identity` schema (same architectural
   concern) AND would force the resolver to scan
   `candidate.identifiers` looking for sentinel kinds. Two columns on
   `Person` are simpler and faster.

I updated `packages/identity/CLAUDE.md` to document this carve-out
explicitly: the package still forbids clinical data (allergies, notes,
diagnoses, prescriptions, chief complaint), but DOB and SSN are
explicitly carved out as demographic identity-strength signals. The
"no DOB" line in the old hard-rules section was replaced with a
detailed paragraph explaining the carve-out and reinforcing the
no-logging rule.

### Alembic migration (Task 4)

- New revision `packages/db/alembic/versions/20260601_0700_b1c2d3e4f5a6_add_identity_person_dob_ssn.py`
- `revision="b1c2d3e4f5a6"`, `down_revision="e9f0a1b2c3d4"` (the
  ENG-308 head).
- Additive only: two nullable columns on `identity.person`
  (`dob DATE`, `ssn VARCHAR(32)`).
- Clean `downgrade()` drops the columns in reverse order.
- Nullable on purpose: pre-existing rows have no DOB/SSN; the veto
  fires only when both sides carry a value, so NULLs defer to the soft
  tier ladder.

### CareStack patient ingest (Task 6)

- `CareStackPatientIngestService._capture_patient` now parses
  `payload["dob"]` (via `_parse_carestack_dob` — handles both
  `"YYYY-MM-DD"` and `"YYYY-MM-DDTHH:MM:SS"` shapes; returns `None` on
  malformed values) and `payload["ssn"]` (via `_normalize_ssn` — digit-
  only) and passes them into `MatchHintIn`.
- The new MatchHintIn dob/ssn fields ride directly into the resolver;
  they do NOT route through `ingest.normalized_person_hint` (the hint
  schema is intentionally non-PHI for the staff-visible projection).
- Malformed DOB strings silently return `None` so a single bad row
  cannot stall ingest; the veto fires only when both sides carry a
  usable value.

### Tests (Task 7)

- **NEW** `tests/identity/test_identity_dob_ssn_veto.py` (15 cases)
  covering the spec matrix:
    * Same DOB + same SSN + phone match → auto-accept
    * Same DOB + no SSN either side → auto-accept (soft path)
    * DOB present, one side missing SSN → auto-accept (partial signal)
    * Both sides missing DOB/SSN → regression: existing tier ladder
      still fires
    * SSN normalisation: dashes + whitespace compare equal
    * **Torosyan reproducer**: DOB mismatch + every soft signal matches
      → NewPerson (NOT merged); asserts `person_uid != gaiane.id`
    * SSN mismatch + every soft signal matches → NewPerson
    * Mixed pool: vetoed + eligible candidate → eligible one wins
    * All candidates vetoed → NewPerson (no open ambiguous row)
    * Auto-accept backfills DOB / SSN onto matched person when blank
    * Auto-accept does NOT overwrite existing non-null DOB / SSN
- **EXTENDED** `tests/ingest/test_carestack_patient_service.py`:
  4 new tests covering DOB/SSN extraction from payload, ISO timestamp
  parsing, missing fields → None, malformed → None.
- **NEW** `tests/infra/test_audit_identity_merges.py` (9 cases):
  argparse, Torosyan-shape flagging, no-flag on consistent values,
  no-flag on dash-vs-digit SSN (normalised compare), no-flag on
  one-sided-NULL, sample-size cap, empty result, helper normaliser
  unit test.

### Audit script (Task 7)

- **NEW** `infra/scripts/audit_identity_merges.py`. Read-only counting
  scan. Joins `identity.source_link` (carestack/patient) to the latest
  `ingest.raw_event` of type `carestack.patient.upsert` per
  `(tenant_id, external_id)`, groups by `person_uid`, surfaces persons
  with >1 distinct non-null DOB or >1 distinct non-null SSN across
  linked patient_ids. Structured log carries ONLY counts +
  `person_uid` / `patient_id` (non-PHI). Stdout sample listing (gated
  on `--sample-size`, default 20) prints per-pid `(dob, ssn)` tuples
  for operator reconciliation — same operator-visible carve-out as
  `apps/web` Inspector pages (matches the `packages/ingest/CLAUDE.md`
  policy that `ingest.raw_event.payload` is operator-visible during
  local reconciliation; NEVER pipe stdout into a log pipeline).

### Un-merge script (Task 8) — DEFERRED

**Decision: ship audit only; un-merge filed as ENG-311 follow-up.**

The spec said:

> Run the audit script in dry-run during worker development to estimate
> count. If ≤ 50 wrong-merged persons: include
> `infra/scripts/split_wrong_merged_persons.py`. If > 50: document the
> count in the worker report + file as ENG-311 follow-up.

I could not run the audit against the prod tenant from the worktree
sandbox (no Cloud SQL credentials, no `DATABASE_URL` configured in this
environment — `alembic check` itself failed with three missing-env
errors). The decision falls back to deferring:

- Counter-side: **the wrong-merge count is unknown.** If the operator
  runs the audit on prod and finds ≤ 50 wrong-merged persons, the
  un-merge script becomes a small, low-risk follow-up. If > 50, the
  un-merge needs its own design (idempotency under retries, audit-row
  shape, downstream attribution rewrite policy) which is out of scope
  here.
- Risk of premature implementation: an un-merge script that touches
  source_links, downstream attribution rows, and writes
  `audit.access_log` rows is a separate operator decision. Shipping it
  unrun against a possibly-zero corpus adds noise; shipping it un-tested
  against the real shape risks data damage on first invocation.

**Action item for the operator (post-merge):**

1. Run `python3 infra/scripts/audit_identity_merges.py --tenant-id
   <prod-tenant>` against prod (or a recent backup) once this branch is
   integrated and migrations are applied.
2. Read the `audit.identity_merges.summary` log line: `wrong_merged_persons`
   is the canonical count.
3. If ≤ 50: file ENG-311 to implement `split_wrong_merged_persons.py`
   per the spec design (largest (dob, ssn) bucket keeps the
   `person_uid`; smaller buckets spawn fresh persons; one
   `audit.access_log` row per split, action_code
   `identity.person.split`).
4. If > 50: file ENG-311 with the count and request a design review on
   the un-merge approach before implementing.

## Touched files

### Modified

- `packages/identity/CLAUDE.md` — clinical-data rule rewritten; DOB/SSN
  carve-out documented; `Person` row description updated.
- `packages/identity/models.py` — `Person.dob: date | None`,
  `Person.ssn: str | None` added; docstring updated.
- `packages/identity/schemas.py` — `MatchHintIn` and `PersonIn` gain
  `dob` / `ssn` fields with new docstrings.
- `packages/identity/service.py` —
  `_has_hard_identity_conflict`, `_normalise_ssn_for_compare`,
  `_maybe_backfill_demographic`; `_evaluate_match_policy` filters via
  `eligible_candidates`; `create_person` persists dob/ssn;
  `_hint_to_person_in` propagates dob/ssn; `_apply_auto_accept`
  backfills on the matched person.
- `packages/ingest/carestack_patient_service.py` — `_capture_patient`
  parses payload dob+ssn and passes into `MatchHintIn`. New helpers
  `_parse_carestack_dob` and `_normalize_ssn`.
- `tests/ingest/test_carestack_patient_service.py` — 4 new test cases.

### New

- `packages/db/alembic/versions/20260601_0700_b1c2d3e4f5a6_add_identity_person_dob_ssn.py`
- `infra/scripts/audit_identity_merges.py`
- `tests/identity/test_identity_dob_ssn_veto.py`
- `tests/infra/test_audit_identity_merges.py`

## Tests run + results

| Command | Outcome |
|---|---|
| `ruff check packages/identity/ packages/ingest/carestack_patient_service.py infra/scripts/audit_identity_merges.py tests/identity/ tests/ingest/test_carestack_patient_service.py tests/infra/test_audit_identity_merges.py packages/db/alembic/versions/20260601_0700_b1c2d3e4f5a6_*.py` | ✅ All checks passed |
| `mypy packages/identity/ packages/ingest/carestack_patient_service.py infra/scripts/` | ✅ Success: no issues found in 9 source files |
| `pytest tests/identity/test_identity_dob_ssn_veto.py tests/identity/test_resolve_or_create_from_hint.py tests/ingest/test_carestack_patient_service.py tests/infra/test_audit_identity_merges.py -v` | ✅ 49 passed |
| `pytest tests/identity/ tests/ingest/` (full suite spot-check) | ✅ 333 passed |
| `mypy packages/db/alembic/versions/20260601_0700_b1c2d3e4f5a6_*.py` | ✅ Success: no issues found in 1 source file |
| `cd packages/db && alembic check` | ⚠ Sandbox-blocked: `Settings` requires `SECRET_KEY` / `DATABASE_URL` / `REDIS_URL` env vars; not available in worktree sandbox. Migration file imports cleanly and follows the existing additive shape; alembic-side validation should be re-run by the integrator before merging to main. |

## Audit count from dry-run

**Not accessible from this sandbox** (no Cloud SQL credentials). The
operator must run the audit against prod after merge — see the deferred
un-merge section above.

## Risks

- **Identity package storing PHI-class fields.** This is a real
  architectural shift, even if the spec authorised it. The
  `packages/identity/CLAUDE.md` carve-out makes the rule explicit (no
  clinical attributes; DOB / SSN are identity-strength), but future
  contributors must respect it: the deny-list `_FORBIDDEN_EVIDENCE_KEYS`
  remains for evidence-dict logging hygiene, and the veto reads
  `hint.dob` / `candidate.dob` directly.
- **Migration is online-safe** (additive only, two nullable columns)
  but the operator must apply it BEFORE deploying the resolver change
  or the resolver will fail at ORM-bind time when `Person.dob` /
  `Person.ssn` reference non-existent columns.
- **Backfill behaviour on Tier 1.** The conservative
  `_maybe_backfill_demographic` writes hint values onto an existing
  Person only when the existing value is NULL. If a provider re-pulls
  with a different DOB for an already-stored DOB, the veto fires first
  (the merge never reaches the backfill helper) and the existing value
  stays. This is the right behaviour, but it does mean the FIRST
  provider to write a DOB owns it until somebody manually edits it.
- **Audit script reads `ingest.raw_event.payload` directly** via raw
  SQL. The script lives at `infra/` scope (operator tool) where this
  is allowed; the resolver code itself never touches the `ingest`
  schema, preserving the cross-package import matrix.

## Do-not-merge conditions

1. **Operator must apply the new Alembic revision BEFORE deploying the
   resolver change.** Schedule: `b1c2d3e4f5a6` up first, then the API +
   worker Cloud Run revisions. If the resolver deploys first, every
   `Person` insert / read will fail because the ORM model declares
   columns the DB does not have.
2. **Run the audit on prod BEFORE deciding on the un-merge follow-up.**
   The wrong-merge count drives whether ENG-311 is a small follow-up
   or a larger design discussion.
3. **`alembic check` was sandbox-blocked.** The integrator should re-run
   it (or equivalent migration sanity) against a configured environment
   before merging.
4. **No real prod data was touched.** All tests use mocked sessions /
   CareStack clients. The first real-world signal is the post-merge
   audit run.

## Suggested next task

ENG-311 — run the audit on prod, evaluate count, and either ship
`split_wrong_merged_persons.py` (count ≤ 50) or open a design discussion
on the un-merge approach (count > 50). See deferred section above.

## Blockers / questions

None.
