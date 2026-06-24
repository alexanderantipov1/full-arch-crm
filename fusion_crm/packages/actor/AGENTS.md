# AGENTS.md — `packages/actor`

The authoritative instructions for this area live in `CLAUDE.md`.

For Codex sessions:

- Read `packages/actor/CLAUDE.md` before editing.
- Also apply the repo-root `AGENTS.md` and `CLAUDE.md`, plus
  `packages/CLAUDE.md` (cross-package import matrix).
- If rules differ, follow the stricter one.
- Treat references to `CLAUDE.md` inside this area as equally binding
  for Codex work.

**Note for Codex review:** the `actor_type` CHECK includes all 4 values
(`human`, `ai`, `system`, `external_service`) from M1 day one, even though
M1 actively uses only `human` + `external_service`. Same rationale as
`auth.*.subject_type` — Postgres ALTER CHECK is expensive; widening the
constraint preemptively is cheaper than rewriting it later.
