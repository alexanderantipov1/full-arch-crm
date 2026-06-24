# Development Workflow — Fusion CRM

> **Status:** living document, v0.1 (2026-04-30).
> **Update rule:** any time reality contradicts this doc, change the doc in
> the same commit as the code. Drift is the failure mode; rewrites are not.

This doc captures **how we build**, not **what we build**. For "what" see
[ROADMAP.md](./ROADMAP.md) and the two whitepapers in repo root.

For a one-page **operator-facing** summary — the two environments
(local vs production), who needs permission for what, the local-deploy signal,
parallel-agent isolation, and where secrets live — see
[DEV_WORKFLOW.md](./DEV_WORKFLOW.md). That page indexes back into this doc for
the engineering loop and into the parallel-work / deployment policies for the
deep rules.

The system is built across **four parallel workstreams** (backend phases,
operator frontend, MCP server, future patient portal — see ROADMAP §4).
The development loop below applies to all four; design decisions in any
workstream must consider impact on the others.

---

## 0. Why this exists

The system is being built by one founder/dev with AI-assisted code generation.
That changes the cost balance:

- **Cheap:** writing code, refactoring within a session, generating boilerplate.
- **Expensive:** carrying mental state of "to be restructured later" across
  weeks; rediscovering deferred decisions; debugging emergent inconsistencies
  from partial designs.

Therefore the workflow is **design-heavy, iteration-light**. We invest in
documentation up-front so future passes don't need to rebuild context.

---

## 1. Languages

- **Conversation with the user:** Russian.
- **Everything in the repo:** English — code, identifiers, comments,
  docstrings, READMEs, CLAUDE.md, log keys, error messages, commit messages,
  API field names, doc files including this one.

If the user pastes Russian text destined for the codebase, translate unless
explicitly told to keep it.

---

## 2. The development loop

For every non-trivial change, follow this sequence. Skipping steps is the
shortcut that costs us a week later.

```
                ┌──────────────┐
   user ask →   │ 1. Restate   │
                └──────┬───────┘
                       ↓
                ┌──────────────┐
                │ 2. Read      │   sub-CLAUDE.md, CATALOG, whitepapers,
                │    context   │   memory entries that match the topic
                └──────┬───────┘
                       ↓
                ┌──────────────┐
                │ 3. Propose   │   write a plan to chat: files touched,
                │    plan      │   invariants applied, risks flagged
                └──────┬───────┘
                       ↓                    ┌─ user revises ─→ back to 3
                ┌──────────────┐
                │ 4. Wait for  │   no code until "делай" / explicit yes
                │    approval  │
                └──────┬───────┘
                       ↓
                ┌──────────────┐
                │ 5. Execute   │   small commits is fine; long-lived branch
                │    in steps  │   is fine; never half-finished commits
                └──────┬───────┘
                       ↓
                ┌──────────────┐
                │ 6. Verify    │   run the verify suite (lint, types,
                │              │   tests, alembic drift)
                └──────┬───────┘
                       ↓
                ┌──────────────┐
                │ 7. Show diff │   never auto-commit; user explicitly asks
                │    + ask     │
                └──────────────┘
```

**Use the `task` skill** (slash command in `.claude/skills/task/`) when the
work touches more than one file or carries an architectural risk. It enforces
this loop end-to-end.

---

## 3. Design before code

Before generating any model, migration, or service, we must have:

1. **A schema design document** in `docs/plans/` or `docs/data-model/`
   describing the table(s), columns, FKs, indexes, status enums, JSONB shape,
   lifecycle. One pass — comprehensive, not "we'll add columns later".
2. **An update to `docs/data-model/CATALOG.md`** in the same commit as the
   migration. CATALOG is the live single-source-of-truth for tables and
   external-ID kinds. CI / review may block migrations that don't update it.
3. **A reference in [ROADMAP.md](./ROADMAP.md)** so the work connects to a
   strategic phase, not floating in isolation.

Skipping step 1 (writing models without a design doc) is the most common way
we end up with shape-rot. Don't.

---

## 4. Hard architectural invariants

These are repo-wide and immutable without explicit user approval. They live
also in the root `CLAUDE.md`; copy-summary here:

1. **One canonical PostgreSQL database**, ten+ schemas (current: `identity`,
   `ops`, `phi`, `audit`, `ingest`; v0.2 adds `actor`, `interaction`,
   `context`, `workflow`, `encounter`, `segmentation`, `insight`,
   `integrations`).
2. **One global entity:** `identity.person.id` is `person_uid`, referenced
   everywhere as a plain UUID column.
3. **Strict domain separation.** Cross-package imports follow the matrix in
   `packages/CLAUDE.md`. Crossings happen via **services**, not models or
   repositories.
4. **PHI is gated at the schema level.** All `phi.*` writes go through
   `PhiService` methods (not raw repos), audit row written for every access.
   *Runtime gating (`Principal.can_read_phi()`) is intentionally deferred —
   see memory `feedback_hipaa_runtime_deferred`.*
5. **No business logic in routes / jobs / tools.** They wire DTO → service.
6. **No DB access from AI agents.** Agents call tools (`packages/tools/*`),
   tools call services. Never the other way.
7. **Layered data flow:** `route|job|tool → service → repository → DB`. Skip
   no layer.
8. **UUID primary keys everywhere.**
9. **Append-only audit.** `audit.*` tables are never `UPDATE`d or `DELETE`d
   in code; DB role privileges enforce this in production.
10. **Secrets are env-only.** Never hardcode credentials.
11. **Migrations are immutable.** New change → new Alembic revision. Never
    edit a merged migration.
12. **Logging uses `packages.core.logging.get_logger`.** Never the stdlib
    `logging` module. **Never log PHI** — only `person_uid`, action codes,
    request id.

When a change requires breaking one of these, the workflow requires:

1. Propose the break and the reason in a design doc.
2. Update root `CLAUDE.md` and the relevant sub-`CLAUDE.md`.
3. Document the migration path for existing code.

---

## 5. Sub-area `CLAUDE.md`

Every top-level area has its own `CLAUDE.md` with rules specific to that
area. When a task touches the area, read its `CLAUDE.md` first, then the root.

| Area | Path |
|---|---|
| Root | `CLAUDE.md` |
| Apps | `apps/CLAUDE.md`, `apps/api/CLAUDE.md`, `apps/worker/CLAUDE.md` |
| Shared packages | `packages/CLAUDE.md` |
| Each domain | `packages/<domain>/CLAUDE.md` (one per domain) |
| Infra | `infra/CLAUDE.md` |

**Rule:** when adding a new top-level area, create **both** its `CLAUDE.md`
AND its `AGENTS.md` BEFORE the first feature lands there. Empty placeholders
are acceptable; missing files are not.

**Dual-doc scheme.** This repo supports two coding agents:

- **`CLAUDE.md`** holds the actual rules — architecture, invariants, conventions.
  This is the authoritative source.
- **`AGENTS.md`** is the Codex entry point. It MUST stay thin (5–12 lines): it
  binds the Codex session to read the local `CLAUDE.md`, applies the repo-root
  AGENTS.md/CLAUDE.md, and follows the stricter rule when they diverge.

When you change a CLAUDE.md rule, check whether the corresponding AGENTS.md needs
an update too — usually no (AGENTS just defers), but if a hard non-negotiable
moves, mention it in both for resilience. Never let the two files drift on
substance.

---

## 6. Definition of done — per change

A change is "done" when **all** of the following hold:

- [ ] Design doc exists (or is unchanged) and matches the implementation.
- [ ] Lint and typecheck pass.
- [ ] Tests pass; new logic has at least one happy-path and one error-path test.
- [ ] Alembic drift check is clean (`alembic check`).
- [ ] If a migration was added: `init-schemas.sql`, `DOMAIN_SCHEMAS`, and
      `registry.py` are updated.
- [ ] If a table was added/changed: `docs/data-model/CATALOG.md` is updated.
- [ ] If an architectural invariant changed: root `CLAUDE.md` is updated.
- [ ] If the strategic phase advanced or shifted: `docs/ROADMAP.md` reflects
      the new state.
- [ ] User has reviewed the diff and explicitly asked to commit.

Use the `verify` skill to run the automated parts of this checklist.

---

## 7. Living-doc discipline

These three documents are **always loaded** into engineering context and must
stay accurate or they actively mislead:

| Doc | Purpose | Update trigger |
|---|---|---|
| `CLAUDE.md` (root) + sub-`CLAUDE.md` | Hard invariants & area rules | Any architectural decision |
| `README.md` (root) | First-impression doc — what is this repo, how to run, where to look | Any time a phase/milestone shifts; any time a new app/schema lands; any time the quick-start commands change |
| `docs/data-model/CATALOG.md` | Live table + external-ID-kind catalog | Any DDL change |
| `docs/ROADMAP.md` | Where we are, where we're going | End of any phase, or any scope shift |
| `docs/WORKFLOW.md` (this) | How we build | Any process change we want to keep |

Plus the two strategic whitepapers, which are **inputs** (not edited by us):

- `AI_Native_Dental_Implant_Clinic_White_Paper_v0_1.docx` — strategic doctrine
  (two-layer model, AI agent charter, BAA strategy, DRI map, 30/60/90 plan).
- `ai_context_workflow_whitepaper.md` — data-model doctrine (5+3 core entities,
  closed-loop operating model, suggested schemas, 7-phase MVP plan).

If the system contradicts a whitepaper, **the whitepaper wins** unless the
user explicitly overrides — then we record the override in this WORKFLOW.md
or the relevant `CLAUDE.md`.

---

## 8. Deferred work — what we are not enforcing yet

The user has explicitly deferred several enforcement layers. Build the
**structure**, skip the **runtime gates**.

- Runtime PHI gating (`PhiService.can_read_phi(principal)`) — currently a
  `# TODO(hipaa-runtime)` in service code, no raise.
- Vendor BAA-eligibility wrapper before LLM / external API calls — TODO,
  no runtime denial.
- Data-class sentinel (`Public | Internal | Restricted Business | PHI`) at
  the AI-tool boundary — design the field, don't enforce.
- Per-actor capability matrix.
- Zero-retention vendor routing.

When any of these is taken off the deferred list, treat it as a Phase entry
in `docs/ROADMAP.md` and a checklist item in this WORKFLOW.md to remove from
this section.

---

## 9. Memory

Cross-session context lives in
`~/.claude/projects/<project-hash>/memory/MEMORY.md` and the linked entries.
Read them at session start when the topic matches.

Currently meaningful entries:

- `feedback_solo_dev_no_iteration` — one founder, AI-generated code,
  do-it-right-first-time bias.
- `feedback_hipaa_runtime_deferred` — HIPAA runtime gating deferred (this
  section above).
- `project_strategic_doctrine` — the AI-native Clinic OS thesis and schema gap.
- `reference_strategic_docs` — locations of whitepapers, design docs, infra.

When a workflow rule emerges that should outlast this WORKFLOW.md (e.g. a
recurring correction), save it as a `feedback_*` memory in addition to (or
instead of) editing this doc.

---

## 10. Cross-agent collaboration (Codex ↔ Claude Code)

The repo supports two coding agents working in parallel:

| Agent | Primary role |
|---|---|
| **Claude Code** | Implementation, multi-step debugging, runs migrations and tests, frontend code, MCP/Linear updates |
| **Codex** | Architecture review, boundary checks, test design + initial test scaffolds, migration safety review, doc consistency |

The **user is the merge point** — both agents propose; user reviews and merges.

### Handoff protocol — Linear-first

Linear is the central asynchronous handoff space. There is **no live channel**
between the two agents; everything is async via Linear, GitHub PRs, and the repo.

1. **Issue assignee = current owner.** Update on handoff.
2. **Status transitions are signals:** `Backlog → Todo → In Progress → In Review → Done`.
   - `Todo` — ready for an agent to pick up
   - `In Progress` — an agent is actively working on it
   - `In Review` — handed off to the other agent (or to user)
   - `Done` — merged to main
3. **Comment on every status change** with one-line rationale. Examples:
   - "Started: branch eduardk/fus-14-add-packagesactor"
   - "Done coding: PR #42, ready for arch review"
   - "Reviewed: 3 findings on PR (boundary import in service.py, missing CHECK on
     capability, prefer Tenacity for retry)"
   - "Addressed: pushed amendment, ready to merge"
4. **Per-issue agent label** (`agent:claude` / `agent:codex` / `agent:either`)
   marks primary owner. Use `agent:either` for trivial work that any agent can grab.

### Code-level handoff — GitHub PRs

- PR description = what changed and why; reference the Linear issue (`FUS-NN`).
- Codex review = inline review comments on the PR.
- Claude addresses feedback, pushes amendment, posts a comment on the Linear
  issue: "addressed in commit `abc123`, ready for re-review".
- Loop until approved → user merges → Claude moves issue to `Done`.

### Long-form architectural decisions — ADRs

Cross-cutting decisions that should outlive a single Linear ticket go to
`docs/decisions/ADR-NNNN-short-title.md`. See `docs/decisions/README.md` for
when to write one and the template format.

### What lives where (one canonical place per artifact)

| Artifact | Place |
|---|---|
| Status of work | Linear issue |
| Conversational handoff between agents | Linear comments |
| Code review feedback | GitHub PR review comments |
| Long-form architectural decisions | `docs/decisions/ADR-NNNN-*.md` |
| Cross-session memory (Claude) | `~/.claude/projects/.../memory/` |
| Codex collaboration notes | `.codex/README.md` |

### Defaults for our project

- **Phase 1 implementation issues default to `agent:claude`** unless explicitly
  re-assigned (visible in the issue label).
- **Test design + initial test scaffolds default to Codex** even when
  implementation is Claude's — Codex names the test cases, Claude makes them
  pass and expands.
- **Migration safety review (FUS-32 in Phase 1, future migration issues)
  is mandatory Codex.** No alembic migration ships without Codex review.
- **Code review on every PR is Codex.** Default; not labeled per-issue.
- **`docs/decisions/`** ADRs may be authored by either agent; both should
  cite ADRs when their work is constrained by one.

---

## 11. When in doubt

Ask the user — in Russian — before guessing. The system will run on real
patient data eventually; "let's just try it" is not an acceptable mode. A
five-minute clarification beats a one-week rebuild.
