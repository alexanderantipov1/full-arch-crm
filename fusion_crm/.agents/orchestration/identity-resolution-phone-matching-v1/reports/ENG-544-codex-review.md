# ENG-544 Codex Cross-Review

**Verdict: CHANGES-REQUESTED** — LIVE pass (315 merges) is NOT safe to run yet.
(Captured from the Codex reviewer log; reviewer ran read-only and could not write
this file — orchestrator persisted it.) PR #196, branch `eng-544-eng-544`.

## Findings (1–6)

1. **POLICY REUSE — PASS.** `replay_open_match_candidate` reconstructs `MatchHintIn`
   and calls the existing `_evaluate_match_policy`; matching is not re-implemented.
2. **CONSERVATISM — PASS.** `would_merge` only on a single Tier-1 auto-accept that
   targets exactly the recorded candidate person; ambiguity / name conflict / a
   different target stay open.
3. **LIVE-PASS SAFETY — CHANGES REQUESTED.** `packages/identity/service.py:~1776`
   has no guard that `source_person_uid` was already retired via
   `merge_event.merged_person_uid`. If one source has multiple open candidates in a
   page, row 1 merges source → survivor A, then a later row re-merges the same
   tombstone source → survivor B. No unique guard on `merged_person_uid`.
4. **IDEMPOTENCY — CHANGES REQUESTED.** Cursor paging is stable, but the same-source
   multi-candidate case makes the live pass non-idempotent by merge topology.
5. **AUDIT/PHI/LOGS — CHANGES REQUESTED.** `MatchReplayDecisionOut` includes
   `source_display_name` / `candidate_display_name`, and the CLI prints the whole
   JSON result → names reach stdout/runtime artifacts. Root `CLAUDE.md` forbids
   names in logs.
6. **SCHEMA/ENV/MIGRATION — PASS.** No `.env*` / migration / shipped-revision /
   deploy changes; ENG-341 unique constraint untouched.

## Required fixes (do-not-merge until done)
- Guard the live merge against an already-retired source (skip if
  `source_person_uid` is a `merge_event.merged_person_uid`); collapse multiple open
  candidates for the same source so a tombstone is never re-merged. Add a regression
  test for same-source-multi-candidate.
- Remove `display_name` fields from the replay DTO / job output / CLI print — use
  `person_uid`s only (no names in logs).
- Re-run focused verification.

Operator sign-off still required before any `--live` / `dry_run=False`.
