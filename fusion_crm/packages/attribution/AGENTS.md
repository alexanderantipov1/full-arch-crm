# AGENTS.md — `packages/attribution`

Follow `packages/attribution/CLAUDE.md` (the authoritative rules for this
package) and the repo-root `CLAUDE.md` / `AGENTS.md` first.

Key reminders:

- Derived data, re-buildable from raw evidence; never a source of truth.
- No PHI: store field names / controlled vocabulary, never clinical values.
- `person_uid` is a plain UUID column (no `identity` import in models).
- Manual (`method='manual'`) attribution is sticky across re-resolution.
- Attribution is never written back to Salesforce (read-only pull guard-rail).
- Layering: routers/jobs → `AttributionService` → repository → DB.

See `.agents/strategy/LEAD_SOURCE_ATTRIBUTION_DESIGN.md` and epic ENG-446.
