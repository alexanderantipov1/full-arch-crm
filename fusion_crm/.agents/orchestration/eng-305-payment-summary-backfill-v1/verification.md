# Verification — ENG-305

```bash
make lint
mypy .
make test
cd packages/db && alembic check
```

Focused checks (worker performs, includes in report):

- `pytest tests/ingest/test_carestack_payment_summary_service.py -v` —
  new tests on `_sweep_patient_ids` (commit-per-batch, sweep coverage,
  throttle/backoff, failure isolation) green.
- `pytest tests/ingest/test_carestack_accounting_transaction_service.py -v` —
  new test asserts `CareStackAccountingTransactionImportOut.patient_ids`
  contains ONLY rows where `_capture_transaction` returned `"imported"`.
- `pytest tests/infra/test_backfill_payment_summary.py -v` (NEW file) —
  cap honored; injectable sleep called; CareStack mocked; logs no PHI.
- `grep -RIn 'requests\.\|httpx\|carestack_client.get_payment_summary'
  tests/` returns only mocked usages (no live URLs).

Out of band (post-merge, separate user go):

- `python3 infra/scripts/backfill_payment_summary.py --dry-run --max-patients 5`
  against real CareStack (gentle): verify shape, no 429.
- Full backfill run (~1803 × 0.5s ≈ 15 min) in background, watching for 429.
