# AGENTS.md — `packages/interaction`

Codex pointer: rules live in `CLAUDE.md` in this directory.

When reviewing changes here, the highest-stakes invariant is the
**no-PII contract** on `summary` and `payload`. Any change that adds a
field accepting names / emails / phones / DOB / addresses / clinical
text is a regression and must be rejected.
