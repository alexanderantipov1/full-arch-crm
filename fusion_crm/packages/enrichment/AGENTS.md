# AGENTS.md — `packages/enrichment`

The authoritative instructions for this area live in `CLAUDE.md`.

For Codex sessions:

- Read `packages/enrichment/CLAUDE.md` before editing anything here.
- Also apply the repo-root `CLAUDE.md` and `packages/CLAUDE.md`.
- If rules differ, follow the stricter one.
- Treat references to `CLAUDE.md` inside this area as equally binding
  for Codex work.

Non-negotiable reminders:

- One service (`EnrichmentService`) is the public surface. The models
  and repository are private — no imports of them outside this
  directory.
- The repository and the service never commit and never roll back —
  they only flush. The caller boundary owns the unit of work.
- Every annotation write also writes an `audit.access_log` row in the
  same unit of work. The annotation `value` (free text / PII) never
  enters the audit `extra`.
- `record_annotation` is append-friendly (NOT unique by key). Use
  `latest_per_key` for current-value reads.
