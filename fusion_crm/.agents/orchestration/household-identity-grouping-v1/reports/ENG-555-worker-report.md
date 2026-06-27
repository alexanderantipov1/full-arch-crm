# ENG-555 — Messenger alert on shared-contact reuse (Layer D) — WORKER REPORT

> **Status:** draft PR ready for Codex cross-review + operator approval.
> **DO NOT MERGE / DO NOT DEPLOY.** Worker = Claude Code. Task class = normal.
> Proposal: `reports/ENG-555-proposal.md` (written + followed).

## What was built

ALWAYS send a Messenger alert when an incoming record reuses an existing shared
phone/email (a contact already held by another person), to nudge staff to
capture a distinct contact per person. Routed per-location to the **leads**
channel. Implemented via the ENG-498 scan-job pattern — `identity` never imports
`integrations`; a worker job reads the reuse signal and emits through the
existing ENG-437 notification runtime.

## Design chosen (matches proposal)

- **Signal source:** an OPEN `identity.match_candidate` with `match_rule ∈
  {phone_only_ambiguous, email_only_ambiguous}` — the matcher already writes this
  on the reuse path (`_apply_open_ambiguous`). `source_person_uid` = incoming
  person, `candidate_person_uid` = existing person. Tier-1 auto-accept (same
  person) and brand-new (no reuse) intentionally do not alert.
- **Routing:** new `identity.shared_contact_reuse` event + a default seed rule →
  channel `leads`; per-location team resolved by the existing ENG-458 engine from
  `context["location_id"]`. Location derived from the person's most-recent
  `ops.person_location_profile` (incoming first, then existing); miss → default
  team. "Tagged lead" = the leads channel + card title.
- **Dedupe:** `emit(dedupe_key = match-candidate id)` against the existing
  `integrations.notification_emitted` ledger → at-most-once ever, idempotent
  re-runs. **No new model / no new migration.**
- **No retro-blast:** the scan only reads candidates with `created_at >=
  NOTIFICATIONS_CUTOFF_AT`; if that env is unset the scan is a NO-OP. `emit` also
  re-checks the cutoff via `source_created_at` (defense in depth). Master gate
  `NOTIFICATIONS_ENABLED` (default False) keeps it dark by default.
- **No PHI:** the card template references only `{{person_uid}}`, `{{deep_link}}`,
  `{{other_person_uid}}`, `{{other_deep_link}}`, `{{contact_kind}}` (the *type*
  phone/email, never the value), `{{location_label}}`. The scan never puts a
  name/phone/email into the context. PHI-free by construction (safe regardless of
  `messenger_phi_full`). Logs emit counts + opaque uids only.

## Changed / added files

| File | Change |
|---|---|
| `packages/integrations/chat/events.py` | + `EVENT_SHARED_CONTACT_REUSE` + roster + `__all__` |
| `packages/integrations/chat/seeds.py` | + `SHARED_CONTACT_REUSE_CHANNEL` (= "leads") + PHI-free `SHARED_CONTACT_REUSE_TEMPLATE` + default rule + `__all__` |
| `packages/identity/models.py` | + `REUSE_MATCH_RULES` constant (no schema change) |
| `packages/identity/repository.py` | + `list_open_reuse_candidates_created_after(...)` (+ `datetime` import) |
| `packages/identity/service.py` | + `list_open_reuse_candidates_created_after(...)` → `MatchCandidateOut` |
| `apps/worker/jobs/shared_contact_reuse.py` | NEW — per-tenant scan + emit logic |
| `apps/worker/jobs/shared_contact_reuse_scan.py` | NEW — Cloud-Run-Job `run()` entrypoint |
| `apps/worker/main.py` | register fn + local-dev cron (every 5 min) |
| `tests/worker/test_shared_contact_reuse.py` | NEW — unit + real-PG integration |
| `.agents/.../reports/ENG-555-proposal.md` | proposal (propose-before-implement gate) |

## Tests run + results

- `tests/worker/test_shared_contact_reuse.py` — **9 passed** (5 unit + 4 real-PG
  integration): new signal → 1 PHI-free alert; re-run → no duplicate; pre-cutoff
  → silent; disabled → silent; no-cutoff → no-op; PHI-free template; roster; rule
  routing; kind mapping.
- Regression: `tests/integrations/test_notification_{dispatch,emit,dedupe}.py`,
  `test_consultation_scheduled_emit.py`, `test_sf_lead_created_notifications.py`,
  `tests/worker/test_consultation_reminders.py` — **42 passed** (+1 isolated
  re-run confirms the lone "ERROR" was the pre-existing cross-test
  event-loop-closed teardown flake, not a failure).
- `tests/identity/` — **126 passed**.
- **ruff:** clean. **mypy:** clean (7 source files).
- **Alembic:** single head `fd36dd4df2f3`; **no migration added** (only a Python
  constant). `alembic check` reports the shared dev DB lags the branch head
  (pre-existing, unrelated to ENG-555); not mutated.

## No-PHI proof

The integration test creates persons with distinctive names
("ReuseIncomingName"/"ReuseExistingName") and asserts those names never appear in
the rendered outbox payload, while the opaque uid + contact kind do. The unit
test asserts no `{{name}}/{{phone}}/{{email}}/{{dob}}/{{ssn}}` placeholder exists
in the template.

## Infra follow-up (NOT in this PR — operator handles, like ENG-550)

Prod has no always-on worker (ENG-172). Required, separately:

1. `deploy_cloud_run.sh`: add `fusion-job-shared-contact-reuse-scan` Cloud Run
   Job (reuses the API image; entry `apps.worker.jobs.shared_contact_reuse_scan`).
2. Cloud Scheduler trigger (~every 5–10 min).
3. Env: set `NOTIFICATIONS_CUTOFF_AT` (deploy instant) + `NOTIFICATIONS_ENABLED=true`.
4. Seed the `identity.shared_contact_reuse` rule per tenant + ensure a `leads`
   channel per team and `tenant.location.external_ref['mattermost_team']` mapping.

## Risks

- **Volume:** every distinct-person reuse pages the leads channel. Mitigated by
  cutoff + dedupe + master gate; operator should watch volume after enabling.
- **Location accuracy:** persons without a `person_location_profile` route to the
  default team (acceptable, documented).
- Shared dev DB: the scan's `summary` counts span all tenants; tests assert
  per-tenant via the outbox (robust to dev-DB noise).

## Do-not-merge conditions

- Pending Codex cross-runtime review + operator approval.
- Infra job + scheduler + env (`NOTIFICATIONS_CUTOFF_AT`, `NOTIFICATIONS_ENABLED`)
  + per-tenant rule seed + per-team `leads` channel mapping are operator
  follow-ups — the feature is dark until they are done.
- No merge = no prod deploy/migration (none needed; no migration in this PR).
