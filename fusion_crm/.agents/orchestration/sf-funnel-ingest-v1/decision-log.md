# Decision Log — sf-funnel-ingest-v1

- 2026-06-09T20:20:03Z | owner | Raw rows are written ONLY on provider-side
  change. No schema rework — fix the capture loop (watermark + change-guard).
- 2026-06-09T20:20:03Z | owner | payment_summary snapshots follow the same
  rule: identical snapshot content → skip; changed → write. Accepted side
  effect: "Last snapshot" UI timestamps become last-change timestamps.
- 2026-06-09T20:20:03Z | owner | ENG-382 scope is maximal: pull EVERY missing
  SF funnel segment (conversion fields, attribution, Contact, Account,
  OpportunityHistory). Each segment is person context for the agent layer.
- 2026-06-09T20:20:03Z | orchestrator | Execution order ENG-381 → ENG-382 so
  new pullers are born watermark-first.
- 2026-06-09T20:20:03Z | orchestrator | Scope: self-execute (claude-code, this
  session) in canonical checkout. Reason: parallel Codex session holds dirty
  files in the same tree (agent_runtime, openai client, web package.json);
  git worktree isolation would not isolate the shared uncommitted state and
  ENG-381 paths are disjoint. Mirrors agent-runtime-control-plane-v1
  precedent (ENG-345). Commit separation enforced at commit time by path.
- 2026-06-09T20:20:03Z | orchestrator | Cleanup script `--apply` requires
  explicit human approval in-session; dry-run is the default and the only
  mode the worker may run unprompted.

## 2026-06-10T22:36:47Z — Scope: bugfix

Self-execute approved for ENG-384 via `--workspace self`.

- Linear: ENG-384 — https://linear.app/fusion-dental-implants/issue/ENG-384/extend-ingest-change-guard-to-carestack-accounting-transaction-invoice
- Prompt size: 4833 chars (under 5000-char threshold)
- Reason: Codex session holds uncommitted apps/web files in canonical checkout; ENG-384 scope (packages/ingest) is disjoint — mirrors ENG-381/382 precedent.
- Allowed scope marker: bugfix

By accepting this scope, the orchestrator certifies the work is small
enough that worktree isolation is not required.
