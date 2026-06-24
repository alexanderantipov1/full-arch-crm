# Codex cross-runtime review — ENG-562 / PR #209

You are an INDEPENDENT reviewer from a different runtime. Review the branch
`feat/identity-phone-format-dedup` (PR #209) against `origin/main`. Be
adversarial: try to find correctness bugs, contract regressions, and prod-deploy
hazards. Do not rubber-stamp.

## Context
Identity persons were duplicated because the same phone was stored in different
formats (`2015550123` vs `+12015550123`) and every identity lookup compared the
raw `value` exactly. This PR introduces a canonical `value_match_key` and
compares on it.

## Focus areas (verify each, cite file:line)
1. **Read-path correctness.** `packages/identity/repository.py` —
   `_value_or_match_key`, `find_identifier`,
   `list_candidate_persons_by_identifiers`, `find_persons_sharing_identifier`.
   Does the match-key + raw-value OR fallback ever (a) miss a match it should
   make, or (b) over-match unrelated rows (esp. when `match_key == ""`)? Check
   the empty-key guard.
2. **Choke point.** Is `IdentityRepository.add_identifier` truly the ONLY insert
   path for `identity.person_identifier`? If any path bypasses it, the key is
   not stamped. (Grep `PersonIdentifier(` / session.add.)
3. **Canonicalisation.** `packages/identity/canonical.py` — are
   `phone_match_key` / `identifier_match_key` total (never raise) for empty /
   junk / international input? Is `normalise_phone` behaviour byte-identical to
   the pre-move version (it was moved out of `service.py`)? Any caller importing
   `normalise_phone`/`normalise_email` from `service` still works (re-export)?
4. **Import cycle.** Confirm `canonical` imports neither `service` nor
   `repository`, and that `repository` importing `canonical` introduces no cycle.
5. **Migration safety.** `e2f4a6c8b0d1` — additive column + index only, nullable,
   no table rewrite/lock risk on a ~150k-row prod table? Single alembic head?
   Down-revision correct? No heavy backfill on the deploy path?
6. **Match-key vs global UNIQUE(kind,value).** Confirm this change does NOT alter
   the unique constraint and does NOT regress household sharing (same phone,
   different person/name) — i.e. it never auto-merges households.
7. **Backfill script.** `infra/scripts/backfill_phone_match_key.py` —
   idempotent, batched, dry-run default, no PHI in logs, resumable.
8. **PHI/logging invariants.** No phone/email/name values written to logs.

## Output
A markdown report with: BLOCKERS (must fix before merge), NON-BLOCKING
follow-ups, and a final verdict (APPROVE / REQUEST CHANGES). Per CLAUDE.md,
missing authn/authz is NOT a blocker in this single-operator phase.
