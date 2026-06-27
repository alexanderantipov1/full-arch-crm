# Decision Log — ENG-306

## 2026-05-31 — Mission opened (post-ENG-305)

ENG-305 (data path) merged at `50da948` + orchestrator follow-up `67c22ff`,
pushed to origin/main. Per-tenant linked-patient population revealed as
55,677 (vs ~1803 with payments), prompting separate ticket ENG-307 to add a
`--only-with-payments` filter to the backfill script before any real
CareStack sweep.

**Decisions:**

1. ENG-307 filed in Backlog (Medium); ENG-306 starts in parallel without
   waiting for ENG-307 — UI can render the empty state (`"—"`) for patients
   whose snapshot has not arrived yet.
2. Hybrid execution mirrors ENG-305: Workflow pre-flight (3 Haiku) →
   single worker via launcher in worktree → Workflow adversarial review
   (3 Sonnet lenses).
3. Mission archived: `.agents/orchestration/eng-305-payment-summary-backfill-v1/`
   + runtime `~/.fusion-agent-orchestrator/c2db50910d08/eng-305-payment-summary-backfill-v1/`.
4. No real CareStack backfill until ENG-307 lands AND operator gives
   explicit go on the window.
