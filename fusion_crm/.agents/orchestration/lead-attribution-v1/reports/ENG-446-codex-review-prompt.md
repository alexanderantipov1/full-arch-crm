Cross-runtime CODE review (read-only) of the Lead Source Attribution epic, PR #156.

You are in a git worktree on branch `eng-447-lead-attribution-v1`. Review the full diff vs main:

    git diff origin/main...HEAD --stat
    git diff origin/main...HEAD

This is a contract_change (adds the canonical `attribution` schema). Focus your review on:

1. **Migration safety.** The branch merges main and adds Alembic merge revision `4c1fe01ca169` (Revises `b69bce1e2195` + `f6a7b8c9d0e1`). Confirm: single head, no edited-after-merge migrations, the merge is a true no-op, attribution migration `f6a7b8c9d0e1` self-creates its schema (CREATE SCHEMA IF NOT EXISTS) and is idempotent. Flag any down_revision or chain issues.

2. **Block D backend (ENG-450)** — the new `GET /attribution/analytics/tree` + `/leads` and their service/repo. Check:
   - SQL correctness of `count_leads_by_chain` / `count_needs_review` / `map_persons_to_chain` / `list_lead_attributions_for_node` (GROUP BY, NULL-bucket handling via `== None` → IS NULL, needs_review exclusion via `_resolved_only`, tenant scoping via `for_tenant`).
   - Drill-down slug→id resolution + the `__none__` sentinel (unknown slug → id=None with match=True → empty result, NOT unconstrained).
   - Domain separation: attribution must NOT import ops/interaction MODELS; cash + consults are passed per-person by the route (`OpsService.consult_counts_by_person`, `InteractionService.collected_by_person`). Confirm no cross-domain model imports in packages/attribution.
   - Async/greenlet safety on identity enrichment (`list_by_ids` identifiers access).

3. **Invariants (root CLAUDE.md).** No business logic in routes; route→service→repo layering; UUID PKs; tenant scoping; append-only audit untouched; no PHI in logs.

4. **Frontend** — Zod schema mirrors the Python DTOs exactly; the drill-down `key.split("/")` → vendor/channel/campaign slugs matches the backend node `key` format; no MSW zombie mocks added.

Real-data context (already verified by the author): resolver ran on 62,817 real leads, needs_review = 0.5% for 2026 (goal met) vs 80.6% for 2025 — a pre-2026 ingestion gap (no CreatedBy.Name), tracked as ENG-453, NOT a logic bug. You do not need to re-litigate that; focus on code correctness.

Output a structured review as your FINAL message: severity-tagged findings (blocker / major / minor / nit) with file:line, then an overall verdict (APPROVE / APPROVE-WITH-NITS / REQUEST-CHANGES). You are read-only — do not modify files; deliver the review as text.
