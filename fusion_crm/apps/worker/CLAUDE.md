# CLAUDE.md — `apps/worker` (arq background jobs)

Background runner. Today it hosts the backup job and a placeholder
ingest processor. Future home for: scheduled GCS uploads, PHI
exports, integration sync, agent batch runs.

> **Production runtime status (2026-05-15, ENG-172):** the
> long-running `fusion-worker` Cloud Run Service was decommissioned.
> arq has no HTTP surface so Cloud Run health checks always failed.
> The recurring background work that was wired to arq cron now runs
> as one-shot **Cloud Run Jobs** (`fusion-job-bounce-poll` every 15min,
> `fusion-job-salesforce-token-keepalive` every 6h,
> `fusion-job-sf-pull` every 15min, and `fusion-job-cs-pull` every
> 30min via Cloud Scheduler; `fusion-job-alembic-upgrade` invoked
> from CI).
> Both Jobs reuse the API image (apps/api/Dockerfile COPYs the whole
> `apps/` tree, so `apps.worker.jobs.*` is importable from there).
>
> **`drain_outbound_queue` is paused.** Outbound email send via the
> `outreach.outbound_queue` table will not happen in production until
> ENG-112 reintroduces a real always-on background runtime + Redis
> (Memorystore). Local dev (docker compose) still runs the full arq
> loop with Redis sidecar — this contract only applies to prod.

## Files

- **`main.py`** — `WorkerSettings` (arq picks it up).
- **`jobs/backup.py`** — `run_backup`: shells out to
  `infra/scripts/backup.sh`.
- **`jobs/example.py`** — `process_unprocessed_events`: scaffold
  for ingest dispatch.

## Hard rules

- **One `AsyncSession` per job invocation.** Use the
  `async_session()` context manager. Never reuse a session across
  jobs; never store one on a module-level variable.
- **Jobs call services**, never repositories or raw SQL.
- **Idempotency is required.** arq retries on failure; design the
  job so a second run is safe (use `external_id` dedupe, `processed_at`
  guards, etc.).
- **Job timeout**: `WorkerSettings.job_timeout = 30 min` accounts
  for backups. Bump only with a reason.
- **Concurrency** comes from `WORKER_CONCURRENCY` env var (default 4).
- **Logging.** Use `packages.core.logging.get_logger("worker.<area>")`.
  Same PHI rules as everywhere else: never log clinical content.
- **Subprocess jobs** (like `run_backup`) must capture stdout+stderr,
  log a tail on failure, and raise on non-zero exit so arq retries.

## Adding a new job

1. Create `apps/worker/jobs/<name>.py` with
   `async def <name>(ctx: dict, **kwargs) -> dict | None`.
2. Open a session via `async with async_session() as session:`.
3. Register the function in `WorkerSettings.functions` list.
4. If it should run on a schedule, add an `arq.cron` entry to
   `WorkerSettings.cron_jobs` (TODO: not yet present — wire when
   the first scheduled job arrives; until then host cron is fine).

## Running

```bash
make worker                          # local
docker compose ... up -d worker      # docker
```

To enqueue from Python:
```python
import arq
pool = await arq.create_pool(redis_settings)
await pool.enqueue_job("run_backup")
```
