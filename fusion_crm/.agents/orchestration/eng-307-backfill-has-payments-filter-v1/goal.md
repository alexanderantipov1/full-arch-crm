# Goal — ENG-307: --only-with-payments filter for backfill_payment_summary.py

`infra/scripts/backfill_payment_summary.py` (landed in ENG-305) currently
selects patients via `IdentityRepository.list_source_links_for_dashboard`
ordered by `first_seen_at DESC` and capped by `--max-patients`. Per the
prod-tenant audit: there are ~55,677 linked CareStack patients but only
~1803 have payment activity. A `--max-patients 2000` run with the current
resolver hits ~2000 NEWEST linked patients, mostly missing the patients
who actually need authoritative balance.

This ticket adds a `--only-with-payments` flag (and matching filtered
resolver) so the operator can backfill exactly the ~1803 patients-with-
payments in ~15 min at low 429 risk, rather than either:
- running against all 55K (~7.7 h, very high CareStack throttle risk —
  the account was blocked ~24 h once before), or
- running with the current newest-first cap and missing most active
  patients.

Backend-only. No UI. No schema change. CareStack mocked in all tests.

Linear: ENG-307
URL: https://linear.app/fusion-dental-implants/issue/ENG-307/add-only-with-payments-filter-to-backfill-payment-summarypy
Parent: ENG-305 — gates the real CareStack backfill run (still requires
SEPARATE operator approval of the window after this lands).
