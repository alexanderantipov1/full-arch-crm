# Acceptance — ENG-307

- [ ] `infra/scripts/backfill_payment_summary.py` gains a `--only-with-payments`
      boolean CLI flag (default `False`).
- [ ] When `--only-with-payments` is set, the patient_ids list comes from a
      new filtered resolver: distinct CareStack `source_link.source_id`
      where the linked `person_uid` has at least one payment-event row on
      the tenant. Reuse the existing payment-event source-of-truth
      (table + query pattern identified by pre-flight) — do NOT invent a
      new SQL shape.
- [ ] `--max-patients` continues to apply as an upper-bound safety cap on
      the filtered set.
- [ ] Structured logs include a `selector` field with value
      `"has_payments"` or `"all_linked"` so an operator scanning runs
      knows which mode produced the patient_ids list.
- [ ] The new resolver is exposed as a small reusable function (in the
      script, OR a service/repository method — pick whichever fits the
      existing pattern best) so the wiring is testable in isolation.
- [ ] No HTTP wiring; script remains background-only.
- [ ] Throttle / backoff unchanged.
- [ ] No PHI in logs (patient_id + counts only).
- [ ] No new migrations.

## Tests (CareStack still fully mocked)

- [ ] `test_resolver_returns_only_patients_with_payments` — seeds 3 linked
      CS patients, 2 with payment rows on the tenant → resolver returns
      exactly 2 CareStack `source_id`s.
- [ ] `test_resolver_dedups_repeated_patient_ids` — 3 payment rows on the
      same patient → resolver returns 1 patient_id.
- [ ] `test_resolver_respects_tenant_scope` — payment rows on a different
      tenant for the same patient → NOT included.
- [ ] `test_only_with_payments_flag_invokes_filtered_resolver` — when
      `--only-with-payments` is set, the filtered resolver is called AND
      `IdentityRepository.list_source_links_for_dashboard` is NOT called.
- [ ] `test_max_patients_still_caps_filtered_resolver` — `--max-patients 3`
      over 10 has-payments matches → only 3 patient_ids forwarded.
- [ ] `test_logs_include_selector_field` — structured log emits
      `selector="has_payments"` (or `"all_linked"` in the default path).
- [ ] All existing tests in `tests/infra/test_backfill_payment_summary.py`
      stay green (no regression in the default `--max-patients`-only
      path).

## Verify

- [ ] `make lint`, `mypy .`, `make test`, `cd packages/db && alembic check` green.
- [ ] `pytest tests/infra/test_backfill_payment_summary.py -v` green.
- [ ] Worker report at `.agents/orchestration/current/reports/ENG-307-worker-report.md`.
- [ ] Commit to worker's worktree branch only; NO push, NO PR; Orchestrator
      integrates.
