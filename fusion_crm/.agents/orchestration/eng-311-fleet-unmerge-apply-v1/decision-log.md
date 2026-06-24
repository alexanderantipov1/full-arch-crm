# Decision Log — ENG-311 Fleet Un-Merge `--apply`

- 2026-06-02T00:54Z | Operator approved fleet un-merge as a hybrid-orchestrator mission.
  DB target = **local Docker :5434** (NOT Cloud SQL; proxy stays down). Fresh dump before
  first apply. Batching = **canary 50 → re-audit + live check → batches of 500**.
- 2026-06-02T00:54Z | This is an operational run of an already-merged script, so the
  hybrid pattern adapts: no code-worker / worktree. Workflow is used only at the edges
  (pre-flight recon already done read-only; adversarial review over the dry-run plan).
  The "durable center" is the gated bash apply loop under operator go, not a launch_worker.
- 2026-06-02T00:54Z | Authoritative count of record = **3,808** wrong-merged (live audit),
  superseding kickoff "~3,415" / ticket "3,416". See incidents.md.
- 2026-06-02T00:54Z | backup.sh requires DATABASE_URL_SYNC (unavailable; .env off-limits) →
  use a direct `docker exec ... pg_dump -Fc` against fusion-crm-postgres-1 instead.

- 2026-06-02T01:05Z | Adversarial review ACCEPTED despite aggregated_pass=false. The lone
  major finding (surviving person.dob/ssn not updated) is empirically inert: person.dob is
  NULL in 0/110042 rows so the ENG-309 veto never fires on a NULL candidate. PHI + idempotency
  gates clean. Proceeding to canary --apply pending explicit operator go. dob/ssn completeness
  deferred to ENG-312 (uniform backfill), not patched into the split script.
