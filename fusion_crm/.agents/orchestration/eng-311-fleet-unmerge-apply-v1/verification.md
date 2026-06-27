# Verification — ENG-311 Fleet Un-Merge `--apply`

Read-only checks (between batches + at close):
1. `audit_identity_merges.py --tenant-id 11111111-1111-4111-8111-111111111111`
   → `wrong_merged_persons` trends 3,808 → 0 / near-0.
2. Web `:3000` person card for a known split (e.g. Torosyan / a canary pid) →
   Paid/Balance attribute per-human. Live data, MSW disabled.
3. `SELECT count(*) FROM audit.access_log WHERE action_code='identity.person.split';`
   == cumulative splits performed (read-only SELECT only; never UPDATE/DELETE audit).
4. Idempotency: final `--apply --max-splits 500` → summary `split=0 new_persons=0`.
5. Restore sanity: `pg_restore --list <dump>` shows `identity.person`.

No `make lint / mypy / pytest / alembic check` required — no repo code changed (the script
is RUN, not modified). If any in-repo file changes, the full verify loop applies before push.
