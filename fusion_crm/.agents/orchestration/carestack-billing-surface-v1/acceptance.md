# Acceptance — ENG-257 (surface partial payments)

- [ ] New Alembic revision (down_revision = current head) widens
      `interaction.event` CHECK constraints: EVENT_KINDS += `payment_recorded`,
      `payment_refunded`, `payment_reversed`; SOURCE_KINDS +=
      `carestack_accounting_transaction`. Mirrors `c1d2e3f4a5b6`; has a working
      downgrade; never edits a shipped revision.
- [ ] `packages/interaction/models.py` (EVENT_KINDS, SOURCE_KINDS),
      `schemas.py` Literals, `_KIND_VERB`, and `packages/interaction/CLAUDE.md`
      kinds table updated to match the migration EXACTLY.
- [ ] `CareStackAccountingTransactionIngestService` emits a safe
      `interaction.event` for PAYMENT folios only
      (PATIENTCREDIT/COLLECTIONCREDIT; refunds → `payment_refunded`;
      `isReversed` → `payment_reversed`), `data_class="billing"`,
      `source_kind="carestack_accounting_transaction"`. Summary/payload carry
      amount + transaction type ONLY — no clinical codes, no patient identifiers.
      Non-payment folios remain raw-only (no event).
- [ ] Dashboard treatment/payments aggregate gains `collected_total` (ledger
      payments) and `outstanding_total` (sum of latest payment-summary
      `balanceDuePatient` [+ insurance] per patient), exposed on
      `DashboardTreatmentPaymentsOut` and wired through the PM endpoint, the Zod
      schema, and the UI widget.
- [ ] Payment events render on the person operational-timeline with safe labels.
- [ ] No CareStack write path. No new schema/domain. No PHI in summaries/logs/
      dashboard responses.
- [ ] Full verify green: `make lint`, `mypy .`, `make test`,
      `cd packages/db && alembic check` (no drift after upgrade).
- [ ] Tests: emission folio→kind mapping, no-PHI assertion, reversal handling,
      dashboard aggregate (collected + outstanding), migration up/down.
- [ ] Worker report at `reports/ENG-257-surface-worker-report.md`.
