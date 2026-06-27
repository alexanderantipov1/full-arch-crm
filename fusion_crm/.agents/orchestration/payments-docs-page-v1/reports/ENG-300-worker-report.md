# Report — ENG-300 Payments docs page (EN/RU) + Docs button + doc-sync rule

- **Task:** ENG-300 — Payments docs page (EN/RU) + Docs button + doc-sync rule
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-300
- **Role / agent:** orchestrator-executed (self, in-checkout) / claude-code
- **Branch / worktree:** main checkout (no worktree — see decision-log; unrelated
  WIP in the base tree)
- **Scope:** docs (frontend page + content + CLAUDE.md rules + pointer comments + test)

## Touched files (ENG-300 only)
- `apps/web/lib/docs/paymentsDoc.ts` (new) — bilingual `paymentsDocEn` / `paymentsDocRu`
  content (source feed, fields, classification table, isReversed rule, derived
  metrics + Collected formula, ingestion model, filters, why) + maintenance note.
- `apps/web/app/(staff)/project-manager/payments/docs/page.tsx` (new) — renders the
  doc with an EN ⇄ Русский toggle (default EN), back link, maintenance callout.
- `apps/web/app/(staff)/project-manager/payments/page.tsx` — added a **Docs** button
  next to the title linking to `…/payments/docs`.
- `apps/web/tests/unit/PaymentsDocsPage.test.tsx` (new) — renders EN, toggles to RU
  and back, asserts the Collected formula + doc-sync note.
- `apps/web/CLAUDE.md` — hard rule #7 (payments doc-sync).
- `packages/ingest/CLAUDE.md` — payments doc-sync rule.
- `packages/ingest/carestack_accounting_transaction_service.py` — pointer comment at
  `_PAYMENT_CODE_TO_KIND` (comment only).
- `packages/interaction/repository.py` — pointer comment at
  `get_treatment_payment_aggregate` (comment only).

## What changed
A staff-facing documentation page now explains the full CareStack payment data flow
(what each transaction means, how we classify by transactionCode, what Collected /
Applied / Reversed / Outstanding / AR-risk mean and why), available in English and
Russian via a toggle. A written doc-sync rule binds the doc to the classification +
Collected formula so code and doc move together.

## Tests run
- `npx tsc --noEmit` — clean.
- `npm run lint` — no ESLint warnings or errors.
- `npm run test` — 12 files, 54/54 passing (incl. the new PaymentsDocsPage test).
- `python3 -m py_compile` on the two edited Python files — OK (comment-only edits).

## Verification status
Green. Acceptance items satisfied: docs route + EN/RU toggle, content from the
authoritative facts, Docs button, doc-sync rule in both CLAUDE.md files + pointer
comments, no PHI, strict TS, no backend logic change.

## Risks
- Low. Frontend doc page + comment-only backend edits. No runtime/data path change.
- The doc-sync rule is process, not enforced by CI — relies on reviewers honoring it.

## Suggested next task
- Deferred per user: ENG-286 backfill hardening (cap payment-summary + async/commit-
  per-entity) and a bounded payment-summary run to make Outstanding/AR-risk real.
- Prod deploy remains deferred (accumulate on git).

## Do-not-merge conditions
- None outstanding.
