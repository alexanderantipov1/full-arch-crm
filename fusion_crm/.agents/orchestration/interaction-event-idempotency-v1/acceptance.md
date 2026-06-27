# Acceptance — ENG-269

- [ ] New Alembic revision (down_revision = current head): (1) DELETE duplicate
      `interaction.event` rows keeping the earliest (min created_at, tie-break min
      id) per `(tenant_id, source_provider, source_kind, source_external_id, kind)`
      where `source_external_id IS NOT NULL`; (2) CREATE partial UNIQUE INDEX on
      those columns `WHERE source_external_id IS NOT NULL`. Working downgrade
      (drops the index; does not resurrect rows).
- [ ] `create_event` (repository/service) inserts with ON CONFLICT DO NOTHING (or
      catches IntegrityError) on the unique index — returns existing/None on
      conflict, never raises. All ingest callers (CareStack invoice/treatment/
      accounting, SF event/task/etc.) treat the no-op gracefully (count as skipped,
      not failed).
- [ ] After local `alembic upgrade head`: per-kind event counts == distinct
      source_external_id counts; Collected (deduped) ≈ $38,178.
- [ ] Re-running a pull does NOT increase event counts (idempotent).
- [ ] No PHI in logs. Migrations immutable (new revision). Append-only runtime
      service contract preserved (DELETE only in the migration).
- [ ] Full verify green: `make lint`, `mypy .`, `make test`,
      `cd packages/db && alembic check`; migration round-trip up→down→up.
- [ ] Tests: duplicate re-emit is a no-op; different kind same id allowed; null
      source_external_id unaffected.
- [ ] Report at `reports/ENG-269-worker-report.md`.
