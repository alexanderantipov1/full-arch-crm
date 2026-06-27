# `apps/portal/` — Patient Portal (RESERVED — not built yet)

This directory is **intentionally empty**. The patient portal is **M11** of
the roadmap and depends on **M8 (HIPAA runtime gating)** being live first.

## When this gets built

When M11 starts, the portal lives here as a separate Next.js app, with its
own auth boundary backed by:

- `auth.portal_account` (1:1 with `identity.person`)
- Polymorphic `auth.credential(subject_type='portal_account')`
- Polymorphic `auth.session(subject_type='portal_account')`

The schema for all of the above is already designed in
[`docs/plans/2026-04-30-full-schema-v0_2.md`](../../docs/plans/2026-04-30-full-schema-v0_2.md)
§15 — no rework needed when M11 lands.

## Boundary rules

- **Staff features go to `apps/web/`, not here.** This directory is for
  patient-facing UI only.
- **PHI access** for portal users requires M8 runtime gating to be live.
  A patient can read their OWN clinical records (treatment plan, post-op
  instructions, scheduling, imaging, financing status). They cannot read
  anything else — `auth.permission_grant` enforces.
- **Audit:** every portal read of PHI lands in `audit.data_access_log`
  with `principal_id = portal_account.id` so audit reports distinguish
  portal access from staff access.

## Do NOT

- Do **not** add code to this directory until M11 is started.
- Do **not** mix staff features here. If you find yourself wanting to,
  the right move is `apps/web/`.
- Do **not** add server-side code under here that imports `phi.*` repos
  directly — same `PhiService.*` discipline as everything else.

## References

- Roadmap: [`docs/ROADMAP.md`](../../docs/ROADMAP.md) §5 Phase 11 (M11)
- Schema: [`docs/plans/2026-04-30-full-schema-v0_2.md`](../../docs/plans/2026-04-30-full-schema-v0_2.md) §15 (`auth` schema)
- Strategic context: `project_frontend_mcp_portal` memory entry (Claude Code)
- Linear: parent issue FUS-13 (M1 portal stub workstream); this directory is FUS-30
