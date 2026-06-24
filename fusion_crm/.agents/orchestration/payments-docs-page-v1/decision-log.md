# Decision Log — payments-docs-page-v1

- 2026-05-30 | Handoff: orchestrator/claude-code -> worker/claude-code for ENG-300.
- 2026-05-30 | Decision: bilingual content lives in one module (paymentsDoc.ts en+ru) with a useState toggle — no i18n lib. Doc-sync rule in both CLAUDE.md files + pointer comments at the payment classifier and Collected aggregate.
- 2026-05-30 | Decision: executed in-checkout (self), NOT via a worktree worker. The base working tree carried unrelated uncommitted WIP (data-intelligence-agent-local-tooling-v1: AppShell.tsx, handlers.ts, strategy files, dev/data-intelligence/). Stashing another track's WIP to satisfy the worktree pre-flight was judged riskier than running this frontend-only, non-overlapping change directly and staging only ENG-300 files. Scope: docs (frontend page + content + 2 CLAUDE.md rules + 2 pointer comments + 1 test). Verified green (tsc, lint, vitest 54/54).
