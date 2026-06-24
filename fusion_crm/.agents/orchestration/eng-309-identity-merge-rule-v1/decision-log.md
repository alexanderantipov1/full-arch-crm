# Decision Log — ENG-309

## 2026-06-01 — Mission opened (identity-merge bug, household ≠ identity)

Surfaced via the Torosyan person card. 3 CS pids merged into one
person.id, but the payloads showed two different humans (Eduard 1968 +
Gaiane 1972 in the same household). Identity resolver weighted shared
phone/address/accountId/lastName as evidence of same-person without
enforcing DOB or SSN equality as a hard veto.

**Decisions:**

1. Hard rule: DOB-mismatch OR SSN-mismatch must NEVER merge, no matter
   how many soft signals overlap. Recorded as memory entry
   `feedback_identity_merge_rule_dob_ssn`.
2. Hybrid orchestration mirrors prior tickets (305-308): 1-agent
   Workflow pre-flight (identity resolver code map) → single worker
   → 3-lens Workflow adversarial review (rule-correctness /
   audit-completeness / mocking).
3. Mission archived: `eng-308-person-carestack-origin-context-v1/`
   + runtime `~/.fusion-agent-orchestrator/c2db50910d08/eng-308-...-v1/`.
4. Un-merge script in this ticket IF audit count ≤ 50 persons; else
   filed as ENG-311 follow-up.
5. ENG-310 (per-pid names + PHI panel) is the sibling UI ticket.
   Sequential execution: 309 first, 310 after.
6. Repo PHI policy updated (`apps/web/CLAUDE.md` rule #1) +
   `feedback_phi_on_staff_frontend_allowed` memory entry.

## Pending audit-script output (post-merge)

After landing, run `audit_identity_merges.py --dry-run` against prod
tenant. If wrong-merged-person count > 50, this mission also files
ENG-311 (un-merge backfill) and operator triages from there.
