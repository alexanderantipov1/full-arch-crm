# Acceptance — ENG-285

- [ ] Operator backfill (extend `apps/api/routers/backfill.py`): add
      `_run_cs_accounting_transactions` + `_run_cs_payment_summary` driving the
      existing CareStack ingest services with a `since` datetime (default
      2026-01-01), UNBOUNDED pagination over continueToken, a throttle (sleep
      between pages, configurable) and backoff/retry on 429/5xx (then stop +
      return resume token). Expose via the existing `POST /backfill/run` scope.
- [ ] Resumable + idempotent (raw dedupe + ENG-269 idempotent emission). sync_run
      journaling like the other backfill steps.
- [ ] Reuse ENG-284 classification (payment events only for payment codes).
- [ ] TESTS MOCK the CareStack client — NO real CareStack traffic in dev/CI.
      Cover: multi-page loop stops on null token; throttle/backoff invoked;
      429 → backoff then resume token; idempotent re-run; sync_run recorded.
- [ ] No migration, no schema, no frontend, no cron change. Verify green: lint,
      mypy, test, alembic check.
- [ ] Report at `reports/ENG-285-worker-report.md` (throttle defaults, backoff
      policy, how to invoke, do-not-merge).
