# ENG-543 Codex Cross-Review

**Verdict: PASS** (captured from the Codex reviewer log — the reviewer ran in a
read-only sandbox and could not write this file itself; orchestrator persisted it.)

Reviewer: Codex (gpt-5.5, read-only worktree), PR #193, branch `eng-543-eng-543`.

## Findings

1. **PASS** — `_names_compatible` implements the approved word-level subset match.
   `packages/identity/service.py` adds `_name_words(...)`, lowercases and splits
   given/family/display on whitespace + punctuation into one word-set per side.
   Compatible when either side has no words, otherwise when the smaller set is a
   subset of the larger. Covers `Newton Patrick` vs `Patrick Newton`; rejects
   `John Smith` vs `Jane Smith`.
2. **PASS** — no new tier; tier ladder shape unchanged. `email_phone_name` /
   `phone_name` / `email_name` / Tier-2 ambiguous / fallback intact. Strong phone +
   incompatible names still falls to `phone_only_ambiguous`; `auto_accept_eligible > 1`
   stays ambiguous.
3. **PASS** — DOB/SSN hard veto still wins before tier rules. `_evaluate_match_policy`
   filters via `_has_hard_identity_conflict(...)` first; the new DOB-veto test confirms
   phone+compatible-name does NOT auto-accept on DOB conflict.
4. **PASS** — PHI/evidence guard intact. `_FORBIDDEN_EVIDENCE_KEYS` unchanged;
   `add_match_candidate` still rejects forbidden keys. New evidence/conflicts are
   boolean/count-only; no DOB/SSN/name/PHI in candidate evidence or logs.
5. **PASS** — tests cover reversed name, all-in-one-field, name+phone/no-email via
   `phone_name`, different-name same-phone stays open, middle-name subset, DOB veto
   over phone+name. PR CI: `Lint + typecheck + tests` passing.

## Blockers
None for code/design.

## Risks
No new over-merge risk beyond the operator-approved subset behavior. Implementation
stays conservative for true name disagreement and does NOT rely on phone being
globally unique. No idempotency or audit-ordering regression found.

## Do-not-merge conditions
- Operator-only merge/deploy (merge to main = unattended prod deploy + migration).
- Keep PR #193 draft until operator approves.
