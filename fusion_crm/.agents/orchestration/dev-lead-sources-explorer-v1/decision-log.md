# Decision log — dev-lead-sources-explorer-v1

- 2026-06-11T01:18:00Z | orchestrator | ENG-391 self-executes in the
  canonical checkout on bundle branch `codex/eng-371-manager-answer-layer-v1`
  (not an isolated worktree): the task's paths are disjoint from the
  parallel session's uncommitted `.agents/dashboard` files, and the bundle
  branch already carries the analytics/repository code this feature builds
  on (ENG-379/382 not yet merged to main). Mirrors the ENG-381/382/384
  precedent recorded in sf-funnel-ingest-v1.
- 2026-06-11T01:18:00Z | orchestrator | Funnel buckets fixed as:
  scheduled = ConsultationStatus.SCHEDULED, attended = COMPLETED;
  NO_SHOW / CANCELLED / RESCHEDULED excluded from both. Chair/treatment
  stage and per-clinic breakdown explicitly deferred.
- 2026-06-12T02:00:00Z | orchestrator | ENG-408 self-executes in the canonical
  checkout on a fresh branch from main (bundle PR #124 merged, main now carries
  the explorer + payments code). Scope: apps/web payments page, apps/api
  dashboard router, packages/ops + packages/interaction read paths. Mirrors the
  ENG-398/399 same-page precedent. Scope: feature (page-local, read-only
  aggregation, no migration).
