# AGENTS.md — `packages/integrations/carestack`

The authoritative instructions for this area live in `CLAUDE.md`.

For Codex sessions:

- Read `packages/integrations/carestack/CLAUDE.md` before editing.
- Also apply the repo-root `AGENTS.md` and `CLAUDE.md`, plus
  `packages/CLAUDE.md` (cross-package import matrix) and
  `packages/integrations/CLAUDE.md` (auth class hierarchy + sync
  rules).
- If rules differ, follow the stricter one.
- Treat references to `CLAUDE.md` inside this area as equally binding
  for Codex work.

**Note for Codex review:** the password-grant flow + 401 re-issue
retry is the contract this package owes the sync layer. Architecture
review should focus on:

1. Does the client only implement read verbs (no POST/PUT/DELETE
   write helpers leaking in)?
2. Is the token cached in-memory only — no plaintext on disk, no
   plaintext in logs?
3. Are credentials sourced from env via `Settings`, not raw
   `os.environ`?
4. Does the 401 retry path bottom out (single re-issue, then raise)?
