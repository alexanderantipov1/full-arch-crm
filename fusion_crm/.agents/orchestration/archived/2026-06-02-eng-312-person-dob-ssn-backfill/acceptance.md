# Acceptance — ENG-312 (see ENG-312 Linear for full detail)

- [ ] `infra/scripts/backfill_person_dob_ssn.py` per the algorithm (set-where-NULL,
      latest CareStack payload, skip placeholder 1900-01-01, multi-pid disagree → skip +
      needs_manual_review, SF-only untouched, audit row counts/bools/uuids only).
- [ ] `tests/infra/test_backfill_person_dob_ssn.py` covering: single-pid set, multi-pid
      agree/disagree, write-once, placeholder skip, SF-only untouched, audit shape no-PHI,
      --dry-run no-op, --max-persons cap, --person-uid, idempotent re-run → 0.
- [ ] `make lint && mypy . && make test && cd packages/db && alembic check` green.
- [ ] Worker report at reports/ENG-312-worker-report.md (changed files, tests, risks).
- [ ] No new migration (no schema change). No product-route wiring (background-only).
