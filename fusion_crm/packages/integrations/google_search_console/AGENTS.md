# AGENTS.md — `packages/integrations/google_search_console`

The authoritative instructions for this area live in `CLAUDE.md`.

For Codex sessions:

- Read `packages/integrations/google_search_console/CLAUDE.md` before editing.
- Also apply the repo-root `AGENTS.md` and `CLAUDE.md`, plus
  `packages/CLAUDE.md` and `packages/integrations/CLAUDE.md`.
- If rules differ, follow the stricter one.

**Note for Codex review:** focus on:

1. Read verbs only (`sites.list` + `searchAnalytics.query`; no write endpoints).
2. Access token cached in-memory only — no plaintext on disk or in logs.
3. Credentials from env via `Settings` (GSC refresh token + Google Ads OAuth
   client), not raw `os.environ`.
4. The 401 retry path bottoms out (single refresh, then raise).
5. `searchAnalytics.query` pagination via `startRow` bottoms out (safety cap).
6. `siteUrl` is URL-encoded in the path.
