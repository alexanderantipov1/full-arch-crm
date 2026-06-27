# AGENTS.md — `packages/integrations/google_ads`

The authoritative instructions for this area live in `CLAUDE.md`.

For Codex sessions:

- Read `packages/integrations/google_ads/CLAUDE.md` before editing.
- Also apply the repo-root `AGENTS.md` and `CLAUDE.md`, plus
  `packages/CLAUDE.md` (cross-package import matrix) and
  `packages/integrations/CLAUDE.md`.
- If rules differ, follow the stricter one.

**Note for Codex review:** focus on:

1. Read verbs only (no mutate endpoints leaking in).
2. Access token cached in-memory only — no plaintext on disk or in logs.
3. Credentials sourced from env via `Settings`, not raw `os.environ`.
4. The 401 retry path bottoms out (single refresh, then raise).
5. `cost_micros` → spend conversion happens in the ingest mapper, not the
   client (the client returns verbatim rows).
