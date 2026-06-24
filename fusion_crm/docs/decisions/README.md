# Architecture Decision Records (ADR)

Long-form, durable architectural decisions that should outlive any single
Linear ticket or PR. ADRs are the canonical place for cross-cutting,
architectural choices both agents (Claude Code, Codex) and humans need
to refer to later.

## When to write an ADR

Write an ADR when **at least one** of the following holds:

- The decision affects more than one domain or workstream.
- The decision overrides or modifies a hard architectural invariant from
  `CLAUDE.md` (the override itself is an ADR).
- The decision settles a debate that may otherwise re-litigate later.
- The decision documents WHY we chose option A over option B, with
  trade-offs that aren't obvious from the code.
- The decision is referenced by multiple Linear issues / PRs.

## When NOT to write an ADR

- **Bug fixes** — Linear comment + commit message suffices.
- **Implementation choices visible in code** — let the code speak.
- **One-off ticket-scoped decisions** — Linear comment.
- **Style / formatting** — pre-commit / lint config.

## Format

Use the template at `ADR-0000-template.md`. Each ADR has:

- **Number** — 4-digit, sequential, never renumbered. Even superseded ADRs
  keep their number.
- **Title** — kebab-case, descriptive.
- **Status** — `Proposed` / `Accepted` / `Superseded by ADR-NNNN` / `Deprecated`.
- **Date** — ISO-8601.
- **Context** — what's the situation, what constraints shape the decision.
- **Decision** — what we chose, precisely (interfaces, files, schemas).
- **Consequences** — what this enables / costs / risks.
- **Alternatives** — what we considered and rejected, with reasoning.
- **References** — Linear issues, related ADRs, source whitepapers.

## Naming

- `ADR-NNNN-short-title.md` (e.g. `ADR-0007-polymorphic-auth-credentials.md`).
- Sequential, never renumber. Skipping numbers is fine if an ADR is abandoned
  before merge.
- Superseded ADRs keep their files; mark status and link to the replacement.

## Authoring

- Either agent (Claude Code or Codex) may draft an ADR. Codex is often a
  better author for architectural ADRs; Claude Code for migration / data-flow
  ADRs.
- An ADR is `Proposed` when first opened; the user moves it to `Accepted`
  by merging the PR with explicit approval.
- Both agents must cite the relevant ADR(s) when their work is constrained
  by one.

## Index

When the ADR set grows beyond a few entries, list them here with status:

| # | Title | Status |
|---|---|---|
| (none yet) | | |

(First real ADR will appear here when we have one to record.)
