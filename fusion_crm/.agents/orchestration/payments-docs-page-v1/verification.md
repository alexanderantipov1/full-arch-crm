# Verification — ENG-300

```bash
cd apps/web && npm run lint && npx tsc --noEmit && npm run test
```

Focused:
- `/project-manager/payments/docs` renders; default English; "Русский" button
  switches to the Russian version (same content), and back.
- The **Docs** button on `/project-manager/payments` links to the docs route.
- The transactionCode table + Collected formula in the doc match the actual code
  (`_PAYMENT_CODE_TO_KIND`, `get_treatment_payment_aggregate`).
- Doc-sync rule present in apps/web/CLAUDE.md + packages/ingest/CLAUDE.md; pointer
  comments at the classifier + aggregate.
- No PHI anywhere in the doc.
