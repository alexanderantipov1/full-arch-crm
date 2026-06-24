# Decision Log — ENG-312

- 2026-06-02T03:00Z | Operator chose ENG-312 as the next hybrid mission (commit+push of
  ENG-311 artifacts done first: commit 7a2836d).
- 2026-06-02T03:00Z | Backfill policy = **write-once / set-where-NULL**, mirroring the
  resolver's `_maybe_backfill_demographic` ("never overwrite"). Since dob/ssn are globally
  NULL now, this fully populates while respecting the existing invariant. Authoritative
  overwrite was rejected (would fight the resolver's non-overwrite contract).
- 2026-06-02T03:00Z | Placeholder DOB `1900-01-01` is skipped (not written) to avoid
  populating junk that would itself trip the veto. Counted as skipped_placeholder_dob.
- 2026-06-02T03:00Z | Multi-pid disagreement (post-ENG-311 should be impossible) → skip +
  needs_manual_review, never guess. Surfaces any wrong-merge that slipped the un-merge.
- 2026-06-02T03:00Z | Run as a hybrid WORKER in an isolated worktree (code task), not
  self-execute. Launch via launch_worker.py --mode print, operator-approved, then detached.
