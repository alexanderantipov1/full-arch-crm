# AGENTS.md — `packages/integrations`

The authoritative instructions for this area live in `CLAUDE.md`.

For Codex sessions:

- Read `packages/integrations/CLAUDE.md` before editing.
- Also apply the repo-root `AGENTS.md` and `CLAUDE.md`, plus
  `packages/CLAUDE.md` (cross-package import matrix).
- If rules differ, follow the stricter one.
- Treat references to `CLAUDE.md` inside this area as equally binding
  for Codex work.

**Note for Codex review:** the auth class hierarchy (`PKCEOAuth` /
`StandardOAuth2` / `PasswordGrantAuth`) and `BaseProviderClient` Protocol
in `base.py` are the contract that all provider subpackages must implement.
Architecture review should focus on:

1. Does the auth abstraction support all three target providers (SF / HubSpot / CareStack) without leaks?
2. Does `EncryptedString` round-trip safely on null + empty + binary-content?
3. Do repository methods respect "no commit" rule?
4. Is `PhiService.upsert(...)` discipline reflected in CLAUDE.md (no `phi.*` import here)?
