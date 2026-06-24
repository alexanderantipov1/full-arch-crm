# AGENTS.md — `apps/web`

The authoritative instructions for this area live in `CLAUDE.md`.

For Codex sessions:

- Read `apps/web/CLAUDE.md` before editing the staff frontend.
- Also apply the repo-root `AGENTS.md` and `CLAUDE.md` and
  `apps/CLAUDE.md`.
- If rules differ, follow the stricter one.
- Treat references to `CLAUDE.md` inside this area as equally binding
  for Codex work.
- This frontend is **mock-driven** in Phase 1 (MSW handlers are the
  contract until backend lands). Do not bypass the Zod schema layer —
  every API call must be schema-parsed both ways.
- This frontend never receives PHI. Phase 1 surfaces only `ops`
  data. If a change feels like it pulls clinical content into the
  browser, stop.
