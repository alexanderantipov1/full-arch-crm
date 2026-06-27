# Lessons — lead-attribution-v1 (ENG-446)

## Real-data resolver run (2026-06-15): needs_review is a DATA gap, not a logic bug

Ran `resolve_attribution.py --all` against the dev DB (real data): **62,817 leads
resolved, 0 skipped**. Overall `needs_review = 62.7%` — far from the ~0% goal at
first glance. But the per-year split is decisive:

| Lead year | Leads | needs_review | % |
| --- | --- | --- | --- |
| 2026 | 14,029 | 71 | **0.5%** ✅ |
| 2025 | 48,788 | 39,324 | **80.6%** ❌ |

**Diagnosis:** every needs_review lead has `created_by_name = NULL`. 2026 leads
got the full-fidelity ingestion + `CreatedBy.Name` backfill (ENG-425/430), so the
waterfall resolves them (utm → phone → manual/created_by) to ~0% unknown. 2025
(and earlier) leads were ingested before `CreatedBy.Name` capture and mostly lack
utm, so they fall through to needs_review.

**Conclusion:** the attribution system works as designed; the "0% unknown" goal
is met for the period with complete ingestion. Closing the gap is an INGESTION
backfill (re-pull / backfill `CreatedBy.Name` + utm for 2025 and earlier), then
re-run the resolver — NOT a Block D code change. Tracked as a follow-up.

**Resolution signal mix (all 62,817):** needs_review 62.7%, digital 29.6%,
phone 7.1%, manual 0.4%, campaign 0.1%, created_by/reactivation <0.1%.

## Verify on real data before declaring "0% unknown"

Unit tests + the fresh-DB smoke all passed and looked complete, but only the
real-data run surfaced that the goal is data-bound (per-year coverage), not
code-bound. Reinforces feedback_verify_with_real_data_before_merge.
