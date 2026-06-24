# Acceptance — ENG-300

- [ ] New route `apps/web/app/(staff)/project-manager/payments/docs/page.tsx`
      rendering the payments documentation with an EN ⇄ Русский toggle (default EN).
- [ ] Content module `apps/web/lib/docs/paymentsDoc.ts` with `en` + `ru` sections
      (both languages live together).
- [ ] **Docs** button next to the title on `/project-manager/payments` linking to
      `…/payments/docs` (mirror existing button style).
- [ ] Doc covers: source feed (accounting-transactions double-entry), key fields,
      the transactionCode → meaning → our kind table, derived metrics
      (Collected/Payments/Outstanding/AR-risk) with formulas, ingestion model, and
      WHY (double-entry → strict classification). Accurate per the prompt facts.
- [ ] Doc-sync rule added to `apps/web/CLAUDE.md` AND `packages/ingest/CLAUDE.md` +
      pointer comments in `_PAYMENT_CODE_TO_KIND` and the Collected aggregate.
- [ ] No PHI. Strict TS. No backend change. Verify green:
      `cd apps/web && npm run lint && npx tsc --noEmit && npm run test`.
- [ ] Report at `reports/ENG-300-worker-report.md`.
