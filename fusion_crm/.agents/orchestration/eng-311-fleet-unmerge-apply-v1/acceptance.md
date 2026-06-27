# Acceptance — ENG-311 Fleet Un-Merge `--apply`

- [ ] Pre-apply dump of the `:5434` DB taken, non-empty, path recorded in runlog.
- [ ] Canary `--apply --max-splits 50` run; re-audit shows count dropped by the number of
      canary splits; no errors / 0 unexpected needs_manual_review spikes.
- [ ] Live verification: a split person card on web `:3000` shows per-human Paid/Balance
      (not summed); confirmed on REAL data, not mocked.
- [ ] Fleet batches of 500 applied until `audit_identity_merges.py` → 0 / near-0.
- [ ] `audit.access_log` `identity.person.split` row count == total splits performed.
- [ ] Idempotent re-run (`--apply --max-splits 500`) after completion → 0 new splits.
- [ ] No PHI values in audit rows or structured logs (counts + uuids only).
- [ ] Operation report at reports/ENG-311-fleet-apply-report.md.
- [ ] ENG-311 Linear comment with totals; HYBRID_KICKOFF "Current state" updated.
