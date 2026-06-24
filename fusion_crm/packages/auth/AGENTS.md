# AGENTS.md — `packages/auth`

The authoritative instructions for this area live in `CLAUDE.md`.

For Codex sessions:

- Read `packages/auth/CLAUDE.md` before editing.
- Also apply the repo-root `AGENTS.md` and `CLAUDE.md`, plus
  `packages/CLAUDE.md` (cross-package import matrix).
- If rules differ, follow the stricter one.
- Treat references to `CLAUDE.md` inside this area as equally binding
  for Codex work.

**Notes for Codex review:**

- `auth.credential.subject_type` and `auth.session.subject_type` CHECK
  include both `actor` and `portal_account` from M1 day one. Per the
  decision recorded on Linear FUS-32: Postgres ALTER CHECK is expensive,
  so widening preemptively is cheaper than rewriting in M11.
- `auth.api_key.actor_id` FK to `actor.actor.id` uses `ondelete=RESTRICT`
  — deleting an actor that has API keys raises rather than silently
  invalidates them.
- Partial unique on `credential` and partial indexes on `session` use
  `postgresql_where` per Codex's FUS-32 review prep.
- argon2-cffi is the password hasher; bearer tokens use sha256 (high-
  entropy plaintext makes a slow hash unnecessary).
