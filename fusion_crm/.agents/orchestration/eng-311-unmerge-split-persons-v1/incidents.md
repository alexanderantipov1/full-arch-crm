# Incidents — ENG-311

## 2026-06-01 — Adversarial review BLOCK (3 lenses failed, 4 blockers) → worker re-dispatched

Workflow `wx3eml7tw` (3 Sonnet lenses) returned `aggregated_pass=false`
on worker commit `44e4833`. First genuine BLOCK of the session — the
script mutates identity for 3,416 persons, so the bar is high. NOT
merged. Re-dispatched the same worker branch with a focused fix prompt.

### Blocker 1 — CRITICAL (split-correctness Claim 5): downstream repoint incomplete + docstring lies

- `ops.consultation` rows have a CareStack patient_id trace (via the
  appointment/consultation source link) but the script counts them as
  `needs_manual_review` instead of repointing them. Result: a moved
  human's consultations stay attributed to the surviving person.
- `ops.lead` is named in the module docstring as "traceable + repointed"
  but NO SQL repoints it — docstring/implementation mismatch.

**Fix:** repoint `ops.consultation` via its patient_id linkage (same
unambiguous trace as `interaction.event source_kind='patient'`).
`ops.lead` is genuinely ambiguous (Salesforce origin, often predates
the CareStack patient) → keep on surviving + `needs_manual_review`, and
FIX the docstring to state that honestly. `ops.followup_task` +
`ops.person_location_profile` — repoint if they carry a clean patient_id
trace, else manual-review; document which.

### Blocker 2 — MAJOR (split-correctness Claim 8): batch rollback loses up to 49 splits

All persons in a `commit_every=50` batch run in one transaction. One
failed person re-raises → unwinds the `async with` → rolls back ALL
uncommitted splits in that batch (up to 49 correct ones). Clean
rollback (no corruption) but silent loss of computed work; operator
must re-run.

**Fix:** wrap each person in `async with session.begin_nested()`
(SAVEPOINT). On a single person's failure, roll back only that
savepoint, increment `error_count`, continue the batch. The outer
`commit_every` batch commit stays.

### Blocker 3 — MAJOR (mocking): repoint test is too weak

`test_interaction_event_repoint_issued_per_bucket` only asserts an
`UPDATE interaction.event` SQL string executed — it never inspects
`session` executed params to confirm the NEW person's UUID was passed.
And there is no `ops.consultation` repoint test at all.

**Fix:** strengthen the repoint test to assert the new person_uid is in
the bound params; add an `ops.consultation` repoint test (fixture with
a consultation tied to a moving patient_id → asserts its person_uid
changed to the new person).

### Passing lenses / claims (no rework)

- Bucketing correctness (Claims 1, 3, 10): two different non-null DOBs
  never share a bucket; legitimate same-person not split; partial-null
  precedence correct.
- Largest-bucket-survives + deterministic tie-break (Claim 2).
- New-person creation + source_link repoint (Claim 4).
- Financials untouched (Claim 6).
- dry-run true no-op (Claim 7 — reviewer retracted to PASS).
- Idempotency (Claim 9).
- Audit-row shape — uuids + counts, no PHI (audit-completeness lens).

### Verify state at block

mypy clean (1 file); 21/21 focused tests passed in the worktree. The
tests pass but DON'T cover the gaps the reviewer found — which is
exactly why the adversarial review matters.

## 2026-06-01 — Round 2 review: 3 blockers fixed; 2 residual non-defects ACCEPTED → merge

Re-review (Workflow `wxxmo4bau`) on round-2 commit `dd0460b`:
`aggregated_pass=false`, but down from 4 blockers → 1, and the remaining
"failures" are NOT defects.

**Round-1 blockers — ALL FIXED:**
- ops.consultation repoint (CRITICAL) → PASS. Repointed via
  `raw_event_id → payload->>'patientId'` join; honest per-table decision
  table in docstring.
- per-person SAVEPOINT (MAJOR) → PASS. `async with session.begin_nested()`
  per person; one failure costs only that person, batch continues.
- repoint test strength (MAJOR) → PASS (mocking lens 7/7, 0 findings):
  test now asserts new person_uid in bound params + ops.consultation
  repoint test added.

**Round-2 residual "failures" — ACCEPTED as non-defects:**

1. split-correctness Claim 4 ("PersonIdentifier rows not copied") —
   the reviewer itself states "This is a documented design choice, not a
   code bug." Identifiers (phone/email) carry a global UNIQUE(kind,value)
   constraint, so they stay on the surviving person. A re-pull of a
   non-surviving patient is recaptured via ENG-309's Tier-0 source-link
   recapture (the source_link was repointed to the new person), NOT via
   identifier lookup — so no duplicate, no re-merge. The "design
   assumption" the reviewer flagged as unverified IS satisfied by
   ENG-309 (already merged). My review claim was worded "copied"; the
   correct behavior is "not copied". No rework.

2. audit-completeness Check 3 (audit `extra` has 2 more fields than the
   example contract) — the worker ADDED `interaction_events_moved` +
   `consultations_moved` counts. Reviewer: "these are counts (not PHI),
   no privacy violation." A richer audit trail than specified — an
   improvement, not a contract breach. No rework.

**Known limitation (documented, not blocking):**
- `needs_manual_review` overcounts `ops.followup_task` (counts all of
  the surviving person's tasks, not just bucket-ambiguous ones). This
  inflates the operator-facing manual-review metric — over-flagging is
  safe (operator triages), under-flagging would not be. Acceptable for
  a v1 cleanup script. Could tighten in a follow-up if the count proves
  noisy in practice.

**Decision:** ACCEPT round-2 and merge. The real safety/correctness gates
(mutation paths, savepoint, dry-run no-op, bucketing, financials
untouched, no-PHI audit, mocking) all pass. `--apply` remains gated
behind explicit operator go regardless.
