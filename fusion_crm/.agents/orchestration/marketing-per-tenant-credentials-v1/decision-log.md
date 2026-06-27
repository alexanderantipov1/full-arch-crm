# Decision Log — Per-tenant marketing/SEO credentials

## 2026-06-17 — Mission accepted (Orchestrator)

**Handoff:** User (operator) → Orchestrator. Discovered while wiring a prod
marketing job: marketing/SEO ingest (Google Ads, Meta, GA4, GSC) reads creds
from env (`Settings.from_env()`, Phase 1/2 bootstrap), not per-tenant DB. Wrong
for multi-tenant.

**Decisions:**
1. **Do it properly now** (operator): per-tenant credentials in
   `tenant.integration_credential` (the SF/CareStack model), not env-only.
2. All four connectors (Ads + Meta + GA4 + GSC) already run in one daily pull —
   "SEO" is included; no separate SEO pull.
3. **Epic DoD includes prod**: keys must land in the **prod** DB (operator
   enters them via the prod integration UI), frontend + backend deployed to prod.
4. Keep `from_env` as a transition fallback so nothing breaks mid-migration.

**Branching:** stacked on the funnel branch `eng-481-full-funnel-v2-backend`
(PR #171) so the local dev funnel v2 stays visible during this work; rebase the
marketing branch onto `main` once #171 merges → clean marketing PRs.

**Linear:** ENG-488 (epic) → ENG-489…493 created.

**Handoff:** Orchestrator → Worker (ENG-489), claude-code in-session (worktree
launcher blocked by pre-existing " 2" junk in the tree). No commit/push without
explicit user approval.
