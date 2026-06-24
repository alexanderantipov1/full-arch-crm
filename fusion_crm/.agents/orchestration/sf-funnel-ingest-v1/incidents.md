# Incidents — sf-funnel-ingest-v1

- 2026-06-09T23:05:00Z | ENG-381 | Test-suite DB pollution. The first
  version of `tests/infra/test_cleanup_raw_event_duplicates.py` called
  the cleanup script's apply path, which committed the fixture
  transaction — the `two_tenant_db` seed (Tenant A/B + fixed unique
  identifiers) persisted into the local dev DB and broke EVERY
  subsequent two_tenant_db test (`uq_person_identifier_kind_value`).
  Root cause fixed by making the script's per-batch `commit` injectable
  (CLI passes `session.commit`; tests omit it). Pollution removed after
  explicit owner approval (auto-mode classifier correctly denied the
  unsupervised mass delete first). Lesson recorded.
- 2026-06-09T23:30:00Z | ENG-381 | Combined `pytest tests/ingest
  tests/worker tests/infra` fails without `DATABASE_URL` exported:
  `tests/worker/test_bounce_poll.py` does
  `os.environ.setdefault("DATABASE_URL", ...role test...)` at import
  time and poisons the lazily-created engine for real-DB fixtures.
  Workaround: export DATABASE_URL from .env when running suites that
  mix worker tests with real-DB tests (CI exports it explicitly).
- 2026-06-09T21:00:00Z | observation | Local arq worker is not running
  (last scheduled capture 19:55Z). Not an ENG-381 defect; the new
  watermark code activates on next worker start.
- 2026-06-10T01:49:40Z | ENG-382 | Alembic upgrade deadlocked against the running cleanup --apply (AccessExclusiveLock vs batched DELETEs); alembic transaction rolled back fully, DB stayed at e4f5a6b7c8d9. Resolution: apply migration after cleanup completes. Lesson: do not run DDL while a long batched repair holds row locks.
- 2026-06-10T08:02:37Z | CRITICAL | Disk-full event corrupted local state: 13 git
  packfiles truncated (incl. commits ENG-371..382), ruff binary
  zeroed, mypy cache broken, transient exec failures (awk/git).
  Recovery: salvaged readable objects from pack copies
  (git unpack-objects -r), quarantined bad packs to
  /tmp/fusion_git_rescue/, imported full origin pack from a fresh
  bare clone, rebuilt the tree from the intact git index
  (1398/1398 blobs verified), squash-restore commit 2dfd07e on top
  of 7497f87, pruned stale refs. Content loss: ZERO. History loss:
  7 commits squashed into one restore commit. Root cause: disk at
  98% (12GiB free of 460) during the 2.2M-row DB cleanup.
