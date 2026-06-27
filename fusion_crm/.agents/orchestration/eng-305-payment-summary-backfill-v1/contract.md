# Contract — ENG-305 (data-only)

- `CareStackPaymentSummaryIngestService` gains:
  - private `_sweep_patient_ids(tenant_id, patient_ids, *, sleep_seconds,
    max_retries, backoff_base_seconds, sleep_fn, commit_every, commit)` —
    the shared per-patient loop with batch commits and failure isolation;
  - public `import_payment_summary_for_patients(tenant_id, patient_ids, *,
    sleep_seconds=0.5, max_retries=5, backoff_base_seconds=1.0,
    sleep=None, commit_every=50, commit=None)` for targeted + live use.
- `pull_all_payment_summaries` delegates to `_sweep_patient_ids` over all
  linked CareStack patients; signature unchanged from caller's view.
- `CareStackAccountingTransactionImportOut.patient_ids: list[str]`
  exposes patient_ids whose accounting rows were genuinely imported this pull.
- `apps/worker/jobs/ingest_scheduled.py` calls
  `import_payment_summary_for_patients(..., commit=session.commit)` after each
  accounting pull, bounded by `accounting_transactions.patient_ids`.
- `infra/scripts/backfill_payment_summary.py` runs the historical sweep as a
  detached background process. NOT exposed via HTTP.
- Tests mock the CareStack client; the live API is never hit from CI/dev.

Hard limits (from past incidents):
- Throttle ≥ 0.5s/patient; exponential backoff on 429/5xx already in
  `_fetch_summary_with_backoff`.
- CareStack blocked this account ~24h once — abort on sustained 429.
- Backfill runs as a background script, NOT through the HTTP backfill endpoint
  (Next proxy 30s timeout → orphaned long-run incident already burned).
- Commits batched (every 50 patients by default) — no 15-minute transaction.
- No PHI in logs: patient_id + counts only.
