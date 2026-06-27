# Decision Log — lead-attribution-v1 (ENG-446)

## 2026-06-15 — Integration strategy: Sync → D → single PR (A–D)
Owner decision. Blocks A/B/C are committed in worktree but not PR'd; main advanced
25 commits (ENG-425 ingestion + ENG-433 messenger + ENG-439 enrichment merged).
Sync the branch first (de-risk the alembic sibling + 3 additive conflicts), then
build Block D on the fresh base, then one PR for the whole epic.

## 2026-06-15 — Alembic sibling resolved by merge revision
attribution `f6a7b8c9d0e1` (down d5e6f7a8b9c0) and main head `b69bce1e2195` were
two heads after merging main. Created merge revision `4c1fe01ca169`
(Revises b69bce1e2195, f6a7b8c9d0e1). Verified on a fresh DB (attr_verify):
init-schemas.sql + `alembic upgrade head` walks the full chain through both
branches and converges; attribution tables created. The "alembic blocker" is
confirmed a local multi-branch-DB artifact, not a real chain break.

## 2026-06-15 — Block D design: new attribution-tree endpoint (mirror explorer)
Owner decision. ENG-450's literal acceptance mentions a `dimension` param on the
funnel API, but the goal is to replace the dashboard "unknown" bucket with the
resolved chain breakdown + drill-down + explicit needs_review. Chosen approach:
a NEW `GET /attribution/analytics/tree` (+ `/leads` drill-down) that mirrors the
proven lead-sources explorer (`ops.get_lead_source_tree`) but sources its
hierarchy from `attribution.lead_attribution` + `source_node` instead of raw utm.
Rationale: does not touch the hot Event-based funnel SQL (lower regression risk),
reuses the proven consult/payment-by-person aggregation, and natively provides
hierarchical drill-down across every chain level (vendor→…→form + agent axis)
with a needs_review count. The funnel-`dimension` variant is explicitly NOT built;
the tree is a superset for the stated goal. Recorded as a deliberate divergence
from the literal ticket wording.

## 2026-06-16T00:04:30Z — Scope: docs

Self-execute approved for ENG-446 via `--workspace self`.

- Linear: ENG-446 — https://linear.app/fusion-dental-implants/issue/ENG-446
- Prompt size: 3757 chars (under 5000-char threshold)
- Reason: Contract_change gate: Codex cross-runtime review of attribution epic A-D before merge.
- Allowed scope marker: docs

By accepting this scope, the orchestrator certifies the work is small
enough that worktree isolation is not required.
