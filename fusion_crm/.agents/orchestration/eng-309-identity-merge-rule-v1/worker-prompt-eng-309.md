You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: **ENG-309**
(https://linear.app/fusion-dental-implants/issue/ENG-309/identity-resolution-hard-block-merge-across-different-dob-ssn).
Isolated git worktree. Implement → verify → write a report. Do NOT touch `main`,
do NOT push, do NOT open a PR. Commit to YOUR worktree branch only once green;
the Orchestrator integrates.

## Mission (backend — identity resolver rule + audit)

Identity-resolution currently merges CareStack patient records into one
`person.id` based on email/phone/name without enforcing DOB or SSN
equality as a hard veto. Real-world impact: the Torosyan card merges
Eduard (DOB 1968-04-19, SSN 623-35-9385) and Gaiane (DOB 1972-08-20,
SSN 602-37-8893) into one person, so `Paid $7,432` sums across two
distinct humans.

Add a hard-block: different DOB → never merge; different SSN → never
merge. Soft signals (phone, email, address) only apply when DOB+SSN
hard checks pass. Plus an audit script to count currently-wrong merges
and (conditional) an un-merge background script.

## Pre-flight facts (AUDITED — do NOT re-investigate)

### Where the merge decision lives

- **Entry point:** `IdentityService.resolve_or_create_from_hint()` at
  `packages/identity/service.py:925-1034`. Tier ladder:
  Tier 0 (source-link recapture) → Tier 1 (auto-accept) → Tier 2
  (ambiguous) → fallback new person.
- **Match policy:** `_evaluate_match_policy(hint, candidates) ->
  _MatchDecision` at `packages/identity/service.py:257-362`. Three
  Tier-1 rules: `email_phone_name` (0.99), `phone_name` (0.95),
  `email_name` (0.92). Tier 2 collapses to `email_only_ambiguous` /
  `phone_only_ambiguous` (0.70). **NO DOB/SSN check anywhere.**
- **Candidate lookup:** `IdentityRepository.list_candidate_persons_by_identifiers()`
  at `packages/identity/repository.py:159-204`. Selects persons by
  exact match on `email_normalized OR phone_normalized`. Returns
  distinct persons with `.identifiers` pre-loaded via `selectinload`.

### The forbidden-evidence design (critical context)

- `_FORBIDDEN_EVIDENCE_KEYS` at `packages/identity/service.py:61-81`
  REJECTS `dob` and `ssn` if anyone tries to put them into
  `MatchCandidate.evidence/conflicts`. They are FORBIDDEN AT THE
  EVIDENCE LAYER but **never read or compared for matching**.
- `MatchHintIn` DTO at `packages/identity/schemas.py:108-156` docstring
  says: *"NO DOB, NO SSN fields. Cannot carry clinical data."*
- This was the OLD design — under the OLD `apps/web/CLAUDE.md`
  rule #1 ("No PHI on the frontend, ever"). **That rule was UPDATED
  2026-06-01**: PHI is now allowed on the staff frontend and through
  the AI agent layer (OpenAI Enterprise BAA covers the path). Memory
  entry: `feedback_phi_on_staff_frontend_allowed`.
- So extending MatchHintIn to carry DOB and SSN is now consistent with
  policy. The forbidden-evidence rule may stay for the evidence dict
  (avoid logging PHI), but the resolver-level veto fields are new
  first-class signals.

### How CareStack feeds the resolver today

- `CareStackPatientIngestService._capture_patient()` at
  `packages/ingest/carestack_patient_service.py:185-243`:
  ```python
  hint = await self._ingest.capture_normalized_person_hint(
      tenant_id,
      NormalizedPersonHintIn(
          given_name=_string_or_none(patient.get("firstName")),
          family_name=_string_or_none(patient.get("lastName")),
          email=_string_or_none(patient.get("email")),
          phone=_first_string(patient.get("mobile"), patient.get("phoneWithExt")),
      ),
  )
  await self._identity.resolve_or_create_from_hint(
      tenant_id,
      MatchHintIn(
          ...
          email_normalized=hint.email_normalized,
          phone_normalized=hint.phone_normalized,
      ),
  )
  ```
- The raw payload (`payload["dob"]`, `payload["ssn"]`) IS stored verbatim
  in `ingest.raw_event.payload` (JSONB), but NEVER parsed for identity.
  We will start parsing them here.

### Test scaffolds

- `tests/identity/test_resolve_or_create_from_hint.py:46-82` —
  `_make_person()` helper constructs `Person` + `PersonIdentifier`
  with emails/phones. Reuse for the new matrix tests.
- `tests/ingest/test_carestack_patient_service.py` — mock CareStack
  patient dicts. Reuse / extend with dob+ssn fields for the
  ingest-side tests.

### Audit query shape

Join `identity.source_link` → `ingest.raw_event` via
`(tenant_id, source_link.source_id = raw_event.external_id)` filtered
to `raw_event.event_type = 'carestack.patient.upsert'`, take latest
`received_at` per `external_id`, group by `person_uid`, count
`DISTINCT payload->>'dob'` and `DISTINCT payload->>'ssn'`. A person is
flagged when EITHER distinct count > 1 (after filtering nulls).

## Tasks (TDD — tests first per piece)

### 1. Extend `MatchHintIn` schema with dob + ssn

In `packages/identity/schemas.py`:

- Add to `MatchHintIn`:
  ```python
  dob: date | None = None
  ssn: str | None = None  # raw SSN string (e.g. "623-35-9385") — opt-in identity signal under the 2026-06-01 PHI policy
  ```
- Update the docstring: the old "NO DOB, NO SSN" line must be replaced
  with: "DOB and SSN are opt-in identity-strength signals. They are
  used as HARD VETOES (mismatch → never merge); they NEVER score
  positively. They are never written to evidence/conflicts/log values."

### 2. Update the resolver to enforce the veto

In `packages/identity/service.py`:

- In `_evaluate_match_policy(hint, candidates)`: BEFORE the
  email_phone_name / phone_name / email_name rules fire (i.e., at the
  top of the per-candidate loop), call a new helper:
  ```python
  if _has_hard_identity_conflict(hint, candidate):
      continue  # skip this candidate; do not merge into it
  ```
- New helper `_has_hard_identity_conflict(hint, candidate) -> bool`:
  - Returns `True` if BOTH `hint.dob` and `candidate.dob` are set AND
    they differ (date equality).
  - Returns `True` if BOTH `hint.ssn` and `candidate.ssn` are set AND
    they differ (string equality after a trivial normalisation —
    strip whitespace + dashes).
  - Returns `False` if either side is missing the field, OR if both
    are equal.
- `_FORBIDDEN_EVIDENCE_KEYS` — keep `dob` and `ssn` in the forbidden
  set (still forbidden from evidence/conflicts dict logging). The veto
  reads from `hint.dob` / `candidate.dob` directly, NOT from evidence.

### 3. Plumb DOB+SSN through Person → PersonIdentifier (storage decision)

Pre-flight identified `Person` and `PersonIdentifier` in
`packages/identity/models.py`. Decide (document in worker report):

- **Option A (preferred):** Store `dob` and `ssn` on `Person` (new
  columns). New Alembic revision adds them. The resolver compares
  `hint.dob` against `candidate.dob` from `Person`.
- **Option B:** Store them as PersonIdentifier rows (`identifier_kind
  = 'dob'` / `'ssn'`). Reuses the existing identifier table; no
  schema change. The resolver pulls them from
  `candidate.identifiers`.
- **Option C:** Skip storage entirely — at every match call, look up
  the latest `carestack.patient.upsert` payload for each candidate's
  linked CareStack pids and extract dob/ssn on the fly. No schema
  change but adds DB roundtrip per match.

Recommendation: **Option A** for clarity and query speed (one column
read vs JSONB extract). One new Alembic revision. The columns are
PHI but the schema is already in `identity` schema which sits next to
PHI architecturally; no new boundary crossed.

### 4. Update CareStack patient ingest to pass DOB+SSN

In `packages/ingest/carestack_patient_service.py:_capture_patient`:

- After extracting other fields, parse:
  ```python
  dob_str = patient.get("dob")
  dob = datetime.fromisoformat(dob_str.split("T")[0]).date() if dob_str else None
  ssn = _normalize_ssn(patient.get("ssn"))  # strip whitespace + dashes
  ```
- Pass `dob=dob`, `ssn=ssn` into `MatchHintIn`.
- Helper `_normalize_ssn(value: str | None) -> str | None`: returns
  `None` for empty/whitespace; otherwise the digit-only string.

### 5. Persist dob+ssn on Person (Option A path)

If Option A chosen:

- Add `dob: Mapped[date | None]` and `ssn: Mapped[str | None]` columns
  to `Person` model in `packages/identity/models.py`.
- New Alembic revision: `2026XXXX_XXXX_<hash>_add_identity_person_dob_ssn.py`.
  Add the two columns (nullable). Down-revision points to the current
  alembic head (`e9f0a1b2c3d4` from ENG-308). Clean `downgrade()`.
- In the resolver: when `resolve_or_create_from_hint` decides to merge
  (or create), persist the dob/ssn from the hint onto the Person row
  IF they are non-null and the Person doesn't already have a
  conflicting value. (If person has dob=1968 and hint says dob=1972
  but it passed the veto — meaning one side was missing originally —
  we never silently overwrite. Document the precedence in the
  docstring.)
- IdentityRepository.list_candidate_persons_by_identifiers needs no
  change; the candidate list is filtered by email/phone identifiers
  as today and the resolver veto reads `candidate.dob` / `candidate.ssn`
  in memory.

### 6. Unit tests for the merge matrix

In `tests/identity/test_resolve_or_create_from_hint.py` (extend) +
sibling `test_identity_dob_ssn_veto.py` (NEW):

- DOB equal + SSN equal + phone match → merge.
- DOB equal + SSN equal + no other signal → merge.
- DOB equal + one side missing SSN + phone+address+lastName all match
  → merge.
- DOB mismatch + every soft signal matches → **NO merge** (Torosyan
  Eduard vs Gaiane reproducer; assert two different person.ids
  emerge).
- SSN mismatch + every soft signal matches → **NO merge**.
- Both sides missing DOB + phone+address+accountId+lastName match →
  may merge (document as soft path, regression-protect with a test
  that asserts the existing email_phone_name rule still fires).
- Same-person multi-registration (same DOB + same SSN, different
  pid, different location) → merge (legitimate Gaiane case).
- Reproducer test using payloads matching pids 1460847 + 1461274.

In `tests/ingest/test_carestack_patient_service.py`:
- Patient payload with dob + ssn → MatchHintIn carries them.
- Patient payload without dob/ssn → MatchHintIn dob=None, ssn=None.

### 7. Audit script

`infra/scripts/audit_identity_merges.py` (NEW):

- CLI flags: `--tenant-id` (required), `--dry-run` (default True),
  `--sample-size N` (default 20).
- Query: enumerate `person.id` rows where any pair of linked CareStack
  patient_ids has DOB or SSN mismatch in their latest
  `carestack.patient.upsert` raw_event payload (audit query shape from
  pre-flight). Tenant-scoped.
- Output: structured log line with counts (total_persons,
  wrong_merged_persons, dob_mismatch_count, ssn_mismatch_count).
  Sample of first N person_uid + per-pid (dob, ssn) tuples printed on
  stdout. **No PHI in structured log values** — only counts.
- Mirror `backfill_payment_summary.py` shape (async_session, principal,
  exit codes).

Tests in `tests/infra/test_audit_identity_merges.py` (NEW) mirror
`test_backfill_payment_summary.py` patterns: importlib loading,
_fake_session_cm, _args. Assert: correct flagging on Torosyan-shape
fixture; no real DB / network.

### 8. Un-merge script (CONDITIONAL on audit count)

Run the audit script in dry-run during worker development to estimate
count. If ≤ 50 wrong-merged persons: include
`infra/scripts/split_wrong_merged_persons.py`. If > 50: document the
count in the worker report + file as ENG-311 follow-up (do NOT
implement here).

If you implement it:

- CLI flags: `--tenant-id`, `--dry-run`, `--max-splits N`, `--apply`
  (default False).
- For each wrong-merged person: group its linked CS source_links by
  (dob, ssn) bucket; the largest bucket stays on the original person;
  each other bucket spawns a new `person.id`; source_links + downstream
  attribution moves with their bucket.
- Writes one `audit.access_log` row per split (`action_code =
  'identity.person.split'`, principal = SYSTEM, includes
  before/after person counts — NO PHI values).
- Idempotent (re-run with no remaining wrong merges → no-op).
- Background-only; do NOT auto-run on merge.

Tests for un-merge in `tests/infra/test_split_wrong_merged_persons.py`
(NEW): dry-run is no-op; --apply against a Torosyan-shape fixture
produces 2 persons (Eduard's pid vs Gaiane's 2 pids); audit row written.

## Hard constraints

- **CareStack mocked in all tests.** No real network in dev/CI.
- **No PHI in structured log values.** Counts, person_uid, patient_id
  only. Never DOB / SSN / names in log values.
- **Schema separation invariant remains.** `phi.*` reads through
  `PhiService` if any new path crosses there. The identity schema can
  store dob/ssn alongside name (per the updated PHI policy).
- **Append-only audit on `audit.access_log`.** Un-merge writes
  one row per split.
- **`except Exception`, never `except BaseException`.**
- **English in repo files.**
- **Strict mypy.**
- **ONE new Alembic revision** if Option A chosen. Never edit shipped
  migrations.
- **Reuse**: `_fake_session_cm`, `_args`, `_principal`, async_session
  pattern from prior backfill scripts (ENG-305 lineage).
- **Do NOT touch `apps/web/lib/msw/handlers.ts`.**
- **DOB and SSN stay in `_FORBIDDEN_EVIDENCE_KEYS`** at the evidence-
  dict layer (logging hygiene). The resolver reads them as top-level
  hint fields, not as evidence.

## Verify (sandbox-aware)

```bash
ruff check packages/identity/ packages/ingest/carestack_patient_service.py \
  infra/scripts/audit_identity_merges.py \
  infra/scripts/split_wrong_merged_persons.py \
  tests/identity/ tests/ingest/test_carestack_patient_service.py \
  tests/infra/test_audit_identity_merges.py \
  tests/infra/test_split_wrong_merged_persons.py
mypy packages/identity/ packages/ingest/carestack_patient_service.py \
  infra/scripts/
pytest tests/identity/ tests/ingest/test_carestack_patient_service.py \
  tests/infra/test_audit_identity_merges.py \
  tests/infra/test_split_wrong_merged_persons.py -v -o pythonpath=.
```

(Some commands may be sandbox-blocked; document outcomes.)

## Definition of done

1. All sandbox-allowed verify commands green.
2. ONE commit on worktree branch:
   `ENG-309: hard-block identity merge on DOB / SSN mismatch + audit + un-merge`.
3. Worker report at
   `.agents/orchestration/current/reports/ENG-309-worker-report.md`
   covering: touched files, design decisions (Option A/B/C, un-merge
   in-or-out), tests added + results, verify commands + outcomes,
   audit count from a dry-run (if accessible), risks, DO-NOT-MERGE
   conditions.
4. Do NOT run the real audit / un-merge against prod — those are
   SEPARATE operator decisions after merge.

If the spec / facts conflict with reality, STOP and write `Blocked:`
in the report rather than guess.
