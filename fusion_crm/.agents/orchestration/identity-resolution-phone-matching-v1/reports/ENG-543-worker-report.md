# ENG-543 — Worker Report

**Task:** B — Matcher: reversed-name compat + phone-strong / empty-lead auto-accept
**Parent epic:** ENG-541 · **Class:** CONTRACT_CHANGE (identity-resolution policy, ENG-185)
**Branch:** `eng-543-eng-543` · **Worktree:** `worktrees/ENG-543` (isolated, NOT canonical)
**Runtime:** claude-code · **Date:** 2026-06-20

---

## Summary

Fixed the root cause where `_names_compatible` compared whole name **fields**
instead of **words**. A lead with `family='Newton Patrick'` (given empty, no
email) tokenized to `{'newton patrick'}` and never intersected the existing
person `Patrick Newton` → name_compatible=false → the `phone_name` (0.95) rule
was skipped → fell through to `phone_only_ambiguous` (0.70) → duplicate person
+ open candidate.

Implemented **Option B (subset match)** exactly as the approved design: a new
`_name_words` helper explodes given/family/display into ONE lowercased word-set
per side; `_names_compatible` returns compatible when either side has no words
(absence ≠ conflict) or when the **shorter word-set is a subset of the longer**.
No new tier, no change to the tier-ladder shape, DOB/SSN hard veto and
`_FORBIDDEN_EVIDENCE_KEYS` untouched.

---

## Changed files

| File | Change |
|------|--------|
| `packages/identity/service.py` | Added `_NAME_WORD_SPLIT` regex + `_name_words(...)` helper; rewrote `_names_compatible` to word-level subset semantics; removed now-unused `_normalise_name_token`. |
| `tests/identity/test_resolve_or_create_from_hint.py` | Added 6 cases (see below). |

The change is consumed in two places, both inside `identity`:
`_evaluate_match_policy` (ingest hint path) and `_evaluate_pair_for_sweep`
(re-merge sweep). Both inherit the improved subset semantics consistently. No
models, schemas, migrations, env, or cross-domain contracts touched.

## Behavior delta

- `'Newton Patrick'` ⊆ `'Patrick Newton'` → **compatible** (reversed order).
- given empty + `family='Newton Patrick'` vs `Patrick Newton` → **compatible**.
- `'John Smith'` vs `'John A Smith'` → **compatible** (middle initial subset).
- `'John Smith'` vs `'Jane Smith'` → **NOT compatible** (`jane` absent).
- A strong phone match with an incompatible name still stays **Tier-2/open**
  (no auto-merge); `auto_accept_eligible>1` still collapses to ambiguous.
- Note (intentional): `'John Smith'` vs `'John Doe'` (one shared word, both
  sides 2 words) is now **incompatible** under subset semantics, where the old
  any-token-overlap rule called it compatible. This is the designed, stricter
  behavior — a shared first name no longer overrides a differing surname.

## Tests added (mirror existing mock style)

1. `test_reversed_first_last_auto_links_no_duplicate` — `phone_name` auto-link, no dup person.
2. `test_everything_in_one_field_auto_links` — given empty, `family='Newton Patrick'`.
3. `test_empty_lead_name_and_phone_no_email_auto_links_via_phone_name`.
4. `test_phone_match_with_different_name_stays_open` — household member, stays `phone_only_ambiguous`.
5. `test_middle_name_subset_auto_links`.
6. `test_dob_veto_wins_over_phone_and_name_match` — ENG-309 veto still fires ahead of phone+name.

## Acceptance

Acceptance scenario covered by tests 1–3: the Patrick Newton lead
(phone `+19167307719`, `family='Newton Patrick'`) auto-links to the existing
person via rule `phone_name` and creates NO duplicate. (Unit-level against the
mock repo; the literal person UID `73e7523b-…` is a DB fixture value not present
in this mock-based suite — the logic path it exercises is asserted directly.)

---

## Verification (`/verify`)

| Step | Result | Notes |
|------|--------|-------|
| `make lint` (ruff) | **PASS** | All checks passed. |
| `mypy .` | **pre-existing baseline** | 62 errors in 31 files — **identical with and without this change** (verified via `git stash`). **Zero** are in `packages/identity/` or the new tests; `mypy packages/identity/service.py tests/identity/test_resolve_or_create_from_hint.py` → *Success, no issues*. All 62 live in unrelated test files (integrations/ingest/worker/api/tools) and predate ENG-543. |
| `make test` (pytest) | **identity scope PASS** | `tests/identity/` = **94/94 PASS** (incl. 6 new). Full `pytest` is env-blocked: 27 collection errors from `Settings` requiring `SECRET_KEY`/`DATABASE_URL`/`REDIS_URL` not present in this worktree — **baseline-identical** (Makefile itself documents full pytest as known-blocked, CI runs a drift subset). Full collectable run with `--continue-on-collection-errors`: env-independent failures are **identical with/without this change** (4 failed / 31 passed / 8 skipped on the affected files, all in unrelated carestack/ops/deploy code) → **zero new failures introduced**. |
| `alembic check` | **PASS** | "No new upgrade operations detected." No schema drift (no model/migration change). Run with the canonical `.env` sourced read-only for DB connectivity; `.env` not modified. |

**Verify verdict for this change:** lint + alembic clean; identity logic fully
green; no regressions anywhere in the runnable suite. The mypy/full-pytest
"failures" are pre-existing, environmental, and unrelated to ENG-543.

---

## Risks

- **Stricter compatibility** (`John Smith` vs `John Doe` now incompatible) could,
  in principle, push a previously auto-linked pair to Tier-2/open. This is the
  intended, more-conservative direction (avoiding wrong merges > avoiding
  duplicates, per `packages/identity/CLAUDE.md`) and the operator-approved
  design. No existing test depended on single-shared-token compatibility.
- **Apostrophe/punctuation splitting**: `O'Brien` splits to `{o, brien}`. Both
  sides split identically, so compatibility is preserved; only a marginal effect
  on subset cardinality. Acceptable; unicode letters are preserved (`José`).
- `_evaluate_pair_for_sweep` inherits the new semantics — desirable and
  consistent, but it slightly changes sweep auto-merge eligibility for
  reversed/packed names (now eligible). In-scope and correct per the policy.

## Do-not-merge conditions

- **Operator-only merge/deploy.** Merge to `main` auto-deploys prod + runs prod
  migration with no gate — do NOT self-merge. This PR ships as **DRAFT**.
- **Hold for Codex cross-runtime review** (CONTRACT_CHANGE to ENG-185 policy).
- Do not merge while the full pytest suite is env-blocked at the integration
  level unless the reviewer accepts the documented baseline (identity scope is
  green; no new failures).

## Needs decision

None. Work stayed within the approved design and task scope.

---

**Ready for Codex cross-review.**
