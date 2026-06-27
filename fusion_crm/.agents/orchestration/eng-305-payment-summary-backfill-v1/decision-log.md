# Decision Log — ENG-305

## 2026-05-30 — Mission opened (strategy → orchestrator handoff)

Accepted ENG-305 from previous-session handoff comment. Investigation already
done by user, no re-derivation needed. Implementation map is explicit
(4 files + 1 new script + tests).

**Decisions:**

1. Hybrid execution: orchestrator-launcher (`launch_worker.py`) for the
   implementation worker (dashboard-visible, Linear-gated, worktree-isolated).
   Workflow used only for read-side fan-out (3 Haiku pre-flight agents
   briefing + 3 Sonnet adversarial review lenses post-implementation).
2. Single worker — files form a dependency chain (service → schema → job →
   script → tests); parallel implementation would conflict.
3. `--mode print` first → user approves the command → `--mode background`.
4. Real CareStack backfill run is OUT OF SCOPE for this ticket — separate
   explicit user go post-merge.
