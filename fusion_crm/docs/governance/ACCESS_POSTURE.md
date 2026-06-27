# Access posture — single-user phase

> Operator decision. Extends the 2026-06-01 "PHI on the staff frontend"
> policy. Applies on **every environment, production included** — there is
> exactly **one user today: the doctor**, who holds full provider access.
>
> The root `CLAUDE.md` carries the compact, decision-bearing version of this
> policy (so every session sees it). This file is the full rationale and the
> authoritative reference. If the two ever diverge, this file wins and root
> `CLAUDE.md` must be updated to match.

## We are pre-access-control

Until more user roles exist, the posture is:

- **Show everything.** Staff UI, the staff-facing API, and MCP read surfaces
  MAY display any captured data — PHI/PII, verbatim provider payloads — with no
  redaction and no env gate. Do not refuse to render or env-hide a field.
- **No authn/authz gating on endpoints — read OR write.** Auth is a stub today
  (`Principal` defaults to `ANONYMOUS`, see `apps/api/CLAUDE.md`). That stub is
  the **accepted, intentional state for ALL endpoints on every environment**,
  including mutating endpoints — even ones that touch PHI routing/config. With a
  single trusted operator and no public multi-tenant surface yet, an
  unauthenticated endpoint is the documented posture, **not a defect**.
- **Access control is a later, uniform layer**, added on top when more roles
  exist (role-scoped capabilities + field-level redaction + endpoint authz),
  granting access only where needed. Build surfaces so that layer can wrap them
  later; do not pre-build redaction or per-endpoint auth now.

## For reviewers (including automated cross-runtime / Codex review)

A missing authn/authz check, or an unauthenticated mutation, is **NOT a
blocker** in this phase — it is this documented posture. Note it at most as a
*pre-multi-user / pre-public follow-up*, never as a merge blocker.

## What this does NOT relax

Three things stay enforced — they are infrastructure/structural, not "what the
doctor sees or does on screen":

1. **Logs stay PHI-free** (see root `CLAUDE.md` → Logging) — logs outlive this
   phase.
2. **The hard architectural invariants stand** — `phi.*` schema separation,
   PHI reads through `PhiService`, append-only `audit`, AI agents never touch
   the DB (services only), full-fidelity raw capture, secrets env-only.
3. **Hard-to-reverse / outward-facing actions still require confirmation**
   (push/merge/deploy/destructive ops) — "no auth gate" is about app endpoints,
   not about the agent skipping operator approval for risky operations.
