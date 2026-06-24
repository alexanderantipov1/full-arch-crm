# ENG-492 — Historical marketing/SEO backfill (worker report)

Branch: `eng-489-marketing-creds-provider-kinds` (builds on ENG-489/490/491,
already in tree). No commit/push, no migration, no `.env*` edits.

## Goal

One-shot ~12-month HISTORICAL backfill for the four marketing/SEO providers
(Google Ads, Meta Ads, GA4, Google Search Console), per tenant + provider,
reusing the ENG-490 per-tenant `from_credential` clients. The daily cron
(`pull_marketing_for_all_tenants`) only re-reads a rolling 7-day window; this
job loads history so the dashboards have months of data.

## Changed files

- **`apps/worker/jobs/marketing_backfill.py`** (new) — the backfill job +
  chunking + CLI.
- **`apps/worker/main.py`** — register `backfill_marketing_history` in
  `WorkerSettings.functions`. **No cron entry** (one-shot / on-demand, per spec).
- **`packages/ingest/google_ads_campaign_service.py`**,
  **`meta_ads_campaign_service.py`**,
  **`ga4_metric_service.py`**,
  **`gsc_query_service.py`** — extracted an explicit date-range core
  `import_window(tenant_id, *, start_date, end_date)`; the existing
  `import_recent_*(days=N)` now delegates to it (anchored to today). Behaviour of
  the daily pull is unchanged. `import_window` rejects an inverted range with
  `ValidationError`.
- **`tests/worker/test_marketing_backfill_job.py`** (new) — chunking math +
  job behaviour.
- **`tests/ingest/test_gsc_query_service.py`** — added `import_window`
  date-pass-through / idempotency / inverted-range tests.

## Entrypoint + CLI

The job exposes three layers:

- `backfill_provider_for_tenant(ctx, tenant_id, provider, *, days, chunk_days)`
  — one (tenant, provider) leg: resolve credential, chunk the window, pull each
  chunk via `import_window`, tally `imported/unchanged/skipped`.
- `run(*, days, chunk_days, providers)` — fan out over every tenant and the
  selected providers; each leg wrapped so one failure never crashes the sweep.
- `backfill_marketing_history(ctx, *, days, chunk_days, providers)` — the arq
  function (enqueue on demand).
- `main()` — CLI wrapper.

```
python -m apps.worker.jobs.marketing_backfill --months 12
python -m apps.worker.jobs.marketing_backfill --days 90 --chunk-days 14
python -m apps.worker.jobs.marketing_backfill --providers google_ads ga4
```

`--months` (×30) and `--days` are mutually exclusive; window clamped to 1..365.
`--chunk-days` defaults to 30. `--providers` accepts a subset of
`google_ads meta_ads ga4 gsc`.

## Chunking strategy

`chunk_windows(end_date, days, chunk_days)` splits `[end-(days-1), end]` into
contiguous, non-overlapping inclusive `(start, end)` pairs, **oldest first** (so
a partial run fills history chronologically). The oldest window may be a short
remainder. E.g. `days=365, chunk_days=30` → 13 windows (12×30 + one 5-day stub).

Each chunk is pulled through the provider's `import_window` with an explicit
date range:

- **Meta** — `act_{id}/insights` rejects very wide `time_range` windows, so the
  backfill never hands it more than one chunk's range.
- **GSC** — each `searchAnalytics/query` response is row-capped; narrow chunks
  stay under the cap.
- **Google Ads / GA4** — tolerate the full window but use the same chunked path
  for one uniform, restart-safe code path.

Each chunk runs in its **own DB session / unit of work**, so a failing chunk
does not roll back already-committed chunks; the idempotent re-run picks up the
rest. Idempotency comes from the ingest services: a re-pulled row whose stored
raw payload is byte-identical is counted `unchanged` and skipped before any
write, and the marketing upserts are keyed on natural keys — so overlapping
chunks, retries, and full re-runs are all safe.

## Credential resolution + graceful skip

Identical to ENG-490: `IntegrationCredentialService.read_for(tenant_id,
provider_kind, "api_key")` → `from_credential`; on `NoCredentialError`/
`PlatformError` fall back to `from_env()`; when neither exists the provider's
`*NotConnectedError` fires and the leg returns `{"skipped": "no_credential"}` —
never a crash. A GSC token with no verified site returns `{"skipped":
"no_site"}`. Logs carry only provider / tenant_id / window dates / counts —
never payload values.

## How to run the real load (once creds exist)

Real provider credentials are entered per tenant via the ENG-491 UI. After that:

- Local / workstation: `python -m apps.worker.jobs.marketing_backfill --months 12`
- Cloud Run Job (future): reuse the API image (already COPYs `apps/`) the same
  way `fusion-job-backfill` does — e.g. a `fusion-job-marketing-backfill`
  invoking `python -m apps.worker.jobs.marketing_backfill --months 12`. Or
  enqueue `backfill_marketing_history` onto the arq pool.

Re-running is safe (idempotent), so a partial/failed run can simply be re-run.

## Verification

- **ruff**: clean on all changed files.
- **mypy**: clean on `marketing_backfill.py` + the four ingest services.
- **Unit tests**: `tests/worker/test_marketing_backfill_job.py` (13) +
  `tests/ingest/test_gsc_query_service.py` (incl. 3 new `import_window` tests)
  + the existing GA4/GAds/Meta/GSC ingest and `test_marketing_pull_job` suites —
  all green (50 tests across the touched files). Covered: chunking math
  (365→13, contiguity/exact-coverage, exact-multiple, single-chunk,
  bad-args), per-(tenant,provider) credential resolution + graceful skip
  (no ingest built), idempotent re-run (all-unchanged → 0 imported),
  one-failing-chunk-doesn't-abort-the-rest, GSC no-site skip, fanout over
  tenants×providers.
- **Live dry-run** against the local DB: the local stack happened to have REAL
  creds, so a `--days 60 --chunk-days 30` run executed an actual chunked load
  and proved the mechanism end to end:
  - 60 days → 2 distinct 30-day `time_range` windows in the Meta/GSC/GAds
    HTTP calls (`2026-04-19..2026-05-18`, `2026-05-19..2026-06-17`).
  - Idempotency: re-pull reported large `unchanged` counts, `imported=0`
    (e.g. GSC `unchanged=53594`).
  - Resilience: a Meta 403 on some ad accounts was logged + skipped, the chunk
    still completed (`chunks_failed=0`).
  - The wall-clock cap I put on the test fired a `TimeoutError` mid-run — that
    is the harness timeout, not a job error.
  - A separate forced no-credential check returned `{"skipped":
    "no_credential"}` and logged `marketing_backfill.no_credential`.

Note: my `marketing_backfill.*` log lines are secret-free. The OAuth tokens
visible in the dry-run output come from the underlying `httpx` request logger in
the integration clients (pre-existing), not from this job.

## Not done (out of scope)

ENG-493 not started. No Cloud Run Job resource was created (deploy/infra change
deferred — the function + CLI are ready for it).
