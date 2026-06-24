# ENG-234 Worker Report

## Summary

Wired the Salesforce token keepalive path into the canonical production
Cloud Run deployment contract. Production remains Cloud Run Jobs + Cloud
Scheduler, not a long-running arq `fusion-worker` service.

The operator full deploy script now converges:

- `fusion-job-salesforce-token-keepalive`
- `fusion-sched-salesforce-token-keepalive`

The scheduler cadence is `7 */6 * * *`, matching the local arq keepalive
cadence of four runs per day.

## Changed Files

- `infra/scripts/deploy_cloud_run.sh`
- `.github/workflows/deploy-prod.yml`
- `infra/CLAUDE.md`
- `infra/env/PRODUCTION.md`
- `apps/worker/CLAUDE.md`
- `tests/core/test_deploy_cloud_run_jobs.py`

## Verification

- `bash -n infra/scripts/deploy_cloud_run.sh` passed.
- `.venv/bin/python -m pytest tests/core/test_deploy_cloud_run_jobs.py tests/core/test_env_reference_matches_settings.py tests/core/test_traffic_primary_filter.py -q` passed: 27 tests.
- `make lint` passed.
- `.venv/bin/mypy .` passed.
- `PATH=.venv/bin:$PATH make test` passed: 656 tests.
- `cd packages/db && set -a; source ../../.env; set +a; PATH=../../.venv/bin:$PATH alembic check` passed: no new upgrade operations detected.

## Production Activation Note

`deploy-prod.yml` uses `CI_MODE=1`, which intentionally skips Cloud Run
Jobs and Cloud Scheduler reprovisioning because that path is operator-owned.
After this branch is merged and the image is available, production scheduler
activation still requires a full operator run of:

```sh
./infra/scripts/deploy_cloud_run.sh
```

without `CI_MODE=1`.
