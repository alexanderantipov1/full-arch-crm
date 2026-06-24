# AGENTS.md — `packages/integrations/meta_ads`

The authoritative instructions for this area live in `CLAUDE.md`.

For Codex sessions:

- Read `packages/integrations/meta_ads/CLAUDE.md` before editing.
- Also apply the repo-root `AGENTS.md` and `CLAUDE.md`, plus
  `packages/CLAUDE.md` and `packages/integrations/CLAUDE.md`.
- If rules differ, follow the stricter one.

**Note for Codex review:** focus on:

1. Read verbs only (no campaign mutate endpoints leaking in).
2. Token read from env via `Settings`, never logged.
3. `paging.next` pagination bottoms out (safety cap).
4. The `fb_exchange_token` helper is NOT on the read path (the token is a
   non-expiring system-user token).
5. spend (string) + actions (list) parsing happens in the ingest mapper, not
   the client (the client returns verbatim rows).
