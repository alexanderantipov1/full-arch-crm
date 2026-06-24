# Codex collaboration notes

This repository uses `AGENTS.md` as the Codex entry point and keeps
the detailed, authoritative policy in the existing `CLAUDE.md` files.

Recommended operator prompts live in:

- `.codex/commands/task.md`
- `.codex/commands/verify.md`
- `.codex/commands/reviewer.md`

Working model:

- Codex and Claude Code must obey the same repository invariants.
- Use Codex for architecture, boundary checks, and cross-area review.
- Use either agent for implementation, but keep all repository output
  in English and all user-facing conversation in Russian.

## Cross-agent collaboration

Full protocol lives in `docs/WORKFLOW.md` §10. Short version for Codex:

- **Linear is the central handoff space.** No live channel between
  Codex and Claude Code; everything is async via Linear, GitHub PRs,
  and the repo.
- **Default roles:**
  - **Claude Code** owns implementation, multi-step debugging,
    migrations, frontend code, MCP/Linear updates.
  - **Codex** owns architecture review, boundary checks, test design
    + initial test scaffolds, migration safety review, doc consistency.
- **Per-issue label** (`agent:claude` / `agent:codex` / `agent:either`)
  marks primary owner.
- **Mandatory Codex tasks** that no PR ships without:
  - Architecture review of new domain packages.
  - Migration safety review (cross-schema FK ordering, CHECK constraints,
    additive-only verification).
  - Code review on every PR.
- **Production Reviewer** can be launched when the team needs an outside
  state audit across git, Linear, GitHub PRs, CI, mission runtime files, and
  worker reports. It is read-only by default and reports state, open work,
  risks, coordination gaps, and next actions.
- **Long-form architectural decisions** go to `docs/decisions/ADR-NNNN-*.md`
  (see `docs/decisions/README.md`). Either agent may author; cite ADRs
  when your work is constrained by them.
- **Status flow on Linear:** `Backlog → Todo → In Progress → In Review → Done`.
  Comment with one-line rationale on every transition (e.g. "started: branch
  eduardk/fus-14-...", "reviewed: 3 findings on PR, see inline").
- **Code review feedback** lives on the GitHub PR; the Linear issue gets a
  pointer ("PR #42 opened, ready for arch review").
