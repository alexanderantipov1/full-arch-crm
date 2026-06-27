# Decision Log — ENG-311

## 2026-06-01 — Mission opened (un-merge backfill, post-ENG-309)

ENG-309 merged (c213772) — resolver now hard-blocks DOB/SSN-mismatch
merges. Audit run this session found **3,416 wrong-merged persons**
already in prod (71% of multi-link). This mission ships the un-merge
split script to clean them.

**Decisions:**

1. Hybrid orchestration: 1-agent Workflow pre-flight (split mechanics)
   → single worker → 3-lens adversarial review (split-correctness /
   audit-completeness / mocking).
2. Mission archived: `eng-309-identity-merge-rule-v1/` + runtime.
3. Split algorithm: group by (dob, ssn); largest bucket stays;
   others → new person.id. Legitimate same-person multi-pid preserved.
4. `--apply` opt-in; fleet split is a SEPARATE operator go after merge.
   Dry-run + single `--person-uid 5758e85c-...` (Torosyan) verified
   first.
5. No new migration — reuses existing identity tables + audit.access_log.
6. After this lands + fleet apply: re-run audit → expect ~0 remaining.
