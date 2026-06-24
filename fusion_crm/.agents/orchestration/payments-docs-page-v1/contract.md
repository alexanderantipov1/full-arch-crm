# Contract — payments-docs-page-v1

- Route `/project-manager/payments/docs` renders bilingual (EN/RU toggle) payment
  documentation from `apps/web/lib/docs/paymentsDoc.ts` (en + ru).
- `/project-manager/payments` gains a Docs button linking to it.
- Doc-sync rule in apps/web/CLAUDE.md + packages/ingest/CLAUDE.md + pointer comments
  at `_PAYMENT_CODE_TO_KIND` and `get_treatment_payment_aggregate`.
- Frontend only; no backend logic change; no PHI.
