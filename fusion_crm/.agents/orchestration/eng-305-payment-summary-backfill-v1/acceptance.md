# Acceptance — ENG-305

- [ ] `packages/ingest/carestack_payment_summary_service.py` refactor:
      private `_sweep_patient_ids(tenant_id, patient_ids, *, sleep_seconds,
      max_retries, backoff_base_seconds, sleep_fn, commit_every, commit)`
      encapsulates the per-patient loop (throttle + backoff + failure-isolation
      + batch commit). `pull_all_payment_summaries` delegates to it.
- [ ] New public `import_payment_summary_for_patients(tenant_id, patient_ids,
      *, sleep_seconds=0.5, max_retries=5, backoff_base_seconds=1.0,
      sleep=None, commit_every=50, commit=None)` dedups input and delegates to
      `_sweep_patient_ids`. Serves both targeted backfill and live wiring.
- [ ] `packages/ingest/carestack_accounting_transaction_service.py`:
      `import_recent_accounting_transactions` collects `set[str]` of patient_id
      ONLY for rows whose `_capture_transaction` returned `"imported"` (genuinely
      new, NOT re-pull dups / skipped / non-payment).
- [ ] `packages/ingest/schemas.py`: `CareStackAccountingTransactionImportOut`
      gains `patient_ids: list[str] = Field(default_factory=list)`.
- [ ] `apps/worker/jobs/ingest_scheduled.py` wiring: after each accounting pull,
      call `payment_summary_svc.import_payment_summary_for_patients(tenant_id,
      accounting_transactions.patient_ids, commit=session.commit)` under
      `if accounting_transactions.patient_ids:`. Rolling
      `import_payment_summary_snapshots(max_patients=50)` stays unless the
      worker has a concrete reason to remove it (document the call in the
      report).
- [ ] NEW `infra/scripts/backfill_payment_summary.py`: opens `async_session()`,
      lists linked CareStack patient_ids via
      `_identity_repo.list_source_links_for_dashboard` (cap default 2000),
      invokes `import_payment_summary_for_patients(..., sleep_seconds=0.5,
      commit_every=50, commit=session.commit)`. Background-runnable, monitorable
      via stdout, logs only `patient_id` + counts (no PHI). MUST NOT be wired
      to an HTTP endpoint.
- [ ] Tests (CareStack fully mocked; NO real API call in dev/CI):
  - `_sweep_patient_ids`: commit invoked per batch; sweep covers all input
    patients; throttle/backoff via injected `sleep`; failure isolation
    (one bad patient → `error_count++`, sweep continues).
  - `import_payment_summary_for_patients`: dedups input list; delegates.
  - `import_recent_accounting_transactions`: `patient_ids` contains ONLY
    imported transactions; updated / skipped / non-payment rows do NOT leak in.
  - `backfill_payment_summary.py`: cap honored; `sleep` injectable;
    no real CareStack call.
- [ ] Verify loop green: `make lint`, `mypy .`, `make test`,
      `cd packages/db && alembic check` (no migrations expected, but discipline).
- [ ] Worker report at `.agents/orchestration/current/reports/ENG-305-worker-report.md`.
- [ ] NO commit to `main`, NO push, NO PR — Orchestrator integrates.
- [ ] NO real CareStack backfill run — that's a SEPARATE explicit go from the
      user after merge.
