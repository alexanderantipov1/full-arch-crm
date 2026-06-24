# Decision Log — ENG-308

## 2026-06-01 — Mission opened (identity context follow-up to ENG-306)

Operator hit confusion on the Torosyan person card
(`/persons/5758e85c-...`): "Patient since" is read as CareStack
creation date but is actually our `first_seen_at`; multi-link people
(3 CS patient_ids merged into one person) have no UI indicator
explaining the larger numbers; `defaultProviderId` never renders as a
name.

**Decisions:**

1. Hybrid orchestration mirrors ENG-305/306/307: 2-agent Workflow
   pre-flight (origin context + providers endpoint) → single worker
   in worktree → 3-lens Workflow adversarial review
   (data-correctness / no-PHI-leak / mocking).
2. Comprehensive ticket per operator request ("полноценный"):
   includes provider sync + backfill script (not just the trivial
   "First ingest" rename). Single coherent landing.
3. Mission archived: `.agents/orchestration/eng-307-backfill-has-payments-filter-v1/`
   + runtime `~/.fusion-agent-orchestrator/c2db50910d08/eng-307-backfill-has-payments-filter-v1/`.
4. Provider table placement (new vs extend existing) left to the
   worker — must be documented in the report.
5. Real provider backfill against prod CareStack is gated behind
   ENG-308 merge + a SEPARATE operator go (mirror ENG-307 pattern).
