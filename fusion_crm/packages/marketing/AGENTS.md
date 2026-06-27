# AGENTS.md — `packages/marketing`

The authoritative instructions for this area live in `CLAUDE.md`.

For Codex sessions:

- Read `packages/marketing/CLAUDE.md` before editing.
- Also apply the repo-root `AGENTS.md` and `CLAUDE.md`, plus
  `packages/CLAUDE.md` (cross-package import matrix).
- If rules differ, follow the stricter one.

**Note for Codex review:** this schema holds aggregate, non-PHI ad-spend
data only. Review should confirm:

1. No person/PHI fields creep into `ad_campaign` / `ad_metric_daily`.
2. Upserts stay idempotent on the documented natural keys.
3. The `provider` CHECK constraint stays in lock-step between the model and
   the migration.
4. Services/repositories never commit.
