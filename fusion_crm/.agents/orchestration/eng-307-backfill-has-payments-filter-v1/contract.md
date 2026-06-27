# Contract — ENG-307

- New `--only-with-payments` boolean CLI flag on
  `infra/scripts/backfill_payment_summary.py` (default `False`).
- New filtered resolver (function or service method) returning
  `set[str]` of CareStack `source_id`s whose linked `person_uid` has at
  least one payment-event row on the tenant. Uses the same
  source-of-truth as the dashboard outstanding aggregate / the new
  ENG-306 per-patient methods (identified by pre-flight).
- When `--only-with-payments` is set: filtered resolver replaces
  `list_source_links_for_dashboard`; `--max-patients` keeps applying as
  upper-bound cap.
- Structured logs gain `selector: "has_payments" | "all_linked"` field.
- No change to throttle / backoff / commit batching / HTTP-disallow /
  PHI-hygiene constraints (all inherited from ENG-305).

Out of contract:
- Schema changes (none).
- API endpoints (none — script stays background-only).
- UI (none — that was ENG-306).
- Running the real backfill (separate operator approval).
