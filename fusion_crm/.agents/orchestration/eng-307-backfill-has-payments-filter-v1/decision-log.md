# Decision Log — ENG-307

## 2026-05-31 — Mission opened (small follow-up to ENG-305)

ENG-305 landed the data path and ENG-306 landed the UI. Both merged.
ENG-307 closes the operator-readiness gap: the prod tenant has 55,677
linked CareStack patients but only ~1803 with payment activity, so the
current `--max-patients`-only resolver in `backfill_payment_summary.py`
would miss most of the active set.

**Decisions:**

1. Hybrid execution mirrors ENG-305 / ENG-306: 1-agent Workflow pre-flight
   (sufficient — the scope is narrow) → single worker via launcher in
   worktree → 2-lens Workflow adversarial review (correctness + mocking).
2. Mission archived: `.agents/orchestration/eng-306-person-card-financials-v1/`
   + runtime `~/.fusion-agent-orchestrator/c2db50910d08/eng-306-person-card-financials-v1/`.
3. No real CareStack backfill until this lands AND operator gives
   explicit go on the window (CareStack throttled ~24 h once before).
